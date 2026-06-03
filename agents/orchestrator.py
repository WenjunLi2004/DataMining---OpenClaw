#!/usr/bin/env python3
"""
OpenClaw ML Pipeline Orchestrator (Agentic Edition)
Uses DeepSeek Chat + Tool Use to inspect state, apply scheduling rules,
and execute only necessary pipeline steps.

Usage:
    python3 ~/openclaw-project/agents/orchestrator.py
    python3 ~/openclaw-project/agents/orchestrator.py "开始分析"

Env vars:
    DEEPSEEK_API_KEY  — DeepSeek API key (auto-read from openclaw.json if unset)
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from openai import OpenAI

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL       = "deepseek-chat"
PROJECT_DIR = Path.home() / "openclaw-project"
SKILLS_DIR  = Path.home() / ".openclaw/workspace/skills"
WORKSPACE   = Path.home() / ".openclaw/workspace"

DATA_DIR    = PROJECT_DIR / "data"
REPORTS_DIR = PROJECT_DIR / "reports"

RAW_DATA    = DATA_DIR / "repos_raw_500_strict.jsonl"
FEATURES    = DATA_DIR / "features.csv"
RESULTS     = DATA_DIR / "model_results.json"
DIAGNOSTIC  = DATA_DIR / "diagnostic_summary.json"
INSIGHTS    = REPORTS_DIR / "INSIGHTS.md"
TODAY_RADAR = REPORTS_DIR / "today_radar.json"
DECISION_LOG = DATA_DIR / "decision_log.json"
RUN_HISTORY  = DATA_DIR / "run_history.json"
MEMORY_MD    = WORKSPACE / "MEMORY.md"
STATUS_FILE  = DATA_DIR / "pipeline_status.jsonl"

# Map skill / script path fragments → dashboard agent_id.
# The orchestrator subprocess-calls scripts directly, so we infer the
# logical agent from the path the command points at.
AGENT_ID_MAP = [
    ("repo-collector",        "data-collector"),
    ("feature-extractor",     "feature-engineer"),
    ("model-trainer",         "model-trainer"),
    ("diagnostic-builder",    "diagnostic-builder"),
    ("insight-analysis",      "insight-analyst"),
    ("report-generator",      "report-generator"),
    ("today-radar",           "today-radar"),
    ("inspect-pipeline-state","inspect"),  # not surfaced as an agent card
]


def _agent_id_from_cmd(cmd: List[str]) -> str:
    joined = " ".join(cmd)
    for fragment, agent_id in AGENT_ID_MAP:
        if fragment in joined:
            return agent_id
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_status_event(event_type: str, agent_id: str = "pipeline-orchestrator",
                        message: str = "", duration_ms: int = 0) -> None:
    """Append a JSONL event for the dashboard. Same schema as dispatch.py."""
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp":   _now_iso(),
            "agent_id":    agent_id,
            "event_type":  event_type,
            "duration_ms": int(duration_ms),
            "message":     message[:240],
        }
        with open(STATUS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # never let logging break the pipeline
        print(f"  [status] WARN: could not write event: {exc}", flush=True)

# ---------------------------------------------------------------------------
# Memory helpers (P2)
# ---------------------------------------------------------------------------

def _load_run_history(n: int = 3) -> List[dict]:
    """Load last N runs from run_history.json."""
    if not RUN_HISTORY.exists():
        return []
    try:
        history = json.loads(RUN_HISTORY.read_text())
        return history[-n:] if isinstance(history, list) else []
    except Exception:
        return []


def _format_history_for_prompt(history: List[dict]) -> str:
    if not history:
        return "No previous runs on record."
    lines = []
    for run in reversed(history):
        date   = run.get("run_at", "?")[:10]
        rf_auc = run.get("rf_auc", "N/A")
        best   = run.get("best_model", "?")
        feats  = ", ".join(run.get("top3_features", []))
        steps  = ", ".join(run.get("steps_executed", []))
        lines.append(
            f"• {date}: RF AUC={rf_auc}, best={best}, "
            f"top features=[{feats}], ran=[{steps}]"
        )
    return "\n".join(lines)


def _write_run_memory(run_record: dict):
    """Append run record to run_history.json and workspace memory markdown."""
    # 1. run_history.json (machine-readable cumulative log)
    history = []
    if RUN_HISTORY.exists():
        try:
            history = json.loads(RUN_HISTORY.read_text())
        except Exception:
            pass
    history.append(run_record)
    RUN_HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False))

    # 2. Daily workspace memory markdown (OpenClaw native memory)
    run_date = run_record.get("run_at", "")[:10]
    daily_md = WORKSPACE / "memory" / f"{run_date}.md"
    rf_auc   = run_record.get("rf_auc", "N/A")
    best     = run_record.get("best_model", "?")
    feats    = ", ".join(run_record.get("top3_features", []))
    steps    = ", ".join(run_record.get("steps_executed", []))
    n_samp   = run_record.get("n_samples", "?")

    auc_str  = f"{rf_auc:.4f}" if isinstance(rf_auc, float) else str(rf_auc)
    md_entry = (
        f"\n## ML Pipeline Run ({run_record.get('run_at', '')[:16]} UTC)\n"
        f"- RF AUC: {auc_str}\n"
        f"- Best model: {best}\n"
        f"- Top 3 features: {feats}\n"
        f"- Dataset size: {n_samp}\n"
        f"- Steps executed: {steps}\n"
    )

    with open(daily_md, "a") as f:
        f.write(md_entry)

    # 3. MEMORY.md (curated long-term, OpenClaw native)
    with open(MEMORY_MD, "a") as f:
        f.write(md_entry)

    # 4. Re-index so vector store picks up new content
    subprocess.run(["openclaw", "memory", "index"], capture_output=True, timeout=30)
    print(f"  [memory] written → {daily_md.name} + MEMORY.md + indexed", flush=True)


# ---------------------------------------------------------------------------
# System prompt (dynamic, injects run history)
# ---------------------------------------------------------------------------

def _build_system_prompt(history: List[dict]) -> str:
    history_str = _format_history_for_prompt(history)
    return f"""You are the OpenClaw ML Pipeline Scheduler. Your job is to
