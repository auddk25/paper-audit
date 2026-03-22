# 实验原始数据

按章节存放实验原始数据文件（CSV、Excel、JSON、TXT 等）。

审计时 Claude 会读取这些数据，用 Python 独立计算比值、百分比、统计量等，与论文中的数值交叉验证。

## 目录

```
data/
├── ch3/    ← 第3章实验数据
├── ch4/    ← 第4章实验数据
└── ch5/    ← 第5章实验数据
```

## 数据格式建议

- CSV / Excel（.xlsx）：表格型数据
- JSON：结构化配置或结果数据
- TXT / LOG：实验日志或原始输出

文件名建议包含实验编号，如 `exp3.1_throughput.csv`、`exp4.2_latency.xlsx`。
