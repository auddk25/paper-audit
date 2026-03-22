# Paper Audit - 论文审计工具

## Project Context
详见 `docs/project_context.md`

## Quick Reference
- **格式检查:** `python scripts/format_checker.py <thesis.pdf>` → JSON stdout
- **完整审计:** Claude Code 中运行 `/audit-paper <thesis.pdf>`
- **写作规范:** `学术写作规范.md`（本地文件，不入 git）

## Key Conventions
- 论文文件（PDF/DOC/DOCX）绝不提交到 git
- 格式检查 = Python 精确数值检查（PyMuPDF）
- 内容审查 + 润色 = Claude 多模态分析
- 审计报告输出到 `output/` 目录（Markdown 格式）
