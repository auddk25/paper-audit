"""Cross-reference checker for master's thesis PDF.

Checks:
  1. Section references: "第X.Y节" / "X.Y节" → does heading exist?
  2. Figure references: "图X.Y" → does figure exist?
  3. Table references: "表X.Y" → does table exist?
  4. Equation references: "式(X.Y)" / "公式(X.Y)" → does equation exist?
  5. Unreferenced: defined figures/tables/equations never cited in body text

Key design: DEFINITION patterns (strict, positional) are separated from
REFERENCE patterns (loose, any context) to avoid counting body-text
citations as definitions.

Usage:
    python cross_ref_checker.py <thesis.pdf>
    Outputs JSON to stdout.
"""
import json
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from pdf_extractor import extract_structure


def check_cross_refs(pdf_path: str) -> dict:
    """Check all cross-references in the thesis.

    Returns dict with 'sections', 'figures', 'tables', 'equations' keys,
    each containing 'valid', 'invalid' lists.
    """
    import fitz

    try:
        structure = extract_structure(pdf_path)
    except Exception as e:
        return {"error": True, "message": f"结构提取失败: {e}"}

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return {"error": True, "message": f"PDF 打开失败: {e}"}

    try:
        return _run_checks(doc, structure)
    except Exception as e:
        return {"error": True, "message": f"检查过程出错: {e}"}
    finally:
        doc.close()


