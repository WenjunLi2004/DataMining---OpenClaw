#!/usr/bin/env python3
"""
Build fact-only diagnostics for OpenClaw.

Input:
  - model_results.json
  - features.csv

Output:
  - diagnostic_summary.json

This script deliberately avoids narrative conclusions. It computes the facts
that an LLM analyst is allowed to cite.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score


DEFAULT_RESULTS = Path.home() / "openclaw-project/data/model_results.json"
DEFAULT_FEATURES = Path.home() / "openclaw-project/data/features.csv"
DEFAULT_OUTPUT = Path.home() / "openclaw-project/data/diagnostic_summary.json"

META_COLS = {
    "is_top20", "_created_at", "_full_name", "_language", "_current_stars",
    "_batch", "_readme_source", "_contributors_source",
}
BASELINE_FEATURES = [
    ("readme_len_30d", "30-day README length ranking"),
    ("commits_30d", "first-30-day commit count ranking"),
    ("contributors_30d", "first-30-day distinct commit-author count ranking"),
    ("issues_30d", "first-30-day issues ranking"),
    ("prs_30d", "first-30-day PR ranking"),
    ("activity_total_30d", "first-30-day total activity ranking"),
]


def _metric_value(d: dict[str, Any], key: str) -> float | None:
    value = d.get(key)
    if isinstance(value, dict):
        value = value.get("mean")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _std_value(d: dict[str, Any], key: str) -> float | None:
    value = d.get(key)
    if not isinstance(value, dict):
        return None
    std = value.get("std")
    try:
        return float(std)
    except (TypeError, ValueError):
        return None


def _round(value: Any, ndigits: int = 6) -> Any:
    if value is None:
        return None
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return None
        return round(float(value), ndigits)
    return value


def _precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float | None:
    if len(y_true) < k:
        return None
    idx = np.argsort(scores)[::-1][:k]
    return float(y_true[idx].sum() / k)


def _safe_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2 or len(np.unique(scores)) < 2:
        return None
    try:
        return float(roc_auc_score(y_true, scores))
    except ValueError:
        return None


def _safe_pr_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    if len(np.unique(y_true)) < 2 or len(np.unique(scores)) < 2:
        return None
    try:
        return float(average_precision_score(y_true, scores))
    except ValueError:
        return None


def build_task_summary(df: pd.DataFrame) -> dict[str, Any]:
    y = df["is_top20"].astype(int)
    pos = int(y.sum())
    n = int(len(df))
    threshold = None
    if "_current_stars" in df.columns and pos:
        threshold = int(df.loc[y == 1, "_current_stars"].min())

    language_counts = {}
    if "_language" in df.columns:
        language_counts = {
            str(lang): int(count)
            for lang, count in df["_language"].fillna("Unknown").value_counts().sort_index().items()
        }

    return {
        "mode": "historical_backtest",
        "positioning": (
            "Course-level historical backtest: use repository early-window signals "
            "to predict whether a repo lands in the sample top 20% by current stars."
        ),
        "not_a_claim": (
            "This does not prove real-time discovery of today's future hits; a Today Radar "
            "mode should be framed as candidate shortlisting only."
        ),
        "label": "is_top20",
        "label_definition": "1 if _current_stars is at or above the sample p80 threshold",
        "top20_threshold_current_stars": threshold,
        "n_samples": n,
        "n_positive": pos,
        "n_negative": int(n - pos),
        "positive_rate": _round(pos / n if n else None, 4),
        "language_counts": language_counts,
        "snapshot_window_days": 30,
        "known_caveats": [
            "model uses 19 strict 30-day features; current-state fields (author followers/repos, has_license, current README, current contributors) are excluded",
            "TypeScript has a small N500 sample and language-level conclusions should be weak",
            "current_stars is a historical backtest label, not a live future label",
        ],
    }


def build_model_summary(results: dict[str, Any]) -> dict[str, Any]:
    models = results.get("models", {})
    metrics: dict[str, Any] = {}
    for name, data in models.items():
        metrics[name] = {
            "auc": _round(_metric_value(data, "auc")),
            "auc_std": _round(_std_value(data, "auc")),
            "pr_auc": _round(_metric_value(data, "pr_auc")),
            "pr_auc_std": _round(_std_value(data, "pr_auc")),
            "f1": _round(_metric_value(data, "f1")),
            "precision": _round(_metric_value(data, "precision")),
            "recall": _round(_metric_value(data, "recall")),
            "accuracy": _round(_metric_value(data, "accuracy")),
            "precision_at_10": _round(data.get("precision_at_10")),
            "precision_at_20": _round(data.get("precision_at_20")),
        }

    def best_by(key: str) -> dict[str, Any] | None:
        candidates = [(name, vals.get(key)) for name, vals in metrics.items()]
        candidates = [(n, v) for n, v in candidates if v is not None]
        if not candidates:
            return None
        name, value = max(candidates, key=lambda item: item[1])
        return {"model": name, "value": value}

    tradeoffs = {}
    recalls = {n: v.get("recall") for n, v in metrics.items() if v.get("recall") is not None}
    precisions = {n: v.get("precision") for n, v in metrics.items() if v.get("precision") is not None}
    best_recall = max(recalls.values()) if recalls else None
    best_precision = max(precisions.values()) if precisions else None
    for name, vals in metrics.items():
        precision = vals.get("precision")
        recall = vals.get("recall")
        p10 = vals.get("precision_at_10")
        tradeoffs[name] = {
            "high_precision_low_recall": (
                precision is not None and recall is not None
                and best_precision is not None and best_recall is not None
                and precision >= best_precision - 0.05
                and recall <= best_recall - 0.20
            ),
            "good_for_shortlist": p10 is not None and p10 >= 0.7,
            "precision_minus_recall": _round(precision - recall if precision is not None and recall is not None else None),
            "details": (
                f"precision={precision:.3f}, recall={recall:.3f}, p@10={p10:.2f}"
                if precision is not None and recall is not None and p10 is not None
                else "insufficient metric data"
            ),
        }

    return {
        "metrics": metrics,
        "best_auc": best_by("auc"),
        "best_pr_auc": best_by("pr_auc"),
        "best_f1": best_by("f1"),
        "best_p10": best_by("precision_at_10"),
        "tradeoffs": tradeoffs,
    }


def build_baselines(df: pd.DataFrame) -> dict[str, Any]:
    y = df["is_top20"].astype(int).to_numpy()
    baselines: dict[str, Any] = {
        "random_positive_rate": {
            "auc": 0.5,
            "precision_at_10": _round(float(y.mean()) if len(y) else None),
            "precision_at_20": _round(float(y.mean()) if len(y) else None),
            "note": "expected random ranking baseline equals positive rate for P@K",
        }
    }
    for col, label in BASELINE_FEATURES:
        if col not in df.columns:
            continue
        scores = pd.to_numeric(df[col], errors="coerce").fillna(0).to_numpy(dtype=float)
        baselines[col] = {
            "label": label,
            "feature": col,
            "direction": "higher_is_better",
            "auc": _round(_safe_auc(y, scores)),
            "pr_auc": _round(_safe_pr_auc(y, scores)),
            "precision_at_10": _round(_precision_at_k(y, scores, 10)),
            "precision_at_20": _round(_precision_at_k(y, scores, 20)),
        }

    scored = [
        (name, vals.get("auc"))
        for name, vals in baselines.items()
        if name != "random_positive_rate" and vals.get("auc") is not None
    ]
    best = None
    if scored:
        name, auc = max(scored, key=lambda item: item[1])
        best = {"name": name, "auc": auc}
    return {"rankers": baselines, "best_single_feature_auc": best}


def build_language_summary(df: pd.DataFrame, results: dict[str, Any]) -> dict[str, Any]:
    if "_language" not in df.columns:
        return {}
    y = df["is_top20"].astype(int)
    global_rate = float(y.mean())
    lang_auc = results.get("language_auc", {})
    per_lang: dict[str, Any] = {}
    for lang, group in df.groupby("_language", dropna=False):
        lang_name = str(lang)
        y_lang = group["is_top20"].astype(int)
        auc_data = lang_auc.get(lang_name, {})
        per_lang[lang_name] = {
            "n_samples": int(len(group)),
            "n_positive": int(y_lang.sum()),
            "positive_rate": _round(float(y_lang.mean()), 4),
            "positive_rate_vs_global": _round(float(y_lang.mean() - global_rate), 4),
            "auc": _round(auc_data.get("auc")),
            "auc_std": _round(auc_data.get("auc_std")),
            "note": auc_data.get("note"),
        }

    aucs = [v["auc"] for v in per_lang.values() if v.get("auc") is not None]
    mean_auc = float(np.mean(aucs)) if aucs else None
    anomaly = None
    if aucs:
        candidates = [
            (lang, vals)
            for lang, vals in per_lang.items()
            if vals.get("auc") is not None and vals.get("n_samples", 0) >= 50
        ]
        if candidates:
            lang, vals = min(candidates, key=lambda item: item[1]["auc"])
            anomaly = {
                "language": lang,
                "reason": "lowest reliable per-language AUC",
                "auc": vals["auc"],
                "positive_rate": vals["positive_rate"],
                "positive_rate_vs_global": vals["positive_rate_vs_global"],
                "auc_drop_below_language_mean": _round(mean_auc - vals["auc"] if mean_auc is not None else None),
            }

    return {
        "global_positive_rate": _round(global_rate, 4),
        "languages": per_lang,
        "mean_auc_available_languages": _round(mean_auc),
        "anomaly": anomaly,
    }


def build_feature_summary(results: dict[str, Any]) -> dict[str, Any]:
    importance = results.get("feature_importance", {})
    rf = importance.get("RF", [])[:10]
    xgb = importance.get("XGBoost", [])[:10]
    lr = importance.get("LR", [])[:10]
    shap_top = results.get("shap", {}).get("top10", [])[:10]

    rf_top5 = {item.get("feature") for item in rf[:5]}
    shap_top5 = {item.get("feature") for item in shap_top[:5]}
    disagreements = []
    if rf_top5 and shap_top5:
        only_rf = sorted(f for f in rf_top5 - shap_top5 if f)
        only_shap = sorted(f for f in shap_top5 - rf_top5 if f)
        if only_rf:
            disagreements.append(f"RF Gini top-5 only: {', '.join(only_rf)}")
        if only_shap:
            disagreements.append(f"SHAP top-5 only: {', '.join(only_shap)}")

    return {
        "top10_gini": rf,
        "top10_shap": shap_top,
        "top10_xgboost": xgb,
        "top10_lr_abs_coef": lr,
        "disagreements": disagreements,
        "interpretation_warning": "Gini can over-weight continuous numeric features; SHAP is safer for interpretation.",
    }


def build_correlations(df: pd.DataFrame) -> dict[str, Any]:
    numeric_cols = [
        c for c in df.columns
        if c not in META_COLS and pd.api.types.is_numeric_dtype(df[c])
    ]
    corr = df[numeric_cols].corr(numeric_only=True) if numeric_cols else pd.DataFrame()
    readme_commit = None
    if "readme_len_30d" in corr.index and "commits_30d" in corr.columns:
        readme_commit = float(corr.loc["readme_len_30d", "commits_30d"])

    pairs = []
    for i, col_a in enumerate(numeric_cols):
        for col_b in numeric_cols[i + 1:]:
            value = corr.loc[col_a, col_b]
            if pd.isna(value):
                continue
            if abs(value) >= 0.45:
                pairs.append({"pair": [col_a, col_b], "value": _round(float(value))})
    pairs.sort(key=lambda item: abs(item["value"]), reverse=True)
    return {
        "readme_len_30d_vs_commits_30d": _round(readme_commit),
        "high_correlations_abs_ge_0_45": pairs[:20],
    }


def build_ablation_summary(results: dict[str, Any]) -> dict[str, Any]:
    ablation = results.get("ablation", {})
    if not ablation:
        return {}
    keys = list(ablation.keys())
    groups = []
    jumps = []
    prev_auc = None
    prev_key = None
    for key in keys:
        data = ablation[key]
        auc = _metric_value(data, "auc")
        groups.append({
            "id": key,
            "label": data.get("label", key),
            "n_features": data.get("n_features"),
            "auc": _round(auc),
            "f1": _round(_metric_value(data, "f1")),
            "precision": _round(_metric_value(data, "precision")),
            "recall": _round(_metric_value(data, "recall")),
        })
        if prev_auc is not None and auc is not None:
            jumps.append({
                "from": prev_key,
                "to": key,
                "delta_auc": _round(auc - prev_auc),
            })
        prev_auc = auc
        prev_key = key

    positive_jumps = [j for j in jumps if j["delta_auc"] is not None]
    biggest = max(positive_jumps, key=lambda item: item["delta_auc"]) if positive_jumps else None
    smallest = min(positive_jumps, key=lambda item: item["delta_auc"]) if positive_jumps else None
    hint = None
    if biggest:
        if biggest["to"] == "B_activity":
            hint = "early_activity_dominant"
        elif biggest["to"] == "C_readme":
            hint = "historical_readme_dominant"
        elif biggest["to"] == "D_all":
            hint = "derived_features_dominant"
        else:
            hint = "language_owner_dominant"

    return {
        "groups": groups,
        "jumps": jumps,
        "biggest_jump": biggest,
        "smallest_jump": smallest,
        "interpretation_hint": hint,
    }


def build_validation_summary(results: dict[str, Any]) -> dict[str, Any]:
    time_split = results.get("time_split") or {}
    if not time_split:
        return {"time_split": None}
    metrics = time_split.get("metrics", {})
    return {
        "time_split": {
            "model": time_split.get("model"),
            "train_size": time_split.get("train_size"),
            "test_size": time_split.get("test_size"),
            "split_date": time_split.get("split_date"),
            "test_positive_rate": _round(time_split.get("test_positive_rate")),
            "auc": _round(metrics.get("auc")),
            "pr_auc": _round(metrics.get("pr_auc")),
            "f1": _round(metrics.get("f1")),
            "precision_at_10": _round(metrics.get("precision_at_10")),
            "precision_at_20": _round(metrics.get("precision_at_20")),
            "random_cv_auc": _round(time_split.get("random_cv_auc")),
            "auc_gap": _round(time_split.get("auc_gap")),
        }
    }


def build_anomalies(summary: dict[str, Any]) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    task = summary.get("task", {})
    per_language = summary.get("per_language", {})
    langs = per_language.get("languages", {})
    py = langs.get("Python")
    if py and py.get("positive_rate_vs_global") is not None and py["positive_rate_vs_global"] >= 0.2:
        anomalies.append({
            "severity": "medium",
            "title": "Python subset has much higher positive rate than global",
            "evidence": py,
            "implication": "Per-language Python AUC may be depressed by class distribution shift and within-language homogeneity.",
        })
    ts = langs.get("TypeScript")
    if ts and ts.get("n_samples", 0) < 50:
        anomalies.append({
            "severity": "medium",
            "title": "TypeScript sample is small",
            "evidence": ts,
            "implication": "Do not make strong TypeScript-specific conclusions from N500.",
        })
    correlations = summary.get("feature_correlations", {}).get("high_correlations_abs_ge_0_45", [])
    if correlations:
        anomalies.append({
            "severity": "low",
            "title": "Some features are strongly correlated",
            "evidence": correlations[:5],
            "implication": "Feature importance should be interpreted as model attribution, not causal attribution.",
        })
    # Surface approximate-mode rows (collected before strict-30d collector update).
    feature_provenance = summary.get("feature_provenance") or {}
    approx_readme = feature_provenance.get("readme_approx_count") or 0
    approx_contrib = feature_provenance.get("contributors_approx_count") or 0
    if approx_readme or approx_contrib:
        anomalies.append({
            "severity": "medium",
            "title": "Some rows used approximate (non-strict-30d) README/contributors features",
            "evidence": {
                "readme_approx_count": approx_readme,
                "contributors_approx_count": approx_contrib,
            },
            "implication": (
                "These rows substituted current-state values for historical 30d values. "
                "Recollect the raw data with the updated collector to obtain fully strict-30d features."
            ),
        })
    validation = summary.get("validation", {}).get("time_split")
    if validation and validation.get("auc_gap") is not None and abs(validation["auc_gap"]) > 0.05:
        anomalies.append({
            "severity": "high",
            "title": "Time-split and random-CV AUC diverge",
            "evidence": validation,
            "implication": "Random k-fold CV may be optimistic for deployment-style evaluation.",
        })
    return anomalies


def build_recommendations(summary: dict[str, Any]) -> list[dict[str, str]]:
    recs = [
        {
            "priority": "P0",
            "action": "Keep the default experiment as a fixed historical backtest.",
            "reason": "It avoids unstable live labels and makes course evaluation reproducible.",
        },
        {
            "priority": "P0",
            "action": "Present Today Radar, if used, as a candidate shortlist rather than verified prediction.",
            "reason": "Recent repositories do not yet have future labels.",
        },
        {
            "priority": "P1",
            "action": "Compare model ranking against simple single-feature baselines.",
            "reason": "This shows whether the ML pipeline beats simple heuristics.",
        },
        {
            "priority": "P1",
            "action": "Verify that raw data was collected with the strict-30d collector (v2+).",
            "reason": "The 19-feature model assumes all features are bounded to the first 30 days; approximate values reduce model validity.",
        },
        {
            "priority": "P2",
            "action": "Treat TypeScript and per-language results as caveated unless more samples are collected.",
            "reason": "N500 TypeScript count is small.",
        },
    ]
    baselines = summary.get("baselines", {}).get("best_single_feature_auc")
    best_auc = summary.get("models", {}).get("best_auc")
    if baselines and best_auc and baselines.get("auc") is not None and best_auc.get("value") is not None:
        if best_auc["value"] - baselines["auc"] < 0.03:
            recs.append({
                "priority": "P1",
                "action": "Investigate why the best model only slightly beats the best simple baseline.",
                "reason": "A small gap weakens the case for complex modeling.",
            })
    return recs


def build_feature_provenance(df: pd.DataFrame) -> dict[str, Any]:
    """Count rows with strict-30d vs approximate (non-30d) feature values."""
    n = len(df)
    readme_approx = 0
    contributors_approx = 0
    if "_readme_source" in df.columns:
        readme_approx = int((df["_readme_source"] == "legacy_fallback").sum())
    if "_contributors_source" in df.columns:
        contributors_approx = int((df["_contributors_source"] == "legacy_fallback").sum())
    return {
        "n_rows": n,
        "readme_approx_count": readme_approx,
        "readme_strict_30d_count": n - readme_approx,
        "contributors_approx_count": contributors_approx,
        "contributors_strict_30d_count": n - contributors_approx,
        "all_strict_30d": readme_approx == 0 and contributors_approx == 0,
    }


def build_summary(results: dict[str, Any], df: pd.DataFrame, results_path: Path, features_path: Path) -> dict[str, Any]:
    def display_path(path: Path) -> str:
        try:
            return str(path.relative_to(Path.cwd()))
        except ValueError:
            return str(path)

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "model_results": display_path(results_path),
            "features": display_path(features_path),
        },
        "task": build_task_summary(df),
        "models": build_model_summary(results),
        "baselines": build_baselines(df),
        "per_language": build_language_summary(df, results),
        "feature_importance": build_feature_summary(results),
        "feature_correlations": build_correlations(df),
        "ablation": build_ablation_summary(results),
        "validation": build_validation_summary(results),
        "feature_provenance": build_feature_provenance(df),
    }
    summary["anomalies"] = build_anomalies(summary)
    summary["recommendations"] = build_recommendations(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--features", default=str(DEFAULT_FEATURES))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    results_path = Path(args.results).expanduser()
    features_path = Path(args.features).expanduser()
    output_path = Path(args.output).expanduser()

    if not results_path.exists():
        raise SystemExit(f"[ERROR] model results not found: {results_path}")
    if not features_path.exists():
        raise SystemExit(f"[ERROR] features file not found: {features_path}")

    results = json.loads(results_path.read_text())
    df = pd.read_csv(features_path)
    if "is_top20" not in df.columns:
        raise SystemExit(f"[ERROR] is_top20 column not found in {features_path}")

    summary = build_summary(results, df, results_path, features_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    best_auc = summary["models"]["best_auc"]
    best_baseline = summary["baselines"]["best_single_feature_auc"]
    print(f"Diagnostic summary written → {output_path}", flush=True)
    if best_auc:
        print(f"  best model AUC: {best_auc['model']}={best_auc['value']:.4f}", flush=True)
    if best_baseline:
        print(f"  best baseline AUC: {best_baseline['name']}={best_baseline['auc']:.4f}", flush=True)
    print(f"  anomalies: {len(summary['anomalies'])}", flush=True)


if __name__ == "__main__":
    main()
