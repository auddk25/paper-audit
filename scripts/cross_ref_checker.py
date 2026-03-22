"""Cross-reference checker for master's thesis PDF.

Checks:
  1. Section references: "第X.Y节" / "X.Y节" → does heading exist?
  2. Figure references: "图X.Y" → does figure exist?
  3. Table references: "表X.Y" → does table exist?
  4. Equation references: "式(X.Y)" / "式（X.Y）" → does equation exist?

Outputs JSON with:
  - valid: references that point to existing targets
  - invalid: references that point to non-existent targets
  - context: each reference with surrounding text for LLM review

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

    structure = extract_structure(pdf_path)
    doc = fitz.open(pdf_path)

    # Build sets of existing targets
    existing_sections = _build_section_set(structure)
    existing_figures = set()
    existing_tables = set()
    existing_equations = set()

    fig_def = re.compile(r"图\s*(\d+)[.\s·](\d+)")
    tab_def = re.compile(r"表\s*(\d+)[.\s·](\d+)")
    eq_def = re.compile(r"[式公]\s*[（(]\s*(\d+)\s*[-.\s·]\s*(\d+)\s*[）)]")

    # First pass: collect all defined figures/tables/equations
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text()
        for m in fig_def.finditer(text):
            existing_figures.add(f"{m.group(1)}.{m.group(2)}")
        for m in tab_def.finditer(text):
            existing_tables.add(f"{m.group(1)}.{m.group(2)}")
        for m in eq_def.finditer(text):
            existing_equations.add(f"{m.group(1)}.{m.group(2)}")

    # Reference patterns (citations in body text)
    sec_ref = re.compile(
        r"(?:第\s*(\d+(?:\.\d+)+)\s*节)|"       # 第X.Y节
        r"(?:(\d+(?:\.\d+)+)\s*节)|"              # X.Y节
        r"(?:第\s*(\d+(?:\.\d+)+)\s*小节)"        # 第X.Y小节
    )
    fig_ref = re.compile(r"图\s*(\d+)[.\s·](\d+)")
    tab_ref = re.compile(r"表\s*(\d+)[.\s·](\d+)")
    eq_ref = re.compile(r"式\s*[（(]\s*(\d+)\s*[-.\s·]\s*(\d+)\s*[）)]")

    results = {
        "sections": {"valid": [], "invalid": []},
        "figures": {"valid": [], "invalid": []},
        "tables": {"valid": [], "invalid": []},
        "equations": {"valid": [], "invalid": []},
    }

    # Second pass: find all references and check
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

            # Figure references
            for m in fig_ref.finditer(line_stripped):
                ref_num = f"{m.group(1)}.{m.group(2)}"
                entry = _ref_entry(ref_num, f"图{ref_num}", page_num, line_stripped)
                if ref_num in existing_figures:
                    results["figures"]["valid"].append(entry)
                else:
                    results["figures"]["invalid"].append(entry)

            # Table references
            for m in tab_ref.finditer(line_stripped):
                ref_num = f"{m.group(1)}.{m.group(2)}"
                entry = _ref_entry(ref_num, f"表{ref_num}", page_num, line_stripped)
                if ref_num in existing_tables:
                    results["tables"]["valid"].append(entry)
                else:
                    results["tables"]["invalid"].append(entry)

            # Equation references
            for m in eq_ref.finditer(line_stripped):
                ref_num = f"{m.group(1)}.{m.group(2)}"
                entry = _ref_entry(ref_num, f"式({ref_num})", page_num, line_stripped)
                if ref_num in existing_equations:
                    results["equations"]["valid"].append(entry)
                else:
                    results["equations"]["invalid"].append(entry)

    doc.close()

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
    for h in structure["headings"]:
        sections[h["number"]] = h["title"]
    # Also add chapter-level
    for ch in structure["chapters"]:
        sections[str(ch["number"])] = ch["title"]
    return sections


def main():
    if len(sys.argv) < 2:
        print("Usage: python cross_ref_checker.py <thesis.pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = check_cross_refs(pdf_path)

    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
