#!/usr/bin/env python3
"""
GitHub repo historical data collector for ML training.
Collects early-snapshot features (first 30 days) + current label data.

New flags (v2):
  --batch-name NAME         Tag every record with this batch name
  --ts-broad                TypeScript: skip AI keywords, use stars:>=5 broad search
  --language-quota K:N,...  Per-language target counts (e.g. Python:100,TypeScript:100)
  --dedup-against PATH      Skip full_names already in this JSONL (can repeat)
  Resume: if --out-file already exists, its full_names are skipped automatically.
"""
import argparse
import json
import os
import sys
import time
import random
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Set, Dict, List

import subprocess
import urllib.parse

# ---------------------------------------------------------------------------
# HTTP helpers (curl-based to work around Python 3.14 SSL issues on macOS)
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE = "https://api.github.com"


def _get(url: str, params: Optional[dict] = None, retries: int = 5) -> dict | list | None:
    """Fetch GitHub API URL using system curl. Handles rate limits and retries."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    backoff = 2
    for attempt in range(retries):
        try:
            cmd = [
                "curl", "-s", "--max-time", "30",
                "-D", "-",        # dump response headers to stdout (before body)
                "-H", "Accept: application/vnd.github+json",
                "-H", "X-GitHub-Api-Version: 2022-11-28",
                "-H", "User-Agent: openclaw-repo-collector/2.0",
            ]
            if GITHUB_TOKEN:
                cmd += ["-H", f"Authorization: Bearer {GITHUB_TOKEN}"]
            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, timeout=35)
            if result.returncode != 0:
                print(f"  [curl error {result.returncode}] attempt {attempt+1}/{retries}", flush=True)
                time.sleep(backoff + random.uniform(0, 1))
                backoff = min(backoff * 2, 60)
                continue

            raw = result.stdout.decode("utf-8", errors="replace")

            # Split headers from body; handle HTTP/2 (may have two header blocks)
            parts = raw.split("\r\n\r\n")
            if len(parts) < 2:
                parts = raw.split("\n\n")
            headers_raw = parts[0] if parts else ""
            body = parts[-1] if len(parts) >= 2 else ""

            # Check HTTP status from first line
            first_line = headers_raw.split("\n")[0].strip()
            if " 403 " in first_line or " 403\r" in first_line:
                reset_at = 0
                for line in headers_raw.split("\n"):
                    if line.lower().startswith("x-ratelimit-reset:"):
                        try:
                            reset_at = int(line.split(":", 1)[1].strip())
                        except ValueError:
                            pass
                wait = max(60, reset_at - int(time.time())) + 2
                print(f"  [403 rate-limit] sleeping {wait}s (attempt {attempt+1}/{retries})", flush=True)
                time.sleep(wait)
                continue
            if " 422 " in first_line or " 422\r" in first_line:
                print(f"  [422 unprocessable] {url}", flush=True)
                return None
            if any(f" {c} " in first_line for c in ("500", "502", "503")):
                time.sleep(backoff + random.uniform(0, 1))
                backoff = min(backoff * 2, 60)
                continue

            # Parse rate-limit headers
            remaining, reset_at = 9999, 0
            for line in headers_raw.split("\n"):
                lk = line.lower()
                if lk.startswith("x-ratelimit-remaining:"):
                    try:
                        remaining = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif lk.startswith("x-ratelimit-reset:"):
                    try:
                        reset_at = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
            if remaining < 5:
                wait = max(0, reset_at - int(time.time())) + 2
                print(f"  [rate-limit] only {remaining} calls left, sleeping {wait}s", flush=True)
                time.sleep(wait)

            return json.loads(body)

        except Exception as ex:
            print(f"  [error] {ex} attempt {attempt+1}/{retries}", flush=True)
            time.sleep(backoff + random.uniform(0, 1))
            backoff = min(backoff * 2, 60)
    return None


# ---------------------------------------------------------------------------
# Dedup helpers
# ---------------------------------------------------------------------------

def load_fullnames_from_jsonl(*paths: str) -> Set[str]:
    """Load all snapshot.full_name values from one or more JSONL files."""
    seen: Set[str] = set()
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    fn = r.get("snapshot", {}).get("full_name")
                    if fn:
                        seen.add(fn)
                except Exception:
                    pass
        print(f"  [dedup] loaded {len(seen)} names from {p}", flush=True)
    return seen


# ---------------------------------------------------------------------------
# Search repos
# ---------------------------------------------------------------------------

AI_KEYWORDS = [
    "machine-learning", "deep-learning", "neural-network", "llm", "gpt",
    "transformer", "computer-vision", "nlp", "reinforcement-learning",
    "diffusion", "embedding", "rag", "agent", "ai", "ml", "pytorch",
    "tensorflow", "huggingface", "langchain", "openai",
]

LANGUAGES = ["Python", "JavaScript", "Go", "Rust", "TypeScript"]


def _build_query(lang: str, created_range: str, keyword: str) -> str:
    return f"language:{lang} created:{created_range} stars:>=1 {keyword} in:topics,description"


def _build_ts_broad_query(created_range: str) -> str:
    # Cap at 500 stars to avoid mega-repos with thousands of commit pages
    return f"language:TypeScript created:{created_range} stars:5..500"


def parse_language_quotas(spec: str, target: int) -> Dict[str, int]:
    """Parse 'Python:100,TypeScript:100,...' → dict. Missing langs get equal share of remainder."""
    if not spec:
        default = max(1, (target + len(LANGUAGES) - 1) // len(LANGUAGES))
        return {lang: default for lang in LANGUAGES}
    quotas: Dict[str, int] = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        lang, n = pair.split(":", 1)
        quotas[lang.strip()] = int(n.strip())
    # Fill missing languages with 0
    for lang in LANGUAGES:
        quotas.setdefault(lang, 0)
    return quotas


def search_repos(
    target: int,
    created_start: str,
    created_end: str,
    ts_broad: bool = False,
    language_quotas: Optional[Dict[str, int]] = None,
    seen: Optional[Set[str]] = None,
) -> List[dict]:
    """Search GitHub for repos. Returns list of raw repo dicts (deduped, skipping `seen`)."""
    seen = seen or set()
    created_range = f"{created_start}..{created_end}"
    found: Dict[str, dict] = {}  # full_name → repo dict

    if language_quotas is None:
        default_quota = max(1, (target + len(LANGUAGES) - 1) // len(LANGUAGES))
        language_quotas = {lang: default_quota for lang in LANGUAGES}

    per_page = 100

    for lang in LANGUAGES:
        if len(found) >= target:
            break

        lang_quota = language_quotas.get(lang, 0)
        if lang_quota == 0:
            continue

        lang_count = 0
        print(f"  [search] language={lang} quota={lang_quota} ts_broad={ts_broad and lang == 'TypeScript'}", flush=True)

        if ts_broad and lang == "TypeScript":
            # Broad search: no keyword filter, lower star threshold
            query = _build_ts_broad_query(created_range)
            page = 1
            while lang_count < lang_quota and len(found) < target:
                params = {
                    "q": query,
                    "sort": "stars",
                    "order": "desc",
                    "per_page": per_page,
                    "page": page,
                }
                data = _get(f"{BASE}/search/repositories", params)
                if data is None or "items" not in data:
                    break
                items = data["items"]
                if not items:
                    break
                for repo in items:
                    fn = repo["full_name"]
                    if fn not in found and fn not in seen:
                        found[fn] = repo
                        lang_count += 1
                    if lang_count >= lang_quota:
                        break
                if len(items) < per_page or page >= 10:
                    break
                page += 1
                time.sleep(1.2)
            time.sleep(1.2)

        else:
            # Standard: iterate AI keywords
            for kw in AI_KEYWORDS:
                if lang_count >= lang_quota or len(found) >= target:
                    break
                query = _build_query(lang, created_range, kw)
                page = 1
                while lang_count < lang_quota and len(found) < target:
                    params = {
                        "q": query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": per_page,
                        "page": page,
                    }
                    data = _get(f"{BASE}/search/repositories", params)
                    if data is None or "items" not in data:
                        break
                    items = data["items"]
                    if not items:
                        break
                    for repo in items:
                        fn = repo["full_name"]
                        if fn not in found and fn not in seen:
                            found[fn] = repo
                            lang_count += 1
                        if lang_count >= lang_quota:
                            break
                    if len(items) < per_page or page >= 10:
                        break
                    page += 1
                    time.sleep(1.2)
                time.sleep(1.2)

    print(f"  [search] found {len(found)} unique new repos", flush=True)
    return list(found.values())[:target]


# ---------------------------------------------------------------------------
# Per-repo data collection
# ---------------------------------------------------------------------------

def _window(created_at: str) -> tuple[str, str]:
    """Return (since, until) ISO strings for the 30-day window."""
    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    until = dt + timedelta(days=30)
    return dt.isoformat(), until.isoformat()


def _count_list_endpoint(url: str, since: str, until: str, extra: dict | None = None) -> int:
    """Count items from a paginated endpoint within a time window."""
    params = {"since": since, "until": until, "per_page": 100, "page": 1, **(extra or {})}
    total = 0
    for _ in range(20):  # max 2000 items
        data = _get(url, params)
        if not isinstance(data, list):
            break
        total += len(data)
        if len(data) < 100:
            break
        params["page"] += 1
        time.sleep(0.4)
    return total


def _count_issues(full_name: str, since: str, until: str, pr: bool) -> int:
    """Count issues or PRs created within the window."""
    url = f"{BASE}/repos/{full_name}/issues"
    params = {
        "state": "all",
        "since": since,
        "per_page": 100,
        "page": 1,
    }
    if pr:
        params["filter"] = "all"
    total = 0
    for _ in range(20):
        data = _get(url, params)
        if not isinstance(data, list):
            break
        window_items = [
            i for i in data
            if i.get("created_at", "") <= until
            and (("pull_request" in i) == pr)
        ]
        total += len(window_items)
        if len(data) < 100:
            break
        params["page"] += 1
        time.sleep(0.4)
    return total


def _readme_stats(full_name: str, ref: Optional[str] = None) -> tuple[int, bool, bool]:
    """Return (readme_len_chars, has_image, has_url).

    If `ref` is supplied (a commit SHA / tag / branch), fetch the README at that
    historical point. Otherwise fall back to the default branch HEAD (legacy
    behaviour, kept only so we can populate the metadata-only `readme_len`).
    """
    url = f"{BASE}/repos/{full_name}/readme"
    params = {"ref": ref} if ref else None
    data = _get(url, params)
    if not isinstance(data, dict):
        return 0, False, False
    import base64
    content = data.get("content", "")
    try:
        text = base64.b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
    except Exception:
        return 0, False, False
    has_image = bool(re.search(r"!\[.*?\]\(.*?\)|<img\s", text, re.IGNORECASE))
    has_url = bool(re.search(r"https?://\S+demo|demo\s+\S*https?://", text, re.IGNORECASE))
    return len(text), has_image, has_url


def _last_commit_sha_before(full_name: str, until_iso: str) -> Optional[str]:
    """Return the SHA of the most recent commit at or before `until_iso`.

    Uses /repos/{full_name}/commits with `until=until_iso` and per_page=1,
    which returns the latest commit not after the cutoff. None on failure.
    """
    params = {"until": until_iso, "per_page": 1, "page": 1}
    data = _get(f"{BASE}/repos/{full_name}/commits", params)
    if not isinstance(data, list) or not data:
        return None
    sha = data[0].get("sha")
    return sha if isinstance(sha, str) else None


def _unique_commit_authors_30d(full_name: str, since: str, until: str) -> int:
    """Count distinct commit-author identities in the 30-day window.

    Identity priority: commit.author.login → commit.commit.author.email →
    commit.commit.author.name. Identities are deduplicated case-insensitively.
    """
    params = {"since": since, "until": until, "per_page": 100, "page": 1}
    seen: Set[str] = set()
    for _ in range(20):  # cap at 2000 commits per repo (same as _count_list_endpoint)
        data = _get(f"{BASE}/repos/{full_name}/commits", params)
        if not isinstance(data, list):
            break
        for c in data:
            ident = None
            author = c.get("author") if isinstance(c, dict) else None
            if isinstance(author, dict):
                login = author.get("login")
                if isinstance(login, str) and login.strip():
                    ident = f"login:{login.strip().lower()}"
            if ident is None:
                commit = c.get("commit") if isinstance(c, dict) else None
                cauth = commit.get("author") if isinstance(commit, dict) else None
                if isinstance(cauth, dict):
                    email = cauth.get("email")
                    if isinstance(email, str) and email.strip():
                        ident = f"email:{email.strip().lower()}"
                    else:
                        name = cauth.get("name")
                        if isinstance(name, str) and name.strip():
                            ident = f"name:{name.strip().lower()}"
            if ident:
                seen.add(ident)
        if len(data) < 100:
            break
        params["page"] += 1
        time.sleep(0.4)
    return len(seen)


def _author_info(login: str) -> dict:
    data = _get(f"{BASE}/users/{login}")
    if not isinstance(data, dict):
        return {}
    return {
        "followers": data.get("followers", 0),
        "public_repos": data.get("public_repos", 0),
        "account_type": data.get("type", "User"),
    }


def collect_repo(repo: dict) -> dict | None:
    """Collect full record for one repo. Returns None on fatal error."""
    full_name = repo["full_name"]
    created_at = repo.get("created_at", "")
    since, until = _window(created_at)

    try:
        commit_count = _count_list_endpoint(
            f"{BASE}/repos/{full_name}/commits", since, until
        )

        # contributors_30d: unique commit-author identities inside the 30-day
        # window. This replaces the previous /contributors-endpoint count,
        # which had no time filter and leaked current-state information.
        contributors_30d = _unique_commit_authors_30d(full_name, since, until)

        # Legacy current-time contributor count is kept as metadata for
        # backwards compatibility / data audit; do NOT use it as a model
        # feature.
        contrib_data = _get(
            f"{BASE}/repos/{full_name}/contributors",
            {"per_page": 100, "anon": "true"}
        )
        contributor_count_now = len(contrib_data) if isinstance(contrib_data, list) else 0

        issue_count = _count_issues(full_name, since, until, pr=False)
        pr_count = _count_issues(full_name, since, until, pr=True)

        # Historical README: find the last commit SHA at or before
        # created_at + 30 days, then fetch /readme?ref=<sha>. This freezes
        # README content to the 30-day window. Fall back to (0, False, False)
        # if no commit found or README missing at that ref.
        readme_ref_sha = _last_commit_sha_before(full_name, until)
        if readme_ref_sha:
            readme_len_30d, has_image_30d, has_demo_url_30d = _readme_stats(
                full_name, ref=readme_ref_sha
            )
        else:
            readme_len_30d, has_image_30d, has_demo_url_30d = 0, False, False

        # Current-time README is kept ONLY as metadata for audit, never as a
        # model feature.
        readme_len_now, has_image_now, has_demo_url_now = _readme_stats(full_name)

        owner_login = repo.get("owner", {}).get("login", "")
        author = _author_info(owner_login) if owner_login else {}

        current = _get(f"{BASE}/repos/{full_name}")
        current_stars = current.get("stargazers_count", repo.get("stargazers_count", 0)) if isinstance(current, dict) else repo.get("stargazers_count", 0)
        current_forks = current.get("forks_count", repo.get("forks_count", 0)) if isinstance(current, dict) else repo.get("forks_count", 0)
        pushed_at = current.get("pushed_at") if isinstance(current, dict) else repo.get("pushed_at")

        record = {
            "snapshot": {
                "name": repo.get("name"),
                "full_name": full_name,
                "language": repo.get("language"),
                "topics": repo.get("topics", []),
                "description": repo.get("description", ""),
                "license": (repo.get("license") or {}).get("spdx_id"),
                # --- strict 30-day historical README (model features) ---
                "has_readme_30d":        readme_len_30d > 0,
                "readme_len_30d":        readme_len_30d,
                "readme_has_image_30d":  has_image_30d,
                "readme_has_demo_url_30d": has_demo_url_30d,
                "readme_ref_sha":        readme_ref_sha,
                # --- 30-day activity (model features) ---
                "commits_30d":     commit_count,
                "contributors_30d": contributors_30d,
                "issues_30d":      issue_count,
                "prs_30d":         pr_count,
                # --- legacy current-time fields (metadata only; not for model) ---
                "has_readme":          readme_len_now > 0,
                "readme_len":          readme_len_now,
                "readme_has_image":    has_image_now,
                "readme_has_demo_url": has_demo_url_now,
                "contributors":        contributor_count_now,
                "author_followers":    author.get("followers", 0),
                "author_public_repos": author.get("public_repos", 0),
                "author_type":         author.get("account_type", "User"),
                "window_since":        since,
                "window_until":        until,
            },
            "labels": {
                "current_stars":  current_stars,
                "current_forks":  current_forks,
                "created_at":     created_at,
                "last_commit_at": pushed_at,
            },
        }
        return record

    except Exception as ex:
        print(f"  [collect error] {full_name}: {ex}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Summary writer
# ---------------------------------------------------------------------------

def write_summary(out_dir: Path, records: list, failures: int):
    from collections import Counter
    stars = [r["labels"]["current_stars"] for r in records]
    langs = Counter(r["snapshot"]["language"] for r in records)
    policies = Counter(r.get("sampling_policy", "standard") for r in records)
    batches = Counter(r.get("batch", "unknown") for r in records)

    def star_bucket(s):
        if s < 10: return "0-9"
        if s < 50: return "10-49"
        if s < 200: return "50-199"
        if s < 1000: return "200-999"
        return "1000+"

    star_dist = Counter(star_bucket(s) for s in stars)

    lines = [
        "# Repo Collector Summary",
        f"\n**Run date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"\n## Collection stats",
        f"- Collected: {len(records)}",
        f"- Failed: {failures}",
        f"- Total attempted: {len(records) + failures}",
        f"\n## Batch distribution",
    ]
    for batch, cnt in batches.most_common():
        lines.append(f"- {batch}: {cnt}")
    lines.append(f"\n## Sampling policy")
    for policy, cnt in policies.most_common():
        lines.append(f"- {policy}: {cnt}")
    lines.append(f"\n## Language distribution")
    for lang, cnt in langs.most_common():
        lines.append(f"- {lang or 'unknown'}: {cnt}")
    lines.append(f"\n## Current star distribution")
    for bucket in ["0-9", "10-49", "50-199", "200-999", "1000+"]:
        lines.append(f"- {bucket}: {star_dist.get(bucket, 0)}")

    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(lines) + "\n")
    print(f"\nSummary written → {summary_path}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GitHub repo ML data collector v2")
    parser.add_argument("--target", type=int, default=20,
                        help="Number of repos to collect (default 20 for test)")
    parser.add_argument("--start", default="2025-03-01", help="Created-after date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-04-30", help="Created-before date YYYY-MM-DD")
    parser.add_argument("--out-dir", default=str(Path.home() / "openclaw-project/data"),
                        help="Output directory (ignored if --out-file is an absolute path)")
    parser.add_argument("--out-file", default="repos_raw.jsonl",
                        help="Output JSONL filename or absolute path")
    parser.add_argument("--batch-name", default="",
                        help="Batch tag written to every record (e.g. early1_2025_03_04)")
    parser.add_argument("--ts-broad", action="store_true",
                        help="TypeScript: use broad search (stars:>=5, no AI keyword filter)")
    parser.add_argument("--language-quota", default="",
                        help="Per-language quotas e.g. Python:100,TypeScript:100,Go:100,Rust:100,JavaScript:100")
    parser.add_argument("--dedup-against", action="append", default=[],
                        metavar="PATH",
                        help="Skip full_names already in this JSONL (repeatable)")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("WARNING: GITHUB_TOKEN not set. Unauthenticated rate limit is 10 req/min.", flush=True)
        print("Set it with: export GITHUB_TOKEN=<your_token>", flush=True)

    # Resolve output path
    out_file_path = Path(args.out_file).expanduser()
    if out_file_path.is_absolute():
        out_path = out_file_path
    else:
        out_path = Path(args.out_dir).expanduser() / args.out_file
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build dedup set: external files + current out-file (resume)
    dedup_sources = list(args.dedup_against)
    if out_path.exists():
        dedup_sources.append(str(out_path))
    seen = load_fullnames_from_jsonl(*dedup_sources)
    print(f"  [dedup] total {len(seen)} full_names to skip", flush=True)

    # Parse language quotas
    language_quotas = parse_language_quotas(args.language_quota, args.target)

    print(f"[1/3] Searching repos (target={args.target}, {args.start}..{args.end})", flush=True)
    repos = search_repos(
        args.target,
        args.start,
        args.end,
        ts_broad=args.ts_broad,
        language_quotas=language_quotas,
        seen=seen,
    )
    print(f"[2/3] Collecting data for {len(repos)} repos...", flush=True)

    # Append mode (for resume)
    mode = "a" if out_path.exists() else "w"
    records = []
    failures = 0

    with open(out_path, mode, encoding="utf-8") as f:
        for i, repo in enumerate(repos, 1):
            fn = repo["full_name"]
            lang = repo.get("language", "")
            print(f"  [{i}/{len(repos)}] {fn}", flush=True)

            record = collect_repo(repo)
            if record:
                # Attach batch metadata
                record["batch"] = args.batch_name or "unknown"
                if args.ts_broad and lang == "TypeScript":
                    record["sampling_policy"] = "ts_broad"
                    record["query_language"] = "TypeScript"
                else:
                    record["sampling_policy"] = "standard"
                    record["query_language"] = None

                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                records.append(record)
            else:
                failures += 1
            time.sleep(0.8)

    print(f"[3/3] Writing summary...", flush=True)
    write_summary(out_path.parent, records, failures)

    # Language breakdown for quick validation
    from collections import Counter
    lang_counts = Counter(r["snapshot"]["language"] for r in records)
    ts_count = lang_counts.get("TypeScript", 0)
    ts_pct = ts_count / max(len(records), 1) * 100
    print(f"\nDone. {len(records)} records → {out_path}", flush=True)
    print(f"Failures: {failures}", flush=True)
    print(f"Language breakdown: {dict(lang_counts.most_common())}", flush=True)
    print(f"TypeScript: {ts_count} ({ts_pct:.1f}%) — target ≥15%", flush=True)


if __name__ == "__main__":
    main()
