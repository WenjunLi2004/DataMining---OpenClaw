---
name: report-generator
description: Generate a self-contained HTML evaluation report from model_results.json + features.csv. Includes dataset overview, feature engineering summary, model comparison table, feature importance bars, key findings, and optional INSIGHTS.md analysis.
metadata: { "openclaw": { "emoji": "📊", "requires": { "bins": ["python3"], "env": [] } } }
---

# Report Generator

Produces a **light-themed** HTML evaluation report viewable in any browser.
All numbers (AUC, PR-AUC, P@10, ablation, feature importance…) are read
dynamically from the current `model_results.json` and `diagnostic_summary.json`
— no hard-coded metrics.

## Usage

```bash
python3 ~/.openclaw/workspace/skills/report-generator/generate.py
# or with explicit paths:
python3 ~/.openclaw/workspace/skills/report-generator/generate.py \
  --results  ~/openclaw-project/data/model_results.json \
  --features ~/openclaw-project/data/features.csv \
  --out-dir  ~/openclaw-project/reports
```

Outputs (identical content, two stable entry points):

- `~/openclaw-project/reports/YYYY-MM-DD_two_part_report.html`
- `~/openclaw-project/reports/latest_final.html`

Open with: `open ~/openclaw-project/reports/latest_final.html`
