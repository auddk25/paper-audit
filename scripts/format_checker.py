"""Format checker for master's thesis PDF (NEU standard).

Checks: page size, body font/size, heading fonts/sizes, figure/table numbering,
reference format, headers, footers.

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
    "body_font": {
        "name_contains": ["SimSun", "宋体", "Song", "STSong"],
        "size_pt": 12.0,
        "tolerance_pt": 0.5,
    },
    "chapter_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 22.0,
        "tolerance_pt": 1.0,
    },
    "section_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 16.0,
        "tolerance_pt": 1.0,
    },
    "subsection_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 14.0,
        "tolerance_pt": 1.0,
    },
    "subsubsection_heading": {
        "name_contains": ["SimHei", "黑体", "Hei", "STHei"],
        "size_pt": 12.0,
        "tolerance_pt": 0.5,
    },
    "caption_font_size": 10.5,  # 五号
    "english_font": ["Times", "TimesNewRoman"],
    "header_left": "东北大学硕士学位论文",
}


def check_format(pdf_path: str) -> dict:
    """Run all format checks on a thesis PDF.

    Args:
        pdf_path: Path to thesis PDF.

    Returns:
        dict with 'issues' list and 'summary' counts.
    """
    structure = extract_structure(pdf_path)
    issues = []

    issues.extend(_check_page_size(structure))
    issues.extend(_check_body_text(pdf_path, structure))
    issues.extend(_check_chapter_headings(structure))
    issues.extend(_check_section_headings(structure))
    issues.extend(_check_figure_table_numbering(pdf_path, structure))
    issues.extend(_check_references(pdf_path, structure))
    issues.extend(_check_headers(pdf_path, structure))
    issues.extend(_check_page_numbers(pdf_path, structure))

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


# ─── Page Size ───────────────────────────────────────────────

def _check_page_size(structure: dict) -> list[dict]:
    """Check page dimensions are A4."""
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


# ─── Body Text ───────────────────────────────────────────────

def _check_body_text(pdf_path: str, structure: dict) -> list[dict]:
    """Check body text font and size on sampled pages."""
    issues = []
    r = RULES["body_font"]

    # Start from first chapter page, skip front matter
    start_page = 1
    if structure["chapters"]:
        start_page = structure["chapters"][0]["page"]

    # Sample every 3rd page for efficiency
    checked_pages = set()
    for pg in range(start_page, structure["pages"] + 1, 3):
        if pg in checked_pages:
            continue
        checked_pages.add(pg)
        spans = extract_page_spans(pdf_path, pg)

        # Filter to body region: below header (y>70pt), above footer (y<780pt)
        body_spans = [s for s in spans if 70 < s["y_pos"] < 780]
        for span in body_spans:
            # Skip headings (larger text) and very short fragments
            if span["size"] > r["size_pt"] + r["tolerance_pt"] + 1:
                continue
            if len(span["text"].strip()) < 4:
                continue

            # Check font — allow SongTi for Chinese, Times for English
            if not _font_matches(span["font"], r["name_contains"]):
                if not _font_matches(span["font"], RULES["english_font"]):
                    issues.append(_issue(
                        pg, f'"{span["text"][:20]}..."',
                        "正文字体", "宋体/Times New Roman", span["font"], "warning"
                    ))

            # Check size
            if abs(span["size"] - r["size_pt"]) > r["tolerance_pt"]:
                # Skip if it's caption size (smaller) — those are OK
                if span["size"] < r["size_pt"] - 2:
                    continue
                issues.append(_issue(
                    pg, f'"{span["text"][:20]}..."',
                    "正文字号", f'小四号({r["size_pt"]}pt)', f'{span["size"]}pt', "warning"
                ))

    return issues


# ─── Chapter Headings ────────────────────────────────────────

def _check_chapter_headings(structure: dict) -> list[dict]:
    """Check chapter heading font and size: should be 二号黑体 (22pt SimHei)."""
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


# ─── Section Headings ────────────────────────────────────────

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


# ─── Figure / Table / Equation Numbering ─────────────────────

def _check_figure_table_numbering(pdf_path: str, structure: dict) -> list[dict]:
    """Check figure/table/equation numbering continuity within each chapter."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    # Patterns: 图2.1, 表2.1, 式(2-1) or (2.1)
    fig_pattern = re.compile(r"图\s*(\d+)[.\s·](\d+)")
    tab_pattern = re.compile(r"表\s*(\d+)[.\s·](\d+)")
    eq_pattern = re.compile(r"[式公]\s*[（(]\s*(\d+)\s*[-.\s·]\s*(\d+)\s*[）)]")

    fig_nums = {}  # chapter -> [(seq_num, page)]
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

    # Check continuity: 1,2,3... with no gaps
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


# ─── References ──────────────────────────────────────────────

def _check_references(pdf_path: str, structure: dict) -> list[dict]:
    """Check reference format: sequential [N] numbering, no gaps."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    ref_pattern = re.compile(r"\[(\d+)\]")
    all_refs = []

    # Find reference section
    ref_start = None
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text()
        if "参考文献" in text:
            ref_start = page_idx
            break

    if ref_start is not None:
        for page_idx in range(ref_start, len(doc)):
            text = doc[page_idx].get_text()
            for m in ref_pattern.finditer(text):
                num = int(m.group(1))
                if num not in all_refs:
                    all_refs.append(num)

    # Check sequential: [1], [2], [3]... no gaps
    if all_refs:
        max_ref = max(all_refs)
        for expected in range(1, max_ref + 1):
            if expected not in all_refs:
                issues.append(_issue(
                    ref_start + 1 if ref_start else 0, "参考文献",
                    "参考文献编号", f"[{expected}] 应存在",
                    f"缺失 [{expected}]", "warning"
                ))

    doc.close()
    return issues


# ─── Page Headers ────────────────────────────────────────────

def _check_headers(pdf_path: str, structure: dict) -> list[dict]:
    """Check page headers on body pages."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    # Headers typically start from abstract page
    start_page = 1
    if structure["chapters"]:
        start_page = max(1, structure["chapters"][0]["page"] - 2)

    for page_idx in range(start_page, len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        # Header region: top 60pt of page
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

        # Check left header content
        left_header = header_spans[0]["text"].strip() if header_spans else ""
        expected = RULES["header_left"]
        if left_header and expected not in left_header:
            # Only flag body pages (after first chapter)
            if any(ch["page"] <= page_idx + 1 for ch in structure["chapters"]):
                issues.append(_issue(
                    page_idx + 1, "页眉左端",
                    "页眉内容", expected,
                    left_header[:30], "warning"
                ))

    doc.close()
    return issues


# ─── Page Numbers ────────────────────────────────────────────

def _check_page_numbers(pdf_path: str, structure: dict) -> list[dict]:
    """Check page numbers exist in footer region of body pages."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    start_page = 1
    if structure["chapters"]:
        start_page = structure["chapters"][0]["page"]

    page_num_pattern = re.compile(r"[-·]\s*\d+\s*[-·]|\d+")

    for page_idx in range(start_page - 1, len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        page_height = page.rect.height

        # Footer region: bottom 50pt
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


# ─── CLI Entry ───────────────────────────────────────────────

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
