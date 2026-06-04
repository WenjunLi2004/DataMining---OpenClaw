#!/usr/bin/env python3
"""
Train LR / RF / XGBoost on features.csv, output model_results.json.
Input:  ~/openclaw-project/data/features.csv  (or --input)
Output: ~/openclaw-project/data/model_results.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from typing import List
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    roc_auc_score, average_precision_score,
    f1_score, precision_score, recall_score, accuracy_score
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier, XGBRegressor


CV_FOLDS = 5
RANDOM_STATE = 42

# Columns that are metadata, not features (excluded from X). Mirrors the
# extractor's META_COLS so any column starting with "_" is also dropped.
META_COLS = {
    "is_top20", "_created_at", "_full_name", "_language", "_current_stars",
    "_batch", "_readme_source", "_contributors_source",
}

# ---------------------------------------------------------------------------
# Ablation feature groups (aligned to the 19-feature strict-30d schema)
# ---------------------------------------------------------------------------

# Group A: language one-hot + owner type only (7 features). The weakest
# baseline — can language alone separate top vs not-top?
_GROUP_A = [
    "lang_Python", "lang_JavaScript", "lang_Go", "lang_Rust",
    "lang_TypeScript", "lang_Other", "is_org",
]

# Group B: A + raw 30-day activity counts (11 features).
_GROUP_B = _GROUP_A + [
    "commits_30d", "issues_30d", "prs_30d", "contributors_30d",
]

# Group C: B + historical README signals (15 features).
_GROUP_C = _GROUP_B + [
    "has_readme_30d", "readme_len_30d",
    "readme_has_image_30d", "readme_has_demo_url_30d",
]

# Group D: full 19-feature set (C + derived activity).  None ⇒ use all model
# features detected at runtime (excludes emb_ columns even if present).
# Group E: D + DeepSeek embedding features (emb_0..emb_7).
#   Only included when emb_ columns are detected in the CSV.
ABLATION_GROUPS = {
    "A_basic":    ("A: Language + Owner",                          _GROUP_A),
    "B_activity": ("B: A + Early Activity (30d)",                  _GROUP_B),
    "C_readme":   ("C: B + Historical README (30d)",               _GROUP_C),
    "D_all":      ("D: All 19 Features (+ Derived)",               None),
    # E_embed is added dynamically in run_ablation() if emb_ columns exist
}


def load_data(path: Path):
    df = pd.read_csv(path)
    if "is_top20" not in df.columns:
        print(f"[ERROR] 'is_top20' column not found in {path}", flush=True)
        sys.exit(1)
    # Drop any meta column or any column starting with "_" so we never train
    # on metadata-source flags like _readme_source / _contributors_source.
    feature_names = [
        c for c in df.columns
        if c not in META_COLS and not c.startswith("_")
    ]
    X = df[feature_names].values
    y = df["is_top20"].values
    return X, y, feature_names, df


def precision_at_k(y_true, probs, k: int) -> float:
    top_k = np.argsort(probs)[::-1][:k]
    return float(y_true[top_k].sum() / k)


def cv_metrics(model, X, y) -> dict:
    """Basic CV metrics (used by ablation — no OOF collection needed)."""
    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    results = {"auc": [], "f1": [], "precision": [], "recall": [], "accuracy": []}

    for train_idx, val_idx in skf.split(X, y):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_val)
        y_prob = model.predict_proba(X_val)[:, 1]

        results["auc"].append(roc_auc_score(y_val, y_prob))
        results["f1"].append(f1_score(y_val, y_pred, zero_division=0))
        results["precision"].append(precision_score(y_val, y_pred, zero_division=0))
        results["recall"].append(recall_score(y_val, y_pred, zero_division=0))
        results["accuracy"].append(accuracy_score(y_val, y_pred))

    return {
        k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
        for k, v in results.items()
    }


def cv_metrics_with_oof(model, X, y):
    """Full CV: per-fold PR-AUC + OOF predicted probabilities for global P@K."""
    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    fold_results = {
        "auc": [], "pr_auc": [], "f1": [], "precision": [], "recall": [], "accuracy": []
    }
    oof_probs = np.zeros(len(y))

    for train_idx, val_idx in skf.split(X, y):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_val)
        y_prob = model.predict_proba(X_val)[:, 1]
        oof_probs[val_idx] = y_prob

        fold_results["auc"].append(roc_auc_score(y_val, y_prob))
        fold_results["pr_auc"].append(average_precision_score(y_val, y_prob))
        fold_results["f1"].append(f1_score(y_val, y_pred, zero_division=0))
        fold_results["precision"].append(precision_score(y_val, y_pred, zero_division=0))
        fold_results["recall"].append(recall_score(y_val, y_pred, zero_division=0))
        fold_results["accuracy"].append(accuracy_score(y_val, y_pred))

    metrics = {
        k: {"mean": float(np.mean(v)), "std": float(np.std(v))}
        for k, v in fold_results.items()
    }
    return metrics, oof_probs


def run_time_split(df: pd.DataFrame, y, feature_names: List[str], rf_cv_auc: float):
    """Train on first 80% (chronological), test on last 20%. RF only."""
    if "_created_at" not in df.columns:
        print("  [SKIP] _created_at missing — re-run feature-extractor first", flush=True)
        return None

    sorted_idx  = df["_created_at"].argsort().values
    split_point = int(len(sorted_idx) * 0.8)
    train_idx   = sorted_idx[:split_point]
    test_idx    = sorted_idx[split_point:]

    X = df[feature_names].values
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    rf = build_rf()
    rf.fit(X_train, y_train)
    y_prob = rf.predict_proba(X_test)[:, 1]
    y_pred = rf.predict(X_test)

    auc    = float(roc_auc_score(y_test, y_prob))
    pr_auc = float(average_precision_score(y_test, y_prob))
    f1val  = float(f1_score(y_test, y_pred, zero_division=0))
    p10    = precision_at_k(y_test, y_prob, 10)
    p20    = precision_at_k(y_test, y_prob, 20)

    sorted_dates = sorted(df["_created_at"].dropna().tolist())
    split_date   = sorted_dates[split_point][:10] if split_point < len(sorted_dates) else "unknown"

    print(f"  time-split AUC={auc:.4f}  PR-AUC={pr_auc:.4f}  F1={f1val:.4f}", flush=True)
    print(f"  vs random 5-fold AUC={rf_cv_auc:.4f}  gap={auc - rf_cv_auc:+.4f}", flush=True)

    return {
        "model":              "RF",
        "train_size":         int(len(train_idx)),
        "test_size":          int(len(test_idx)),
        "split_date":         split_date,
        "test_positive_rate": float(y_test.mean()),
        "metrics": {
            "auc":             auc,
            "pr_auc":          pr_auc,
            "f1":              f1val,
            "precision_at_10": p10,
            "precision_at_20": p20,
        },
        "random_cv_auc": rf_cv_auc,
        "auc_gap":       float(auc - rf_cv_auc),
    }


def feature_importance(model, feature_names: List[str], top_n: int = 10) -> List[dict]:
    if hasattr(model, "feature_importances_"):
        # RF / XGBoost — use last fitted estimator (inside Pipeline it's model[-1])
        est = model[-1] if hasattr(model, "__getitem__") else model
        importances = est.feature_importances_
    elif hasattr(model, "coef_"):
        est = model[-1] if hasattr(model, "__getitem__") else model
        importances = np.abs(est.coef_[0])
    else:
        return []

    idx = np.argsort(importances)[::-1][:top_n]
    return [
        {"feature": feature_names[i], "importance": float(importances[i])}
        for i in idx
    ]


def build_rf():
    return RandomForestClassifier(
        n_estimators=200, class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1
    )


def build_models():
    lr = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)),
    ])
    rf = build_rf()
    xgb = XGBClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=4,
        scale_pos_weight=4,  # ~4:1 negative:positive
        eval_metric="logloss",
        random_state=RANDOM_STATE,
        verbosity=0,
    )
    return {"LR": lr, "RF": rf, "XGBoost": xgb}


def run_ablation(df: pd.DataFrame, y) -> dict:
    """Run RF on each ablation feature group; return metrics dict keyed by group id."""
    # Separate base features (19) from embedding columns (emb_*)
    base_feature_cols = [
        c for c in df.columns
        if c not in META_COLS and not c.startswith("_") and not c.startswith("emb_")
    ]
    emb_cols = [c for c in df.columns if c.startswith("emb_")]

    groups = dict(ABLATION_GROUPS)
    # Dynamically add Group E when embedding columns are present
    if emb_cols:
        e_cols = base_feature_cols + emb_cols
        groups["E_embed"] = (
            f"E: D + DeepSeek Embedding ({len(emb_cols)}d)",
            e_cols,
        )

    results = {}
    for group_id, (label, col_list) in groups.items():
        if col_list is None:
            cols = base_feature_cols          # Group D: 19 base features only
        else:
            cols = [c for c in col_list if c in df.columns]

        X_group = df[cols].values
        rf = build_rf()
        metrics = cv_metrics(rf, X_group, y)
        results[group_id] = {
            "label":       label,
            "n_features":  len(cols),
            "features":    cols,
            **metrics,
        }
        auc = metrics["auc"]["mean"]
        f1  = metrics["f1"]["mean"]
        print(f"    {label:<48s}  n={len(cols):>2d}  AUC={auc:.4f}  F1={f1:.4f}", flush=True)

    return results


def run_language_auc(df: pd.DataFrame, y, feature_names: List[str]) -> dict:
    """Per-language RF AUC. Flags languages with < 30 samples as unreliable."""
    if "_language" not in df.columns:
        return {}

    LANGUAGES = ["Python", "Go", "Rust", "JavaScript", "TypeScript"]
    results = {}

    for lang in LANGUAGES:
        mask   = (df["_language"] == lang).values
        n      = int(mask.sum())
        y_lang = y[mask]
        n_pos  = int(y_lang.sum())

        if n < 30:
            results[lang] = {
                "n_samples": n, "n_positive": n_pos,
                "auc": None, "auc_std": None, "note": "insufficient_samples",
            }
            print(f"    {lang:<15s} n={n:>3d}  [insufficient samples, skipped]", flush=True)
            continue

        if n_pos == 0 or n_pos == n:
            results[lang] = {
                "n_samples": n, "n_positive": n_pos,
                "auc": None, "auc_std": None, "note": "single_class",
            }
            continue

        X_lang = df.loc[mask, feature_names].values
        n_folds = min(CV_FOLDS, n_pos, n - n_pos)   # never more folds than minority class
        n_folds = max(2, n_folds)
        skf     = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=RANDOM_STATE)

        aucs = []
        for tr_idx, val_idx in skf.split(X_lang, y_lang):
            rf = build_rf()
            rf.fit(X_lang[tr_idx], y_lang[tr_idx])
            # Skip fold if training or validation set is single-class
            if len(rf.classes_) < 2:
                continue
            if len(np.unique(y_lang[val_idx])) < 2:
                continue
            try:
                prob = rf.predict_proba(X_lang[val_idx])[:, 1]
                aucs.append(roc_auc_score(y_lang[val_idx], prob))
            except (ValueError, IndexError):
                pass

        note = "low_samples" if n < 50 else None
        if not aucs:
            note = "insufficient_samples"   # all folds skipped (single-class splits)
        entry = {
            "n_samples": n, "n_positive": n_pos, "n_folds": n_folds,
            "auc": float(np.mean(aucs)) if aucs else None,
            "auc_std": float(np.std(aucs)) if aucs else None,
            "note": note,
        }
        results[lang] = entry
        auc_str = f"{entry['auc']:.4f} ±{entry['auc_std']:.4f}" if entry["auc"] else "N/A"
        note_str = f"  [{note}]" if note else ""
        print(f"    {lang:<15s} n={n:>3d}  pos={n_pos:>2d}  AUC={auc_str}{note_str}", flush=True)

    return results


def run_shap(rf_model, X: np.ndarray, feature_names: List[str], n_samples: int = 300) -> dict:
    """Mean |SHAP| values for RF top-10 features using TreeExplainer."""
    try:
        import shap as _shap
    except ImportError:
        print("  [SKIP] shap not installed", flush=True)
        return {}

    rng = np.random.RandomState(RANDOM_STATE)
    idx = rng.choice(len(X), min(n_samples, len(X)), replace=False)
    X_sample = X[idx]

    explainer   = _shap.TreeExplainer(rf_model)
    shap_values = explainer.shap_values(X_sample)

    # Handle both list-of-arrays and 3-D array formats (SHAP version differences)
    if isinstance(shap_values, list):
        sv = shap_values[1] if len(shap_values) > 1 else shap_values[0]
    elif hasattr(shap_values, "ndim") and shap_values.ndim == 3:
        sv = shap_values[:, :, 1]
    else:
        sv = shap_values

    mean_abs = np.mean(np.abs(sv), axis=0)
    top_idx  = np.argsort(mean_abs)[::-1][:10]

    return {
        "n_samples": int(len(idx)),
        "top10": [
            {"feature": feature_names[i], "mean_abs_shap": float(mean_abs[i])}
            for i in top_idx
        ],
    }


def run_regression(df: pd.DataFrame, feature_names: List[str]) -> dict:
    """Ridge / RF / XGBoost regressor on log1p(current_stars), 5-fold CV."""
    from sklearn.linear_model import Ridge
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import KFold, cross_val_score

    if "_current_stars" not in df.columns:
        print("  [SKIP] _current_stars not in features — re-run feature-extractor", flush=True)
        return {}

    y_log = np.log1p(df["_current_stars"].values.astype(float))
    X     = df[feature_names].values
    kf    = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    reg_models: dict = {
        "Ridge":   Pipeline([("scaler", StandardScaler()), ("reg", Ridge(alpha=1.0))]),
        "RF":      RandomForestRegressor(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1),
        "XGBoost": XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=4,
                                random_state=RANDOM_STATE, verbosity=0),
    }

    model_results: dict = {}
    for name, model in reg_models.items():
        rmse = np.sqrt(-cross_val_score(model, X, y_log, cv=kf, scoring="neg_mean_squared_error"))
        mae  = -cross_val_score(model, X, y_log, cv=kf, scoring="neg_mean_absolute_error")
        r2   = cross_val_score(model, X, y_log, cv=kf, scoring="r2")
        model_results[name] = {
            "rmse_log1p": {"mean": round(float(rmse.mean()), 4), "std": round(float(rmse.std()), 4)},
            "mae_log1p":  {"mean": round(float(mae.mean()),  4), "std": round(float(mae.std()),  4)},
            "r2":         {"mean": round(float(r2.mean()),   4), "std": round(float(r2.std()),   4)},
        }
        print(f"  {name:<10} RMSE={rmse.mean():.4f}  MAE={mae.mean():.4f}  R²={r2.mean():.4f}", flush=True)

    best_r2 = max(model_results, key=lambda m: model_results[m]["r2"]["mean"])
    print(f"  Best R²: {best_r2} ({model_results[best_r2]['r2']['mean']:.4f})", flush=True)
    return {"models": model_results, "target": "log1p(current_stars)", "cv_folds": CV_FOLDS}


def run_clustering(df: pd.DataFrame, y, feature_names: List[str]) -> dict:
    """KMeans (k=4) on 19 features + PCA 2D scatter for visualization."""
    try:
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler as _SS
    except ImportError:
        print("  [SKIP] sklearn.cluster not available", flush=True)
        return {}

    X = df[feature_names].values
    scaler = _SS()
    X_scaled = scaler.fit_transform(X)

    k = 4
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=20, max_iter=300)
    labels = km.fit_predict(X_scaled)

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    X_2d = pca.fit_transform(X_scaled)

    key_features = ["commits_30d", "issues_30d", "prs_30d", "contributors_30d",
                    "readme_len_30d", "activity_total_30d"]

    clusters = []
    for c in range(k):
        mask = labels == c
        n = int(mask.sum())
        pos = int(y[mask].sum())
        feat_means = {}
        for feat in key_features:
            if feat in feature_names:
                idx = feature_names.index(feat)
                feat_means[feat] = round(float(X[mask, idx].mean()), 3)
        clusters.append({
            "id": c,
            "size": n,
            "positive_count": pos,
            "positive_rate": round(pos / n, 4) if n > 0 else 0.0,
            "feature_means": feat_means,
        })

    clusters.sort(key=lambda x: -x["positive_rate"])
    # Re-label by rank so cluster 0 = highest positive rate
    for rank, c in enumerate(clusters):
        c["id"] = rank

    scatter = [
        {"x": round(float(X_2d[i, 0]), 4), "y": round(float(X_2d[i, 1]), 4),
         "c": int(labels[i]), "t": int(y[i])}
        for i in range(len(y))
    ]

    result = {
        "k": k,
        "clusters": clusters,
        "scatter": scatter,
        "pca_variance_explained": [round(float(v), 4) for v in pca.explained_variance_ratio_],
    }
    rates = [f"{c['positive_rate']:.0%}" for c in clusters]
    sizes = [c["size"] for c in clusters]
    print(f"  KMeans k={k}: sizes={sizes}, positive_rates={rates}", flush=True)
    return result


def collect_oof_top10(df: pd.DataFrame, y, oof_probs: np.ndarray) -> List[dict]:
    """Return top-10 repos by OOF predicted probability with display metadata."""
    top_idx = np.argsort(oof_probs)[::-1][:10]
    results = []
    for rank, i in enumerate(top_idx, 1):
        results.append({
            "rank":          rank,
            "full_name":     str(df["_full_name"].iloc[i]) if "_full_name" in df.columns else f"repo_{i}",
            "language":      str(df["_language"].iloc[i]) if "_language" in df.columns else "unknown",
            "prob":          float(oof_probs[i]),
            "current_stars": int(df["_current_stars"].iloc[i]) if "_current_stars" in df.columns else 0,
            "is_top20":      int(y[i]),
        })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default=str(Path.home() / "openclaw-project/data/features.csv"))
    parser.add_argument("--output", default=str(Path.home() / "openclaw-project/data/model_results.json"))
    parser.add_argument("--artifacts-dir", default=str(Path.home() / "openclaw-project/data/model_artifacts"))
    args = parser.parse_args()

    in_path  = Path(args.input)
    out_path = Path(args.output)
    artifacts_dir = Path(args.artifacts_dir).expanduser()

    def display_path(path: Path) -> str:
        try:
            return str(path.relative_to(Path.cwd()))
        except ValueError:
            return str(path)

    if not in_path.exists():
        print(f"[ERROR] features file not found: {in_path}", flush=True)
        sys.exit(1)

    print(f"[1/10] Loading features from {in_path}", flush=True)
    X, y, feature_names, df = load_data(in_path)
    print(f"  {X.shape[0]} samples × {X.shape[1]} features | pos={y.sum()} neg={(y==0).sum()}", flush=True)

    models   = build_models()
    output   = {
        "models": {}, "feature_importance": {}, "ablation": {},
        "time_split": None, "language_auc": {}, "shap": {}, "top10": [],
        "regression": {}, "clustering": {}, "oof_probs_rf": [],
        "meta": {},
    }
    oof_probs_rf = None

    print(f"[2/10] Running {CV_FOLDS}-fold CV for each model (+ PR-AUC + P@K)...", flush=True)
    for name, model in models.items():
        print(f"  Training {name}...", flush=True)
        metrics, oof_probs = cv_metrics_with_oof(model, X, y)
        metrics["precision_at_10"] = precision_at_k(y, oof_probs, 10)
        metrics["precision_at_20"] = precision_at_k(y, oof_probs, 20)
        output["models"][name] = metrics
        if name == "RF":
            oof_probs_rf = oof_probs
        print(
            f"    AUC={metrics['auc']['mean']:.4f}  PR-AUC={metrics['pr_auc']['mean']:.4f}"
            f"  P@10={metrics['precision_at_10']:.2f}  P@20={metrics['precision_at_20']:.2f}",
            flush=True,
        )

    print("[3/10] Computing feature importance (RF + XGBoost + LR)...", flush=True)
    for name in ["RF", "XGBoost"]:
        models[name].fit(X, y)
        output["feature_importance"][name] = feature_importance(models[name], feature_names)
    models["LR"].fit(X, y)
    output["feature_importance"]["LR"] = feature_importance(models["LR"], feature_names)

    print("[4/10] Running ablation study (RF, feature groups)...", flush=True)
    output["ablation"] = run_ablation(df, y)

    print("[5/10] Running time-aware split (RF, chrono 80/20)...", flush=True)
    output["time_split"] = run_time_split(df, y, feature_names, output["models"]["RF"]["auc"]["mean"])

    print("[6/10] Per-language AUC (RF, 5-fold)...", flush=True)
    output["language_auc"] = run_language_auc(df, y, feature_names)

    print("[7/10] SHAP analysis (RF, TreeExplainer)...", flush=True)
    output["shap"] = run_shap(models["RF"], X, feature_names)
    if output["shap"].get("top10"):
        print(f"  Top feature: {output['shap']['top10'][0]['feature']}"
              f"  mean|SHAP|={output['shap']['top10'][0]['mean_abs_shap']:.4f}", flush=True)

    print("[8/10] Collecting OOF Top-10 Rising Stars...", flush=True)
    if oof_probs_rf is not None:
        output["top10"] = collect_oof_top10(df, y, oof_probs_rf)
        output["oof_probs_rf"] = [round(float(p), 6) for p in oof_probs_rf]
        for item in output["top10"]:
            tag = "✓" if item["is_top20"] else "✗"
            print(f"  #{item['rank']} {item['full_name']:<45s} prob={item['prob']:.3f} stars={item['current_stars']} {tag}", flush=True)

    print("[9/10] Running regression experiments (log1p(stars) target)...", flush=True)
    output["regression"] = run_regression(df, feature_names)

    print("[10/10] Running KMeans clustering (k=4) + PCA visualization...", flush=True)
    output["clustering"] = run_clustering(df, y, feature_names)

    output["meta"] = {
        "n_samples":    int(X.shape[0]),
        "n_features":   int(X.shape[1]),
        "n_positive":   int(y.sum()),
        "cv_folds":     CV_FOLDS,
        "feature_names": feature_names,
    }

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(models["RF"], artifacts_dir / "rf_model.joblib")

    # Compute RF training-set predicted-probability percentiles so Today Radar
    # can use data-driven action thresholds instead of magic numbers
    # (0.75 / 0.60 / 0.40). We use the RF re-fitted on the full training set
    # above; predict_proba is well-defined here.
    try:
        train_probs = models["RF"].predict_proba(X)[:, 1]
        score_thresholds = {
            "deep_dive": float(np.percentile(train_probs, 80)),
            "try":       float(np.percentile(train_probs, 60)),
            "watch":     float(np.percentile(train_probs, 40)),
            "_source":   "RF predict_proba on full training set, p80/p60/p40",
        }
        print(
            f"  Score thresholds (deep_dive/try/watch) = "
            f"{score_thresholds['deep_dive']:.3f}/{score_thresholds['try']:.3f}/{score_thresholds['watch']:.3f}",
            flush=True,
        )
    except Exception as exc:
        print(f"  [warn] could not compute score thresholds: {exc}", flush=True)
        score_thresholds = None

    model_schema = {
        "model": "RF",
        "model_file": "rf_model.joblib",
        "feature_names": feature_names,
        "feature_stats": {
            c: {
                "median": float(df[c].median()),
                "p75": float(df[c].quantile(0.75)),
                "p90": float(df[c].quantile(0.90)),
            }
            for c in feature_names
            if c in df.columns and pd.api.types.is_numeric_dtype(df[c])
        },
        "score_thresholds": score_thresholds,
        "label": "is_top20",
        "trained_on": display_path(in_path),
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "n_positive": int(y.sum()),
        "random_state": RANDOM_STATE,
    }
    (artifacts_dir / "model_schema.json").write_text(
        json.dumps(model_schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Model artifacts written → {artifacts_dir}", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nDone → {out_path}", flush=True)

    print("\n--- Model Results ---", flush=True)
    print(f"{'Model':<10} {'AUC':>8} {'PR-AUC':>8} {'F1':>8} {'P@10':>6} {'P@20':>6}", flush=True)
    for name, m in output["models"].items():
        print(
            f"{name:<10} {m['auc']['mean']:>8.4f} {m['pr_auc']['mean']:>8.4f}"
            f" {m['f1']['mean']:>8.4f} {m['precision_at_10']:>6.2f} {m['precision_at_20']:>6.2f}",
            flush=True,
        )

    print("\n--- Ablation (RF) ---", flush=True)
    for gdata in output["ablation"].values():
        print(f"  {gdata['label']:<42} {gdata['auc']['mean']:.4f}", flush=True)

    print("\n--- Language AUC (RF) ---", flush=True)
    for lang, d in output["language_auc"].items():
        auc_str = f"{d['auc']:.4f}" if d["auc"] else "N/A"
        print(f"  {lang:<15s} n={d['n_samples']:>3d}  AUC={auc_str}", flush=True)


if __name__ == "__main__":
    main()
