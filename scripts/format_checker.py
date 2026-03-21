"""Format checker for master's thesis PDF (NEU standard).

Checks 15 categories:
  1.  Page size (A4)
  2.  Body area (版芯 160×247mm)
  3.  Lines per page (30~35) & chars per line (35~38)
  4.  Body font/size (小四宋体 12pt)
  5.  English font (Times New Roman)
  6.  Chapter heading font/size (二号黑体 22pt)
  7.  Section heading font/size (三号/四号黑体)
  8.  Chapter heading alignment (centered)
  9.  Section heading alignment (left-aligned)
  10. Heading spacing (chapter 3 lines, section 2 lines)
  11. Figure/table/equation numbering continuity
  12. Figure caption (below, 五号宋体) & table caption (above, 五号宋体)
  13. Reference numbering + GB/T 7714 format
  14. Page headers (left+right, 楷体五号)
  15. Page numbers

Usage:
    python format_checker.py <thesis.pdf>
    Outputs JSON to stdout.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from pdf_extractor import extract_structure, extract_page_spans


# === NEU Format Rules ===
# Chinese font size standard (号 → pt):
#   初号=42, 小初=36, 一号=26, 小一=24, 二号=22, 小二=18,
#   三号=16, 小三=15, 四号=14, 小四=12, 五号=10.5, 小五=9
RULES = {
    "page_size": {
        "width_mm": 210.0,
        "height_mm": 297.0,
        "tolerance_mm": 1.0,
    },
    "body_area": {
        "width_mm": 160.0,
        "height_mm": 247.0,
        "tolerance_mm": 5.0,  # 宽容一些，排版有微调
    },
    "lines_per_page": {"min": 30, "max": 35},
    "chars_per_line": {"min": 35, "max": 38},
    "body_font": {
        "name_contains": ["SimSun", "宋体", "Song", "STSong"],
        "size_pt": 12.0,
        "tolerance_pt": 0.5,
    },
    "english_font": {
        "name_contains": ["Times", "TimesNewRoman"],
        "size_pt": 12.0,
        "tolerance_pt": 0.5,
    },
    "chapter_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 22.0,
        "tolerance_pt": 1.0,
        "alignment": "center",
        "spacing_lines": 3,  # 占3行
    },
    "section_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 16.0,
        "tolerance_pt": 1.0,
        "alignment": "left",
        "spacing_lines": 2,  # 占2行
    },
    "subsection_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 14.0,
        "tolerance_pt": 1.0,
        "alignment": "left",
        "spacing_lines": 2,  # 占2行
    },
    "subsubsection_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 12.0,
        "tolerance_pt": 0.5,
        "alignment": "left",
        "spacing_lines": 1,  # 占1行
    },
    "caption_font": {
        "name_contains": ["SimSun", "宋体", "Song", "STSong"],
        "size_pt": 10.5,  # 五号
        "tolerance_pt": 0.5,
    },
    "header_font": {
        "name_contains": ["KaiTi", "楷体", "Kai", "STKai"],
        "size_pt": 10.5,
        "tolerance_pt": 0.5,
    },
    "header_left": "东北大学硕士学位论文",
}

# PT → MM conversion factor
PT_TO_MM = 25.4 / 72


def check_format(pdf_path: str) -> dict:
    """Run all format checks on a thesis PDF.

    Returns dict with 'issues' list and 'summary' counts.
    """
    structure = extract_structure(pdf_path)
    issues = []

    issues.extend(_check_page_size(structure))
    issues.extend(_check_body_area(pdf_path, structure))
    issues.extend(_check_lines_and_chars(pdf_path, structure))
    issues.extend(_check_body_text(pdf_path, structure))
    issues.extend(_check_english_font(pdf_path, structure))
    issues.extend(_check_chapter_headings(structure))
    issues.extend(_check_section_headings(structure))
    issues.extend(_check_heading_alignment(pdf_path, structure))
    issues.extend(_check_heading_spacing(pdf_path, structure))
    issues.extend(_check_figure_table_numbering(pdf_path, structure))
    issues.extend(_check_caption_format(pdf_path, structure))
    issues.extend(_check_references(pdf_path, structure))
    issues.extend(_check_headers(pdf_path, structure))
    issues.extend(_check_page_numbers(pdf_path, structure))
    issues.extend(_check_paragraph_last_line(pdf_path, structure))
    issues.extend(_check_page_bottom_blank(pdf_path, structure))

    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = len(issues) - errors

    return {
        "issues": issues,
        "summary": {"total": len(issues), "errors": errors, "warnings": warnings},
    }


def _issue(page, location, rule, expected, actual, severity="warning"):
    """Create a standardized issue dict."""
    return {
        "page": page,
        "location": location,
        "rule": rule,
        "expected": expected,
        "actual": actual,
        "severity": severity,
    }


def _font_matches(font_name: str, candidates: list[str]) -> bool:
    """Check if font_name contains any of the candidate strings (case-insensitive)."""
    fn = font_name.lower()
    return any(c.lower() in fn for c in candidates)


def _get_body_page_range(structure: dict) -> tuple[int, int]:
    """Get (start, end) page range for body content (1-indexed, inclusive)."""
    start = 1
    if structure["chapters"]:
        start = structure["chapters"][0]["page"]
    return start, structure["pages"]


def _is_cjk(char: str) -> bool:
    """Check if a character is CJK (Chinese/Japanese/Korean)."""
    cp = ord(char)
    return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
            0xF900 <= cp <= 0xFAFF or 0x20000 <= cp <= 0x2A6DF)


def _has_cjk(text: str) -> bool:
    """Check if text contains any CJK characters."""
    return any(_is_cjk(c) for c in text)


# ═══════════════════════════════════════════════════════════════
# 1. Page Size
# ═══════════════════════════════════════════════════════════════

def _check_page_size(structure: dict) -> list[dict]:
    """Check page dimensions are A4 (210×297mm)."""
    issues = []
    r = RULES["page_size"]
    ps = structure["page_size"]
    if abs(ps["width_mm"] - r["width_mm"]) > r["tolerance_mm"]:
        issues.append(_issue(
            1, "全文", "页面宽度",
            f'{r["width_mm"]}mm', f'{ps["width_mm"]}mm', "error"
        ))
    if abs(ps["height_mm"] - r["height_mm"]) > r["tolerance_mm"]:
        issues.append(_issue(
            1, "全文", "页面高度",
            f'{r["height_mm"]}mm', f'{ps["height_mm"]}mm', "error"
        ))
    return issues


# ═══════════════════════════════════════════════════════════════
# 2. Body Area (版芯 160×247mm)
# ═══════════════════════════════════════════════════════════════

def _check_body_area(pdf_path: str, structure: dict) -> list[dict]:
    """Check body area (版芯) dimensions: 160×247mm, not including header/footer."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)
    r = RULES["body_area"]
    start, end = _get_body_page_range(structure)

    # Sample a few body pages
    sample_pages = list(range(start - 1, min(end, start + 9)))  # first 10 body pages
    if not sample_pages:
        doc.close()
        return issues

    widths_mm = []
    heights_mm = []

    for page_idx in sample_pages:
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        # Collect bbox of all text blocks in body region (skip header/footer)
        body_blocks = []
        for block in blocks:
            if "lines" not in block:
                continue
            by0 = block["bbox"][1]
            by1 = block["bbox"][3]
            # Skip header (top 60pt) and footer (bottom 50pt)
            if by0 < 60 or by1 > page.rect.height - 50:
                continue
            body_blocks.append(block["bbox"])

        if not body_blocks:
            continue

        # Compute bounding box of all body content
        x0 = min(b[0] for b in body_blocks)
        y0 = min(b[1] for b in body_blocks)
        x1 = max(b[2] for b in body_blocks)
        y1 = max(b[3] for b in body_blocks)

        widths_mm.append((x1 - x0) * PT_TO_MM)
        heights_mm.append((y1 - y0) * PT_TO_MM)

    doc.close()

    if widths_mm:
        avg_w = sum(widths_mm) / len(widths_mm)
        avg_h = sum(heights_mm) / len(heights_mm)

        if abs(avg_w - r["width_mm"]) > r["tolerance_mm"]:
            issues.append(_issue(
                start, "版芯", "版芯宽度",
                f'{r["width_mm"]}mm', f'{avg_w:.1f}mm', "warning"
            ))
        if abs(avg_h - r["height_mm"]) > r["tolerance_mm"]:
            issues.append(_issue(
                start, "版芯", "版芯高度",
                f'{r["height_mm"]}mm', f'{avg_h:.1f}mm', "warning"
            ))

    return issues


