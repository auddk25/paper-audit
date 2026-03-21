"""Extract structural information from a thesis PDF.

Extracts: page count, page size, chapter boundaries (from TOC page or heading detection),
and per-page text blocks with font/size metadata.
"""
import re
import fitz  # PyMuPDF


def extract_structure(pdf_path: str) -> dict:
    """Extract thesis structure: pages, chapters, headings.

    Args:
        pdf_path: Path to the thesis PDF file.

    Returns:
        dict with keys: pages, page_size, chapters, headings
    """
    doc = fitz.open(pdf_path)
    result = {
        "pages": len(doc),
        "page_size": _get_page_size(doc[0]),
        "chapters": [],
        "headings": [],
    }

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"]).strip()
                if not text:
                    continue
                font_size = line["spans"][0]["size"] if line["spans"] else 0
                font_name = line["spans"][0]["font"] if line["spans"] else ""

                # Detect chapter headings: "第X章" with large font (>=20pt ~ 二号)
                chapter_match = re.match(r"第\s*([一二三四五六七八九十\d]+)\s*章\s*(.*)", text)
                if chapter_match and font_size >= 20:
                    ch_num = _chinese_to_int(chapter_match.group(1))
                    result["chapters"].append({
                        "number": ch_num,
                        "title": chapter_match.group(2).strip(),
                        "page": page_idx + 1,  # 1-indexed
                        "font_size": round(font_size, 1),
                        "font_name": font_name,
                    })
                    continue

                # Detect section headings: "X.X " with medium font (>=14pt ~ 三号/四号)
                section_match = re.match(r"(\d+\.\d+)\s+(.*)", text)
                if section_match and font_size >= 14:
                    result["headings"].append({
                        "number": section_match.group(1),
                        "title": section_match.group(2).strip(),
                        "page": page_idx + 1,
                        "level": 2,
                        "font_size": round(font_size, 1),
                        "font_name": font_name,
                    })
                    continue

                # Detect subsection headings: "X.X.X " with body-size font (>=12pt)
                subsection_match = re.match(r"(\d+\.\d+\.\d+)\s+(.*)", text)
                if subsection_match and font_size >= 12:
                    result["headings"].append({
                        "number": subsection_match.group(1),
                        "title": subsection_match.group(2).strip(),
                        "page": page_idx + 1,
                        "level": 3,
                        "font_size": round(font_size, 1),
                        "font_name": font_name,
                    })

    # Compute chapter page ranges
    for i, ch in enumerate(result["chapters"]):
        if i + 1 < len(result["chapters"]):
            ch["end_page"] = result["chapters"][i + 1]["page"] - 1
        else:
            ch["end_page"] = result["pages"]

    doc.close()
    return result


def extract_page_text(pdf_path: str, page_num: int) -> str:
    """Extract plain text from a single page (1-indexed)."""
    doc = fitz.open(pdf_path)
    text = doc[page_num - 1].get_text()
    doc.close()
    return text


def extract_page_spans(pdf_path: str, page_num: int) -> list[dict]:
    """Extract all text spans with font metadata from a page (1-indexed).

    Returns list of dicts with: text, font, size, bbox, y_pos
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]
    spans = []
    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    spans.append({
                        "text": span["text"],
                        "font": span["font"],
                        "size": round(span["size"], 1),
                        "bbox": [round(v, 1) for v in span["bbox"]],
                        "y_pos": round(line["bbox"][1], 1),
                    })
    doc.close()
    return spans


def _get_page_size(page) -> dict:
    """Get page dimensions in mm."""
    rect = page.rect
    return {
        "width_pt": round(rect.width, 1),
        "height_pt": round(rect.height, 1),
        "width_mm": round(rect.width / 72 * 25.4, 1),
        "height_mm": round(rect.height / 72 * 25.4, 1),
    }


def _chinese_to_int(s: str) -> int:
    """Convert Chinese numeral string or digit string to int.

    Handles: '一' through '十', '1' through '99', and combinations like '十二'.
    """
    if s.isdigit():
        return int(s)

    mapping = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    }

    if len(s) == 1:
        return mapping.get(s, 0)

    # Handle '十X' = 10+X, 'X十' = X*10, 'X十Y' = X*10+Y
    if '十' in s:
        parts = s.split('十')
        tens = mapping.get(parts[0], 1) if parts[0] else 1
        ones = mapping.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones

    return mapping.get(s, 0)
