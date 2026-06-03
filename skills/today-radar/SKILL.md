---
name: today-radar
description: Apply the trained OpenClaw model to recent GitHub repositories that have just completed an early observation window. Produces a candidate shortlist, not verified predictions.
metadata: { "openclaw": { "emoji": "📡", "requires": { "bins": ["python3"], "env": ["GITHUB_TOKEN?"] } } }
---

# Today Radar

Today Radar is OpenClaw's application mode.

It scans repositories created roughly 30-45 days ago, extracts the same early
signals used by the historical backtest, scores them with the trained RF model,
and outputs a small candidate observation list.

## Important Framing

The output is a candidate shortlist, not a claim that these projects will
definitely become popular. Future labels are not available yet.

## Usage

```bash
python3 ~/.openclaw/workspace/skills/today-radar/radar.py \
  --target 20 \
  --days-min 30 \
  --days-max 45
```

Offline smoke test using existing JSONL:

```bash
python3 ~/.openclaw/workspace/skills/today-radar/radar.py \
  --input-jsonl ~/openclaw-project/data/repos_raw_500_strict.jsonl \
  --target 10
```

## Outputs

| File | Description |
|------|-------------|
| `data/today_repos_raw.jsonl` | Raw recent repo snapshot records |
| `data/today_features.csv` | Predict-mode features aligned to training schema |
| `reports/today_radar.json` | Machine-readable candidate shortlist |
| `reports/today_radar.html` | Human-readable Today Radar report |
