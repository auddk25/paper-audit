# Project Context

## Purpose
学位论文（硕士）审计工具 — 自动检查格式规范、内容质量和学术写作风格，输出 Markdown 审计报告。

## Tech Stack
- **Language:** Python 3.10+
- **Word extraction:** python-docx（字体/对齐/间距/页眉等结构化数据）
- **PDF extraction:** PyMuPDF (fitz)（版芯/题注位置等空间坐标）
- **LLM integration:** Claude Code Skill（内容审查 + 学术润色由 Claude 本体执行）
- **Output:** Markdown 报告 → `output/`

## Build / Test / Lint
```bash
# 安装依赖
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# 运行 Word 格式检查（34项，推荐）
python scripts/word_checker.py <thesis.docx>

# 运行 PDF 空间检查（9项）
python scripts/format_checker.py <thesis.pdf>

# 完整审计（Claude Code Skill）
# 在 Claude Code 中运行 /audit-paper <thesis.pdf>
```

## Architecture
```
论文文件 (Word + PDF)
  │
  ├─ scripts/word_checker.py    → 34项 Word 格式检查 → JSON
  ├─ scripts/format_checker.py  → 9项 PDF 空间检查 → JSON
  ├─ scripts/cross_ref_checker.py → 交叉引用验证 → JSON
  ├─ scripts/pdf_extractor.py   → 章节边界/页码范围
  │
  └─ .claude/skills/audit-paper/SKILL.md
       ├─ Stage 1:   Python 自动化预检（并行）
       ├─ Stage 1.5: 边界文本审查（LLM sub-agent）
       ├─ Stage 2:   通读建档
       ├─ Stage 3:   逐章深度审查（清单驱动 sub-agent）
       ├─ Stage 4:   全局检查
       └─ Stage 5:   汇总评分 → output/
```

## Format Spec
> **用户需自行准备格式规范文件。**
> 在 `scripts/word_checker.py` 的 `RULES` 字典中配置学校的具体要求。

默认配置示例：
- 纸张 A4，版芯 160×247mm，正文小四号宋体，英文 Times New Roman
- 标题四级：二号黑体 → 三号黑体 → 四号黑体 → 小四号黑体
- 图表按章编号，参考文献 GB/T 7714

## Writing Style
> **用户需自行准备 `学术写作规范.md` 文件。**
> 该文件是 LLM 内容审查和润色的唯一依据。

建议包含：写作约束（去人化/禁用词/句式多样性等）、自检清单、句式速查表。

## Constraints
- 论文 PDF/DOC/DOCX 文件绝不上传到 git
- 实验数据（CSV 等）绝不上传到 git
- 格式检查由 Python 精确执行（字号/字体/边距等数值检查）
- 内容审查和润色由 Claude 执行（利用长文本理解 + 多模态能力）
- 论文类型：学位论文，110页以内，每章不超过20页
