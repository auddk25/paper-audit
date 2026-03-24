# Paper Audit - 论文审计工具

东北大学硕士学位论文审计工具，作为 Claude Code Skill 运行。自动检查格式规范、内容质量和学术写作风格。

## 功能概览

| 审计线 | 执行者 | 检查内容 |
|--------|--------|---------|
| Word 格式检查 | Python + python-docx（27项） | 字体字号、标题层级/对齐/间距、页眉页脚、图表编号+中英文标题、公式、参考文献、空行 |
| PDF 空间检查 | Python + PyMuPDF（5项） | 页面尺寸、版芯、图表题注位置、页底空白 |
| 交叉引用检查 | Python + PyMuPDF | 节/图/表/公式引用是否指向存在的目标 |
| 边界文本审查 | Claude LLM | 标题/图题/表题/算法名的错别字、编辑残留 |
| 内容审查 | Claude LLM（逐章） | 逻辑连贯性、论证充分性、章节衔接、镜像对应 |
| 学术润色 | Claude LLM | 去人化、禁用词、句式多样性、段落粒度 |
| 实验数据验算 | Claude + Python | 读取原始CSV数据，独立计算后与论文声明值交叉验证 |

### Word 格式检查项（27项，精确结构化数据）

| 类别 | 检查项 |
|------|--------|
| 字体 | 正文宋体12pt、英文Times New Roman、图题/表题五号宋体 |
| 标题 | 四级标题字号/字体/对齐/间距、摘要等特殊标题按一级排版、章标题≤20字 |
| 页眉 | 楷体10.5pt、左端"东北大学硕士学位论文"、右端章号章题、起始页 |
| 页脚 | 页码12pt居中、·N·或-N-修饰 |
| 图表 | 编号按章连续、中英文双语标题（顺序+编号匹配）、题号间距 |
| 公式 | 编号按章连续、居中排版、式号右对齐、引用风格统一（式vs公式） |
| 参考文献 | [N]顺序编号、GB/T 7714格式标识（[M][J][D]） |
| 段落 | 末行≥5字、连续空行检测、编号分隔符半角点 |
| 目录 | 标题一致性、编号连续性 |

### PDF 空间检查项（5项，需要渲染坐标）

| # | 检查项 |
|---|--------|
| 1 | 页面尺寸 A4（210×297mm） |
| 2 | 版芯尺寸 160×247mm（按章抽样） |
| 3 | 图题在图下方 + 表题在表上方（支持矢量图检测） |
| 4 | 页底空白不超过2行 |
| 5 | 图内标注字号不大于图题字号 |

## 使用方式

在 Claude Code 中运行完整审计：

```
/audit-paper input/pdf/论文.pdf
```

输出按章节拆分的 Markdown 审计报告到 `output/` 目录（00-前置部分 ~ 09-全局检查）。

### 仅运行格式检查（CLI）

```bash
# Word 格式检查（27项，推荐）
python scripts/word_checker.py input/word/论文.docx

# PDF 空间检查（5项）
python scripts/format_checker.py input/pdf/论文.pdf

# 交叉引用检查
python scripts/cross_ref_checker.py input/pdf/论文.pdf
```

所有脚本输出 JSON 到 stdout。

## 五阶段审计流水线

```
Stage 1:   自动化预检（4个Python脚本并行）
Stage 1.5: 边界文本审查（LLM sub-agent，审查标题/图题/表题错别字）
Stage 2:   通读建档（LLM 略读全文，生成上下文档案）
Stage 3:   逐章深度审查（混合串并行，实验章节强制读原始数据验算）
Stage 4:   全局检查（交叉引用合理性 + 镜像对应 + 术语一致性）
Stage 5:   汇总评分（格式/内容/写作三维评分 + Top 10 改进建议）
```

## 项目结构

```
paper-audit/
├── .claude/skills/audit-paper/
│   └── SKILL.md                # Claude Code Skill 定义（五阶段流水线）
├── scripts/
│   ├── word_checker.py         # ★ Word 格式检查（27项）→ JSON
│   ├── format_checker.py       # PDF 空间检查（5项）→ JSON
│   ├── cross_ref_checker.py    # 交叉引用检查 → JSON
│   └── pdf_extractor.py        # PDF 结构提取（章节边界、页码范围）
├── input/                      # ← 用户放论文和数据的地方
│   ├── pdf/                    # 论文 PDF
│   ├── word/                   # 论文 Word .docx
│   └── data/                   # 实验原始数据（按章节）
│       ├── ch3/                # 第3章实验数据（CSV/Excel/JSON）
│       ├── ch4/                # 第4章实验数据
│       └── ch5/                # 第5章实验数据
├── output/                     # 审计报告输出（按章节拆分）
├── ref/                        # 原始参考文件（不入git）
├── 学术写作规范.md               # ★ LLM 唯一权威文档
├── docs/                       # 项目文档
├── requirements.txt
└── CLAUDE.md
```

### 使用前准备

1. 论文 PDF 放入 `input/pdf/`
2. 论文 Word (.docx) 放入 `input/word/`
3. 实验原始数据按章节放入 `input/data/ch3/`、`ch4/`、`ch5/`

> **铁律**：审计实验章节时，Claude 强制先读原始数据，用 Python 独立计算后与论文数据交叉验证。LLM 不做计算。

## 技术栈

- **Python 3.10+** — 格式检查脚本
- **python-docx** — Word 结构化数据读取（字体/对齐/间距/页眉/页脚）
- **PyMuPDF (fitz)** — PDF 空间坐标分析（版芯/题注位置/页底空白）
- **Claude Code** — Skill 宿主，负责内容审查、润色、数据验算和报告生成

## 快速开始

```bash
git clone https://github.com/auddk25/paper-audit.git
cd paper-audit
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

## 设计决策

### 为什么用 Word + PDF 双源？

| 数据类型 | Word 准确 | PDF 准确 | 选择 |
|---------|-----------|----------|------|
| 字体名 | ✅ `run.font.name = "SimSun"` | ❌ `CIDFont+F1`（编码后） | **Word** |
| 对齐方式 | ✅ `para.alignment = CENTER` | ⚠️ 靠x坐标猜 | **Word** |
| 间距行距 | ✅ `paragraph_format.line_spacing` | ⚠️ 靠y坐标差算 | **Word** |
| 页眉页脚 | ✅ `section.header` 直接读 | ⚠️ 靠y坐标区域猜 | **Word** |
| 版芯尺寸 | ❌ 只有margin设置 | ✅ 实际渲染bbox | **PDF** |
| 图题位置 | ❌ 无空间信息 | ✅ y坐标比较 | **PDF** |

纯 PDF 方案产生 1833/2310 个字体误报。双源架构将误报降至 0。

## License

MIT
