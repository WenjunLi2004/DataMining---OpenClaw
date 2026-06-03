---
name: insight-analysis
description: Generate a fact-grounded INSIGHTS.md report from diagnostic_summary.json. Uses an LLM when available and falls back to a deterministic template. The diagnostic summary is the only allowed source of numeric claims.
metadata: { "openclaw": { "emoji": "🧠", "requires": { "bins": ["python3"], "env": [] } } }
---

# Insight Analysis

This skill is the LLM reasoning layer of OpenClaw. It reads the fact-only
`diagnostic_summary.json` and produces `reports/INSIGHTS.md`.

## Strict Grounding Rule

All numeric claims must come from `diagnostic_summary.json`. If a useful metric
is missing, write that it is not measured instead of inventing a value.

## Usage

```bash
python3 ~/.openclaw/workspace/skills/insight-analysis/analyze.py \
  --diagnostic ~/openclaw-project/data/diagnostic_summary.json \
  --output ~/openclaw-project/reports/INSIGHTS.md \
  --mode auto
```

`--mode auto` tries DeepSeek/OpenAI-compatible generation when an API key is
available, then falls back to the deterministic template if the call fails.
