---
name: feature-extractor
description: Extract 19 strict-30d ML features from GitHub repo JSONL data. Outputs features.csv with language one-hot, owner type, early activity, historical README, and derived activity features. Adds binary is_top20 label (top 80th percentile by current_stars).
metadata: { "openclaw": { "emoji": "⚙️", "requires": { "bins": ["python3"], "env": [] } } }
---

# Feature Extractor (v3 — strict-30d)

Converts `repos_raw_*.jsonl` into model-ready `features.csv` using exactly **19 features**, all
derivable from the first 30 days of a repository's life. No current-state fields enter the model.

## Features produced (19 total)

| Group | Count | Columns |
|-------|-------|---------|
| Language one-hot | 6 | lang_Python, lang_JavaScript, lang_Go, lang_Rust, lang_TypeScript, lang_Other |
| Owner type | 1 | is_org |
| Early activity (raw counts) | 4 | commits_30d, issues_30d, prs_30d, contributors_30d |
| Historical README (frozen at created_at + 30d) | 4 | has_readme_30d, readme_len_30d, readme_has_image_30d, readme_has_demo_url_30d |
| Derived activity | 4 | activity_total_30d, commits_per_contributor_30d, prs_per_issue_30d, has_pr_activity_30d |
| **Label (train mode only)** | 1 | **is_top20** (1 if current_stars ≥ p80 threshold) |

**Deliberately excluded**: author_followers, author_public_repos, has_license, TF-IDF text features,
and all current-state (non-30d) README / contributors fields — to eliminate posterior-information leakage.

## Strict-30d enforcement

By default the extractor **fails with an error** if the input JSONL is missing the `*_30d`-suffixed
fields (`has_readme_30d`, `readme_len_30d`, `contributors_30d`, etc.). These fields are emitted by
the repo-collector v2+. If your data was collected before the v2 upgrade, recollect it.

To run in approximate mode (uses current-state fields as substitutes), pass `--allow-legacy-fallback`.
This is only appropriate for debugging or backwards-compatibility checks — do not train on such data.

## Usage

```bash
# Standard (requires strict-30d raw data)
python3 ~/.openclaw/workspace/skills/feature-extractor/extract.py \
  --input ~/openclaw-project/data/repos_raw_500_strict.jsonl \
  --output ~/openclaw-project/data/features.csv

# Approximate mode (old pre-v2 raw data — audit only, not recommended for training)
python3 ~/.openclaw/workspace/skills/feature-extractor/extract.py \
  --input /path/to/legacy_raw_without_30d_fields.jsonl \
  --output ~/openclaw-project/data/features_legacy_audit.csv \
  --allow-legacy-fallback

# Predict mode (align to saved schema, no label)
python3 ~/.openclaw/workspace/skills/feature-extractor/extract.py \
  --input ~/openclaw-project/data/repos_raw_new.jsonl \
  --output ~/openclaw-project/data/features_new.csv \
  --mode predict
```

## Options

```
--input PATH              JSONL input file (default: ~/openclaw-project/data/repos_raw_500_strict.jsonl)
--output PATH             CSV output file (default: ~/openclaw-project/data/features.csv)
--mode train|predict      train: writes is_top20 + schema; predict: aligns to saved schema
--artifacts-dir PATH      Where to write/read feature_schema.json (default: data/model_artifacts)
--allow-legacy-fallback   Permit current-state fields when *_30d fields are absent (approximate)
```

## Artifacts written (train mode)

- `data/model_artifacts/feature_schema.json` — locked feature list, version `strict_30d_v3`
- Removes stale `tfidf_vectorizer.joblib` if present