# ═══════════════════════════════════════════════════════════════
# 3. Lines per page (30~35) & chars per line (35~38)
# ═══════════════════════════════════════════════════════════════

def _check_lines_and_chars(pdf_path: str, structure: dict) -> list[dict]:
    """Check lines per page (30~35) and characters per line (35~38)."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)
    r_lines = RULES["lines_per_page"]
    r_chars = RULES["chars_per_line"]
    start, end = _get_body_page_range(structure)

    # Sample every 5th body page
    for page_idx in range(start - 1, end, 5):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        # Count text lines in body region
        body_lines = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                y = line["bbox"][1]
                if 60 < y < page.rect.height - 50:
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    if len(text) > 1:  # skip trivially short lines
                        body_lines.append(text)

        line_count = len(body_lines)
        if line_count > 0 and (line_count < r_lines["min"] - 5 or line_count > r_lines["max"] + 5):
            # Only flag significant deviations (allow some tolerance for pages with figures)
            issues.append(_issue(
                page_idx + 1, "正文区域",
                "每页行数", f'{r_lines["min"]}~{r_lines["max"]}行',
                f'{line_count}行', "warning"
            ))

        # Check chars per line on body text lines (not headings)
        for text in body_lines:
            char_count = len(text)
            # Only check substantial body text lines, skip headings and short lines
            if char_count < 10:
                continue
            if char_count > r_chars["max"] + 5:
                issues.append(_issue(
                    page_idx + 1, f'"{text[:15]}..."',
                    "每行字数", f'{r_chars["min"]}~{r_chars["max"]}字',
                    f'{char_count}字', "warning"
                ))
                break  # Only report once per page

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# 4. Body Text Font/Size (小四宋体)
# ═══════════════════════════════════════════════════════════════

def _check_body_text(pdf_path: str, structure: dict) -> list[dict]:
    """Check body text font and size on sampled pages."""
    issues = []
    r = RULES["body_font"]
    start, _ = _get_body_page_range(structure)

    checked_pages = set()
    for pg in range(start, structure["pages"] + 1, 3):
        if pg in checked_pages:
            continue
        checked_pages.add(pg)
        spans = extract_page_spans(pdf_path, pg)

        body_spans = [s for s in spans if 70 < s["y_pos"] < 780]
        for span in body_spans:
            if span["size"] > r["size_pt"] + r["tolerance_pt"] + 1:
                continue
            if len(span["text"].strip()) < 4:
                continue
            # Skip English text (handled separately)
            if not _has_cjk(span["text"]):
                continue

            if not _font_matches(span["font"], r["name_contains"]):
                issues.append(_issue(
                    pg, f'"{span["text"][:20]}..."',
                    "正文中文字体", "宋体(SimSun)", span["font"], "warning"
                ))

            if abs(span["size"] - r["size_pt"]) > r["tolerance_pt"]:
                if span["size"] < r["size_pt"] - 2:
                    continue
                issues.append(_issue(
                    pg, f'"{span["text"][:20]}..."',
                    "正文字号", f'小四号({r["size_pt"]}pt)', f'{span["size"]}pt', "warning"
                ))

    return issues


# ═══════════════════════════════════════════════════════════════
# 5. English Font (Times New Roman)
# ═══════════════════════════════════════════════════════════════

def _check_english_font(pdf_path: str, structure: dict) -> list[dict]:
    """Check English/number text uses Times New Roman, same size as body."""
    issues = []
    r = RULES["english_font"]
    start, _ = _get_body_page_range(structure)

    # Sample every 5th page
    for pg in range(start, structure["pages"] + 1, 5):
        spans = extract_page_spans(pdf_path, pg)
        body_spans = [s for s in spans if 70 < s["y_pos"] < 780]

        for span in body_spans:
            text = span["text"].strip()
            # Only check spans that are primarily English/numbers (not CJK)
            if len(text) < 3 or _has_cjk(text):
                continue
            # Skip if it looks like a heading (larger font)
            if span["size"] > 13:
                continue

            # Check font
            if not _font_matches(span["font"], r["name_contains"]):
                # Allow SimSun for mixed text — only flag purely non-CJK, non-Times
                if not _font_matches(span["font"], RULES["body_font"]["name_contains"]):
                    issues.append(_issue(
                        pg, f'"{text[:20]}..."',
                        "英文/数字字体", "Times New Roman",
                        span["font"], "warning"
                    ))

    return issues


# ═══════════════════════════════════════════════════════════════
# 6. Chapter Heading Font/Size (二号黑体 22pt)
# ═══════════════════════════════════════════════════════════════

def _check_chapter_headings(structure: dict) -> list[dict]:
    """Check chapter heading font and size."""
    issues = []
    r = RULES["chapter_heading"]
    for ch in structure["chapters"]:
        if abs(ch["font_size"] - r["size_pt"]) > r["tolerance_pt"]:
            issues.append(_issue(
                ch["page"], f'第{ch["number"]}章 {ch["title"]}',
                "章标题字号", f'二号黑体({r["size_pt"]}pt)',
                f'{ch["font_size"]}pt', "error"
            ))
        if not _font_matches(ch["font_name"], r["name_contains"]):
            issues.append(_issue(
                ch["page"], f'第{ch["number"]}章 {ch["title"]}',
                "章标题字体", "黑体(SimHei)", ch["font_name"], "error"
            ))
    return issues


# ═══════════════════════════════════════════════════════════════
# 7. Section Heading Font/Size
# ═══════════════════════════════════════════════════════════════

def _check_section_headings(structure: dict) -> list[dict]:
    """Check section/subsection heading fonts and sizes."""
    issues = []
    for h in structure["headings"]:
        if h["level"] == 2:
            r = RULES["section_heading"]
            label = "节标题"
            expected_desc = f'三号黑体({r["size_pt"]}pt)'
        elif h["level"] == 3:
            r = RULES["subsection_heading"]
            label = "款标题"
            expected_desc = f'四号黑体({r["size_pt"]}pt)'
        else:
            continue

        if abs(h["font_size"] - r["size_pt"]) > r["tolerance_pt"]:
            issues.append(_issue(
                h["page"], f'{h["number"]} {h["title"][:20]}',
                f"{label}字号", expected_desc,
                f'{h["font_size"]}pt', "warning"
            ))
        if not _font_matches(h["font_name"], r["name_contains"]):
            issues.append(_issue(
                h["page"], f'{h["number"]} {h["title"][:20]}',
                f"{label}字体", "黑体(SimHei)", h["font_name"], "warning"
            ))
    return issues


# ═══════════════════════════════════════════════════════════════
# 8 & 9. Heading Alignment (chapter=center, section=left)
# ═══════════════════════════════════════════════════════════════

def _check_heading_alignment(pdf_path: str, structure: dict) -> list[dict]:
    """Check chapter headings are centered, section headings are left-aligned."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    # Check chapter headings — should be centered
    for ch in structure["chapters"]:
        page = doc[ch["page"] - 1]
        page_width = page.rect.width
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if f'第{ch["number"]}章' in text or f'第 {ch["number"]} 章' in text:
                    # Check if centered: left margin ≈ right margin
                    x0 = line["bbox"][0]
                    x1 = line["bbox"][2]
                    left_margin = x0
                    right_margin = page_width - x1
                    # Centered if margins are roughly equal (within 30pt)
                    if abs(left_margin - right_margin) > 30:
                        issues.append(_issue(
                            ch["page"], f'第{ch["number"]}章 {ch["title"]}',
                            "章标题对齐", "居中",
                            f'左边距{left_margin:.0f}pt 右边距{right_margin:.0f}pt',
                            "warning"
                        ))
                    break

    # Check section headings — should be left-aligned
    for h in structure["headings"]:
        if h["level"] not in (2, 3):
            continue
        page = doc[h["page"] - 1]
        page_width = page.rect.width
        # Left margin for A4 with 160mm body: (210-160)/2 = 25mm ≈ 71pt
        expected_left_margin = 71  # ~25mm
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if h["number"] in text and h["title"][:5] in text:
                    x0 = line["bbox"][0]
                    # Left-aligned: x0 should be near the left margin
                    if x0 > expected_left_margin + 40:
                        level_name = "节" if h["level"] == 2 else "款"
                        issues.append(_issue(
                            h["page"], f'{h["number"]} {h["title"][:15]}',
                            f"{level_name}标题对齐", "居左",
                            f'左边距{x0:.0f}pt（偏右）', "warning"
                        ))
                    break

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# 10. Heading Spacing (chapter=3 lines, section=2 lines)
# ═══════════════════════════════════════════════════════════════