inspect pipeline state, apply scheduling rules, and execute only the
steps that are actually needed.

## Mandatory execution protocol

STEP 1: Call run_inspect_pipeline_state — get current file facts (ALWAYS first).
STEP 2: Apply the scheduling rules below to each pipeline step.
STEP 3: Execute steps in order (collect → extract → train → diagnose → insight → report).
STEP 4: Output a brief Chinese summary of what ran and why.

## Scheduling rules (apply after inspection)

RULE 1 — Data collection:
  IF raw_data.exists == false → run_repo_collector
  ELSE → skip
  NOTE: This is a reproducible historical backtest. Do NOT auto-refresh data
        just because it is older than 7 days. Only re-collect when the user
        explicitly asks to recollect or force refresh.

RULE 2 — Feature extraction:
  IF features.exists == false OR features.newer_than_raw == false → run_feature_extractor
  ELSE → skip

RULE 3 — Model training:
  IF model_results.exists == false OR model_results.newer_than_features == false → run_model_trainer
  ELSE → skip

RULE 4 — Diagnostic summary:
  IF diagnostic_summary.exists == false
     OR diagnostic_summary.newer_than_model_results == false
     OR diagnostic_summary.newer_than_features == false
  → run_diagnostic_builder
  ELSE → skip

RULE 5 — Insight analysis:
  IF insights.exists == false OR insights.newer_than_diagnostic == false → run_insight_analysis
  ELSE → skip

