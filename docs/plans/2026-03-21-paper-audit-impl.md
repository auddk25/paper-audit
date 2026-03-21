# Paper Audit Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Claude Code Skill (`/audit-paper`) that audits NEU master's theses for format compliance, content quality, and academic writing style.

**Architecture:** Python script (`scripts/format_checker.py`) extracts PDF layout data via PyMuPDF and checks format rules, outputting JSON. The Skill (`SKILL.md`) orchestrates: runs Python format check, then reads the thesis PDF chapter-by-chapter with Claude for content review and polishing suggestions, finally merges everything into a Markdown report.

**Tech Stack:** Python 3.10 (`.venv`), PyMuPDF 1.27, Claude Code Skills

---

### Task 1: Project scaffolding

**Files:**
- Create: `scripts/__init__.py` (empty)
- Create: `output/.gitkeep` (empty)

**Step 1: Create directory structure**

```bash
mkdir -p E:/code/paper-audit/scripts
mkdir -p E:/code/paper-audit/output
touch E:/code/paper-audit/scripts/__init__.py
touch E:/code/paper-audit/output/.gitkeep
```

**Step 2: Initialize git repo**

```bash
cd E:/code/paper-audit
git init
```

**Step 3: Create .gitignore**

Create `E:/code/paper-audit/.gitignore`:

```
.venv/
__pycache__/
*.pyc
output/*.md
```

**Step 4: Commit**

```bash
git add .gitignore scripts/__init__.py output/.gitkeep
git commit -m "chore: project scaffolding"
```

---

### Task 2: PDF structure extractor (`scripts/pdf_extractor.py`)

This module extracts structural info from a thesis PDF: TOC, chapter boundaries, page ranges. It is a prerequisite for both the format checker and the Skill.

**Files:**
- Create: `scripts/pdf_extractor.py`
- Create: `scripts/test_pdf_extractor.py`

**Step 1: Write the failing test**

Create `scripts/test_pdf_extractor.py`:

```python
"""Tests for pdf_extractor using the format spec sample thesis (pages 5-11)."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from pdf_extractor import extract_structure

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "..", "5-论文格式（硕士）.pdf")


def test_extract_structure_returns_dict():
    result = extract_structure(SAMPLE_PDF)
    assert isinstance(result, dict)
    assert "pages" in result
    assert "chapters" in result


def test_page_count():
    result = extract_structure(SAMPLE_PDF)
    assert result["pages"] == 11  # format spec PDF has 11 pages


def test_page_size():
    result = extract_structure(SAMPLE_PDF)
    assert result["page_size"]["width_mm"] == 210.0
    assert result["page_size"]["height_mm"] == 297.0


if __name__ == "__main__":
    test_extract_structure_returns_dict()
    test_page_count()
    test_page_size()
    print("All tests passed!")
```

**Step 2: Run test to verify it fails**

```bash
E:/code/paper-audit/.venv/Scripts/python.exe scripts/test_pdf_extractor.py
```

Expected: `ModuleNotFoundError: No module named 'pdf_extractor'`

**Step 3: Write the implementation**

Create `scripts/pdf_extractor.py`:

```python
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

    # Try to find chapters by detecting heading patterns in text
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(span["text"] for span in line["spans"]).strip()
                font_size = line["spans"][0]["size"] if line["spans"] else 0
                font_name = line["spans"][0]["font"] if line["spans"] else ""

                # Detect chapter headings: "第X章" with large font
                chapter_match = re.match(r"第\s*(\d+)\s*章\s*(.*)", text)
                if chapter_match and font_size >= 20:
                    result["chapters"].append({
                        "number": int(chapter_match.group(1)),
                        "title": chapter_match.group(2).strip(),
                        "page": page_idx + 1,  # 1-indexed
                        "font_size": round(font_size, 1),
                        "font_name": font_name,
                    })

                # Detect section headings: "X.X " with medium font
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

                # Detect subsection headings: "X.X.X " with medium font
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
```

**Step 4: Run tests to verify they pass**

```bash
E:/code/paper-audit/.venv/Scripts/python.exe scripts/test_pdf_extractor.py
```

Expected: `All tests passed!`

**Step 5: Commit**

```bash
git add scripts/pdf_extractor.py scripts/test_pdf_extractor.py
git commit -m "feat: add PDF structure extractor"
```

