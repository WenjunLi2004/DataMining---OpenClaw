#!/usr/bin/env python3
"""
Pipeline state inspector — pure facts, no judgments.
Outputs JSON to stdout. Called by the orchestrator before any decision.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path.home() / "openclaw-project"
DATA_DIR    = PROJECT_DIR / "data"
REPORTS_DIR = PROJECT_DIR / "reports"


def _file_info(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    stat  = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    age_s = (datetime.now(timezone.utc) - mtime).total_seconds()
    return {
        "exists":    True,
        "path":      str(path),
        "mtime_iso": mtime.isoformat(),
        "age_days":  round(age_s / 86400, 2),
        "size_bytes": stat.st_size,
    }


def _count_jsonl(path: Path) -> int:
    try:
        with open(path) as f:
            return sum(1 for ln in f if ln.strip())
    except Exception:
        return -1


def inspect_raw():
    info = _file_info(DATA_DIR / "repos_raw_500_strict.jsonl")
    if info["exists"]:
        info["record_count"] = _count_jsonl(DATA_DIR / "repos_raw_500_strict.jsonl")
    return info


def inspect_features():
    raw_path  = DATA_DIR / "repos_raw_500_strict.jsonl"
    feat_path = DATA_DIR / "features.csv"
    info = _file_info(feat_path)
    if info["exists"] and raw_path.exists():
        info["newer_than_raw"] = feat_path.stat().st_mtime > raw_path.stat().st_mtime
    return info


def inspect_model_results():
    feat_path  = DATA_DIR / "features.csv"
    model_path = DATA_DIR / "model_results.json"
    info = _file_info(model_path)
    if info["exists"]:
        try:
            data = json.loads(model_path.read_text())
            info["models"]            = list(data.get("models", {}).keys())
            info["has_ablation"]      = bool(data.get("ablation"))
            info["has_shap"]          = bool(data.get("shap"))
            info["has_time_split"]    = bool(data.get("time_split"))
            if feat_path.exists():
                info["newer_than_features"] = (
                    model_path.stat().st_mtime > feat_path.stat().st_mtime
                )
        except Exception as e:
            info["parse_error"] = str(e)
    return info


def inspect_diagnostic_summary():
    feat_path  = DATA_DIR / "features.csv"
    model_path = DATA_DIR / "model_results.json"
    diag_path  = DATA_DIR / "diagnostic_summary.json"
    info = _file_info(diag_path)
    if info["exists"]:
        if model_path.exists():
            info["newer_than_model_results"] = diag_path.stat().st_mtime > model_path.stat().st_mtime
        if feat_path.exists():
            info["newer_than_features"] = diag_path.stat().st_mtime > feat_path.stat().st_mtime
        try:
            data = json.loads(diag_path.read_text())
            info["has_baselines"] = bool(data.get("baselines"))
            info["has_anomalies"] = bool(data.get("anomalies"))
            info["anomaly_count"] = len(data.get("anomalies", []))
            info["best_auc"] = data.get("models", {}).get("best_auc")
        except Exception as e:
            info["parse_error"] = str(e)
    return info


def inspect_insights():
    diag_path = DATA_DIR / "diagnostic_summary.json"
    insights_path = REPORTS_DIR / "INSIGHTS.md"
    info = _file_info(insights_path)
    if info["exists"]:
        if diag_path.exists():
            info["newer_than_diagnostic"] = insights_path.stat().st_mtime > diag_path.stat().st_mtime
        try:
            text = insights_path.read_text()
            info["section_count"] = text.count("\n## ")
            info["has_required_sections"] = all(
                marker in text for marker in [
                    "## 1. 实验结论",
                    "## 2. 模型行为解释",
                    "## 3. 数据集问题诊断",
                    "## 4. 真正有意义的特征",
                    "## 5. 不能过度相信的结论",
                    "## 6. 下一步实验建议",
                    "## 7. 可追问问题",
                ]
            )
        except Exception as e:
            info["parse_error"] = str(e)
    return info


def inspect_error_analysis():
    model_path = DATA_DIR / "model_results.json"
    error_path = DATA_DIR / "error_analysis.json"
    info = _file_info(error_path)
    if info["exists"]:
        if model_path.exists():
            info["newer_than_model_results"] = error_path.stat().st_mtime > model_path.stat().st_mtime
        try:
            data = json.loads(error_path.read_text())
            info["fp_count"] = len(data.get("fp_cases", []))
            info["fn_count"] = len(data.get("fn_cases", []))
            info["used_llm"] = data.get("used_llm")
        except Exception as e:
            info["parse_error"] = str(e)

    html_path = REPORTS_DIR / "error_analysis.html"
    html_info = _file_info(html_path)
    if html_info["exists"] and model_path.exists():
        html_info["newer_than_model_results"] = html_path.stat().st_mtime > model_path.stat().st_mtime
    info["html"] = html_info
    return info


def inspect_today_radar():
    path = REPORTS_DIR / "today_radar.json"
    info = _file_info(path)
    if info["exists"]:
        try:
            data = json.loads(path.read_text())
            info["mode"] = data.get("mode")
            info["candidate_count"] = len(data.get("candidates", []))
            info["generated_at"] = data.get("generated_at")
            if data.get("candidates"):
                info["top_candidate"] = data["candidates"][0].get("full_name")
                info["top_score"] = data["candidates"][0].get("attention_score")
        except Exception as e:
            info["parse_error"] = str(e)
    html_info = _file_info(REPORTS_DIR / "today_radar.html")
    info["html"] = html_info
    return info


def inspect_reports():
    """latest_report = canonical analysis report.

    Picks the stable alias `reports/latest_final.html` if present so the
    orchestrator's decision log keeps pointing at the historical-backtest
    HTML even after auxiliary files (insights.html / today_radar.html /
    modification summaries) are written and end up with newer mtimes.

    If `latest_final.html` is missing we fall back to the most recent HTML
    in `reports/`, ignoring known auxiliary files (insights.html,
    today_radar.html, *_modification_summary.html) so they cannot steal
    the slot.
    """
    if not REPORTS_DIR.exists():
        return {"exists": False, "latest_report": None, "total_reports": 0}

    all_reports = sorted(REPORTS_DIR.glob("*.html"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    total = len(all_reports)
    if total == 0:
        return {"exists": True, "latest_report": None, "total_reports": 0}

    AUX_NAMES = {"insights.html", "today_radar.html", "error_analysis.html", "llm_comparison.html"}
    AUX_SUFFIXES = ("_modification_summary.html",)

    def is_auxiliary(p: Path) -> bool:
        return p.name in AUX_NAMES or p.name.endswith(AUX_SUFFIXES)

    canonical = REPORTS_DIR / "latest_final.html"
    if canonical.exists():
        latest = canonical
        source = "latest_final_alias"
    else:
        non_aux = [p for p in all_reports if not is_auxiliary(p)]
        latest = non_aux[0] if non_aux else all_reports[0]
        source = "mtime_fallback"

    mtime = datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
    return {
        "exists":              True,
        "latest_report":       latest.name,
        "latest_report_path":  str(latest),
        "latest_report_source": source,
        "latest_mtime_iso":    mtime.isoformat(),
        "latest_age_days":     round(
            (datetime.now(timezone.utc) - mtime).total_seconds() / 86400, 2
        ),
        "total_reports":       total,
    }


def main():
    state = {
        "checked_at":    datetime.now(timezone.utc).isoformat(),
        "raw_data":      inspect_raw(),
        "features":      inspect_features(),
        "model_results": inspect_model_results(),
        "diagnostic_summary": inspect_diagnostic_summary(),
        "insights":      inspect_insights(),
        "error_analysis": inspect_error_analysis(),
        "today_radar":   inspect_today_radar(),
        "reports":       inspect_reports(),
    }
    print(json.dumps(state, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