RULE 6 — Report generation:
  ALWAYS run run_report_generator (never skip — report captures today's date and decision log)

OPTIONAL — Today Radar:
  IF the user explicitly asks for "today", "今日", "今天", "近期项目", or "Today Radar"
  → run_today_radar after the backtest artifacts are up to date.
  Today Radar is a candidate shortlist, not a verified prediction.

## Recent run history (last 3 sessions)

{history_str}

## Critical rules
- NEVER skip run_report_generator
- NEVER guess at file state — always call inspect first
- NEVER auto-refresh historical raw data based on age alone
- NEVER run Today Radar unless the user explicitly asks for it, because it may call GitHub live APIs
- State your reasoning for each skip/execute decision
"""


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_inspect_pipeline_state",
            "description": (
                "Inspect current pipeline file state. Returns JSON with facts about "
                "repos_raw_500_strict.jsonl, features.csv, model_results.json, "
                "diagnostic_summary.json, INSIGHTS.md, and reports/. "
                "ALWAYS call this first before any other tool."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_repo_collector",
            "description": (
                "Collect GitHub repo raw data → repos_raw_500_strict.jsonl. "
                "Only call if raw_data.exists==false, unless the user explicitly asked "
                "to force recollection. This project defaults to a fixed historical snapshot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "integer", "description": "Number of repos (default 500)"},
                    "start":  {"type": "string",  "description": "Start date YYYY-MM-DD"},
                    "end":    {"type": "string",   "description": "End date YYYY-MM-DD"},
                    "force":  {"type": "boolean", "description": "Recollect even if raw data exists"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_diagnostic_builder",
            "description": (
                "Build fact-only diagnostic_summary.json from model_results.json and features.csv. "
                "Call after model training when diagnostic summary is missing or stale."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "results":  {"type": "string"},
                    "features": {"type": "string"},
                    "output":   {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_insight_analysis",
            "description": (
                "Generate fact-grounded reports/INSIGHTS.md from diagnostic_summary.json. "
                "Call after diagnostic_builder when insights are missing or stale."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diagnostic": {"type": "string"},
                    "output":     {"type": "string"},
                    "mode":       {"type": "string", "description": "auto, llm, or template"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_feature_extractor",
            "description": (
                "Extract ML features → features.csv. "
                "Only call if features.exists==false or features.newer_than_raw==false."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "input":  {"type": "string"},
                    "output": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_model_trainer",
            "description": (
                "Train LR/RF/XGBoost models → model_results.json. "
                "Only call if model_results.exists==false or model_results.newer_than_features==false."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "input":  {"type": "string"},
                    "output": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_report_generator",
            "description": (
                "Generate HTML report → reports/YYYY-MM-DD_final.html. "
                "ALWAYS call this — never skip report generation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "results":  {"type": "string"},
                    "features": {"type": "string"},
                    "out_dir":  {"type": "string"},
                    "out_file": {"type": "string"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_today_radar",
            "description": (
                "Run Today Radar: apply the trained model to recent repositories and "
                "generate reports/today_radar.json + reports/today_radar.html. "
                "Only call when the user explicitly asks for today/radar/recent project recommendations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "integer"},
                    "top_k": {"type": "integer"},
                    "days_min": {"type": "integer"},
                    "days_max": {"type": "integer"},
                    "input_jsonl": {"type": "string", "description": "Optional offline JSONL for smoke tests"},
                    "force": {"type": "boolean"},
                },
                "required": [],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

def _run(cmd: List[str]) -> str:
    print(f"\n  $ {' '.join(cmd)}", flush=True)
    agent_id = _agent_id_from_cmd(cmd)
    track = bool(agent_id) and agent_id != "inspect"

    import time as _time
    t0 = _time.time()
    if track:
        _write_status_event("agent_start", agent_id, message=" ".join(cmd[-3:])[:200])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    output = result.stdout + result.stderr
    print(output, flush=True, end="")
    duration_ms = int((_time.time() - t0) * 1000)

    if result.returncode != 0:
        if track:
            # last meaningful line of stderr/stdout for the dashboard summary
            err_summary = (result.stderr or result.stdout or "unknown error").strip().splitlines()
            tail = err_summary[-1] if err_summary else "unknown error"
            _write_status_event("agent_failed", agent_id, message=tail[:200],
                                duration_ms=duration_ms)
        return f"[FAILED exitcode={result.returncode}]\n{output}"

    if track:
        # last non-empty line of stdout as the completion message
        out_lines = [ln for ln in (result.stdout or "").splitlines() if ln.strip()]
        tail = out_lines[-1] if out_lines else "completed"
        _write_status_event("agent_completed", agent_id, message=tail[:200],
                            duration_ms=duration_ms)
    return output or "[OK]"


def run_inspect_pipeline_state() -> str:
    return _run(["python3", str(SKILLS_DIR / "inspect-pipeline-state/inspect.py")])


def run_repo_collector(target: int = 500, start: str = "2025-03-01",
                        end: str = "2025-04-30", force: bool = False,
                        overwrite_canonical: bool = False) -> str:
    """Collect GitHub raw data.

    Default (force=False): only runs when canonical RAW_DATA is missing.
    force=True (force-full path):
        - By default writes to data/repos_raw_500_strict_force_<timestamp>.jsonl, leaving
          the canonical fixed snapshot in place. This preserves course
          reproducibility even after a force-full run.
        - overwrite_canonical=True is required to actually overwrite the
          canonical file. Not exposed in the natural-language flow.
    """
    if RAW_DATA.exists() and not force:
        return (
            f"[SKIP] {RAW_DATA.name} already exists. "
            "OpenClaw keeps the default historical backtest snapshot fixed; "
            "use --force-full only for an explicit recollection request."
        )

    if force and RAW_DATA.exists() and overwrite_canonical:
        # Loud warning; keep a backup; print rollback command.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = RAW_DATA.with_suffix(RAW_DATA.suffix + f".bak-{stamp}")
        RAW_DATA.rename(backup)
        print("", flush=True)
        print("╔" + "═" * 70 + "╗", flush=True)
        print("║  ⚠️  FORCE-FULL: overwriting canonical historical snapshot         ║", flush=True)
        print(f"║  backup: {str(backup)[:58]:<58s} ║", flush=True)
        print("║  GitHub Search results are NOT deterministic across calls.        ║", flush=True)
        print("║  Reproducibility of past experiments is now broken until rollback.║", flush=True)
        print("║  Rollback:                                                        ║", flush=True)
        rollback = f"mv {backup} {RAW_DATA}"
        print(f"║    $ {rollback[:60]:<60s}   ║", flush=True)
        print("╚" + "═" * 70 + "╝", flush=True)
        print("", flush=True)
        out_filename = "repos_raw_500_strict.jsonl"
    elif force:
        # Safe default: write force output to a separate file so the canonical
        # snapshot is preserved.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_filename = f"repos_raw_500_strict_force_{stamp}.jsonl"
        print("", flush=True)
        print("╔" + "═" * 70 + "╗", flush=True)
        print("║  ⚠️  FORCE-FULL collection (canonical snapshot preserved)         ║", flush=True)
        print(f"║  output:  data/{out_filename:<55s} ║", flush=True)
        print("║  Downstream steps still consume data/repos_raw_500_strict.jsonl.  ║", flush=True)
        print("║  To make this run authoritative, manually replace the canonical   ║", flush=True)
        print("║  file or pass overwrite_canonical=true.                           ║", flush=True)
        print("╚" + "═" * 70 + "╝", flush=True)
        print("", flush=True)
    else:
        out_filename = "repos_raw_500_strict.jsonl"

    return _run([
        "python3", str(SKILLS_DIR / "repo-collector/collect.py"),
        "--target", str(target),
        "--start", start, "--end", end,
        "--out-file", out_filename,
        "--batch-name", "strict_30d_1y_2025_03_04",
    ])


def run_feature_extractor(input: str = str(RAW_DATA),
                           output: str = str(FEATURES)) -> str:
    return _run([
        "python3", str(SKILLS_DIR / "feature-extractor/extract.py"),
        "--input", input, "--output", output,
    ])


def run_model_trainer(input: str = str(FEATURES),
                       output: str = str(RESULTS)) -> str:
    return _run([
        "python3", str(SKILLS_DIR / "model-trainer/train.py"),
        "--input", input, "--output", output,
    ])


def run_diagnostic_builder(results: str = str(RESULTS),
                           features: str = str(FEATURES),
                           output: str = str(DIAGNOSTIC)) -> str:
    return _run([
        "python3", str(SKILLS_DIR / "diagnostic-builder/diagnose.py"),
        "--results", results, "--features", features, "--output", output,
    ])


def run_insight_analysis(diagnostic: str = str(DIAGNOSTIC),
                         output: str = str(INSIGHTS),
                         mode: str = "auto") -> str:
    return _run([
        "python3", str(SKILLS_DIR / "insight-analysis/analyze.py"),
        "--diagnostic", diagnostic, "--output", output, "--mode", mode,
    ])


def run_report_generator(results: str = str(RESULTS),
                          features: str = str(FEATURES),
                          out_dir: str = str(REPORTS_DIR),
                          out_file: str = "") -> str:
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = out_file or f"{today}_final.html"
    return _run([
        "python3", str(SKILLS_DIR / "report-generator/generate.py"),
        "--results", results, "--features", features,
        "--out-dir", out_dir, "--out-file", filename,
    ])


def run_today_radar(target: int = 20, top_k: int = 10,
                    days_min: int = 30, days_max: int = 45,
                    input_jsonl: str = "", force: bool = False) -> str:
    cmd = [
        "python3", str(SKILLS_DIR / "today-radar/radar.py"),
        "--target", str(target),
        "--top-k", str(top_k),
        "--days-min", str(days_min),
        "--days-max", str(days_max),
    ]
    if input_jsonl:
        cmd += ["--input-jsonl", input_jsonl]
    if force:
        cmd += ["--force"]
    return _run(cmd)


TOOL_HANDLERS = {
    "run_inspect_pipeline_state": run_inspect_pipeline_state,
    "run_repo_collector":          run_repo_collector,
    "run_feature_extractor":       run_feature_extractor,
    "run_model_trainer":           run_model_trainer,
    "run_diagnostic_builder":      run_diagnostic_builder,
    "run_insight_analysis":        run_insight_analysis,
    "run_report_generator":        run_report_generator,
    "run_today_radar":             run_today_radar,
}

# ---------------------------------------------------------------------------
# Decision log
# ---------------------------------------------------------------------------

def _derive_decisions(state: dict, executed: List[str]) -> List[dict]:
    """Derive decision log post-hoc from state + executed tool list."""
    decisions = []
    raw   = state.get("raw_data", {})
    feat  = state.get("features", {})
    model = state.get("model_results", {})
    diag  = state.get("diagnostic_summary", {})
    ins   = state.get("insights", {})
    radar = state.get("today_radar", {})

    # Collect
    if "run_repo_collector" in executed:
        if not raw.get("exists"):
            reason = "repos_raw_500_strict.jsonl not found"
        else:
            reason = "explicit forced re-collection requested"
        decisions.append({"step": "Data Collection", "action": "executed", "reason": reason})
    else:
        age = raw.get("age_days") if raw.get("exists") else None
        decisions.append({
            "step": "Data Collection", "action": "skipped",
            "reason": (
                f"fixed historical snapshot exists ({age:.1f}d old); age alone does not trigger recollection"
                if age is not None else "raw data not checked"
            ),
        })

    # Feature extraction
    if "run_feature_extractor" in executed:
        if not feat.get("exists"):
            reason = "features.csv not found"
        elif feat.get("newer_than_raw") is False:
            reason = "features.csv older than raw data → refresh needed"
        else:
            reason = "forced re-extraction"
        decisions.append({"step": "Feature Extraction", "action": "executed", "reason": reason})
    else:
        decisions.append({
            "step": "Feature Extraction", "action": "skipped",
            "reason": "features.csv exists and is newer than raw data",
        })

    # Model training
    if "run_model_trainer" in executed:
        if not model.get("exists"):
            reason = "model_results.json not found"
        elif model.get("newer_than_features") is False:
            reason = "model_results.json older than features.csv → retrain"
        else:
            reason = "forced re-training"
        decisions.append({"step": "Model Training", "action": "executed", "reason": reason})
    else:
        decisions.append({
            "step": "Model Training", "action": "skipped",
            "reason": "model_results.json exists and is newer than features.csv",
        })

    # Diagnostic builder
    if "run_diagnostic_builder" in executed:
        if not diag.get("exists"):
            reason = "diagnostic_summary.json not found"
        elif diag.get("newer_than_model_results") is False:
            reason = "diagnostic_summary.json older than model_results.json → rebuild"
        elif diag.get("newer_than_features") is False:
            reason = "diagnostic_summary.json older than features.csv → rebuild"
        else:
            reason = "forced diagnostic rebuild"
        decisions.append({"step": "Diagnostic Builder", "action": "executed", "reason": reason})
    else:
        decisions.append({
            "step": "Diagnostic Builder", "action": "skipped",
            "reason": "diagnostic_summary.json exists and is newer than model_results.json/features.csv",
        })

    # Insight analysis
    if "run_insight_analysis" in executed:
        if not ins.get("exists"):
            reason = "reports/INSIGHTS.md not found"
        elif ins.get("newer_than_diagnostic") is False:
            reason = "INSIGHTS.md older than diagnostic_summary.json → regenerate"
        else:
            reason = "forced insight regeneration"
        decisions.append({"step": "Insight Analysis", "action": "executed", "reason": reason})
    else:
        decisions.append({
            "step": "Insight Analysis", "action": "skipped",
            "reason": "INSIGHTS.md exists and is newer than diagnostic_summary.json",
        })

    # Report (always)
    decisions.append({
        "step": "Report Generation", "action": "executed",
        "reason": "always regenerated — captures today's date, decision log, run history, and insight analysis",
    })

    if "run_today_radar" in executed:
        decisions.append({
            "step": "Today Radar", "action": "executed",
            "reason": "user explicitly requested recent/today candidate shortlist",
        })
    elif radar.get("exists"):
        decisions.append({
            "step": "Today Radar", "action": "available",
            "reason": f"latest candidate shortlist exists at {radar.get('path')}",
        })

    return decisions


def _save_decision_log(state: dict, executed: List[str], run_at: str):
    decisions = _derive_decisions(state, executed)
    log = {
        "run_at":             run_at,
        "state_snapshot":     state,
        "decisions":          decisions,
        "tool_calls_sequence": executed,
    }
    DECISION_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False))
    print(f"  [decision] log written → {DECISION_LOG}", flush=True)
    return log


def _build_run_record(run_at: str, executed: List[str]) -> dict:
    """Build a concise run record for run_history.json."""
    record: dict = {"run_at": run_at, "steps_executed": executed}
    try:
        data     = json.loads(RESULTS.read_text())
        models   = data.get("models", {})
        rf       = models.get("RF", {})
        best     = max(models.keys(), key=lambda n: models[n].get("auc", {}).get("mean", 0)) if models else "N/A"
        top_feats = [f["feature"] for f in data.get("feature_importance", {}).get("RF", [])[:3]]
        record.update({
            "rf_auc":       rf.get("auc", {}).get("mean"),
            "rf_pr_auc":    rf.get("pr_auc", {}).get("mean"),
            "best_model":   best,
            "top3_features": top_feats,
            "n_samples":    data.get("meta", {}).get("n_samples"),
        })
    except Exception:
        pass
    return record


def _force_mode(user_message: str) -> str:
    """Return '' / 'local' / 'full'. Only env vars trigger force mode.

    Natural-language triggers were removed: words like "强制" or "完整 pipeline"
    are too easy to type by accident, and silently switching from agent-driven
    scheduling to a deterministic path is misleading during a demo. The only
    supported entry points are now:
      - OPENCLAW_FORCE_LOCAL=1  (from run.py --force-local)
      - OPENCLAW_FORCE_FULL=1   (from run.py --force-full)
    """
    if os.environ.get("OPENCLAW_FORCE_FULL") == "1":
        return "full"
    if os.environ.get("OPENCLAW_FORCE_LOCAL") == "1":
        return "local"
    return ""


def run_forced_pipeline(user_message: str, mode: str):
    """Deterministic no-skip path for demos and explicit force requests."""
    run_at = datetime.now(timezone.utc).isoformat()
    print(f"\n{'='*60}", flush=True)
    print(f"[orchestrator] Starting FORCED pipeline ({mode}): {user_message!r}", flush=True)
    print(f"{'='*60}", flush=True)

    _write_status_event(
        "pipeline_start", "pipeline-orchestrator",
        message=f"force-{mode}: {user_message[:120]}",
    )

    state_snapshot: dict = {}
    try:
        state_snapshot = json.loads(run_inspect_pipeline_state())
    except Exception:
        pass

    executed_tools: List[str] = []
    if mode == "full":
        # Power-user override: only OPENCLAW_FORCE_FULL_OVERWRITE=1 actually
        # rewrites data/repos_raw_500_strict.jsonl. Default writes to a sibling file
        # so the canonical historical snapshot stays put.
        overwrite = os.environ.get("OPENCLAW_FORCE_FULL_OVERWRITE") == "1"
        run_repo_collector(force=True, overwrite_canonical=overwrite)
        executed_tools.append("run_repo_collector")
    else:
        print("[force-local] keeping fixed raw snapshot; forcing downstream recomputation", flush=True)

    run_feature_extractor()
    executed_tools.append("run_feature_extractor")
    run_model_trainer()
    executed_tools.append("run_model_trainer")
    run_diagnostic_builder()
    executed_tools.append("run_diagnostic_builder")
    run_insight_analysis()
    executed_tools.append("run_insight_analysis")

    _save_decision_log(state_snapshot, executed_tools, run_at)
    run_report_generator()
    all_executed = executed_tools + ["run_report_generator"]

    if any(t in user_message.lower() for t in ["today", "今日", "今天", "近期项目", "today radar"]):
        run_today_radar()
        all_executed.append("run_today_radar")

    _save_decision_log(state_snapshot, all_executed, run_at)
    run_record = _build_run_record(run_at, all_executed)
    _write_run_memory(run_record)

    _write_status_event(
        "pipeline_complete", "pipeline-orchestrator",
        message=f"force-{mode} pipeline complete",
    )

    print(f"\n{'='*60}", flush=True)
    print("[orchestrator] Forced pipeline complete.", flush=True)
    print(f"{'='*60}", flush=True)
    if mode == "full":
        print("已强制执行完整链路：重新采集 → 特征 → 训练 → 诊断 → 洞察 → 报告。", flush=True)
    else:
        print("已强制执行本地分析链路：特征 → 训练 → 诊断 → 洞察 → 报告；保留固定历史原始数据。", flush=True)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def _resolve_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    try:
        cfg = json.loads((Path.home() / ".openclaw/openclaw.json").read_text())
        return cfg.get("models", {}).get("providers", {}).get("deepseek", {}).get("apiKey", "")
    except Exception:
        return ""


def dispatch(tool_call) -> str:
    name   = tool_call.function.name
    args   = json.loads(tool_call.function.arguments or "{}")
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f"[ERROR] Unknown tool: {name}"
    kw_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
    print(f"\n[orchestrator] → {name}({kw_str})", flush=True)
    return handler(**args)


def run_pipeline(user_message: str):
    forced = _force_mode(user_message)
    if forced:
        run_forced_pipeline(user_message, forced)
        return

    api_key = _resolve_api_key()
    if not api_key:
        print("[ERROR] DEEPSEEK_API_KEY not set.", flush=True)
        sys.exit(1)

    run_at  = datetime.now(timezone.utc).isoformat()
    history = _load_run_history(3)
    client  = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    messages = [
        {"role": "system",  "content": _build_system_prompt(history)},
        {"role": "user",    "content": user_message},
    ]

    print(f"\n{'='*60}", flush=True)
    print(f"[orchestrator] Starting pipeline: {user_message!r}", flush=True)
    print(f"{'='*60}", flush=True)

    _write_status_event(
        "pipeline_start", "pipeline-orchestrator",
        message=f"agentic: {user_message[:120]}",
    )

    executed_tools: List[str] = []
    state_snapshot: dict      = {}

    for step in range(20):
        response = client.chat.completions.create(
            model=MODEL, messages=messages,
            tools=TOOLS, tool_choice="auto",
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                # Pre-save decision log before report generator runs so it
                # can be included in the HTML output.
                if tc.function.name == "run_report_generator":
                    _save_decision_log(state_snapshot, executed_tools, run_at)

                result = dispatch(tc)

                # Capture state from inspect call
                if tc.function.name == "run_inspect_pipeline_state":
                    try:
                        state_snapshot = json.loads(result)
                    except Exception:
                        pass
                elif tc.function.name != "run_report_generator":
                    executed_tools.append(tc.function.name)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
        else:
            print(f"\n{'='*60}", flush=True)
            print("[orchestrator] Pipeline complete.", flush=True)
            print(f"{'='*60}\n", flush=True)
            print(msg.content, flush=True)

            # Decision log was pre-saved before report generation.
            # Overwrite with final complete version (includes report in tool sequence).
            all_executed = executed_tools + ["run_report_generator"]
            _save_decision_log(state_snapshot, all_executed, run_at)
            run_record = _build_run_record(run_at, all_executed)
            _write_run_memory(run_record)
            _write_status_event(
                "pipeline_complete", "pipeline-orchestrator",
                message=f"agentic pipeline complete · ran={','.join(all_executed)[:140]}",
            )
            return

    print("\n[orchestrator] Reached step limit.", flush=True)
    _write_status_event(
        "pipeline_complete", "pipeline-orchestrator",
        message="agentic pipeline hit step limit",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
    else:
        print("OpenClaw ML Pipeline Orchestrator")
        print("Message (default: 开始分析): ", end="", flush=True)
        msg = input().strip() or "开始分析"
    run_pipeline(msg)


if __name__ == "__main__":
    main()