def _run_checks(doc, structure: dict) -> dict:
    """Core check logic, separated for clean resource management."""

    # Build sets of existing targets
    existing_sections = _build_section_set(structure)
    existing_figures = set()
    existing_tables = set()
    existing_equations = set()

    # Position tracking for order checking: {ref_num: (page, y)}
    fig_def_pos = {}   # 图定义位置
    tab_def_pos = {}   # 表定义位置

    # === DEFINITION patterns (strict, positional) ===
    fig_def = re.compile(r"^\s*图\s*(\d+)[.\s·．](\d+)")
    tab_def = re.compile(r"^\s*表\s*(\d+)[.\s·．](\d+)")
    eq_def = re.compile(r"[（(]\s*(\d+)\s*[.\-·．]\s*(\d+)\s*[）)]\s*$")

    # First pass: collect DEFINITIONS with positions
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text:
                    continue
                y_pos = line["bbox"][1]

                # Figure definition
                m = fig_def.match(text)
                if m:
                    ref_num = f"{m.group(1)}.{m.group(2)}"
                    existing_figures.add(ref_num)
                    if ref_num not in fig_def_pos:
                        fig_def_pos[ref_num] = (page_idx + 1, y_pos)

                # Table definition
                m = tab_def.match(text)
                if m:
                    ref_num = f"{m.group(1)}.{m.group(2)}"
                    existing_tables.add(ref_num)
                    if ref_num not in tab_def_pos:
                        tab_def_pos[ref_num] = (page_idx + 1, y_pos)

                # Equation definition
                m = eq_def.search(text)
                if m:
                    existing_equations.add(f"{m.group(1)}.{m.group(2)}")

    # === REFERENCE patterns (loose, any context) ===
    sec_ref = re.compile(
        r"(?:第\s*(\d+(?:\.\d+)+)\s*节)|"       # 第X.Y节
        r"(?:(\d+(?:\.\d+)+)\s*节)|"              # X.Y节
        r"(?:第\s*(\d+(?:\.\d+)+)\s*小节)"        # 第X.Y小节
    )
    fig_ref = re.compile(r"图\s*(\d+)[.\s·．](\d+)")
    tab_ref = re.compile(r"表\s*(\d+)[.\s·．](\d+)")
    eq_ref = re.compile(r"(?:式|公式)\s*[（(]\s*(\d+)\s*[.\-\s·．]\s*(\d+)\s*[）)]")

    results = {
        "sections": {"valid": [], "invalid": []},
        "figures": {"valid": [], "invalid": []},
        "tables": {"valid": [], "invalid": []},
        "equations": {"valid": [], "invalid": []},
    }

    # Track first reference position for order checking
    fig_first_ref = {}  # {ref_num: (page, context)}
    tab_first_ref = {}

    # Second pass: find all REFERENCES using dict blocks (for y-coordinate)
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        blocks = page.get_text("dict")["blocks"]

        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_stripped = "".join(s["text"] for s in line["spans"]).strip()
                if not line_stripped:
                    continue
                line_y = line["bbox"][1]

                # Section references
                for m in sec_ref.finditer(line_stripped):
                    ref_num = m.group(1) or m.group(2) or m.group(3)
                    if ref_num:
                        entry = _ref_entry(ref_num, f"节{ref_num}", page_num, line_stripped)
                        if ref_num in existing_sections:
                            entry["target_title"] = existing_sections[ref_num]
                            results["sections"]["valid"].append(entry)
                        else:
                            results["sections"]["invalid"].append(entry)

                # Figure references (skip pure caption lines)
                for m in fig_ref.finditer(line_stripped):
                    is_caption = bool(fig_def.match(line_stripped))
                    has_ref_verb = bool(re.search(
                        r"(如图|如表|所示|给出|见图|见表|列出|对比|展示)", line_stripped))
                    if is_caption and not has_ref_verb:
                        continue  # Pure caption, skip
                    ref_num = f"{m.group(1)}.{m.group(2)}"
                    entry = _ref_entry(ref_num, f"图{ref_num}", page_num, line_stripped)
                    if ref_num in existing_figures:
                        results["figures"]["valid"].append(entry)
                    else:
                        results["figures"]["invalid"].append(entry)
                    # Record first body-text reference position (including caption+verb lines)
                    if ref_num not in fig_first_ref and (not is_caption or has_ref_verb):
                        fig_first_ref[ref_num] = (page_num, line_y, line_stripped[:50])

                # Table references (skip pure caption lines)
                for m in tab_ref.finditer(line_stripped):
                    is_caption = bool(tab_def.match(line_stripped))
                    has_ref_verb = bool(re.search(
                        r"(如图|如表|所示|给出|见图|见表|列出|对比|展示)", line_stripped))
                    if is_caption and not has_ref_verb:
                        continue  # Pure caption, skip
                    ref_num = f"{m.group(1)}.{m.group(2)}"
                    entry = _ref_entry(ref_num, f"表{ref_num}", page_num, line_stripped)
                    if ref_num in existing_tables:
                        results["tables"]["valid"].append(entry)
                    else:
                        results["tables"]["invalid"].append(entry)
                    # Record first body-text reference position
                    if ref_num not in tab_first_ref and (not is_caption or has_ref_verb):
                        tab_first_ref[ref_num] = (page_num, line_y, line_stripped[:50])

            # Equation references (skip definition lines)
            for m in eq_ref.finditer(line_stripped):
                # Skip if this is a definition line (number at end)
                if eq_def.search(line_stripped) and not re.search(r"[由根据见如]", line_stripped[:10]):
                    continue
                ref_num = f"{m.group(1)}.{m.group(2)}"
                entry = _ref_entry(ref_num, f"式({ref_num})", page_num, line_stripped)
                if ref_num in existing_equations:
                    results["equations"]["valid"].append(entry)
                else:
                    results["equations"]["invalid"].append(entry)

    # Deduplicate (same ref on same page)
    for category in results.values():
        category["valid"] = _dedup(category["valid"])
        category["invalid"] = _dedup(category["invalid"])

    # === Unreferenced check: defined but never cited ===
    referenced_figures = {e["ref"] for e in results["figures"]["valid"]}
    referenced_tables = {e["ref"] for e in results["tables"]["valid"]}
    referenced_equations = {e["ref"] for e in results["equations"]["valid"]}

    results["unreferenced"] = {
        "figures": sorted(existing_figures - referenced_figures),
        "tables": sorted(existing_tables - referenced_tables),
        "equations": sorted(existing_equations - referenced_equations),
    }

    # === Order check: 先文后图/表 ===
    # Rule: first body-text reference must appear BEFORE the definition.
    # Compare page first; if same page, compare y-coordinate.
    # fig_first_ref/tab_first_ref: {ref_num: (page, y, context)}
    # fig_def_pos/tab_def_pos: {ref_num: (page, y)}
    order_violations = []

    for ref_num in existing_figures:
        if ref_num in fig_first_ref and ref_num in fig_def_pos:
            ref_page, ref_y, ref_ctx = fig_first_ref[ref_num]
            def_page, def_y = fig_def_pos[ref_num]
            # Violation: ref appears AFTER def (later page, or same page but lower y)
            if ref_page > def_page or (ref_page == def_page and ref_y > def_y):
                order_violations.append({
                    "type": "图",
                    "ref": ref_num,
                    "label": f"图{ref_num}",
                    "def_page": def_page,
                    "ref_page": ref_page,
                    "ref_context": ref_ctx,
                    "issue": f"图{ref_num}定义在p{def_page}，首次引用在p{ref_page}（违反先文后图）",
                })

    for ref_num in existing_tables:
        if ref_num in tab_first_ref and ref_num in tab_def_pos:
            ref_page, ref_y, ref_ctx = tab_first_ref[ref_num]
            def_page, def_y = tab_def_pos[ref_num]
            if ref_page > def_page or (ref_page == def_page and ref_y > def_y):
                order_violations.append({
                    "type": "表",
                    "ref": ref_num,
                    "label": f"表{ref_num}",
                    "def_page": def_page,
                    "ref_page": ref_page,
                    "ref_context": ref_ctx,
                    "issue": f"表{ref_num}定义在p{def_page}，首次引用在p{ref_page}（违反先文后表）",
                })

    results["order_violations"] = order_violations

    # Summary
    results["summary"] = {
        "sections": {
            "valid": len(results["sections"]["valid"]),
            "invalid": len(results["sections"]["invalid"]),
        },
        "figures": {
            "valid": len(results["figures"]["valid"]),
            "invalid": len(results["figures"]["invalid"]),
        },
        "tables": {
            "valid": len(results["tables"]["valid"]),
            "invalid": len(results["tables"]["invalid"]),
        },
        "equations": {
            "valid": len(results["equations"]["valid"]),
            "invalid": len(results["equations"]["invalid"]),
        },
    }
    total_invalid = sum(v["invalid"] for v in results["summary"].values())
    results["summary"]["total_invalid"] = total_invalid
    results["summary"]["unreferenced"] = {
        "figures": len(results["unreferenced"]["figures"]),
        "tables": len(results["unreferenced"]["tables"]),
        "equations": len(results["unreferenced"]["equations"]),
    }
    results["summary"]["total_unreferenced"] = sum(
        results["summary"]["unreferenced"].values()
    )
    results["summary"]["order_violations"] = len(order_violations)

    # Definition counts for transparency
    results["definitions"] = {
        "sections": len(existing_sections),
        "figures": len(existing_figures),
        "tables": len(existing_tables),
        "equations": len(existing_equations),
    }

    return results


def _ref_entry(ref_num: str, label: str, page: int, context: str) -> dict:
    """Create a reference entry."""
    return {
        "ref": ref_num,
        "label": label,
        "page": page,
        "context": context[:80],
    }


def _dedup(entries: list[dict]) -> list[dict]:
    """Remove duplicate entries (same ref + same page)."""
    seen = set()
    result = []
    for e in entries:
        key = (e["ref"], e["page"])
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result


def _build_section_set(structure: dict) -> dict:
    """Build a dict of section_number -> title from structure headings."""
    sections = {}
    for h in structure.get("headings", []):
        sections[h["number"]] = h["title"]
    for ch in structure.get("chapters", []):
        sections[str(ch["number"])] = ch["title"]
    return sections


def main():
    if len(sys.argv) < 2:
        print("Usage: python cross_ref_checker.py <thesis.pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(json.dumps({
            "error": True,
            "message": f"文件不存在: {pdf_path}"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    # Force UTF-8 on Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    try:
        result = check_cross_refs(pdf_path)
    except Exception as e:
        result = {"error": True, "message": f"未预期错误: {e}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result.get("error"):
        sys.exit(2)


if __name__ == "__main__":
    main()
