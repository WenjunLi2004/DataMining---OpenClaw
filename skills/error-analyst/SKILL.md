# error-analyst

## 功能

分析 RF 模型的高置信度预测错误，用大模型归纳 FP / FN 的共同模式。

- **FP（假阳性）**：模型高度确信"会火"，实际却未入 Top 20%。
- **FN（假阴性）**：模型认为"不太行"，实际却进入了 Top 20%。

## 输入

| 文件 | 说明 |
|------|------|
| `data/features.csv` | 500 × 19 特征矩阵 + `is_top20` 标签 |
| `data/model_results.json` | 包含 `oof_probs_rf`（500 个 OOF 概率） |

## 输出

| 文件 | 说明 |
|------|------|
| `data/error_analysis.json` | FP/FN 案例 + LLM 分析文本 |
| `reports/error_analysis.html` | 可读 HTML 报告 |

## 运行

```bash
python3 skills/error-analyst/analyze.py
# 可选参数
python3 skills/error-analyst/analyze.py \
    --features data/features.csv \
    --results  data/model_results.json \
    --out-json data/error_analysis.json \
    --out-html reports/error_analysis.html
```

需要 `DEEPSEEK_API_KEY` 环境变量来启用 LLM 分析；
未设置时自动回退到确定性统计摘要。
