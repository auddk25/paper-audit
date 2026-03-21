# Paper Audit - 论文审计工具

学位论文审计工具，作为 Claude Code Skill 运行。自动检查格式规范、内容质量和学术写作风格。

## 功能

| 审计线 | 执行者 | 检查内容 |
|--------|--------|---------|
| 格式检查 | Python + PyMuPDF | 页面尺寸、字号字体、标题层级、图表编号连续性、参考文献格式、页眉页码 |
| 内容审查 | Claude Code | 逻辑连贯性、论证充分性、引用规范、章节衔接、摘要-绪论-总结镜像对应 |
| 学术润色 | Claude Code | 去人化、禁用词替换、句式多样性、量化表达分级、段落粒度 |

## 使用方式

在 Claude Code 中运行：

```
/audit-paper 论文.pdf
```

输出 Markdown 审计报告到 `output/` 目录。

## 项目结构

```
paper-audit/
├── .claude/skills/audit-paper/
│   └── SKILL.md                # Claude Code Skill 定义
├── scripts/
│   ├── pdf_extractor.py        # PDF 结构提取（章节边界、页码范围）
│   └── format_checker.py       # 格式规范自动检查 → JSON
├── examples/
│   └── sample_spec.yaml        # 格式规范示例（YAML）
├── docs/
│   └── plans/                  # 设计文档
├── output/                     # 审计报告输出
├── requirements.txt
└── README.md
```

> 用户需自行准备：论文 PDF、学校格式规范文件、写作风格参考文档，放在项目根目录即可。

## 技术栈

- **Python 3.10+** — 格式检查脚本
- **PyMuPDF** — PDF 布局数据提取（字号、字体、坐标）
- **Claude Code** — Skill 宿主，负责内容审查和润色

## 快速开始

```bash
git clone https://github.com/auddk25/paper-audit.git
cd paper-audit
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

## 配置格式规范

复制 `examples/sample_spec.yaml` 到项目根目录，按学校要求修改参数：

```bash
cp examples/sample_spec.yaml format_spec.yaml
# 编辑 format_spec.yaml 中的字号、页边距等
```