---

### Task 3: Format checker core (`scripts/format_checker.py`)

**Files:**
- Create: `scripts/format_checker.py`
- Create: `scripts/test_format_checker.py`

**Step 1: Write the failing test**

Create `scripts/test_format_checker.py`:

```python
"""Tests for format_checker."""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from format_checker import check_format

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "..", "5-论文格式（硕士）.pdf")


def test_check_format_returns_valid_structure():
    result = check_format(SAMPLE_PDF)
    assert isinstance(result, dict)
    assert "issues" in result
    assert "summary" in result
    assert isinstance(result["issues"], list)
    assert "total" in result["summary"]
    assert "errors" in result["summary"]
    assert "warnings" in result["summary"]


def test_issues_have_required_fields():
    result = check_format(SAMPLE_PDF)
    for issue in result["issues"]:
        assert "page" in issue
        assert "location" in issue
        assert "rule" in issue
        assert "expected" in issue
        assert "actual" in issue
        assert "severity" in issue
        assert issue["severity"] in ("error", "warning")


def test_output_is_json_serializable():
    result = check_format(SAMPLE_PDF)
    json_str = json.dumps(result, ensure_ascii=False, indent=2)
    assert len(json_str) > 0


if __name__ == "__main__":
    test_check_format_returns_valid_structure()
    test_issues_have_required_fields()
    test_output_is_json_serializable()
    print("All tests passed!")
```

**Step 2: Run test to verify it fails**

```bash
E:/code/paper-audit/.venv/Scripts/python.exe scripts/test_format_checker.py
```

Expected: `ModuleNotFoundError: No module named 'format_checker'`

**Step 3: Write the implementation**

Create `scripts/format_checker.py`:

