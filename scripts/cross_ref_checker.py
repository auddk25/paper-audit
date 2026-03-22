"""Cross-reference checker for master's thesis PDF.

Checks:
  1. Section references: "第X.Y节" / "X.Y节" → does heading exist?
  2. Figure references: "图X.Y" → does figure exist?
  3. Table references: "表X.Y" → does table exist?
  4. Equation references: "式(X.Y)" / "公式(X.Y)" → does equation exist?

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

    # === DEFINITION patterns (strict, positional) ===
    # Figure/table definitions: must be at line start or standalone caption line
    # e.g. "图3.2 系统架构图" or "表4.1 实验参数"
    fig_def = re.compile(r"^\s*图\s*(\d+)[.\s·．](\d+)")
    tab_def = re.compile(r"^\s*表\s*(\d+)[.\s·．](\d+)")
    # Equation definitions: number at line end, e.g. "(2.1)" or "（2.1）" at right side
    eq_def = re.compile(r"[（(]\s*(\d+)\s*[.\-·．]\s*(\d+)\s*[）)]\s*$")

    # First pass: collect DEFINITIONS only (line-by-line, positional matching)
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

                # Figure definition: line starts with "图X.Y"
                m = fig_def.match(text)
                if m:
                    existing_figures.add(f"{m.group(1)}.{m.group(2)}")

                # Table definition: line starts with "表X.Y"
                m = tab_def.match(text)
                if m:
                    existing_tables.add(f"{m.group(1)}.{m.group(2)}")

                # Equation definition: "(X.Y)" at line end
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

    # Second pass: find all REFERENCES and check against definitions
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text()
        page_num = page_idx + 1
        lines = text.split("\n")

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

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

            # Figure references (skip definition lines themselves)
            for m in fig_ref.finditer(line_stripped):
                # Skip if this line IS the definition (starts with 图X.Y)
                if fig_def.match(line_stripped):
                    continue
                ref_num = f"{m.group(1)}.{m.group(2)}"
                entry = _ref_entry(ref_num, f"图{ref_num}", page_num, line_stripped)
                if ref_num in existing_figures:
                    results["figures"]["valid"].append(entry)
                else:
                    results["figures"]["invalid"].append(entry)

            # Table references (skip definition lines)
            for m in tab_ref.finditer(line_stripped):
                if tab_def.match(line_stripped):
                    continue
                ref_num = f"{m.group(1)}.{m.group(2)}"
                entry = _ref_entry(ref_num, f"表{ref_num}", page_num, line_stripped)
                if ref_num in existing_tables:
                    results["tables"]["valid"].append(entry)
                else:
                    results["tables"]["invalid"].append(entry)

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
