# Project Context

## Purpose
学位论文（硕士）审计工具 — 自动检查格式规范、内容质量和学术写作风格，输出 Markdown 审计报告。

## Tech Stack
- **Language:** Python 3.10+
- **PDF extraction:** PyMuPDF (fitz)
- **LLM integration:** Claude Code Skill（内容审查 + 学术润色由 Claude 本体执行）
- **Output:** Markdown 报告 → `output/`

## Build / Test / Lint
```bash
# 安装依赖
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# 运行格式检查（CLI）
python scripts/format_checker.py <thesis.pdf>

# 完整审计（Claude Code Skill）
# 在 Claude Code 中运行 /audit-paper <thesis.pdf>
```

## Architecture
```
PDF 论文
  │
  ├─ scripts/pdf_extractor.py  → 提取目录/章节边界/页码范围
  ├─ scripts/format_checker.py → 18项格式自动检查 → JSON
  │
  └─ .claude/skills/audit-paper/SKILL.md
       ├─ 调用 Python 脚本获取格式问题
       ├─ 逐章阅读 PDF 做内容审查（Claude 多模态）
       ├─ 基于《学术写作规范.md》做润色建议
       └─ 输出综合审计报告 → output/
```

## Format Spec
- 基于东北大学硕士学位论文排版格式（`5-论文格式（硕士）.pdf`）
- 纸张 A4，版芯 160×247mm，正文小四号宋体，英文 Times New Roman
- 标题四级：二号黑体 → 三号黑体 → 四号黑体 → 小四号黑体
- 图表按章编号，参考文献 GB/T 7714

## Writing Style
- 基于《学术写作规范.md》（合并自通信学报论文风格 + Powsharing 风格修订版）
- 11节写作约束 + 自检清单 + 句式速查表

## Constraints
- 论文 PDF/DOC/DOCX 文件绝不上传到 git（`.gitignore` 已配置）
- 格式检查由 Python 精确执行（字号/字体/边距等数值检查）
- 内容审查和润色由 Claude 执行（利用长文本理解 + 多模态能力）
- 论文类型：学位论文，110页以内，每章不超过20页