```python
"""Format checker for NEU master's thesis PDF.

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
# Font sizes in pt (Chinese standard):
#   初号=42, 小初=36, 一号=26, 小一=24, 二号=22, 小二=18,
#   三号=16, 小三=15, 四号=14, 小四=12, 五号=10.5, 小五=9
RULES = {
    "page_size": {"width_mm": 210.0, "height_mm": 297.0, "tolerance_mm": 1.0},
    "body_font": {"name_contains": ["SimSun", "宋体", "Song"], "size_pt": 12.0, "tolerance_pt": 0.5},
    "chapter_heading": {"name_contains": ["SimHei", "黑体", "Hei"], "size_pt": 22.0, "tolerance_pt": 1.0},
    "section_heading": {"name_contains": ["SimHei", "黑体", "Hei"], "size_pt": 16.0, "tolerance_pt": 1.0},
    "subsection_heading": {"name_contains": ["SimHei", "黑体", "Hei"], "size_pt": 14.0, "tolerance_pt": 1.0},
    "header_font": {"name_contains": ["KaiTi", "楷体", "Kai"], "size_pt": 10.5, "tolerance_pt": 0.5},
    "header_left": "东北大学硕士学位论文",
    "caption_font_size": 10.5,  # 五号
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
    issues.extend(_check_figure_table_numbering(pdf_path, structure))
    issues.extend(_check_references(pdf_path, structure))
    issues.extend(_check_headers(pdf_path, structure))

    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = len(issues) - errors

    return {
        "issues": issues,
        "summary": {"total": len(issues), "errors": errors, "warnings": warnings},
    }


def _issue(page, location, rule, expected, actual, severity="warning"):
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


def _check_page_size(structure: dict) -> list[dict]:
    issues = []
    r = RULES["page_size"]
    ps = structure["page_size"]
    if abs(ps["width_mm"] - r["width_mm"]) > r["tolerance_mm"]:
        issues.append(_issue(1, "全文", "页面宽度", f'{r["width_mm"]}mm', f'{ps["width_mm"]}mm', "error"))
    if abs(ps["height_mm"] - r["height_mm"]) > r["tolerance_mm"]:
        issues.append(_issue(1, "全文", "页面高度", f'{r["height_mm"]}mm', f'{ps["height_mm"]}mm', "error"))
    return issues


def _check_body_text(pdf_path: str, structure: dict) -> list[dict]:
    """Check body text font and size on sampled pages."""
    issues = []
    r = RULES["body_font"]

    # Sample pages from the body (skip front matter, check every 5th page)
    start_page = 1
    if structure["chapters"]:
        start_page = structure["chapters"][0]["page"]

    checked_pages = set()
    for pg in range(start_page, structure["pages"] + 1, 5):
        if pg in checked_pages:
            continue
        checked_pages.add(pg)
        spans = extract_page_spans(pdf_path, pg)

        # Filter to body text: y > 70 (below header), y < 780 (above footer), size ~12
        body_spans = [s for s in spans if 70 < s["y_pos"] < 780]
        for span in body_spans:
            # Skip headings, captions, and very short text
            if span["size"] > r["size_pt"] + r["tolerance_pt"]:
                continue
            if len(span["text"].strip()) < 4:
                continue

            # Check font
            if not _font_matches(span["font"], r["name_contains"]):
                # Could be Times New Roman for English — that's allowed
                if not _font_matches(span["font"], ["Times", "TimesNewRoman"]):
                    issues.append(_issue(
                        pg, f'"{span["text"][:20]}..."',
                        "正文字体", "宋体(SimSun)", span["font"], "warning"
                    ))

            # Check size
            if abs(span["size"] - r["size_pt"]) > r["tolerance_pt"]:
                if span["size"] < r["size_pt"] - 2:  # Skip captions (smaller is OK)
                    continue
                issues.append(_issue(
                    pg, f'"{span["text"][:20]}..."',
                    "正文字号", f'小四号({r["size_pt"]}pt)', f'{span["size"]}pt', "warning"
                ))

    return issues


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


def _check_figure_table_numbering(pdf_path: str, structure: dict) -> list[dict]:
    """Check figure and table numbering continuity."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    fig_pattern = re.compile(r"图\s*(\d+)[.\s·](\d+)")
    tab_pattern = re.compile(r"表\s*(\d+)[.\s·](\d+)")
    eq_pattern = re.compile(r"式\s*[（(]\s*(\d+)[.\s·-](\d+)\s*[）)]")

    fig_nums = {}  # chapter -> list of fig numbers
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

    # Check continuity for each type
    for label, nums_dict in [("图", fig_nums), ("表", tab_nums), ("公式", eq_nums)]:
        for ch, entries in nums_dict.items():
            seen = sorted(set(n for n, _ in entries))
            expected = list(range(1, max(seen) + 1)) if seen else []
            missing = set(expected) - set(seen)
            for m in missing:
                issues.append(_issue(
                    entries[0][1], f"第{ch}章",
                    f"{label}编号连续性", f"{label}{ch}.{m} 应存在",
                    f"缺失{label}{ch}.{m}", "warning"
                ))

    return issues


def _check_references(pdf_path: str, structure: dict) -> list[dict]:
    """Check reference format: sequential [N] numbering."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    ref_pattern = re.compile(r"\[(\d+)\]")
    all_refs = []

    # Find reference section (look for "参考文献" heading)
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

    # Check sequential
    if all_refs:
        for i, expected in enumerate(range(1, max(all_refs) + 1)):
            if expected not in all_refs:
                issues.append(_issue(
                    ref_start + 1 if ref_start else 0, "参考文献",
                    "参考文献编号", f"[{expected}] 应存在", f"缺失 [{expected}]", "warning"
                ))

    doc.close()
    return issues


def _check_headers(pdf_path: str, structure: dict) -> list[dict]:
    """Check page headers: left side should be '东北大学硕士学位论文'."""
    issues = []
    import fitz
    doc = fitz.open(pdf_path)

    # Headers start from the abstract page, check body pages
    start_page = 1
    if structure["chapters"]:
        start_page = max(1, structure["chapters"][0]["page"] - 2)  # abstract is before ch1

    for page_idx in range(start_page, len(doc)):
        page = doc[page_idx]
        blocks = page.get_text("dict")["blocks"]

        # Header is typically in the top 60pt of the page
        header_spans = []
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                if line["bbox"][1] < 60:  # top of page
                    for span in line["spans"]:
                        if span["text"].strip():
                            header_spans.append(span)

        if not header_spans:
            continue

        # Check if left header contains the university name
        left_header = header_spans[0]["text"].strip() if header_spans else ""
        expected = RULES["header_left"]
        if left_header and expected not in left_header:
            # Could be a front-matter page, only flag for body pages
            if any(ch["page"] <= page_idx + 1 for ch in structure["chapters"]):
                issues.append(_issue(
                    page_idx + 1, "页眉左端",
                    "页眉内容", expected, left_header[:30], "warning"
                ))

    doc.close()
    return issues


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
```

