#!/usr/bin/env python3
"""
Feature extraction for the OpenClaw GitHub-repo ML pipeline.

v3 (strict-30d): the model uses exactly 19 features that are all derivable
from the first-30-day window of a repository:

    Language / owner (7):
        lang_Python, lang_JavaScript, lang_Go, lang_Rust,
        lang_TypeScript, lang_Other, is_org
    Early activity (4):
        commits_30d, issues_30d, prs_30d, contributors_30d
    Historical README (4):
        has_readme_30d, readme_len_30d,
        readme_has_image_30d, readme_has_demo_url_30d
    Derived activity (4):
        activity_total_30d, commits_per_contributor_30d,
        prs_per_issue_30d, has_pr_activity_30d

Fields removed from the model: TF-IDF of topics/description, author_followers,
author_public_repos, has_license, and the legacy current-state README /
contributors fields. They may still exist in raw JSONL for audit, but never
enter the feature matrix.

By default the extractor requires every snapshot to carry the *_30d-suffixed
fields emitted by the updated repo-collector (v2+). If any are absent, the
process exits with an error. Pass --allow-legacy-fallback to allow reading
current-state fields as approximate substitutes (not recommended for training).
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import numpy as np
import pandas as pd


LANGUAGES = ["Python", "JavaScript", "Go", "Rust", "TypeScript"]

# Exactly 19 model features, in the order they will appear in feature_schema.
FEATURE_NAMES = [
    # language / owner
    "lang_Python",
    "lang_JavaScript",
    "lang_Go",
    "lang_Rust",
    "lang_TypeScript",
    "lang_Other",
    "is_org",
    # early activity (raw counts)
    "commits_30d",
    "issues_30d",
    "prs_30d",
    "contributors_30d",
    # historical README (frozen at created_at + 30 days)
    "has_readme_30d",
    "readme_len_30d",
    "readme_has_image_30d",
    "readme_has_demo_url_30d",
    # derived activity
    "activity_total_30d",
    "commits_per_contributor_30d",
    "prs_per_issue_30d",
    "has_pr_activity_30d",
]

# Metadata columns kept alongside features for downstream use; never trained on.
META_COLS = {
    "is_top20",
    "_created_at",
    "_full_name",
    "_language",
    "_current_stars",
    "_batch",
    "_readme_source",
    "_contributors_source",
}

# Fields that are required in every snapshot for strict-30d extraction.
STRICT_30D_README_KEYS = ("readme_len_30d", "has_readme_30d")
STRICT_30D_CONTRIB_KEY = "contributors_30d"


def load_records(path: Path) -> List[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def check_strict_30d_fields(records: List[dict]) -> Dict[str, int]:
    """Scan records for missing strict-30d fields.

    Returns a dict of violation counts (empty means all records are clean).
    """
    readme_missing = 0
    contrib_missing = 0
    for r in records:
        s = r.get("snapshot", {})
        if not any(k in s for k in STRICT_30D_README_KEYS):
            readme_missing += 1
        if STRICT_30D_CONTRIB_KEY not in s:
            contrib_missing += 1
    counts: Dict[str, int] = {}
    if readme_missing:
        counts["readme_missing"] = readme_missing
    if contrib_missing:
        counts["contributors_missing"] = contrib_missing
    return counts


def _readme_30d(s: dict, allow_legacy: bool = False) -> Tuple[int, int, int, int, str]:
    """Return (has_readme_30d, readme_len_30d, has_image_30d, has_demo_url_30d, source).

    source is "strict_30d" when the snapshot carries explicit *_30d fields.
    When those fields are absent and allow_legacy=True, current-state README
    fields are used and source is "legacy_fallback".
    """
    if "readme_len_30d" in s or "has_readme_30d" in s:
        return (
            int(bool(s.get("has_readme_30d", False))),
            int(s.get("readme_len_30d", 0) or 0),
            int(bool(s.get("readme_has_image_30d", False))),
            int(bool(s.get("readme_has_demo_url_30d", False))),
            "strict_30d",
        )
    if not allow_legacy:
        raise ValueError(
            f"Snapshot for '{s.get('full_name', '?')}' is missing strict-30d README fields "
            "(has_readme_30d / readme_len_30d). Recollect with the updated repo-collector, "
            "or run with --allow-legacy-fallback."
        )
    return (
        int(bool(s.get("has_readme", False))),
        int(s.get("readme_len", 0) or 0),
        int(bool(s.get("readme_has_image", False))),
        int(bool(s.get("readme_has_demo_url", False))),
        "legacy_fallback",
    )


def _contributors_30d(s: dict, allow_legacy: bool = False) -> Tuple[int, str]:
    """Return (contributors_30d, source)."""
    if "contributors_30d" in s:
        return int(s.get("contributors_30d", 0) or 0), "strict_30d"
    if not allow_legacy:
        raise ValueError(
            f"Snapshot for '{s.get('full_name', '?')}' is missing contributors_30d. "
            "Recollect with the updated repo-collector, or run with --allow-legacy-fallback."
        )
    return int(s.get("contributors", 0) or 0), "legacy_fallback"


def build_dataframe(records: List[dict], allow_legacy: bool = False) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Convert raw JSONL records → DataFrame with the 19 model features
    plus metadata columns. Returns (df, fallback_counts).
    """
    rows: List[dict] = []
    fallback_counts = {"readme_legacy": 0, "contributors_legacy": 0}

    for r in records:
        s = r.get("snapshot", {})
        labels = r.get("labels", {})

        has_readme_30d, readme_len_30d, readme_has_image_30d, readme_has_demo_url_30d, readme_src = _readme_30d(s, allow_legacy)
        contributors_30d, contrib_src = _contributors_30d(s, allow_legacy)

        if readme_src == "legacy_fallback":
            fallback_counts["readme_legacy"] += 1
        if contrib_src == "legacy_fallback":
            fallback_counts["contributors_legacy"] += 1

        language = s.get("language") or "Other"
        author_type = s.get("author_type", "User")
        commits_30d = int(s.get("commits_30d", 0) or 0)
        issues_30d = int(s.get("issues_30d", 0) or 0)
        prs_30d = int(s.get("prs_30d", 0) or 0)

        activity_total_30d = commits_30d + issues_30d + prs_30d
        commits_per_contributor_30d = commits_30d / max(contributors_30d, 1)
        prs_per_issue_30d = prs_30d / max(issues_30d, 1)
        has_pr_activity_30d = int(prs_30d > 0)

        row: Dict[str, Any] = {
            # language one-hot (6)
            "lang_Python":     int(language == "Python"),
            "lang_JavaScript": int(language == "JavaScript"),
            "lang_Go":         int(language == "Go"),
            "lang_Rust":       int(language == "Rust"),
            "lang_TypeScript": int(language == "TypeScript"),
            "lang_Other":      int(language not in LANGUAGES),
            # owner type (1)
            "is_org": int(author_type == "Organization"),
            # early activity (4)
            "commits_30d":      commits_30d,
            "issues_30d":       issues_30d,
            "prs_30d":          prs_30d,
            "contributors_30d": contributors_30d,
            # historical README (4)
            "has_readme_30d":          has_readme_30d,
            "readme_len_30d":          readme_len_30d,
            "readme_has_image_30d":    readme_has_image_30d,
            "readme_has_demo_url_30d": readme_has_demo_url_30d,
            # derived (4)
            "activity_total_30d":          activity_total_30d,
            "commits_per_contributor_30d": float(commits_per_contributor_30d),
            "prs_per_issue_30d":           float(prs_per_issue_30d),
            "has_pr_activity_30d":         has_pr_activity_30d,
            # metadata
            "_created_at":          labels.get("created_at", ""),
            "_full_name":           s.get("full_name", ""),
            "_language":            language,
            "_current_stars":       int(labels.get("current_stars", 0) or 0),
            "_batch":               r.get("batch", "unknown"),
            "_readme_source":       readme_src,
            "_contributors_source": contrib_src,
            # used only to compute is_top20 then dropped
            "current_stars": int(labels.get("current_stars", 0) or 0),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df, fallback_counts


def align_to_schema(df: pd.DataFrame, feature_names: List[str]) -> pd.DataFrame:
    """Ensure prediction data has exactly the trained feature columns, in order.

    Missing columns are added as 0; extra non-meta columns are dropped.
    """
    for col in feature_names:
        if col not in df.columns:
            df[col] = 0
    ordered = [c for c in df.columns if c in META_COLS or c.startswith("_")]
    ordered += [c for c in feature_names if c in df.columns]
    if "is_top20" in df.columns and "is_top20" not in ordered:
        ordered.append("is_top20")
    return df.loc[:, list(dict.fromkeys(ordered))]


def write_artifacts(artifacts_dir: Path, df: pd.DataFrame):
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    # Old TF-IDF vectorizer is no longer used. Remove it so downstream code
    # doesn't accidentally pick up a stale artifact.
    stale = artifacts_dir / "tfidf_vectorizer.joblib"
    if stale.exists():
        try:
            stale.unlink()
            print(f"  Removed stale artifact {stale.name}", flush=True)
        except OSError:
            pass

    schema = {
        "feature_names": list(FEATURE_NAMES),
        "meta_cols":     sorted(META_COLS),
        "languages":     LANGUAGES,
        "version":       "strict_30d_v3",
        "tfidf_features": 0,
        "notes": (
            "All model features are restricted to the first-30-day window of "
            "the repo. Current-state fields (author_followers/public_repos, "
            "has_license, current README, current contributors count) are "
            "deliberately excluded to reduce posterior-information leakage."
        ),
    }
    (artifacts_dir / "feature_schema.json").write_text(
        json.dumps(schema, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Artifacts written → {artifacts_dir}", flush=True)


def add_label(df: pd.DataFrame) -> Tuple[pd.DataFrame, Union[int, Dict[str, int]]]:
    """Compute is_top20 label (p80 of current_stars).

    Multi-batch input → per-batch threshold; single batch → global p80.
    """
    batches = df["_batch"].unique() if "_batch" in df.columns else []
    multi_batch = len(batches) > 1

    if multi_batch:
        thresholds: Dict[str, int] = {}
        df["is_top20"] = 0
        for batch in batches:
            mask = df["_batch"] == batch
            group_stars = df.loc[mask, "current_stars"]
            threshold = int(np.percentile(group_stars, 80))
            thresholds[batch] = threshold
            df.loc[mask, "is_top20"] = (group_stars >= threshold).astype(int)

        print(f"\n  {'batch':<30} {'count':>6} {'p80_stars':>10} {'pos%':>7}", flush=True)
        print(f"  {'-'*57}", flush=True)
        for batch in sorted(thresholds):
            mask = df["_batch"] == batch
            count = int(mask.sum())
            pos = int(df.loc[mask, "is_top20"].sum())
            print(
                f"  {batch:<30} {count:>6} {thresholds[batch]:>10} {pos/max(count,1)*100:>6.1f}%",
                flush=True,
            )

        df.drop(columns=["current_stars"], inplace=True)
        return df, thresholds

    threshold = int(np.percentile(df["current_stars"], 80))
    batch_name = batches[0] if len(batches) == 1 else "all"
    print(f"  [label] {batch_name}: Top-20% threshold = {threshold} stars", flush=True)
    df["is_top20"] = (df["current_stars"] >= threshold).astype(int)
    df.drop(columns=["current_stars"], inplace=True)
    return df, threshold


def main():
    parser = argparse.ArgumentParser(description="Feature extractor (strict-30d, 19 features)")
    parser.add_argument("--input",  default=str(Path.home() / "openclaw-project/data/repos_raw_500_strict.jsonl"))
    parser.add_argument("--output", default=str(Path.home() / "openclaw-project/data/features.csv"))
    parser.add_argument("--mode", choices=["train", "predict"], default="train",
                        help="train: writes is_top20 + schema; predict: aligns to saved schema")
    parser.add_argument("--artifacts-dir", default=str(Path.home() / "openclaw-project/data/model_artifacts"))
    parser.add_argument(
        "--allow-legacy-fallback",
        action="store_true",
        default=False,
        help=(
            "Allow using current-state README/contributors fields when strict-30d fields "
            "are absent. Produces approximate features — not recommended for training. "
            "Requires recollection with the updated repo-collector to remove this flag."
        ),
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    artifacts_dir = Path(args.artifacts_dir).expanduser()
    allow_legacy: bool = args.allow_legacy_fallback

    if not in_path.exists():
        print(f"[ERROR] Input file not found: {in_path}", flush=True)
        sys.exit(1)

    print(f"[1/4] Loading records from {in_path}", flush=True)
    records = load_records(in_path)
    print(f"  Loaded {len(records)} records", flush=True)

    from collections import Counter
    batch_counts = Counter(r.get("batch", "unknown") for r in records)
    print(f"  Batches: {dict(batch_counts.most_common())}", flush=True)

    if not allow_legacy:
        violations = check_strict_30d_fields(records)
        if violations:
            print("[ERROR] Raw data is missing strict-30d fields.", flush=True)
            print("  Recollect with the updated repo-collector (v2+) to obtain *_30d-suffixed snapshot fields.", flush=True)
            for key, count in violations.items():
                print(f"  {key}: {count}/{len(records)} records affected", flush=True)
            print("  To use approximate current-state values instead, run with --allow-legacy-fallback (not recommended for training).", flush=True)
            sys.exit(1)
    else:
        print("  [legacy-fallback mode] current-state fields will substitute missing strict-30d fields.", flush=True)

    print("[2/4] Building feature matrix (strict-30d, 19 features)...", flush=True)
    df, fallback_counts = build_dataframe(records, allow_legacy=allow_legacy)

    if allow_legacy and (fallback_counts["readme_legacy"] or fallback_counts["contributors_legacy"]):
        print(
            f"  [warn] README fallback: {fallback_counts['readme_legacy']}/{len(records)} rows used current-state README.",
            flush=True,
        )
        print(
            f"  [warn] Contributors fallback: {fallback_counts['contributors_legacy']}/{len(records)} rows used current-state count.",
            flush=True,
        )

    print("[3/4] Aligning columns to the 19-feature schema...", flush=True)
    if args.mode == "predict":
        schema_path = artifacts_dir / "feature_schema.json"
        if not schema_path.exists():
            print(f"[ERROR] feature_schema.json missing in {artifacts_dir}; run train mode first", flush=True)
            sys.exit(1)
        schema = json.loads(schema_path.read_text())
        feature_names = schema.get("feature_names", FEATURE_NAMES)
    else:
        feature_names = list(FEATURE_NAMES)

    threshold = None
    if args.mode == "train":
        print("[4/4] Adding is_top20 label...", flush=True)
        # Label first so that align_to_schema (which drops current_stars) does
        # not delete the column we need for thresholding.
        df, threshold = add_label(df)
        df = align_to_schema(df, feature_names)
        write_artifacts(artifacts_dir, df)
    else:
        print("[4/4] Predict mode: skipping label generation", flush=True)
        if "current_stars" in df.columns:
            df.drop(columns=["current_stars"], inplace=True)
        df = align_to_schema(df, feature_names)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"\nDone. {len(df)} rows × {len(df.columns)} cols → {out_path}", flush=True)
    print(f"Model features ({len(feature_names)}): {feature_names}", flush=True)

    if args.mode == "predict":
        print("Predict mode: no is_top20 label generated", flush=True)
        return

    pos = int(df["is_top20"].sum())
    print(f"Label balance: {pos} positive ({pos/max(len(df),1)*100:.1f}%) / {len(df)-pos} negative", flush=True)
    if isinstance(threshold, dict):
        print(f"Per-batch thresholds: {threshold}", flush=True)
    else:
        print(f"Threshold: {threshold} stars", flush=True)


if __name__ == "__main__":
    main()
