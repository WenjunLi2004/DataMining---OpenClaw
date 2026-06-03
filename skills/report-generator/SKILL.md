---
name: report-generator
description: Generate a self-contained HTML evaluation report from model_results.json + features.csv. Includes dataset overview, feature engineering summary, model comparison table, feature importance bars, key findings, and optional INSIGHTS.md analysis.
metadata: { "openclaw": { "emoji": "📊", "requires": { "bins": ["python3"], "env": [] } } }
---

# Report Generator

Produces a dark-themed HTML report viewable in any browser. If
`~/openclaw-project/reports/INSIGHTS.md` exists, it is embedded as an
`Insight Analysis` section.

## Usage

```bash
python3 ~/.openclaw/workspace/skills/report-generator/generate.py
# or with explicit paths:
python3 ~/.openclaw/workspace/skills/report-generator/generate.py \
  --results  ~/openclaw-project/data/model_results.json \
  --features ~/openclaw-project/data/features.csv \
  --out-dir  ~/openclaw-project/reports
```

Output: `~/openclaw-project/reports/YYYY-MM-DD_final.html`

Open with: `open ~/openclaw-project/reports/YYYY-MM-DD_analysis.html`