**Step 4: Run tests to verify they pass**

```bash
E:/code/paper-audit/.venv/Scripts/python.exe scripts/test_format_checker.py
```

Expected: `All tests passed!`

**Step 5: Manual test with the sample PDF**

```bash
E:/code/paper-audit/.venv/Scripts/python.exe scripts/format_checker.py "E:/code/paper-audit/5-论文格式（硕士）.pdf"
```

Expected: JSON output with issues list. Review that the output makes sense.

**Step 6: Commit**

```bash
git add scripts/format_checker.py scripts/test_format_checker.py
git commit -m "feat: add format checker with NEU thesis rules"
```

---

### Task 4: Claude Code Skill definition (`SKILL.md`)

**Files:**
- Create: `.claude/skills/audit-paper/SKILL.md`

**Step 1: Create the skill directory**

```bash
mkdir -p E:/code/paper-audit/.claude/skills/audit-paper
```

**Step 2: Write the SKILL.md**

Create `.claude/skills/audit-paper/SKILL.md`:

````markdown
---
name: audit-paper
description: Audit a master's thesis PDF for format compliance (NEU standard), content quality, and academic writing style. Run with /audit-paper <path-to-thesis.pdf>
user_invocable: true
---

# 论文审计 Skill

审计东北大学硕士学位论文，检查格式规范、内容质量和学术写作风格。

## 输入

用户提供论文 PDF 路径作为参数。如果没有提供，提示用户输入。

## 参考文档（项目根目录）

- `5-论文格式（硕士）.pdf` — 东北大学硕士论文格式规范
- `学术写作规范.md` — 学术写作规范（内容审查+润色规则）
- `基于区块链预言机的安全高效电力数据共享平台构建方法_鲁宁.pdf` — 写作风格范例

## 执行流程

### Phase 1: 格式检查（Python 自动化）

1. 确认论文 PDF 路径存在
2. 运行格式检查脚本：
   ```bash
   E:/code/paper-audit/.venv/Scripts/python.exe E:/code/paper-audit/scripts/format_checker.py "<论文路径>"
   ```
3. 解析 JSON 输出，记录格式问题

### Phase 2: 结构提取

1. 运行结构提取获取章节列表：
   ```bash
   E:/code/paper-audit/.venv/Scripts/python.exe -u -c "
   import sys, io, json
   sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
   sys.path.insert(0, 'E:/code/paper-audit/scripts')
   from pdf_extractor import extract_structure
   print(json.dumps(extract_structure(r'<论文路径>'), ensure_ascii=False, indent=2))
   "
   ```
2. 记录章节列表和页码范围

### Phase 3: 内容审查 + 润色（Claude 逐章分析）

对每个章节执行以下步骤：

1. **读取章节内容**：使用 Read 工具读取论文 PDF 的对应页码范围（每次最多20页）
2. **读取写作规范**：首次分析时读取 `学术写作规范.md` 的自检清单（十一节）
3. **逐章分析**，每章输出：

**内容审查**（检查以下方面）：
- 逻辑连贯性：段落间是否有逻辑连接词衔接
- 论证充分性：论点是否有数据/引用支撑
- 引用规范：图表、公式是否在正文中被引用
- 章节衔接：与上一章的过渡是否自然

**润色建议**（对照写作规范）：
- 去人化：检测"我/我们/笔者"
- 禁用词：对照7.1节替换表
- 句式多样性：是否有连续相同句式开头
- 段落粒度：每段是否3-8句
- 量化表达：提升幅度与表达策略是否匹配

4. **上下文传递**：分析第N章时，简述前N-1章的核心内容（关键论点、术语、创新点），确保跨章一致性检查

### Phase 4: 全局检查

在所有章节分析完成后：

1. **镜像对应检查**：对比摘要、绪论研究内容、总结章的条目，检查是否一一对应
2. **术语一致性**：汇总全文术语，检查是否存在同一概念不同表述
3. **符号一致性**：检查数学符号是否跨章一致

### Phase 5: 生成报告

将所有结果合并为 Markdown 报告，保存到 `output/` 目录：

