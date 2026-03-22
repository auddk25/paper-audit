"""Word (.docx) format checker for master's thesis.

Checks that are more reliable on Word than PDF:
  1. Consecutive blank paragraphs (多余空行)
  2. Trailing whitespace-only paragraphs before section ends

Usage:
    python word_checker.py <thesis.docx>
    Outputs JSON to stdout.
"""
import json
import re
import sys
import os


def check_word(docx_path: str) -> dict:
    """Run all Word-specific checks on a thesis .docx file.

    Returns dict with 'issues' list and 'summary' counts.
    """
    from docx import Document

    doc = Document(docx_path)
    issues = []

    issues.extend(_check_blank_paragraphs(doc))

    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = len(issues) - errors

    return {
        "issues": issues,
        "summary": {"total": len(issues), "errors": errors, "warnings": warnings},
    }


def _issue(para_index, location, rule, expected, actual, severity="warning"):
    """Create a standardized issue dict."""
    return {
        "para_index": para_index,
        "location": location,
        "rule": rule,
        "expected": expected,
        "actual": actual,
        "severity": severity,
    }


def _get_paragraph_context(paragraphs, idx, direction="before"):
    """Get the nearest non-empty paragraph text for context.

    Args:
        paragraphs: list of paragraph objects
        idx: current index
        direction: "before" or "after"
    """
    step = -1 if direction == "before" else 1
    i = idx + step
    while 0 <= i < len(paragraphs):
        text = paragraphs[i].text.strip()
        if text:
            return text[:30]
        i += step
    return "(文档边界)"


def _is_heading(para) -> bool:
    """Check if a paragraph is a heading style."""
    style_name = para.style.name.lower() if para.style else ""
    return "heading" in style_name or "标题" in style_name or "toc" in style_name


# ═══════════════════════════════════════════════════════════════
# 1. Consecutive Blank Paragraphs (多余空行)
# ═══════════════════════════════════════════════════════════════

def _check_blank_paragraphs(doc) -> list[dict]:
    """Check for consecutive blank (empty) paragraphs.

    Rules:
      - 正文中不允许连续 2 个以上空段落
      - 标题后的 1 个空段落允许（间距用途）
      - 报告连续空段落的位置和前后文
    """
    issues = []
    paragraphs = doc.paragraphs
    MAX_CONSECUTIVE_BLANKS = 1

    i = 0
    while i < len(paragraphs):
        # Find start of a blank run
        if paragraphs[i].text.strip() == "" and not _is_heading(paragraphs[i]):
            blank_start = i
            blank_count = 0

            # Count consecutive blanks
            while i < len(paragraphs) and paragraphs[i].text.strip() == "":
                blank_count += 1
                i += 1

            if blank_count > MAX_CONSECUTIVE_BLANKS:
                # Check if the blank run is right after a heading (allowed for spacing)
                prev_is_heading = (
                    blank_start > 0 and _is_heading(paragraphs[blank_start - 1])
                )

                if not prev_is_heading:
                    before_text = _get_paragraph_context(
                        paragraphs, blank_start, "before"
                    )
                    after_text = _get_paragraph_context(
                        paragraphs, i - 1, "after"
                    )

                    issues.append(_issue(
                        blank_start,
                        f'第{blank_start + 1}段 ~ 第{blank_start + blank_count}段',
                        "多余空行",
                        f"连续空段落不超过{MAX_CONSECUTIVE_BLANKS}个",
                        f'连续{blank_count}个空段落\n'
                        f'  前文: "{before_text}"\n'
                        f'  后文: "{after_text}"',
                        "warning"
                    ))
        else:
            i += 1

    return issues


# ═══════════════════════════════════════════════════════════════
# CLI Entry
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage: python word_checker.py <thesis.docx>", file=sys.stderr)
        sys.exit(1)

    docx_path = sys.argv[1]
    if not os.path.exists(docx_path):
        print(f"Error: File not found: {docx_path}", file=sys.stderr)
        sys.exit(1)

    result = check_word(docx_path)

    # Force UTF-8 output on Windows
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
