---
name: pipeline-orchestrator
description: Run the GitHub Star Prediction ML pipeline. Inspect state first, apply scheduling rules, execute only what's needed. Orchestrated by a DeepSeek Tool Use agent loop.
metadata: { "openclaw": { "emoji": "🚀", "requires": { "bins": ["python3"], "env": [] } } }
---

# Pipeline Orchestrator

Agentic ML pipeline that inspects current state, applies scheduling rules, and executes only necessary steps.

## When to Use

**USE this skill when:**
- "开始分析" — trigger the full ML pipeline
- "run pipeline" — English trigger
- "分析github项目" or "分析 github 项目" — Chinese alternative
- "重新跑分析" or "rerun pipeline" — force full re-run
- "检查 pipeline 状态" — inspect without running
- "今日雷达" / "Today Radar" — run the application mode that scores recent repositories as a candidate shortlist

**DON'T use this skill when:**
- Only want raw data: use `repo-collector` directly
- Only want feature extraction: use `feature-extractor` directly
- Pipeline already ran and user just wants results: read `data/model_results.json`

## Scheduling Strategy (agent applies these rules after inspect)

```
RULE 1 — Data collection:
  IF raw_data.exists == false
  THEN run_repo_collector
  ELSE skip (log reason: "fixed historical snapshot exists")

  Note: the default course experiment uses a fixed historical snapshot.
  Do not refresh data based on file age alone.

RULE 2 — Feature extraction:
  IF features.exists == false
     OR features.newer_than_raw == false
  THEN run_feature_extractor
  ELSE skip (log reason: "features.csv is newer than raw data")

RULE 3 — Model training:
  IF model_results.exists == false
     OR model_results.newer_than_features == false
  THEN run_model_trainer
  ELSE skip (log reason: "model_results.json is up to date")

RULE 4 — Diagnostic summary:
  IF diagnostic_summary.exists == false
     OR diagnostic_summary.newer_than_model_results == false
     OR diagnostic_summary.newer_than_features == false
  THEN run_diagnostic_builder
  ELSE skip (log reason: "diagnostic_summary.json is up to date")

RULE 5 — Insight analysis:
  IF insights.exists == false
     OR insights.newer_than_diagnostic == false
  THEN run_insight_analysis
  ELSE skip (log reason: "INSIGHTS.md is up to date")

RULE 6 — Report generation:
  ALWAYS run_report_generator
  (reason: report reflects current date, decision log, run history, and insight analysis)

OPTIONAL — Today Radar:
  IF the user explicitly asks for today/radar/recent project recommendations
  THEN run_today_radar after model artifacts are available.
  Do not present outputs as verified future predictions; they are candidate shortlists.
```

## Execution Protocol

1. **ALWAYS** call `run_inspect_pipeline_state` first — get facts
2. Apply rules above to each step — decide skip or execute
3. Execute in order: collect → extract → train → diagnose → insight → report
4. After completion: summarize decisions made and why

## Quick Start

```bash
python3 /Users/wenjun/.openclaw/workspace/skills/pipeline-orchestrator/run.py
```

No API key setup — read automatically from `~/.openclaw/openclaw.json`.

The runner automatically starts and opens the OpenClaw Console at
`http://localhost:8080/dashboard/`. For silent runs:

```bash
python3 /Users/wenjun/.openclaw/workspace/skills/pipeline-orchestrator/run.py \
  --no-open-dashboard "开始分析"
```

## Reproducing the pipeline vs. forcing a re-run

The canonical reproduction command is still:

```bash
openclaw agent --agent pipeline-orchestrator --message "开始分析"
```

This does **not** force every step to re-execute. The orchestrator first calls
`run_inspect_pipeline_state` and decides which steps to skip based on file
timestamps. To actually re-run a step, prefer deleting the corresponding
artifact (e.g. `data/diagnostic_summary.json`) and let the orchestrator
recover it as a "missing/stale" step.

### --force-local — demo-friendly forced re-run

Force every local analysis step while keeping the fixed historical raw
snapshot intact:

```bash
python3 /Users/wenjun/.openclaw/workspace/skills/pipeline-orchestrator/run.py \
  --force-local "开始分析"
```

This deterministically runs `feature-extractor → model-trainer →
diagnostic-builder → insight-analysis → report-generator` without skipping.

### --force-full — **NOT recommended for defense demos**

Full chain including GitHub recollection:

```bash
python3 /Users/wenjun/.openclaw/workspace/skills/pipeline-orchestrator/run.py \
  --force-full "开始分析"
```

By default `--force-full` writes the new snapshot to
`data/repos_raw_500_force_<timestamp>.jsonl` and leaves the canonical
`data/repos_raw_500.jsonl` untouched, so course reproducibility is preserved.

To actually overwrite the canonical historical snapshot you have to add
`--force-full-overwrite` explicitly. GitHub Search API results are not
deterministic across calls, so overwriting breaks reproducibility of past
experiments. The script prints a loud warning and a rollback command before
proceeding.

### Natural-language force triggers are disabled

Messages such as `请强制按规则执行` or `跑完整 pipeline` will no longer flip the
orchestrator into a forced mode. Use the CLI flags above or set the
environment variables `OPENCLAW_FORCE_LOCAL=1` / `OPENCLAW_FORCE_FULL=1`
deliberately.

## How It Works

```
openclaw agent → pipeline-orchestrator skill
    └── run.py → orchestrator.py "开始分析"
            └── DeepSeek Tool Use loop
                ├── [1] run_inspect_pipeline_state → facts JSON
                ├── [2?] run_repo_collector         (if rule 1 triggers)
                ├── [3?] run_feature_extractor       (if rule 2 triggers)
                ├── [4?] run_model_trainer           (if rule 3 triggers)
                ├── [5?] run_diagnostic_builder      (if rule 4 triggers)
                ├── [6?] run_insight_analysis        (if rule 5 triggers)
                └── [7]  run_report_generator        (always)
```

## Output

| File | Description |
|------|-------------|
| `data/decision_log.json` | Agent's inspection result + decisions made |
| `data/run_history.json` | Cumulative run history (all sessions) |
| `data/pipeline_status.jsonl` | Live event stream consumed by the dashboard (now written from Python orchestrator path too) |
| `data/model_results.json` | LR/RF/XGBoost metrics + feature importance |
| `data/diagnostic_summary.json` | Fact-only diagnostics for insight analysis |
| `reports/INSIGHTS.md` | Insight analysis grounded in diagnostic facts (LLM output is rejected if it cites numbers not present in the diagnostic summary) |
| `reports/insights.html` | HTML render of INSIGHTS.md for the dashboard 洞察分析 tab |
| `reports/YYYY-MM-DD_final.html` | Full analysis report |
| `reports/latest_final.html` | Stable filename for dashboard iframe |
| `reports/today_radar.json` | Recent-repo candidate shortlist, if Today Radar was requested |
| `reports/today_radar.html` | Human-readable Today Radar report (action thresholds come from `model_schema.json::score_thresholds`, p80/p60/p40 of RF training-set probabilities) |
| `dashboard/index.html` | Unified OpenClaw Console showing all 6 worker nodes (数据采集 / 特征工程 / 模型训练 / 事实诊断 / 洞察分析 / 报告生成); auto-started by this runner |