报告结构：
```
# 论文审计报告
**论文**: [标题]  **审计时间**: [时间]

## 一、格式检查结果
[Python 格式检查的 issues 转为表格]

## 二、内容审查（按章节）
[每章的逻辑/论证/引用/衔接分析]

## 三、润色建议（按章节）
[每章的去人化/禁用词/句式/段落/量化问题，带页码和原文]

## 四、全局检查
[镜像对应表 + 术语一致性 + 符号一致性]

## 五、综合评估
[格式/内容/写作三维评分 + 重点改进建议]
```

保存路径：`E:/code/paper-audit/output/<论文文件名>-audit-report.md`

## 注意事项

- 论文限110页以内，每章不超过20页
- 读取 PDF 时使用 Read 工具的 pages 参数分批读取（每次最多20页）
- 格式检查由 Python 脚本完成，不要重复检查格式问题
- 内容审查和润色是 Claude 的核心任务，要深入分析，不要泛泛而谈
- 润色建议要给出具体的原文和修改建议，精确到页码
````

**Step 3: Commit**

```bash
git add .claude/skills/audit-paper/SKILL.md
git commit -m "feat: add audit-paper Claude Code skill"
```

---

### Task 5: Update project permissions for Bash

**Files:**
- Modify: `.claude/settings.local.json`

**Step 1: Update settings to allow the Python script execution**

Update `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "mcp__plugin_episodic-memory_episodic-memory__search",
      "Bash(E:/code/paper-audit/.venv/Scripts/python.exe*)"
    ]
  }
}
```

**Step 2: Commit**

```bash
git add .claude/settings.local.json
git commit -m "chore: allow Python venv execution in permissions"
```

---

### Task 6: End-to-end test with the format spec PDF

**Step 1: Run format checker on the sample thesis (format spec PDF pages 5-11 are a sample thesis)**

```bash
E:/code/paper-audit/.venv/Scripts/python.exe scripts/format_checker.py "E:/code/paper-audit/5-论文格式（硕士）.pdf"
```

**Step 2: Review the JSON output**

Verify:
- Page size check passes (A4)
- Chapter headings are detected (if any in the sample)
- No crashes or encoding errors

**Step 3: Run structure extractor**

```bash
E:/code/paper-audit/.venv/Scripts/python.exe -u -c "
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'E:/code/paper-audit/scripts')
from pdf_extractor import extract_structure
print(json.dumps(extract_structure('E:/code/paper-audit/5-论文格式（硕士）.pdf'), ensure_ascii=False, indent=2))
"
```

**Step 4: Test the skill by invoking `/audit-paper` on the format spec PDF**

This is a manual test — invoke the skill in Claude Code:

```
/audit-paper E:/code/paper-audit/5-论文格式（硕士）.pdf
```

Verify the skill:
1. Runs the Python format checker
2. Extracts structure
3. Reads pages and analyzes content
4. Generates a report in `output/`

**Step 5: Fix any issues found during testing, then commit**

```bash
git add -A
git commit -m "test: verify end-to-end with format spec PDF"
```

---

### Task 7: Create progress file and finalize

**Files:**
- Create: `claude-progress.txt`

**Step 1: Write progress file**

Create `claude-progress.txt`:

```
# Paper Audit Tool - Progress

## Status: MVP Complete

## Completed
- [x] Project scaffolding (git, venv, directories)
- [x] PDF structure extractor (scripts/pdf_extractor.py)
- [x] Format checker (scripts/format_checker.py) — NEU thesis rules
- [x] Claude Code Skill (SKILL.md) — /audit-paper command
- [x] Academic writing standard (学术写作规范.md) — merged final version
- [x] End-to-end test with format spec PDF

## Architecture
- Python scripts: format checking (PyMuPDF)
- Claude Code Skill: content review + polishing (Claude itself)
- Output: Markdown audit report

## Key Files
- .claude/skills/audit-paper/SKILL.md — skill definition
- scripts/format_checker.py — format checking
- scripts/pdf_extractor.py — PDF structure extraction
- 学术写作规范.md — writing style rules
- 5-论文格式（硕士）.pdf — NEU format specification

## Next Steps
- Test with a real thesis PDF
- Add academic style guide document for polishing reference
- Iterate on format checker rules based on real thesis feedback
```

**Step 2: Commit**

```bash
git add claude-progress.txt
git commit -m "docs: add progress tracking file"
```