def _check_heading_spacing(pdf_path: str, structure: dict) -> list[dict]:
    """Check heading vertical spacing: chapter=3行, section=2行, subsubsection=1行.

    Estimated by measuring vertical gap before and after heading text.
    一行 ≈ body line height ≈ 20pt (12pt font + ~8pt spacing at 1.5x line spacing).
    """
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    LINE_HEIGHT_PT = 20.0  # approximate body line height

    for ch in structure["chapters"]:
        page = doc[ch["page"] - 1]
        blocks = page.get_text("dict")["blocks"]

        # Find the chapter heading line and the next content line
        heading_y1 = None
        next_content_y0 = None

        all_lines = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if text:
                    all_lines.append((line["bbox"][1], line["bbox"][3], text))

        all_lines.sort(key=lambda x: x[0])

        for i, (y0, y1, text) in enumerate(all_lines):
            if f'第{ch["number"]}章' in text:
                heading_y1 = y1
                # Find next non-empty line
                if i + 1 < len(all_lines):
                    next_content_y0 = all_lines[i + 1][0]
                break

        if heading_y1 is not None and next_content_y0 is not None:
            gap = next_content_y0 - heading_y1
            expected_gap = RULES["chapter_heading"]["spacing_lines"] * LINE_HEIGHT_PT
            # Chapter heading should "occupy" 3 lines of space
            # The gap after should be roughly 2 line heights (heading is 1 line itself)
            if gap < LINE_HEIGHT_PT * 1.0:
                issues.append(_issue(
                    ch["page"], f'第{ch["number"]}章 {ch["title"]}',
                    "章标题间距", "占3行（标题后应有足够间距）",
                    f'标题后间距{gap:.0f}pt（不足）', "warning"
                ))

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# 11. Figure / Table / Equation Numbering
# ═══════════════════════════════════════════════════════════════

