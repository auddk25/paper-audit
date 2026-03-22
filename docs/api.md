# API Reference

## scripts/pdf_extractor.py

PDF 结构提取模块，基于 PyMuPDF。

### `extract_structure(pdf_path: str) -> dict`

提取论文整体结构。

**参数：**
- `pdf_path` — PDF 文件路径

**返回：**
```python
{
    "pages": int,              # 总页数
    "page_size": {
        "width_pt": float,
        "height_pt": float,
        "width_mm": float,     # 宽度（毫米）
        "height_mm": float,    # 高度（毫米）
    },
    "chapters": [              # 章列表
        {
            "number": int,     # 章号（1, 2, 3...）
            "title": str,      # 章标题
            "page": int,       # 起始页码（1-indexed）
            "font_name": str,  # 标题字体名
            "font_size": float # 标题字号（pt）
        }
    ],
    "headings": [              # 节/款/项标题列表
        {
            "level": int,      # 层级（2=节, 3=款, 4=项）
            "number": str,     # 编号（如 "2.1", "3.2.1"）
            "title": str,
            "page": int,
            "font_name": str,
            "font_size": float
        }
    ]
}
```

---

### `extract_page_text(pdf_path: str, page_num: int) -> str`

提取单页纯文本。

**参数：**
- `pdf_path` — PDF 文件路径
- `page_num` — 页码（1-indexed）

**返回：** 页面纯文本字符串

---

### `extract_page_spans(pdf_path: str, page_num: int) -> list[dict]`

提取单页所有文本 span 及字体元数据。

**参数：**
- `pdf_path` — PDF 文件路径
- `page_num` — 页码（1-indexed）

**返回：**
```python
[
    {
        "text": str,        # 文本内容
        "font": str,        # 字体名（如 "SimSun", "TimesNewRomanPSMT"）
        "size": float,      # 字号（pt）
        "bbox": [x0, y0, x1, y1],  # 边界框（pt）
        "y_pos": float      # 行 y 坐标（pt）
    }
]
```

---

## scripts/format_checker.py

格式规范自动检查模块，18 项检查。

### `check_format(pdf_path: str) -> dict`

运行所有格式检查。

**参数：**
- `pdf_path` — 论文 PDF 文件路径

**返回：**
```python
{
    "issues": [
        {
            "page": int,        # 页码
            "location": str,    # 位置描述（如 "正文区域", "页眉左端"）
            "rule": str,        # 规则名（如 "章标题字号"）
            "expected": str,    # 期望值
            "actual": str,      # 实际值
            "severity": str     # "error" | "warning"
        }
    ],
    "summary": {
        "total": int,
        "errors": int,
        "warnings": int
    }
}
```

### CLI 用法

```bash
python scripts/format_checker.py <thesis.pdf>
# 输出 JSON 到 stdout
```

### 检查项列表

| # | 内部函数 | 检查内容 |
|---|---------|---------|
| 1 | `_check_page_size` | A4 尺寸 210×297mm |
| 2 | `_check_body_area` | 版芯 160×247mm |
| 3 | `_check_lines_and_chars` | 每页 30~35 行，每行 35~38 字 |
| 4 | `_check_body_text` | 正文小四宋体 12pt |
| 5 | `_check_english_font` | 英文 Times New Roman |
| 6 | `_check_chapter_headings` | 章标题二号黑体 22pt + 长度 ≤20 字 |
| 7 | `_check_section_headings` | 节标题三号黑体 / 款标题四号黑体 |
| 8-9 | `_check_heading_alignment` | 章居中 / 节款居左 |
| 10 | `_check_heading_spacing` | 章占 3 行 / 节占 2 行 |
| 11 | `_check_figure_table_numbering` | 图/表/公式按章连续编号 |
| 12 | `_check_caption_format` | 图题图下 + 表题表上 + 五号宋体 |
| 13 | `_check_references` | 参考文献 [N] 连续 + GB/T 7714 |
| 14 | `_check_headers` | 页眉左端固定文字 + 右端匹配章标题 + 楷体五号 |
| 15 | `_check_page_numbers` | 页脚存在页码 |
| 16 | `_check_paragraph_last_line` | 段落末行 ≥ 5 字 |
| 17 | `_check_page_bottom_blank` | 页底空白 ≤ 2 行 |

### 规则常量 `RULES`

格式规则硬编码于 `RULES` 字典，包含字号、字体、容差等参数。如需适配其他学校，修改此字典即可。
