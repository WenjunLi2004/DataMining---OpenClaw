---
name: inspect-pipeline-state
description: Inspect the current ML pipeline file state and return pure facts as JSON — file existence, modification times, staleness, record counts. No judgments, no decisions. Always call this first before deciding what to run.
metadata: { "openclaw": { "emoji": "🔍", "requires": { "bins": ["python3"], "env": [] } } }
---

# Pipeline State Inspector

Returns a JSON snapshot of the pipeline's current data state. Pure facts only — the orchestrator applies scheduling rules to decide what to do next.

## When to Use

**ALWAYS call this skill first** when the pipeline-orchestrator skill is triggered.
Never make scheduling decisions without calling this first.

## Output fields

```json
{
  "checked_at": "ISO timestamp",
  "raw_data": {
    "exists": true,
    "age_days": 0.8,
    "record_count": 500
  },
  "features": {
    "exists": true,
    "age_days": 0.5,
    "newer_than_raw": true
  },
  "model_results": {
    "exists": true,
    "models": ["LR", "RF", "XGBoost"],
    "newer_than_features": true
  },
  "reports": {
    "latest_report": "2026-05-19_final.html",
    "latest_age_days": 0.1
  }
}
```

## Quick Start

```bash
python3 ~/.openclaw/workspace/skills/inspect-pipeline-state/inspect.py
```