def _check_figure_table_numbering(pdf_path: str, structure: dict) -> list[dict]:
    """Check figure/table/equation numbering continuity within each chapter."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    fig_pattern = re.compile(r"图\s*(\d+)[.\s·](\d+)")
    tab_pattern = re.compile(r"表\s*(\d+)[.\s·](\d+)")
    eq_pattern = re.compile(r"[式公]\s*[（(]\s*(\d+)\s*[-.\s·]\s*(\d+)\s*[）)]")

    fig_nums = {}
    tab_nums = {}
    eq_nums = {}

    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text()

        for m in fig_pattern.finditer(text):
            ch, num = int(m.group(1)), int(m.group(2))
            fig_nums.setdefault(ch, []).append((num, page_idx + 1))

        for m in tab_pattern.finditer(text):
            ch, num = int(m.group(1)), int(m.group(2))
            tab_nums.setdefault(ch, []).append((num, page_idx + 1))

        for m in eq_pattern.finditer(text):
            ch, num = int(m.group(1)), int(m.group(2))
            eq_nums.setdefault(ch, []).append((num, page_idx + 1))

    doc.close()

    for label, nums_dict in [("图", fig_nums), ("表", tab_nums), ("公式", eq_nums)]:
        for ch, entries in nums_dict.items():
            seen = sorted(set(n for n, _ in entries))
            if not seen:
                continue
            expected = list(range(1, max(seen) + 1))
            missing = set(expected) - set(seen)
            for m in missing:
                issues.append(_issue(
                    entries[0][1], f"第{ch}章",
                    f"{label}编号连续性",
                    f"{label}{ch}.{m} 应存在",
                    f"缺失 {label}{ch}.{m}", "warning"
                ))

    return issues


# ═══════════════════════════════════════════════════════════════
# 12. Caption Format: figure below + table above + 五号宋体
# ═══════════════════════════════════════════════════════════════

def _check_caption_format(pdf_path: str, structure: dict) -> list[dict]:
    """Check figure captions are below figures, table captions are above tables.

    Also checks caption font: 五号宋体 (10.5pt SimSun).
    """
    issues = []
    import fitz
    doc = fitz.open(pdf_path)
    r = RULES["caption_font"]

    fig_caption_re = re.compile(r"图\s*\d+[.\s·]\d+")
    tab_caption_re = re.compile(r"表\s*\d+[.\s·]\d+")

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        # Collect all lines with their y-position and content
        all_spans_on_page = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text:
                        all_spans_on_page.append({
                            "text": text,
                            "font": span["font"],
                            "size": span["size"],
                            "y": line["bbox"][1],
                        })

        # Find image blocks (non-text blocks are images)
        image_blocks = []
        for block in blocks:
            if block.get("type") == 1:  # image block
                image_blocks.append(block["bbox"])

        # Check figure captions
        for span in all_spans_on_page:
            if fig_caption_re.search(span["text"]):
                # Figure caption should be BELOW the figure
                # Check if there's an image block above this caption
                caption_y = span["y"]
                has_image_above = any(
                    img[3] < caption_y + 10  # image bottom is above caption
                    for img in image_blocks
                )
                if image_blocks and not has_image_above:
                    # Image exists but caption might be in wrong position
                    has_image_below = any(
                        img[1] > caption_y - 10
                        for img in image_blocks
                    )
                    if has_image_below:
                        issues.append(_issue(
                            page_idx + 1, f'{span["text"][:25]}',
                            "图题位置", "图题应在图的下方",
                            "图题可能在图的上方", "warning"
                        ))

                # Check caption font: 五号宋体
                if abs(span["size"] - r["size_pt"]) > r["tolerance_pt"]:
                    issues.append(_issue(
                        page_idx + 1, f'{span["text"][:25]}',
                        "图题字号", f'五号({r["size_pt"]}pt)',
                        f'{span["size"]}pt', "warning"
                    ))
                if not _font_matches(span["font"], r["name_contains"]):
                    issues.append(_issue(
                        page_idx + 1, f'{span["text"][:25]}',
                        "图题字体", "宋体(SimSun)", span["font"], "warning"
                    ))

            if tab_caption_re.search(span["text"]):
                # Table caption font check: 五号宋体
                if abs(span["size"] - r["size_pt"]) > r["tolerance_pt"]:
                    issues.append(_issue(
                        page_idx + 1, f'{span["text"][:25]}',
                        "表题字号", f'五号({r["size_pt"]}pt)',
                        f'{span["size"]}pt', "warning"
                    ))
                if not _font_matches(span["font"], r["name_contains"]):
                    issues.append(_issue(
                        page_idx + 1, f'{span["text"][:25]}',
                        "表题字体", "宋体(SimSun)", span["font"], "warning"
                    ))

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# 13. References: numbering + GB/T 7714 format
# ═══════════════════════════════════════════════════════════════

def _check_references(pdf_path: str, structure: dict) -> list[dict]:
    """Check reference format: sequential [N] numbering + GB/T 7714 patterns."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    ref_num_pattern = re.compile(r"\[(\d+)\]")
    all_refs = []

    # Find reference section
    ref_start = None
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text()
        if "参考文献" in text:
            ref_start = page_idx
            break

    if ref_start is None:
        doc.close()
        return issues

    # Collect all reference entries
    ref_entries = []  # (ref_number, full_text, page)
    current_ref_text = ""
    current_ref_num = None
    current_ref_page = ref_start + 1

    for page_idx in range(ref_start, len(doc)):
        text = doc[page_idx].get_text()
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            m = re.match(r"\[(\d+)\]\s*(.*)", line)
            if m:
                # Save previous entry
                if current_ref_num is not None:
                    ref_entries.append((current_ref_num, current_ref_text.strip(), current_ref_page))
                current_ref_num = int(m.group(1))
                current_ref_text = m.group(2)
                current_ref_page = page_idx + 1
                if current_ref_num not in all_refs:
                    all_refs.append(current_ref_num)
            elif current_ref_num is not None:
                current_ref_text += " " + line

    # Save last entry
    if current_ref_num is not None:
        ref_entries.append((current_ref_num, current_ref_text.strip(), current_ref_page))

    doc.close()

    # --- Check sequential numbering ---
    if all_refs:
        max_ref = max(all_refs)
        for expected in range(1, max_ref + 1):
            if expected not in all_refs:
                issues.append(_issue(
                    ref_start + 1, "参考文献",
                    "参考文献编号", f"[{expected}] 应存在",
                    f"缺失 [{expected}]", "warning"
                ))

    # --- Check GB/T 7714 format ---
    # Expected patterns:
    #   [M] — monograph/book: Author. Title[M]. Place: Publisher, Year, Pages.
    #   [J] — journal:        Author. Title[J]. Journal, Year, Vol(Issue): Pages.
    #   [D] — dissertation:   Author. Title[D]. Place: University, Year.
    #   [C] — conference:     Author. Title[C]//Proceedings. Place: Publisher, Year: Pages.
    #   [P] — patent:         Author. Title[P]. Country: Patent No., Year.
    #   [EB/OL] — online:     Author. Title[EB/OL]. URL, Date.

    type_marker_re = re.compile(r"\[(M|J|D|C|P|S|R|N|Z|EB/OL|DB/OL|OL)\]")

    for ref_num, ref_text, ref_page in ref_entries:
        if not ref_text:
            continue

        # Check if type marker exists
        if not type_marker_re.search(ref_text):
            issues.append(_issue(
                ref_page, f"[{ref_num}]",
                "参考文献类型标识",
                "应含文献类型标识如[M][J][D]等",
                f'"{ref_text[:40]}..."', "warning"
            ))
            continue

        # Check if it has author and period-separated structure
        if '.' not in ref_text:
            issues.append(_issue(
                ref_page, f"[{ref_num}]",
                "参考文献格式",
                "GB/T 7714格式：作者.题名[类型].出版信息",
                f'缺少句点分隔: "{ref_text[:40]}..."', "warning"
            ))

    return issues


