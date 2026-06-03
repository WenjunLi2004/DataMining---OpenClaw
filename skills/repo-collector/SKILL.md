---
name: repo-collector
description: Collect GitHub repository historical data for ML training. Fetches repos created in a target date range, captures strict-30d snapshot features (historical README via last-commit SHA, contributors_30d via commit-author deduplication) and current label data (stars/forks), outputs JSONL + summary.md.
metadata: { "openclaw": { "emoji": "🗄️", "requires": { "bins": ["python3"], "env": ["GITHUB_TOKEN"] } } }
---

# Repo Collector (v2 — strict-30d)

Collect GitHub repo data for ML training. Produces:
- `repos_raw_*.jsonl` — one JSON record per repo with strict-30d snapshot features + current labels
- `summary.md` — collection stats, language distribution, star distribution

## Anti-leakage design

All snapshot features are strictly bounded to `created_at + 30 days`:

| Field | How collected |
|-------|--------------|
| `commits_30d` | `/commits?since=created_at&until=cutoff` |
| `issues_30d` | `/issues?state=all&since=created_at` filtered to `created_at ≤ cutoff` |
| `prs_30d` | Same as issues, `pull_request` key present |
| `contributors_30d` | Deduplicated commit authors within 30d window (login → email → name priority) |
| `has_readme_30d`, `readme_len_30d`, `readme_has_image_30d`, `readme_has_demo_url_30d` | Historical README: last commit SHA before cutoff via `/commits?until=cutoff&per_page=1`, then `/readme?ref=SHA` |
| `readme_ref_sha` | SHA used for historical README lookup (audit metadata) |

Fields `author_followers`, `author_public_repos`, `has_readme`, `readme_len`, `contributors` are
retained in the snapshot as **audit metadata only** — they never enter the feature matrix.

## When to Use

**USE this skill when:**
- "collect repos", "crawl github repos", "gather ML training data from GitHub"
- "repo-collector" — run the collector directly
- "test run 20 repos" or "full run 500 repos"

**DON'T use this skill when:**
- User wants trending/daily snapshots (use github-trending skill)
- User wants paper/arXiv data (use arxiv-cs-tracker)

## Quick Start

```bash
export GITHUB_TOKEN=<your_personal_access_token>

# Test run: 20 repos (verify pipeline)
python3 ~/.openclaw/workspace/skills/repo-collector/collect.py --target 20

# Full run: 500 repos (strict-30d, 1-year label window)
# Date constraint: created_at + 30d + 365d <= 2026-05-30  →  created_at <= 2025-04-30
python3 ~/.openclaw/workspace/skills/repo-collector/collect.py \
  --target 500 \
  --start 2025-03-01 \
  --end 2025-04-30 \
  --out-file ~/openclaw-project/data/repos_raw_500_strict.jsonl \
  --batch-name strict_30d_1y_2025_03_04
```

## Options

```
--target N            Number of repos to collect (default: 20)
--start YYYY-MM-DD    Created-after date (default: 2025-05-01)
--end   YYYY-MM-DD    Created-before date (default: 2025-06-30)
--out-dir PATH        Output directory (default: ~/openclaw-project/data)
--out-file PATH       Full JSONL output path (overrides out-dir + filename)
--batch-name NAME     Value written to each record's "batch" field
```

## Output schema

Each JSONL line:
```json
{
  "batch": "strict_30d_2025_05_06",
  "snapshot": {
    "name": "...",
    "full_name": "owner/repo",
    "language": "Python",
    "topics": ["llm", "ai"],
    "description": "...",
    "license": "MIT",

    "has_readme_30d": true,
    "readme_len_30d": 3400,
    "readme_has_image_30d": true,
    "readme_has_demo_url_30d": false,
    "readme_ref_sha": "abc123...",

    "commits_30d": 42,
    "contributors_30d": 3,
    "issues_30d": 5,
    "prs_30d": 2,

    "author_type": "User",
    "window_since": "2025-05-03T12:00:00+00:00",
    "window_until": "2025-06-02T12:00:00+00:00",

    "has_readme": true,
    "readme_len": 3400,
    "contributors": 3,
    "author_followers": 120,
    "author_public_repos": 18
  },
  "labels": {
    "current_stars": 847,
    "current_forks": 91,
    "created_at": "2025-05-03T12:00:00Z",
    "last_commit_at": "2026-01-10T08:22:00Z"
  }
}
```

## Rate limit notes

- Authenticated: 5000 req/h (core), 30 req/min (search)
- Script auto-sleeps when `X-RateLimit-Remaining < 5`
- Search API calls are throttled to 1 req/1.2s
- Set `GITHUB_TOKEN` before running (never write the token to any file):
  ```bash
  export GITHUB_TOKEN=<your_personal_access_token>
  ```

## How It Works

1. **Search**: rotates through 5 languages × 20 AI keywords, using `created:YYYY-MM-DD..YYYY-MM-DD stars:>=1` query
2. **Deduplication**: keyed on `full_name`, stops at target count
3. **Per-repo collection**:
   - Commits: `/repos/{owner}/{repo}/commits?since=...&until=...`
   - Issues/PRs: filtered by `created_at ≤ cutoff`
   - Historical README: last commit SHA before cutoff → `/readme?ref=SHA`
   - Contributors 30d: deduplicated commit author identities within window
   - Author metadata: `/users/{login}` (stored as audit metadata only)
   - Labels: fresh `/repos/{owner}/{repo}` for current stars/forks
4. **Output**: JSONL written incrementally (crash-safe), summary.md at end
