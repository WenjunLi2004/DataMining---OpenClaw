#!/usr/bin/env python3
"""
Today Radar: score recent repos with the trained OpenClaw model.

This is an application mode, not an evaluation mode. It outputs candidates for
human review because future labels are not available yet.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import joblib
import pandas as pd


PROJECT_DIR = Path.home() / "openclaw-project"
DATA_DIR = PROJECT_DIR / "data"
REPORTS_DIR = PROJECT_DIR / "reports"
SKILLS_DIR = Path.home() / ".openclaw/workspace/skills"
COLLECTOR_PATH = SKILLS_DIR / "repo-collector/collect.py"
EXTRACTOR_PATH = SKILLS_DIR / "feature-extractor/extract.py"
DEFAULT_ARTIFACTS = DATA_DIR / "model_artifacts"


def load_collector_module():
    spec = importlib.util.spec_from_file_location("openclaw_repo_collector", COLLECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import collector from {COLLECTOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def collect_recent_repos(args) -> Path:
    raw_out = Path(args.raw_out).expanduser()
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    if raw_out.exists() and not args.force:
        print(f"[SKIP] raw recent repo file exists → {raw_out}", flush=True)
        return raw_out
    if raw_out.exists():
        raw_out.unlink()

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=args.days_max)
    end = today - timedelta(days=args.days_min)

    collector = load_collector_module()
    quotas = collector.parse_language_quotas(args.language_quota, args.target)
    print(f"[1/4] Searching recent repos: {start}..{end} target={args.target}", flush=True)
    repos = collector.search_repos(
        args.target,
        start.isoformat(),
        end.isoformat(),
        ts_broad=args.ts_broad,
        language_quotas=quotas,
        seen=set(),
    )

    records = []
    failures = 0
    print(f"[2/4] Collecting early-window snapshots for {len(repos)} repos...", flush=True)
    with open(raw_out, "w", encoding="utf-8") as f:
        for idx, repo in enumerate(repos, 1):
            full_name = repo.get("full_name", "?")
            print(f"  [{idx}/{len(repos)}] {full_name}", flush=True)
            record = collector.collect_repo(repo)
            if record:
                record["batch"] = f"today_radar_{today.isoformat()}"
                record["sampling_policy"] = "today_radar"
                record["query_language"] = repo.get("language")
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                records.append(record)
            else:
                failures += 1

    print(f"  collected={len(records)} failed={failures} → {raw_out}", flush=True)
    return raw_out


def run_feature_extractor(raw_path: Path, features_path: Path, artifacts_dir: Path):
    features_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python3", str(EXTRACTOR_PATH),
        "--mode", "predict",
        "--input", str(raw_path),
        "--output", str(features_path),
        "--artifacts-dir", str(artifacts_dir),
    ]
    print("[3/4] Extracting predict-mode features...", flush=True)
    print("  $ " + " ".join(cmd), flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(result.stdout + result.stderr, end="", flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"feature extractor failed with exit code {result.returncode}")


def feature_value(row: pd.Series, name: str) -> float:
    try:
        return float(row.get(name, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def build_reasons(row: pd.Series, stats: dict[str, Any]) -> tuple[list[str], list[str], str]:
    reasons: list[str] = []
    risks: list[str] = []

    def high(feature: str) -> bool:
        value = feature_value(row, feature)
        p75 = stats.get(feature, {}).get("p75")
        return p75 is not None and value >= float(p75) and value > 0

    # Historical README signals (frozen at created_at + 30 days)
    if high("readme_len_30d"):
        reasons.append("30-day README length is above the training-set p75 — stronger early documentation.")
    elif feature_value(row, "has_readme_30d") <= 0:
        risks.append("No README at the 30-day mark (or could not be fetched).")

    if feature_value(row, "readme_has_demo_url_30d") > 0:
        reasons.append("30-day README contains a demo URL.")
    if feature_value(row, "readme_has_image_30d") > 0:
        reasons.append("30-day README includes images/screenshots.")

    # 30-day activity signals
    if high("commits_30d"):
        reasons.append("First-30-day commit count is high.")
    elif feature_value(row, "commits_30d") <= 1:
        risks.append("First-30-day commit activity is very low.")

    if high("activity_total_30d"):
        reasons.append("Total 30-day activity (commits + issues + PRs) is in the top quartile.")
    if feature_value(row, "has_pr_activity_30d") > 0:
        reasons.append("PRs appeared inside the first 30 days — early external engagement.")

    if feature_value(row, "issues_30d") <= 0 and feature_value(row, "prs_30d") <= 0:
        risks.append("No early issue/PR interaction observed.")
    if feature_value(row, "contributors_30d") <= 1:
        risks.append("Single-author commits in the first 30 days.")

    if not reasons:
        reasons.append("Score is driven by a combination of weaker signals rather than one standout feature.")

    action = "watch"
    return reasons[:4], risks[:4], action


DEFAULT_ACTION_THRESHOLDS = {"deep_dive": 0.75, "try": 0.60, "watch": 0.40}


def load_action_thresholds(schema: dict[str, Any]) -> dict[str, float]:
    """Use thresholds saved by model-trainer (p80/p60/p40 of training-set
    predicted probabilities) when available. Fall back to the legacy fixed
    cutoffs so older artifacts keep working."""
    saved = schema.get("score_thresholds")
    if not isinstance(saved, dict):
        return dict(DEFAULT_ACTION_THRESHOLDS)
    try:
        thresholds = {
            "deep_dive": float(saved["deep_dive"]),
            "try":       float(saved["try"]),
            "watch":     float(saved["watch"]),
        }
    except (KeyError, TypeError, ValueError):
        return dict(DEFAULT_ACTION_THRESHOLDS)
    # Sanity: must be monotone-decreasing.
    if not (thresholds["deep_dive"] >= thresholds["try"] >= thresholds["watch"]):
        print(
            "  [warn] non-monotone score thresholds in schema; using defaults",
            flush=True,
        )
        return dict(DEFAULT_ACTION_THRESHOLDS)
    return thresholds


def action_for_score(score: float, thresholds: dict[str, float] | None = None) -> str:
    t = thresholds or DEFAULT_ACTION_THRESHOLDS
    if score >= t["deep_dive"]:
        return "deep_dive"
    if score >= t["try"]:
        return "try"
    if score >= t["watch"]:
        return "watch"
    return "ignore"


def score_features(features_path: Path, artifacts_dir: Path, top_k: int) -> list[dict[str, Any]]:
    model_path = artifacts_dir / "rf_model.joblib"
    schema_path = artifacts_dir / "model_schema.json"
    if not model_path.exists() or not schema_path.exists():
        raise RuntimeError(f"model artifacts missing in {artifacts_dir}; run model-trainer first")

    model = joblib.load(model_path)
    schema = json.loads(schema_path.read_text())
    feature_names = schema["feature_names"]
    stats = schema.get("feature_stats", {})
    thresholds = load_action_thresholds(schema)
    print(
        f"  Action thresholds (deep_dive/try/watch) = "
        f"{thresholds['deep_dive']:.3f}/{thresholds['try']:.3f}/{thresholds['watch']:.3f}"
        + (" [from schema]" if "score_thresholds" in schema else " [defaults]"),
        flush=True,
    )
    df = pd.read_csv(features_path)

    missing = [c for c in feature_names if c not in df.columns]
    if missing:
        raise RuntimeError(f"features missing required columns: {missing[:8]}")

    X = df[feature_names].values
    scores = model.predict_proba(X)[:, 1]
    df = df.copy()
    df["_attention_score"] = scores
    df = df.sort_values("_attention_score", ascending=False).head(top_k)

    candidates = []
    for rank, (_, row) in enumerate(df.iterrows(), 1):
        score = float(row["_attention_score"])
        reasons, risks, _ = build_reasons(row, stats)
        candidates.append({
            "rank": rank,
            "full_name": str(row.get("_full_name", "")),
            "url": f"https://github.com/{row.get('_full_name', '')}",
            "language": str(row.get("_language", "Other")),
            "attention_score": round(score, 6),
            "current_stars": int(row.get("_current_stars", 0) or 0),
            "created_at": str(row.get("_created_at", "")),
            "action": action_for_score(score, thresholds),
            "reasons": reasons,
            "risks": risks,
            "signals": {
                "commits_30d":              int(row.get("commits_30d", 0) or 0),
                "issues_30d":               int(row.get("issues_30d", 0) or 0),
                "prs_30d":                  int(row.get("prs_30d", 0) or 0),
                "contributors_30d":         int(row.get("contributors_30d", 0) or 0),
                "readme_len_30d":           int(row.get("readme_len_30d", 0) or 0),
                "has_readme_30d":           int(row.get("has_readme_30d", 0) or 0),
                "activity_total_30d":       int(row.get("activity_total_30d", 0) or 0),
                "has_pr_activity_30d":      int(row.get("has_pr_activity_30d", 0) or 0),
            },
        })
    return candidates


def write_json_report(path: Path, args, raw_path: Path, features_path: Path,
                      candidates: list[dict[str, Any]], mode: str):
    today = datetime.now(timezone.utc).date()
    raw_name = raw_path.name.replace("_strict_tmp", "_strict")
    features_name = features_path.name.replace("_strict_tmp", "")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "framing": "candidate_shortlist_not_verified_prediction",
        "window": {
            "days_min": args.days_min,
            "days_max": args.days_max,
            "created_start": (today - timedelta(days=args.days_max)).isoformat(),
            "created_end": (today - timedelta(days=args.days_min)).isoformat(),
        },
        "inputs": {
            "raw_jsonl": raw_name,
            "features_csv": features_name,
            "artifacts_dir": "data/model_artifacts",
        },
        "candidates": candidates,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def esc(value: Any) -> str:
    return html.escape(str(value))


def write_html_report(path: Path, json_payload: dict[str, Any]):
    rows = []
    for item in json_payload["candidates"]:
        reasons = "".join(f"<li>{esc(r)}</li>" for r in item["reasons"])
        risks = "".join(f"<li>{esc(r)}</li>" for r in item["risks"]) or "<li>No major risk flagged by heuristics.</li>"
        rows.append(f"""
        <article class="candidate">
          <div class="rank">#{item['rank']}</div>
          <div class="main">
            <h3><a href="{esc(item['url'])}" target="_blank">{esc(item['full_name'])}</a></h3>
            <p class="meta">{esc(item['language'])} · {esc(item['created_at'])} · current stars {item['current_stars']}</p>
            <div class="score">Attention Score <strong>{item['attention_score']:.3f}</strong> · action <strong>{esc(item['action'])}</strong></div>
            <div class="cols">
              <div><h4>Why Watch</h4><ul>{reasons}</ul></div>
              <div><h4>Risks</h4><ul>{risks}</ul></div>
            </div>
          </div>
        </article>
        """)

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenClaw Today Radar</title>
<style>
body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:#f6f8fa; color:#1f2328; line-height:1.6; }}
main {{ max-width:980px; margin:0 auto; padding:36px 24px 80px; }}
h1 {{ margin:0; font-size:30px; color:#0d1117; }}
.sub {{ color:#656d76; margin:6px 0 24px; }}
.note {{ background:#ddf4ff; border:1px solid #80ccff; border-radius:10px; padding:14px 18px; color:#0969da; margin-bottom:18px; }}
.candidate {{ display:flex; gap:18px; background:#ffffff; border:1px solid #d0d7de; border-radius:12px; padding:18px 20px; margin:14px 0; box-shadow:0 1px 0 rgba(31,35,40,0.04); }}
.rank {{ width:48px; height:48px; border-radius:50%; background:#dbeafe; color:#0969da; display:flex; align-items:center; justify-content:center; font-weight:800; flex-shrink:0; }}
.main {{ flex:1; min-width:0; }}
h3 {{ margin:0 0 2px; font-size:19px; }}
a {{ color:#0969da; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.meta {{ color:#656d76; margin:0 0 8px; font-size:14px; }}
.score {{ color:#1f2328; margin:8px 0 12px; }}
.score strong {{ color:#1a7f37; }}
.cols {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
h4 {{ margin:0 0 6px; color:#57606a; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
ul {{ margin:0; padding-left:18px; color:#24292f; font-size:14px; }}
li {{ margin:4px 0; }}
footer {{ margin-top:32px; color:#8c959f; text-align:center; font-size:13px; }}
@media (max-width:720px) {{ .candidate {{ flex-direction:column; }} .cols {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<main>
  <h1>OpenClaw Today Radar</h1>
  <p class="sub">Generated at {esc(json_payload['generated_at'])} · Mode: {esc(json_payload['mode'])}</p>
  <div class="note">
    This is a candidate shortlist, not a verified prediction. The model applies historical early-signal patterns to recent repositories that have completed an early observation window.
  </div>
  {''.join(rows) if rows else '<p>No candidates available.</p>'}
  <footer>openclaw-project · Today Radar</footer>
</main>
</body>
</html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--days-min", type=int, default=30)
    parser.add_argument("--days-max", type=int, default=45)
    parser.add_argument("--language-quota", default="")
    parser.add_argument("--ts-broad", action="store_true")
    parser.add_argument("--input-jsonl", default="", help="Score an existing JSONL instead of collecting live repos")
    parser.add_argument("--raw-out", default=str(DATA_DIR / "today_repos_raw.jsonl"))
    parser.add_argument("--features-out", default=str(DATA_DIR / "today_features.csv"))
    parser.add_argument("--json-out", default=str(REPORTS_DIR / "today_radar.json"))
    parser.add_argument("--html-out", default=str(REPORTS_DIR / "today_radar.html"))
    parser.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir).expanduser()
    features_path = Path(args.features_out).expanduser()

    mode = "live_recent_window"
    if args.input_jsonl:
        raw_path = Path(args.input_jsonl).expanduser()
        if not raw_path.exists():
            raise SystemExit(f"[ERROR] input JSONL not found: {raw_path}")
        mode = "offline_existing_jsonl"
    else:
        raw_path = collect_recent_repos(args)

    run_feature_extractor(raw_path, features_path, artifacts_dir)
    print("[4/4] Scoring candidates with RF model...", flush=True)
    candidates = score_features(features_path, artifacts_dir, args.top_k)

    json_out = Path(args.json_out).expanduser()
    html_out = Path(args.html_out).expanduser()
    write_json_report(json_out, args, raw_path, features_path, candidates, mode)
    payload = json.loads(json_out.read_text())
    write_html_report(html_out, payload)

    print(f"Today Radar JSON → {json_out}", flush=True)
    print(f"Today Radar HTML → {html_out}", flush=True)
    print(f"Candidates: {len(candidates)}", flush=True)
    for item in candidates[:5]:
        print(f"  #{item['rank']} {item['full_name']} score={item['attention_score']:.3f} action={item['action']}", flush=True)


if __name__ == "__main__":
    main()
