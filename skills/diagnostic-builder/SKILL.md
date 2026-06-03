---
name: diagnostic-builder
description: Build a fact-only diagnostic_summary.json from OpenClaw model results and features. Computes model tradeoffs, simple baselines, language anomalies, feature agreement, correlations, ablation jumps, and dataset caveats for downstream LLM insight analysis.
metadata: { "openclaw": { "emoji": "🧪", "requires": { "bins": ["python3"], "env": [] } } }
---

# Diagnostic Builder

This skill turns model artifacts into a compact, machine-readable fact base.
It does not interpret results rhetorically and does not call an LLM.

## Usage

```bash
python3 ~/.openclaw/workspace/skills/diagnostic-builder/diagnose.py \
  --results ~/openclaw-project/data/model_results.json \
  --features ~/openclaw-project/data/features.csv \
  --output ~/openclaw-project/data/diagnostic_summary.json
```

## Output

`~/openclaw-project/data/diagnostic_summary.json`

The downstream `insight-analysis` skill must treat this file as the source of truth.
