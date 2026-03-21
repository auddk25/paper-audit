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
2. **读取写作规范**：首次分析时读取 `E:/code/paper-audit/学术写作规范.md` 的自检清单（十一节）
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

将所有结果合并为 Markdown 报告，保存到 `E:/code/paper-audit/output/` 目录：

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
