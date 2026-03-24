"""Format checker for master's thesis PDF — spatial checks only.

Checks 9 categories that require PDF coordinate analysis:
  1. Page size (A4: 210x297mm)
  2. Body area (版芯 160x247mm)
  3. Caption position (图题在图下方 + 表题在表上方)
  4. Page bottom blank (页底空白 <= 2行)
  5. Annotation vs caption size (图中标注字号 <= 图题字号)
  6. Image resolution (图片分辨率 >= 150 DPI)
  7. Equation centering (公式居中)
  8. Equation number alignment (式号右对齐)
  9. Table cross-page (表格跨页续表头)

Font/text/numbering checks have been migrated to word_checker.py.

Usage:
    python format_checker.py <thesis.pdf>
    Outputs JSON to stdout.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from pdf_extractor import extract_structure


# === NEU Format Rules (spatial only) ===
RULES = {
    "page_size": {
        "width_mm": 210.0,
        "height_mm": 297.0,
        "tolerance_mm": 1.0,
    },
    "body_area": {
        "width_mm": 160.0,
        "height_mm": 247.0,
        "tolerance_mm": 5.0,
    },
    "caption_font": {
        "size_pt": 10.5,  # 五号
        "tolerance_pt": 0.5,
    },
}

# PT -> MM conversion factor
PT_TO_MM = 25.4 / 72


def check_format(pdf_path: str) -> dict:
    """Run all PDF spatial checks on a thesis PDF.

    Returns dict with 'issues' list and 'summary' counts.
    """
    structure = extract_structure(pdf_path)
    issues = []

    issues.extend(_check_page_size(structure))
    issues.extend(_check_body_area(pdf_path, structure))
    issues.extend(_check_caption_position(pdf_path, structure))
    issues.extend(_check_page_bottom_blank(pdf_path, structure))
    issues.extend(_check_annotation_vs_caption_size(pdf_path, structure))
    issues.extend(_check_image_resolution(pdf_path, structure))
    issues.extend(_check_equation_centering(pdf_path, structure))
    issues.extend(_check_equation_number_alignment(pdf_path, structure))
    # TODO: _check_table_cross_page 误报率高（PDF无法可靠区分表格数据和正文），
    # 暂时禁用。表格跨页检查改由 word_checker.py #28 通过 Word 表格属性实现。
    # issues.extend(_check_table_cross_page(pdf_path, structure))

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
        "source": "pdf",
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


# ===============================================================
# 1. Page Size (A4: 210x297mm)
# ===============================================================

def _check_page_size(structure: dict) -> list[dict]:
    """Check page dimensions are A4 (210x297mm)."""
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


# ===============================================================
# 2. Body Area (版芯 160x247mm)
# ===============================================================

def _check_body_area(pdf_path: str, structure: dict) -> list[dict]:
    """Check body area (版芯) dimensions: 160x247mm, not including header/footer."""
    issues = []
    import fitz
    r = RULES["body_area"]
    start, end = _get_body_page_range(structure)

    with fitz.open(pdf_path) as doc:
        # Sample per-chapter: first, middle, last page of each chapter
        sample_pages = set()
        chapters = structure.get("chapters", [])
        if chapters:
            for i, ch in enumerate(chapters):
                ch_start = ch["page"] - 1  # 0-indexed
                ch_end = (chapters[i + 1]["page"] - 2) if i + 1 < len(chapters) else (end - 1)
                ch_mid = (ch_start + ch_end) // 2
                for p in [ch_start, ch_mid, ch_end]:
                    if 0 <= p < len(doc):
                        sample_pages.add(p)
        else:
            sample_pages = set(range(start - 1, end, 5))

        sample_pages = sorted(sample_pages)
        if not sample_pages:
            return issues

        widths_mm = []
        heights_mm = []

        for page_idx in sample_pages:
            page = doc[page_idx]
            blocks = page.get_text("dict")["blocks"]

            body_blocks = []
            for block in blocks:
                if "lines" not in block:
                    continue
                by0 = block["bbox"][1]
                by1 = block["bbox"][3]
                if by0 < 60 or by1 > page.rect.height - 50:
                    continue
                body_blocks.append(block["bbox"])

            if not body_blocks:
                continue

            x0 = min(b[0] for b in body_blocks)
            y0 = min(b[1] for b in body_blocks)
            x1 = max(b[2] for b in body_blocks)
            y1 = max(b[3] for b in body_blocks)

            widths_mm.append((x1 - x0) * PT_TO_MM)
            heights_mm.append((y1 - y0) * PT_TO_MM)

    if widths_mm:
        avg_w = sum(widths_mm) / len(widths_mm)
        avg_h = sum(heights_mm) / len(heights_mm)

        if abs(avg_w - r["width_mm"]) > r["tolerance_mm"]:
            issues.append(_issue(
                start, f"版芯（抽样{len(sample_pages)}页）", "版芯宽度",
                f'{r["width_mm"]}mm', f'{avg_w:.1f}mm', "warning"
            ))
        if abs(avg_h - r["height_mm"]) > r["tolerance_mm"]:
            issues.append(_issue(
                start, f"版芯（抽样{len(sample_pages)}页）", "版芯高度",
                f'{r["height_mm"]}mm', f'{avg_h:.1f}mm', "warning"
            ))

    return issues


# ===============================================================
# 3. Caption Position (图题在图下方 + 表题在表上方)
# ===============================================================

def _check_caption_position(pdf_path: str, structure: dict) -> list[dict]:
    """Check figure captions are below figures, table captions are above tables.

    Extracted from the former _check_caption_format — only position logic,
    font checks have been migrated to word_checker.py.
    """
    issues = []
    import fitz

    fig_caption_re = re.compile(r"^图\s*\d+[.\s·]\d+")
    tab_caption_re = re.compile(r"^表\s*\d+[.\s·]\d+")

    with fitz.open(pdf_path) as doc:
      for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        # Collect all text lines with y-position
        text_lines = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if text:
                    text_lines.append({
                        "text": text,
                        "y": line["bbox"][1],
                        "y_bottom": line["bbox"][3],
                    })

        # Find visual elements: image blocks (type==1) + vector drawings
        image_blocks = [block["bbox"] for block in blocks if block.get("type") == 1]

        # Also detect vector drawings (流程图、架构图等矢量图形)
        try:
            drawings = page.get_drawings()
            if drawings:
                # Cluster nearby drawings into bounding regions
                for d in drawings:
                    r = d.get("rect")
                    if r and (r.width > 50 and r.height > 50):  # ignore tiny decorations
                        image_blocks.append(tuple(r))
        except Exception:
            pass  # get_drawings not available in older PyMuPDF

        # --- Figure caption position: should be BELOW the figure ---
        for tl in text_lines:
            if not fig_caption_re.match(tl["text"]):
                continue
            caption_y = tl["y"]

            if not image_blocks:
                # No image or drawing detected — cannot verify, skip (不报误报)
                continue

            has_image_above = any(
                img[3] < caption_y + 10  # image/drawing bottom above caption
                for img in image_blocks
            )
            if not has_image_above:
                has_image_below = any(
                    img[1] > caption_y - 10
                    for img in image_blocks
                )
                if has_image_below:
                    issues.append(_issue(
                        page_idx + 1, f'{tl["text"][:25]}',
                        "图题位置", "图题应在图的下方",
                        "图题可能在图的上方", "warning"
                    ))

        # --- Table caption position: should be ABOVE the table ---
        for tl in text_lines:
            if not tab_caption_re.match(tl["text"]):
                continue
            caption_y_bottom = tl["y_bottom"]

            # Look for table-like content below caption.
            # Tables in PDF either appear as image blocks or as dense
            # text blocks with structured/aligned columns below the caption.
            # Heuristic: there should be content immediately below the caption.
            has_content_below = False
            for tl2 in text_lines:
                if tl2["y"] > caption_y_bottom + 5 and tl2["y"] < caption_y_bottom + 80:
                    has_content_below = True
                    break
            if not has_content_below:
                for img in image_blocks:
                    if img[1] > caption_y_bottom - 5 and img[1] < caption_y_bottom + 80:
                        has_content_below = True
                        break

            if not has_content_below:
                # Caption is at bottom with nothing below — might be misplaced
                # Check if there's content ABOVE that looks like table data
                has_content_above = False
                for tl2 in text_lines:
                    if tl2["y_bottom"] < tl["y"] - 5 and tl2["y_bottom"] > tl["y"] - 80:
                        has_content_above = True
                        break
                if has_content_above:
                    issues.append(_issue(
                        page_idx + 1, f'{tl["text"][:25]}',
                        "表题位置", "表题应在表的上方",
                        "表题可能在表的下方", "warning"
                    ))

    return issues


# ===============================================================
# 4. Page Bottom Blank (页底空白 <= 2行)
# ===============================================================

def _check_page_bottom_blank(pdf_path: str, structure: dict) -> list[dict]:
    """Check that body pages don't have more than 2 blank lines at the bottom.

    Measures the gap between the last text line and the footer/page bottom.
    2 blank lines ~ 2 x 20pt = 40pt. Flag if gap > 60pt (~3 lines).
    """
    issues = []
    import fitz
    start, end = _get_body_page_range(structure)

    LINE_HEIGHT_PT = 20.0
    MAX_BLANK_LINES = 2

    with fitz.open(pdf_path) as doc:
        for page_idx in range(start - 1, end):
            page = doc[page_idx]
            blocks = page.get_text("dict")["blocks"]
            page_height = page.rect.height
            footer_top = page_height - 50

            last_body_y = 0
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    y_bottom = line["bbox"][3]
                    if 60 < line["bbox"][1] < footer_top:
                        text = "".join(s["text"] for s in line["spans"]).strip()
                        if text:
                            last_body_y = max(last_body_y, y_bottom)

            if last_body_y == 0:
                continue

            gap = footer_top - last_body_y
            blank_lines = gap / LINE_HEIGHT_PT

            if blank_lines > MAX_BLANK_LINES + 1:
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

    return issues


# ===============================================================
# 5. Annotation vs Caption Size (图中标注字号 <= 图题字号)
# ===============================================================

def _check_annotation_vs_caption_size(pdf_path: str, structure: dict) -> list[dict]:
    """Check that annotation text inside figures/tables uses font size <= caption size.

    NEU rule: text annotations within figures (axis labels, legends, etc.)
    must not exceed the caption font size (五号 10.5pt).
    """
    issues = []
    import fitz

    fig_caption_re = re.compile(r"图\s*(\d+)[.\s·](\d+)")
    tab_caption_re = re.compile(r"表\s*(\d+)[.\s·](\d+)")

    caption_size = RULES["caption_font"]["size_pt"]  # 10.5pt
    tolerance = RULES["caption_font"]["tolerance_pt"]

    with fitz.open(pdf_path) as doc:
     for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        # 1. Identify image blocks (type==1) on this page
        image_bboxes = [block["bbox"] for block in blocks if block.get("type") == 1]
        if not image_bboxes:
            continue

        # 2. Collect caption lines and their font sizes
        caption_lines = []  # (y, size, text)
        all_text_spans = []  # (bbox, size, text, font)

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text = "".join(s["text"] for s in line["spans"]).strip()
                for span in line["spans"]:
                    span_text = span["text"].strip()
                    if span_text:
                        all_text_spans.append({
                            "bbox": span["bbox"],
                            "size": span["size"],
                            "text": span_text,
                            "font": span["font"],
                        })
                if fig_caption_re.match(line_text) or tab_caption_re.match(line_text):
                    sizes = [s["size"] for s in line["spans"] if s["text"].strip()]
                    avg_size = sum(sizes) / len(sizes) if sizes else caption_size
                    caption_lines.append({
                        "y": line["bbox"][1],
                        "size": avg_size,
                        "text": line_text,
                    })

        if not caption_lines:
            continue

        # 3. For each image, find text spans that overlap or are immediately
        #    adjacent to the image bbox — these are annotations inside the figure
        for img_bbox in image_bboxes:
            ix0, iy0, ix1, iy1 = img_bbox
            # Expand image region slightly to catch adjacent labels
            margin = 5
            for span in all_text_spans:
                sx0, sy0, sx1, sy1 = span["bbox"]

                # Check if span is within the image region
                if (sx0 >= ix0 - margin and sx1 <= ix1 + margin and
                        sy0 >= iy0 - margin and sy1 <= iy1 + margin):

                    # Skip if this span is itself a caption
                    span_text = span["text"]
                    if fig_caption_re.search(span_text) or tab_caption_re.search(span_text):
                        continue

                    # Skip very short text (single chars, punctuation)
                    if len(span_text) < 2:
                        continue

                    # Find the nearest caption to determine reference size
                    nearest_caption_size = caption_size
                    if caption_lines:
                        # Use closest caption by y distance
                        nearest = min(caption_lines,
                                      key=lambda c: abs(c["y"] - sy0))
                        nearest_caption_size = nearest["size"]

                    # Check if annotation font is larger than caption
                    if span["size"] > nearest_caption_size + tolerance:
                        issues.append(_issue(
                            page_idx + 1,
                            f'图内标注 "{span_text[:20]}"',
                            "图内标注字号",
                            f"不大于图题字号({nearest_caption_size}pt)",
                            f'{span["size"]}pt',
                            "warning"
                        ))

    return issues


# ===============================================================
# 6. Image Resolution (图片分辨率 >= 150 DPI)
# ===============================================================

def _check_image_resolution(pdf_path: str, structure: dict) -> list[dict]:
    """检查图片分辨率：DPI < 150 报 warning，< 72 报 error。"""
    issues = []
    import fitz
    with fitz.open(pdf_path) as doc:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            images = page.get_images(full=True)
            for img_info in images:
                xref = img_info[0]
                # 获取图片像素尺寸
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue
                pix_w = base_image.get("width", 0)
                pix_h = base_image.get("height", 0)
                if pix_w == 0 or pix_h == 0:
                    continue
                # 获取图片在页面中的渲染尺寸
                rects = page.get_image_rects(xref)
                for rect in rects:
                    render_w_inch = rect.width / 72  # pt to inch
                    render_h_inch = rect.height / 72
                    if render_w_inch > 0 and render_h_inch > 0:
                        dpi_x = pix_w / render_w_inch
                        dpi_y = pix_h / render_h_inch
                        dpi = min(dpi_x, dpi_y)
                        if dpi < 72:
                            issues.append(_issue(
                                page_idx + 1, f"图片(xref={xref})",
                                "图片分辨率", ">=150 DPI",
                                f"{dpi:.0f} DPI（严重模糊）", "error"))
                        elif dpi < 150:
                            issues.append(_issue(
                                page_idx + 1, f"图片(xref={xref})",
                                "图片分辨率", ">=150 DPI",
                                f"{dpi:.0f} DPI", "warning"))
    return issues


# ===============================================================
# 7. Equation Centering (公式居中)
# ===============================================================

def _check_equation_centering(pdf_path: str, structure: dict) -> list[dict]:
    """检查公式是否水平居中：找含 (X.Y) 式号的行，检查公式主体左右边距差。"""
    issues = []
    import fitz

    eq_num_re = re.compile(r"\(\d+\.\d+\)")
    start, end = _get_body_page_range(structure)

    with fitz.open(pdf_path) as doc:
        for page_idx in range(start - 1, end):
            page = doc[page_idx]
            page_width = page.rect.width
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    line_text = "".join(s["text"] for s in line["spans"]).strip()
                    if not eq_num_re.search(line_text):
                        continue

                    # 收集非式号部分的 span bbox (公式主体)
                    formula_spans = []
                    for span in line["spans"]:
                        span_text = span["text"].strip()
                        if not span_text:
                            continue
                        if eq_num_re.fullmatch(span_text):
                            continue  # 跳过式号 span
                        formula_spans.append(span["bbox"])

                    if not formula_spans:
                        continue

                    # 排除正文中引用式号的行：
                    # 独立公式行通常较短且以公式符号为主，
                    # 正文行含大量中文汉字
                    non_eq_text = eq_num_re.sub("", line_text).strip()
                    cjk_count = sum(1 for c in non_eq_text if '\u4e00' <= c <= '\u9fff')
                    if cjk_count > 6:
                        continue  # 正文引用式号，跳过

                    # 计算公式主体的 bbox
                    fx0 = min(s[0] for s in formula_spans)
                    fx1 = max(s[2] for s in formula_spans)

                    # 检查公式主体中心是否接近页面中心
                    formula_center = (fx0 + fx1) / 2
                    page_center = page_width / 2
                    center_offset = abs(formula_center - page_center)

                    if center_offset > 30:
                        issues.append(_issue(
                            page_idx + 1,
                            f'公式行 "{line_text[:30]}"',
                            "公式居中", "公式主体水平居中",
                            f"偏离中心 {center_offset:.0f}pt",
                            "warning"
                        ))

    return issues


# ===============================================================
# 8. Equation Number Alignment (式号右对齐)
# ===============================================================

def _check_equation_number_alignment(pdf_path: str, structure: dict) -> list[dict]:
    """检查式号 (X.Y) 是否右对齐：式号右边界应接近页面右边界。"""
    issues = []
    import fitz

    eq_num_re = re.compile(r"\(\d+\.\d+\)")
    start, end = _get_body_page_range(structure)

    with fitz.open(pdf_path) as doc:
        for page_idx in range(start - 1, end):
            page = doc[page_idx]
            page_width = page.rect.width
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    line_text = "".join(s["text"] for s in line["spans"]).strip()
                    if not eq_num_re.search(line_text):
                        continue

                    # 排除正文中引用式号的行（独立公式行汉字很少）
                    non_eq_text = eq_num_re.sub("", line_text).strip()
                    cjk_count = sum(1 for c in non_eq_text if '\u4e00' <= c <= '\u9fff')
                    if cjk_count > 6:
                        continue

                    # 找到式号 span 的右边界
                    eq_num_x1 = None
                    eq_num_text = None
                    for span in line["spans"]:
                        span_text = span["text"].strip()
                        if eq_num_re.search(span_text):
                            eq_num_x1 = span["bbox"][2]
                            eq_num_text = span_text

                    if eq_num_x1 is None:
                        continue

                    # 检查式号右边界是否接近页面右边界
                    # 85pt ≈ 30mm，对应正常右边距位置
                    gap = page_width - eq_num_x1
                    if gap > 85:
                        issues.append(_issue(
                            page_idx + 1,
                            f'式号 "{eq_num_text}"',
                            "式号右对齐",
                            "式号应靠近右边界（距右 <85pt）",
                            f"距右边界 {gap:.0f}pt",
                            "warning"
                        ))

    return issues


# ===============================================================
# 9. Table Cross-Page (表格跨页续表头)
# ===============================================================

def _check_table_cross_page(pdf_path: str, structure: dict) -> list[dict]:
    """检查表格跨页时是否有续表头。

    策略：找表题行，判断表格是否真的延伸到页底（通过检测表格特征：
    短行、多列对齐、数字密集），而非把正文段落误认为表格内容。
    如果确认跨页，检查下一页顶部是否有续表标记。
    """
    issues = []
    import fitz

    table_caption_re = re.compile(r"^表\s*\d+")
    start, end = _get_body_page_range(structure)

    with fitz.open(pdf_path) as doc:
        total_pages = len(doc)

        for page_idx in range(start - 1, end):
            page = doc[page_idx]
            blocks = page.get_text("dict")["blocks"]
            page_height = page.rect.height
            footer_top = page_height - 50

            # 收集本页文本行（含 bbox 信息）
            text_lines = []
            for block in blocks:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    if text:
                        text_lines.append({
                            "text": text,
                            "y": line["bbox"][1],
                            "y_bottom": line["bbox"][3],
                            "x0": line["bbox"][0],
                            "x1": line["bbox"][2],
                            "width": line["bbox"][2] - line["bbox"][0],
                        })

            # 找本页的表题
            table_captions = [
                tl for tl in text_lines if table_caption_re.match(tl["text"])
            ]
            if not table_captions:
                continue

            for cap in table_captions:
                # 收集表题下方到页底的所有行
                lines_after_cap = [
                    tl for tl in text_lines if tl["y"] > cap["y_bottom"]
                ]
                if not lines_after_cap:
                    continue

                # 判断这些行是否具有"表格特征"：
                # 1. 多数行较短（<页宽60%）或包含多个空格分隔的列
                # 2. 行间距较小且均匀
                # 3. 不是连续的长段落文字
                page_width = page.rect.width
                table_like_lines = 0
                paragraph_like_lines = 0
                for tl in lines_after_cap:
                    is_short = tl["width"] < page_width * 0.6
                    has_columns = "  " in tl["text"] or "\t" in tl["text"]
                    is_long_text = len(tl["text"]) > 60 and not has_columns
                    if (is_short or has_columns) and not is_long_text:
                        table_like_lines += 1
                    elif is_long_text:
                        paragraph_like_lines += 1

                # 如果表格下方大部分是长段落文字，说明表格已结束，后面是正文
                if paragraph_like_lines > table_like_lines:
                    continue  # 不是跨页，是表格后接正文

                # 检查最后一个表格样行是否接近页底
                table_lines_sorted = sorted(
                    [tl for tl in lines_after_cap
                     if tl["width"] < page_width * 0.6 or "  " in tl["text"]],
                    key=lambda x: x["y_bottom"],
                    reverse=True
                )
                if not table_lines_sorted:
                    continue
                last_table_y = table_lines_sorted[0]["y_bottom"]
                if last_table_y < footer_top - 80:
                    continue  # 表格在页面中部就结束了，没到页底

                # 确认跨页：检查下一页
                next_page_idx = page_idx + 1
                if next_page_idx >= total_pages:
                    continue

                next_page = doc[next_page_idx]
                next_blocks = next_page.get_text("dict")["blocks"]

                next_top_lines = []
                for block in next_blocks:
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        text = "".join(s["text"] for s in line["spans"]).strip()
                        if text and 60 < line["bbox"][1] < 210:
                            next_top_lines.append(text)

                if not next_top_lines:
                    continue

                # 排除：下一页是新章节
                chapter_re = re.compile(r"^第[一二三四五六七八九十\d]+章")
                if any(chapter_re.match(t) for t in next_top_lines):
                    continue

                # 排除：下一页是新的节标题
                section_re = re.compile(r"^\d+\.\d+")
                if any(section_re.match(t) for t in next_top_lines[:2]):
                    continue

                # 检查下一页顶部是否有续表标记
                has_cont_marker = any(
                    "续" in t or table_caption_re.match(t)
                    for t in next_top_lines[:3]
                )

                if not has_cont_marker:
                    # 下一页顶部也要有表格特征才报
                    next_table_like = sum(
                        1 for t in next_top_lines[:5]
                        if len(t) < 40 and ("  " in t or re.search(r"\d.*\d", t))
                    )
                    if next_table_like >= 2:
                        issues.append(_issue(
                            next_page_idx + 1,
                            f'{cap["text"][:25]}',
                            "表格跨页续表头",
                            "跨页表格应有续表标记和重复表头",
                            "下一页顶部未发现续表标记",
                            "warning"
                        ))

    return issues


# ===============================================================
# CLI Entry
# ===============================================================

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
