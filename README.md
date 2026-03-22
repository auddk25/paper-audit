# Paper Audit - 论文审计工具

学位论文审计工具，作为 Claude Code Skill 运行。自动检查格式规范、内容质量和学术写作风格。

## 功能

| 审计线 | 执行者 | 检查内容 |
|--------|--------|---------|
| 格式检查 | Python + PyMuPDF | 页面尺寸、版芯、字号字体、标题层级/对齐/间距、图表编号、参考文献、页眉页码、段末字数、页底空白 |
| 内容审查 | Claude Code | 逻辑连贯性、论证充分性、引用规范、章节衔接、摘要-绪论-总结镜像对应 |
| 学术润色 | Claude Code | 去人化、禁用词替换、句式多样性、量化表达分级、段落粒度 |

### 格式检查项（18 项）

| # | 检查项 | 严重度 |
|---|--------|--------|
| 1 | 页面尺寸 A4（210×297mm） | error |
| 2 | 版芯尺寸（160×247mm） | warning |
| 3 | 每页行数（30~35）& 每行字数（35~38） | warning |
| 4 | 正文字体/字号（小四宋体 12pt） | warning |
| 5 | 英文字体（Times New Roman） | warning |
| 6 | 章标题字体/字号（二号黑体 22pt） | error |
| 7 | 节/款标题字体/字号（三号/四号黑体） | warning |
| 8 | 章标题居中对齐 | warning |
| 9 | 节/款标题居左对齐 | warning |
| 10 | 标题间距（章占3行、节占2行） | warning |
| 11 | 图/表/公式编号连续性（按章编号） | warning |
| 12 | 图题（图下方 五号宋体）& 表题（表上方 五号宋体） | warning |
| 13 | 参考文献编号连续性 + GB/T 7714 格式 | warning |
| 14 | 页眉（左端"东北大学硕士学位论文"，右端"第X章 章标题"，楷体五号） | warning |
| 15 | 页码存在性 | warning |
| 16 | 段落末行不少于5个字 | warning |
| 17 | 页底空白不超过2行 | warning |
| 18 | 章标题长度不超过20个字 | warning |

## 使用方式

在 Claude Code 中运行：

```
/audit-paper 论文.pdf
```

输出 Markdown 审计报告到 `output/` 目录。

### 仅运行格式检查（CLI）

```bash
python scripts/format_checker.py 论文.pdf
# 输出 JSON 到 stdout
```

## 项目结构

```
paper-audit/
├── .claude/skills/audit-paper/
│   └── SKILL.md                # Claude Code Skill 定义
├── scripts/
│   ├── pdf_extractor.py        # PDF 结构提取（章节边界、页码范围）
│   ├── format_checker.py       # PDF 格式规范自动检查（18项）→ JSON
│   └── word_checker.py         # Word 格式检查（空行检测）→ JSON
├── input/                      # ← 用户放论文和数据的地方
│   ├── pdf/                    # 论文 PDF（格式检查用）
│   ├── word/                   # 论文 Word .docx（空行检查用）
│   └── data/                   # 实验原始数据（计算验证用）
│       ├── ch3/                # 第3章实验数据
│       ├── ch4/                # 第4章实验数据
│       └── ch5/                # 第5章实验数据
├── ref/                        # 原始参考文件（不入 git，仅更新规范时读取）
│   ├── 5-论文格式（硕士）.pdf
│   └── 基于区块链…鲁宁.pdf     # 风格参考论文
├── 学术写作规范.md               # ★ 唯一权威文档（写作风格 + 排版格式）
├── docs/
│   ├── project_context.md      # 项目上下文
│   ├── api.md                  # 脚本 API 参考
│   └── plans/                  # 设计文档
├── output/                     # 审计报告 + 验算脚本输出
├── requirements.txt
├── CLAUDE.md                   # Claude Code 项目指引
└── README.md
```

### 文档架构

```
学术写作规范.md（唯一权威文档，LLM 默认只读这一个）
  ├── 写作风格规范（11节 + 自检清单 + 句式速查表）
  └── 排版格式规范（附录C：页面/字体/标题/目录/图表/页眉/参考文献）

ref/（原始参考文件，仅在用户要求"更新规范"时才去读取）
  ├── 东北大学格式规范 PDF
  └── 风格参考论文 PDF
```

### 使用前准备

1. 论文 PDF 放入 `input/pdf/`
2. 论文 Word (.docx) 放入 `input/word/`
3. 实验原始数据按章节放入 `input/data/ch3/`、`ch4/`、`ch5/`（支持 CSV/Excel/JSON/TXT）

> 审计实验章节时，Claude 会强制读取原始数据，用 Python 独立计算后与论文数据交叉验证。

## 技术栈

- **Python 3.10+** — 格式检查脚本
- **PyMuPDF (fitz)** — PDF 布局数据提取（字号、字体、坐标、bbox）
- **python-docx** — Word 文档空行检测
- **Claude Code** — Skill 宿主，负责内容审查、润色和实验数据验算

## 快速开始

```bash
git clone https://github.com/auddk25/paper-audit.git
cd paper-audit
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

## 配置格式规范

当前硬编码为东北大学硕士学位论文格式。如需适配其他学校：

1. 修改 `scripts/format_checker.py` 中的 `RULES` 字典
2. 或复制 `examples/sample_spec.yaml` 自定义参数（未来支持）

## License

MIT
