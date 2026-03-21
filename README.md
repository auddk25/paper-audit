# Paper Audit - 论文审计工具

东北大学硕士学位论文审计工具，作为 Claude Code Skill 运行。自动检查格式规范、内容质量和学术写作风格。

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
├── docs/
│   ├── plans/                  # 设计文档
│   └── archive/                # 归档旧版文件
├── output/                     # 审计报告输出
├── 5-论文格式（硕士）.pdf        # 东北大学格式规范
├── 学术写作规范.md               # 写作规范（合并最终版）
└── 基于区块链预言机...pdf        # 写作风格范例
```

## 技术栈

- **Python 3.10+** — 格式检查脚本
- **PyMuPDF** — PDF 布局数据提取（字号、字体、坐标）
- **Claude Code** — Skill 宿主，负责内容审查和润色

## 环境搭建

```bash
python -m venv .venv
.venv/Scripts/pip install PyMuPDF
```

## 格式规范

基于东北大学硕士学位论文排版打印格式：

- 纸张 A4（210×297mm），版芯 160×247mm
- 正文小4号宋体（12pt），外文 Times New Roman
- 标题四级：二号黑体（章）→ 三号黑体（节）→ 四号黑体（款）→ 小四号黑体（项）
- 图表按章编号（图2.1、表2.1），参考文献顺序编号

## 写作规范

基于通信学报论文《基于区块链预言机的安全高效电力数据共享平台构建方法》风格提取，包含：

- 11节写作约束（铁律、章节结构、词汇表达、量化分级等）
- 自检清单（全局/章节/实验/表达四维度）
- 句式速查表