# ═══════════════════════════════════════════════════════════════
# 14. Page Headers (left + right, 楷体五号)
# ═══════════════════════════════════════════════════════════════

def _get_current_chapter(page_idx_0based: int, chapters: list[dict]) -> dict | None:
    """Find which chapter a page belongs to (page_idx is 0-based)."""
    page_1based = page_idx_0based + 1
    for i in range(len(chapters) - 1, -1, -1):
        if page_1based >= chapters[i]["page"]:
            return chapters[i]
    return None


def _check_headers(pdf_path: str, structure: dict) -> list[dict]:
    """Check page headers on body pages.

    NEU standard:
      - Left:  楷体五号 "东北大学硕士学位论文"
      - Right: 楷体五号 "第X章 章标题"
    """
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    chapters = structure["chapters"]
    if not chapters:
        doc.close()
        return issues

    start_page = chapters[0]["page"] - 1  # 0-indexed

    for page_idx in range(start_page, len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        page_width = page.rect.width

        # Header region: top 60pt
        header_spans = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                if line["bbox"][1] < 60:
                    for span in line["spans"]:
                        if span["text"].strip():
                            header_spans.append(span)

        if not header_spans:
            continue

        # Split left / right by x-coordinate
        mid_x = page_width / 2
        left_spans = [s for s in header_spans if s["bbox"][0] < mid_x]
        right_spans = [s for s in header_spans if s["bbox"][0] >= mid_x]

        # --- Left header ---
        left_text = "".join(s["text"].strip() for s in left_spans)
        expected_left = RULES["header_left"]
        if left_text and expected_left not in left_text:
            issues.append(_issue(
                page_idx + 1, "页眉左端",
                "页眉内容", expected_left,
                left_text[:30], "warning"
            ))

        # --- Right header: "第X章 章标题" ---
        right_text = "".join(s["text"].strip() for s in right_spans)
        current_ch = _get_current_chapter(page_idx, chapters)
        if current_ch and right_text:
            expected_ch_marker = f"第{current_ch['number']}章"
            if expected_ch_marker not in right_text:
                issues.append(_issue(
                    page_idx + 1, "页眉右端",
                    "页眉章节标题",
                    f"{expected_ch_marker} {current_ch['title'][:15]}",
                    right_text[:30], "warning"
                ))

        # --- Header font: 楷体 + 五号 ---
        for span in header_spans:
            if not _font_matches(span["font"], RULES["header_font"]["name_contains"]):
                issues.append(_issue(
                    page_idx + 1, f'页眉 "{span["text"][:15]}"',
                    "页眉字体", "楷体(KaiTi)",
                    span["font"], "warning"
                ))
            r = RULES["header_font"]
            if abs(span["size"] - r["size_pt"]) > r["tolerance_pt"]:
                issues.append(_issue(
                    page_idx + 1, f'页眉 "{span["text"][:15]}"',
                    "页眉字号", f'五号({r["size_pt"]}pt)',
                    f'{span["size"]}pt', "warning"
                ))

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# 15. Page Numbers
# ═══════════════════════════════════════════════════════════════

def _check_page_numbers(pdf_path: str, structure: dict) -> list[dict]:
    """Check page numbers exist in footer region of body pages."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    start, _ = _get_body_page_range(structure)
    page_num_pattern = re.compile(r"[-·]\s*\d+\s*[-·]|\d+")

    for page_idx in range(start - 1, len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        page_height = page.rect.height

        footer_spans = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                if line["bbox"][1] > page_height - 50:
                    for span in line["spans"]:
                        if span["text"].strip():
                            footer_spans.append(span)

        footer_text = " ".join(s["text"].strip() for s in footer_spans)
        if not page_num_pattern.search(footer_text):
            issues.append(_issue(
                page_idx + 1, "页脚",
                "页码", "应有页码", "未检测到页码", "warning"
            ))

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# 16. Paragraph Last Line (末行不少于5字)
# ═══════════════════════════════════════════════════════════════

def _check_paragraph_last_line(pdf_path: str, structure: dict) -> list[dict]:
    """Check that the last line of each paragraph has at least 5 characters.

    If the last line is too short (<5 chars), suggest condensing the paragraph
    to avoid a dangling short line (排版术语：孤字/短尾行).
    """
    issues = []
    import fitz
    doc = fitz.open(pdf_path)
    start, end = _get_body_page_range(structure)

    MIN_LAST_LINE_CHARS = 5

    for page_idx in range(start - 1, end):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue

            # Only check text blocks in body region
            block_y = block["bbox"][1]
            if block_y < 60 or block_y > page.rect.height - 50:
                continue

            lines = block["lines"]
            if len(lines) < 2:
                # Single-line blocks are headings or short items, skip
                continue

            # The last line of a multi-line block is a paragraph ending
            last_line = lines[-1]
            prev_line = lines[-2]
            last_text = "".join(s["text"] for s in last_line["spans"]).strip()
            prev_text = "".join(s["text"] for s in prev_line["spans"]).strip()

            # Only check if previous line is a full-width line (>20 chars)
            # to confirm this is a real paragraph, not a list or heading
            if len(prev_text) < 20:
                continue

            # Skip if last line looks like a caption, formula, or reference
            if re.match(r"^(图|表|式|[（(]\d)", last_text):
                continue

            char_count = len(last_text)
            if 0 < char_count < MIN_LAST_LINE_CHARS:
                issues.append(_issue(
                    page_idx + 1,
                    f'段落末行 "{last_text}"',
                    "段落末行字数",
                    f"末行不少于{MIN_LAST_LINE_CHARS}个字",
                    f'仅{char_count}字，建议缩减上文使末行更饱满',
                    "warning"
                ))

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# 17. Page Bottom Blank (页底不超过2行空白)
# ═══════════════════════════════════════════════════════════════

def _check_page_bottom_blank(pdf_path: str, structure: dict) -> list[dict]:
    """Check that body pages don't have more than 2 blank lines at the bottom.

    Measures the gap between the last text line and the footer/page bottom.
    2 blank lines ≈ 2 × 20pt = 40pt. Flag if gap > 60pt (≈3 lines).
    """
    issues = []
    import fitz
    doc = fitz.open(pdf_path)
    start, end = _get_body_page_range(structure)

    LINE_HEIGHT_PT = 20.0
    MAX_BLANK_LINES = 2
    MAX_GAP_PT = (MAX_BLANK_LINES + 1) * LINE_HEIGHT_PT  # 60pt ≈ 3行

    for page_idx in range(start - 1, end):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        page_height = page.rect.height
        footer_top = page_height - 50  # footer region starts here

        # Find the y-coordinate of the bottom of the last body text line
        last_body_y = 0
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                y_bottom = line["bbox"][3]
                # Must be in body region (below header, above footer)
                if 60 < line["bbox"][1] < footer_top:
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    if text:
                        last_body_y = max(last_body_y, y_bottom)

        if last_body_y == 0:
            continue

        # Gap from last text to footer region
        gap = footer_top - last_body_y
        blank_lines = gap / LINE_HEIGHT_PT

        if blank_lines > MAX_BLANK_LINES + 1:
            # Skip chapter-start pages (they often have extra space after heading)
            is_chapter_start = any(
                ch["page"] == page_idx + 1 for ch in structure["chapters"]
            )
            if is_chapter_start:
                continue

            issues.append(_issue(
                page_idx + 1, "页面底部",
                "页底空白",
                f"页底空行不超过{MAX_BLANK_LINES}行",
                f'底部约{blank_lines:.0f}行空白，建议调整内容填满',
                "warning"
            ))

    doc.close()
    return issues


# ═══════════════════════════════════════════════════════════════
# CLI Entry
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage: python format_checker.py <thesis.pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = check_format(pdf_path)

    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
