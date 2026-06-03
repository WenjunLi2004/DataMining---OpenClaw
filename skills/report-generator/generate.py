#!/usr/bin/env python3
"""
Generate a two-part HTML report:
  Part 1 — Main Experiment (N500): single-window, clean leakage prevention
  Part 2 — Scale & Distribution Shift Study (N1500): methodological pitfalls

Usage:
  python3 generate.py \
    --results     ~/openclaw-project/data/model_results.json \
    --results-1500 ~/openclaw-project/data/model_results_1500.json \
    --features    ~/openclaw-project/data/features.csv \
    --features-1500 ~/openclaw-project/data/features_1500.csv
"""
import argparse
import html as html_lib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #0f1117; color: #e2e8f0;
  line-height: 1.6; padding: 32px; max-width: 1100px; margin: 0 auto;
}
h1 { font-size: 1.8rem; font-weight: 700; color: #f8fafc; margin-bottom: 4px; }
h2 { font-size: 1.1rem; font-weight: 600; color: #94a3b8; margin: 24px 0 10px;
     text-transform: uppercase; letter-spacing: .08em; }
h3 { font-size: 1rem; font-weight: 600; color: #cbd5e1; margin: 16px 0 8px; }
.subtitle { color: #64748b; font-size: .9rem; margin-bottom: 32px; }

/* Part divider */
.part-header {
  border-top: 2px solid #2d3748; margin: 48px 0 24px;
  padding-top: 24px;
}
.part-header .part-num {
  font-size: .75rem; font-weight: 700; letter-spacing: .15em;
  text-transform: uppercase; margin-bottom: 6px;
}
.part-header.part1 .part-num { color: #3b82f6; }
.part-header.part2 .part-num { color: #f59e0b; }
.part-header .part-title {
  font-size: 1.4rem; font-weight: 700; color: #f1f5f9; margin-bottom: 6px;
}
.part-header .part-subtitle {
  font-size: .9rem; color: #64748b; font-style: italic;
}

/* Cards */
.card {
  background: #1e2330; border: 1px solid #2d3748; border-radius: 10px;
  padding: 20px 24px; margin-bottom: 20px;
}
.card-warn {
  background: #1c1a0f; border: 1px solid #92400e; border-radius: 10px;
  padding: 20px 24px; margin-bottom: 20px;
}
.warn-title {
  display: flex; align-items: center; gap: 10px;
  font-size: 1rem; font-weight: 700; color: #fbbf24; margin-bottom: 12px;
}
.warn-title .warn-icon { font-size: 1.3rem; }

/* Stats */
.stats-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px;
  margin-top: 12px;
}
.stat { background: #161b27; border-radius: 8px; padding: 14px 16px; text-align: center; }
.stat-value { font-size: 1.6rem; font-weight: 700; color: #60a5fa; }
.stat-label { font-size: .75rem; color: #64748b; margin-top: 2px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: .9rem; }
th {
  text-align: left; padding: 10px 14px; background: #161b27;
  color: #94a3b8; font-weight: 600; border-bottom: 2px solid #2d3748;
}
td { padding: 9px 14px; border-bottom: 1px solid #1e2a3a; }
tr:hover td { background: #1a2235; }
.best { color: #34d399; font-weight: 700; }

/* Bar */
.bar-wrap { display: flex; align-items: center; gap: 8px; }
.bar-bg { flex: 1; background: #1a2235; border-radius: 4px; height: 10px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); border-radius: 4px; }
.bar-fill-amber { height: 100%; background: linear-gradient(90deg, #d97706, #fbbf24); border-radius: 4px; }

/* Badges */
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: .75rem; font-weight: 600;
}
.badge-blue  { background: #1e3a5f; color: #60a5fa; }
.badge-green { background: #14532d; color: #34d399; }
.badge-amber { background: #451a03; color: #fbbf24; }

/* Finding blocks */
.finding { padding: 10px 16px; background: #161b27; border-left: 3px solid #3b82f6;
           border-radius: 0 6px 6px 0; margin-bottom: 8px; font-size: .9rem; }
.finding-warn { border-left-color: #f59e0b; }
.finding-green { border-left-color: #34d399; }

/* Layout */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 12px; }
.col-label { color: #64748b; font-size: .78rem; font-weight: 600; text-transform: uppercase;
             letter-spacing: .07em; margin-bottom: 8px; }

/* Special rows */
.row-star td { background: #1e1a00 !important; }
.row-star:hover td { background: #2a2400 !important; }
.star-badge { display:inline-block; padding:2px 7px; border-radius:4px;
              background:#3d2d00; color:#fbbf24; font-size:.75rem; font-weight:700; }

/* Misc */
.leakage-note { background:#0f1e2a; border:1px solid #1d3a52; border-radius:7px;
                padding:10px 14px; margin-top:14px; font-size:.85rem; color:#7dd3fc; }
code { background:#1a2235; padding:1px 5px; border-radius:3px; font-size:.88em; }
.footer { color: #374151; font-size: .8rem; text-align: center; margin-top: 40px; }
.section-num { color: #475569; font-size: .7rem; font-weight: 700;
               letter-spacing: .1em; text-transform: uppercase; margin-bottom: 2px; }
.delta-pos { color: #34d399; font-weight: 700; }
.delta-neg { color: #f87171; font-weight: 700; }
.delta-neu { color: #64748b; }
.highlight-box {
  background: #12263a; border: 1px solid #1e4a6a; border-radius: 8px;
  padding: 14px 18px; margin-top: 14px; font-size: .9rem;
}
.insight-md { color:#cbd5e1; font-size:.9rem; }
.insight-md h1 { font-size:1.25rem; margin:0 0 12px; color:#f8fafc; }
.insight-md h2 { font-size:1rem; color:#93c5fd; margin:24px 0 8px; text-transform:none; letter-spacing:0; }
.insight-md p { margin:8px 0 12px; color:#cbd5e1; }
.insight-md ul { margin:8px 0 14px; padding-left:1.2rem; color:#cbd5e1; }
.insight-md li { margin:5px 0; }
.insight-md table { margin:12px 0 18px; }
.insight-md code { color:#7dd3fc; }
"""


def _pct_bar(value: float, max_val: float = 1.0, amber: bool = False) -> str:
    pct = min(100, value / max_val * 100)
    fill_cls = "bar-fill-amber" if amber else "bar-fill"
    return (
        f'<div class="bar-wrap">'
        f'<div class="bar-bg"><div class="{fill_cls}" style="width:{pct:.1f}%"></div></div>'
        f'<span style="min-width:46px;text-align:right">{value:.4f}</span>'
        f'</div>'
    )


def _badge(name: str) -> str:
    colors = {"LR": "badge-blue", "RF": "badge-green", "XGBoost": "badge-amber"}
    return f'<span class="badge {colors.get(name, "badge-blue")}">{name}</span>'


def _delta(val: float, decimals: int = 4) -> str:
    sign = "+" if val >= 0 else ""
    cls = "delta-pos" if val > 0.001 else ("delta-neg" if val < -0.001 else "delta-neu")
    return f'<span class="{cls}">{sign}{val:.{decimals}f}</span>'


def _get_auc(d: dict) -> float:
    v = d.get("auc", 0)
    return v["mean"] if isinstance(v, dict) else float(v or 0)


def _get_metric(d: dict, key: str) -> float:
    v = d.get(key, 0)
    return v["mean"] if isinstance(v, dict) else float(v or 0)


def _get_std(d: dict, key: str) -> float:
    v = d.get(key, {})
    return v.get("std", 0) if isinstance(v, dict) else 0


def _importance_table(feats: list, val_key: str = "importance") -> str:
    if not feats:
        return "<p style='color:#475569'>No data.</p>"
    max_v = max(f[val_key] for f in feats[:10]) or 1
    rows = "".join(
        f"<tr>"
        f"<td style='color:#64748b;width:20px'>{i+1}</td>"
        f"<td style='font-family:monospace;font-size:.83rem'>{f['feature']}</td>"
        f"<td>{_pct_bar(f[val_key], max_v)}</td>"
        f"</tr>"
        for i, f in enumerate(feats[:10])
    )
    return f"<table><thead><tr><th>#</th><th>Feature</th><th>Score</th></tr></thead><tbody>{rows}</tbody></table>"


def _inline_md(text: str) -> str:
    text = html_lib.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return text


def _markdown_table(lines: list[str]) -> str:
    headers = [h.strip() for h in lines[0].strip().strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(cells)
    head_html = "".join(f"<th>{_inline_md(h)}</th>" for h in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{_inline_md(c)}</td>" for c in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"


def _markdown_to_html(md: str) -> str:
    """Small Markdown renderer for the generated INSIGHTS.md subset."""
    lines = md.splitlines()
    html_parts = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        if line.startswith("# "):
            html_parts.append(f"<h1>{_inline_md(line[2:].strip())}</h1>")
            i += 1
            continue
        if line.startswith("## "):
            html_parts.append(f"<h2>{_inline_md(line[3:].strip())}</h2>")
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            html_parts.append(_markdown_table(table_lines))
            continue
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline_md(lines[i][2:].strip())}</li>")
                i += 1
            html_parts.append("<ul>" + "".join(items) + "</ul>")
            continue

        paragraph = [line]
        i += 1
        while (
            i < len(lines)
            and lines[i].strip()
            and not lines[i].startswith(("# ", "## ", "- ", "|"))
        ):
            paragraph.append(lines[i].strip())
            i += 1
        html_parts.append(f"<p>{_inline_md(' '.join(paragraph))}</p>")
    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# Shared: part headers
# ---------------------------------------------------------------------------

def part_header(num: int, title: str, subtitle: str) -> str:
    cls = "part1" if num == 1 else "part2"
    label = "Part 1" if num == 1 else "Part 2"
    return f"""
<div class="part-header {cls}">
  <div class="part-num">{label}</div>
  <div class="part-title">{title}</div>
  <div class="part-subtitle">{subtitle}</div>
</div>
"""


def section_num(n: str, title: str) -> str:
    return f'<div class="section-num">{n}</div><h2>{title}</h2>'


# ---------------------------------------------------------------------------
# Part 1 sections
# ---------------------------------------------------------------------------

def s1_dataset(df: pd.DataFrame, meta: dict) -> str:
    n = meta["n_samples"]
    nf = meta["n_features"]
    pos = meta["n_positive"]
    neg = n - pos
    pos_pct = pos / n * 100
    return f"""
<div class="card">
  {section_num("1.1", "Dataset Overview")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:12px">
    AI/ML repositories on GitHub, created between <strong>2025-05-01 and 2025-06-30</strong>.
    Single time window eliminates cross-batch label distribution drift by design.
  </p>
  <div class="stats-grid">
    <div class="stat"><div class="stat-value">{n}</div><div class="stat-label">Total Repos</div></div>
    <div class="stat"><div class="stat-value">{nf}</div><div class="stat-label">Features</div></div>
    <div class="stat"><div class="stat-value">{pos}</div><div class="stat-label">Top-20% (positive)</div></div>
    <div class="stat"><div class="stat-value">{neg}</div><div class="stat-label">Bottom-80% (negative)</div></div>
    <div class="stat"><div class="stat-value">{pos_pct:.1f}%</div><div class="stat-label">Positive Rate</div></div>
    <div class="stat"><div class="stat-value">48 ⭐</div><div class="stat-label">Top-20% threshold</div></div>
    <div class="stat"><div class="stat-value">5</div><div class="stat-label">CV Folds</div></div>
    <div class="stat"><div class="stat-value">5</div><div class="stat-label">Languages</div></div>
  </div>
  <div style="margin-top:14px">
    <table>
      <thead><tr><th>Language</th><th>Repos</th><th>Search strategy</th></tr></thead>
      <tbody>
        <tr><td>Python</td><td>100</td><td>AI keywords (machine-learning, llm, transformer, …)</td></tr>
        <tr><td>JavaScript</td><td>100</td><td>AI keywords</td></tr>
        <tr><td>Go</td><td>~118</td><td>AI keywords</td></tr>
        <tr><td>Rust</td><td>~151</td><td>AI keywords</td></tr>
        <tr><td>TypeScript</td><td>~31</td><td>AI keywords (low yield in target window)</td></tr>
      </tbody>
    </table>
  </div>
</div>
"""


def s1_feature_engineering() -> str:
    groups = [
        ("Language one-hot (6)", "lang_Python · lang_JavaScript · lang_Go · lang_Rust · lang_TypeScript · lang_Other"),
        ("Owner type (1)", "is_org"),
        ("Early activity (4)", "commits_30d · issues_30d · prs_30d · contributors_30d (distinct commit-author logins inside 30d window)"),
        ("Historical README (4)", "has_readme_30d · readme_len_30d · readme_has_image_30d · readme_has_demo_url_30d (README fetched via commits API at SHA ≤ created_at+30d)"),
        ("Derived activity (4)", "activity_total_30d · commits_per_contributor_30d · prs_per_issue_30d · has_pr_activity_30d"),
        ("Label (target)", "<strong>is_top20</strong> = 1 if current_stars ≥ 80th percentile of the sample (single-batch → global p80; multi-batch → per-batch p80). Stored in <em>labels</em>, never mixed into snapshot."),
    ]
    rows = "".join(
        f"<tr><td><strong>{g}</strong></td><td style='color:#94a3b8'>{d}</td></tr>"
        for g, d in groups
    )
    return f"""
<div class="card">
  {section_num("1.2", "Feature Engineering — 19 strict-30d features")}
  <table>
    <thead><tr><th>Group</th><th>Columns</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="leakage-note">
    <strong>Anti-leakage design</strong> — every one of the 19 model features is derivable
    from the first-30-day window of a repository: commits / issues / PRs use GitHub API
    <code>since</code> + <code>until</code> filters; <code>contributors_30d</code> counts
    distinct commit-author identities within the window (login → email → name); README
    features are fetched at the most recent commit SHA ≤ <code>created_at + 30 days</code>.
    Current-state fields (<code>author_followers</code>, <code>author_public_repos</code>,
    <code>has_license</code>, current README, current contributors count, TF-IDF over topics
    / description) are deliberately excluded from the model. <code>current_stars</code> /
    <code>current_forks</code> live only in <em>labels</em> and never enter the feature
    vector.
  </div>
</div>
"""


def s1_model_comparison(models: dict) -> str:
    metrics = ["auc", "pr_auc", "f1", "precision", "recall", "accuracy"]
    labels  = ["AUC-ROC", "PR-AUC", "F1", "Precision", "Recall", "Accuracy"]
    avail   = [m for m in metrics if any(m in d for d in models.values())]
    avail_l = [labels[metrics.index(m)] for m in avail]
    best    = {m: max(models, key=lambda n: _get_metric(models[n], m)) for m in avail}

    header = "<tr><th>Model</th>" + "".join(f"<th>{l}</th>" for l in avail_l) + "</tr>"
    rows = ""
    for name, data in models.items():
        cells = f"<td>{_badge(name)}</td>"
        for m in avail:
            val = _get_metric(data, m)
            std = _get_std(data, m)
            cls = ' class="best"' if name == best[m] else ""
            cells += f'<td{cls}>{_pct_bar(val)} <span style="color:#475569;font-size:.8rem">±{std:.3f}</span></td>'
        rows += f"<tr>{cells}</tr>"

    return f"""
<div class="card">
  {section_num("1.3", "Model Comparison (5-fold Stratified CV)")}
  <table>
    <thead>{header}</thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#475569;font-size:.8rem;margin-top:10px">
    Green = best per metric. PR-AUC = area under Precision-Recall curve
    (better for imbalanced classes at 20.2% positive rate).
  </p>
</div>
"""


def s1_precision_at_k(models: dict) -> str:
    has_pk = any("precision_at_10" in d for d in models.values())
    if not has_pk:
        return ""
    best_p10 = max(models, key=lambda n: models[n].get("precision_at_10", 0))
    rows = ""
    for name, data in models.items():
        p10 = data.get("precision_at_10")
        p20 = data.get("precision_at_20")
        if p10 is None:
            continue
        lift10 = p10 / 0.20
        lift20 = p20 / 0.20 if p20 else 0
        cls = ' class="best"' if name == best_p10 else ""
        rows += (
            f"<tr><td>{_badge(name)}</td>"
            f"<td{cls}>{p10:.2f} <span style='color:#64748b;font-size:.8rem'>({lift10:.1f}× baseline)</span></td>"
            f"<td>{p20:.2f} <span style='color:#64748b;font-size:.8rem'>({lift20:.1f}× baseline)</span></td>"
            f"<td style='color:#94a3b8;font-size:.85rem'>"
            f"{p10*10:.0f}/10 correct in top-10; {p20*20:.0f}/20 in top-20"
            f"</td></tr>"
        )
    return f"""
<div class="card">
  {section_num("1.4", "Precision@K (OOF predictions, full 500-sample pool)")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:10px">
    P@K = fraction of actual Top-20% repos among K highest-confidence OOF predictions.
    Baseline (random) = 20.2%. A P@10 of 0.90 means 9 of 10 recommended repos are genuinely high-growth.
  </p>
  <table>
    <thead><tr><th>Model</th><th>P@10</th><th>P@20</th><th>Interpretation</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
"""


def s1_ablation(ablation: dict) -> str:
    if not ablation:
        return ""
    metrics = ["auc", "f1", "precision", "recall"]
    labels  = ["AUC-ROC", "F1", "Precision", "Recall"]
    best    = {m: max(ablation, key=lambda k: _get_metric(ablation[k], m)) for m in metrics}
    header  = "<tr><th>Group</th><th>Features</th>" + "".join(f"<th>{l}</th>" for l in labels) + "<th>ΔAUC</th></tr>"

    rows = ""
    prev_auc = None
    for gid, g in ablation.items():
        cur_auc = _get_metric(g, "auc")
        delta_html = ""
        if prev_auc is not None:
            delta = cur_auc - prev_auc
            delta_html = _delta(delta)
        prev_auc = cur_auc

        cells = f"<td><strong>{g['label']}</strong></td><td style='color:#64748b'>{g['n_features']}</td>"
        for m in metrics:
            val = _get_metric(g, m)
            std = _get_std(g, m)
            cls = ' class="best"' if gid == best[m] else ""
            cells += f'<td{cls}>{val:.4f} <span style="color:#475569;font-size:.8rem">±{std:.3f}</span></td>'
        cells += f"<td>{delta_html}</td>"
        rows += f"<tr>{cells}</tr>"

    # Auto conclusion
    keys = list(ablation.keys())
    gains = []
    prev = None
    for k in keys:
        cur = _get_metric(ablation[k], "auc")
        if prev is not None:
            gains.append((k, ablation[k]["label"], cur - prev))
        prev = cur
    best_gain = max(gains, key=lambda x: x[2]) if gains else None
    d_auc = _get_metric(ablation.get("D_all", {}), "auc")
    c_auc = _get_metric(ablation.get("C_readme", {}), "auc")
    derived_note = ("Derived activity features add meaningful lift (+{:.4f}).".format(d_auc - c_auc)
                    if d_auc > c_auc + 0.005 else
                    f"Derived activity features marginal lift (+{d_auc-c_auc:.4f}); raw 30-day signals + README already explain most of the gap.")
    conclusion = (
        f'Adding <strong>{best_gain[1].split(":")[-1].strip()}</strong> yields the largest AUC jump '
        f'({_delta(best_gain[2])}), making it the highest-value feature group. {derived_note}'
    ) if best_gain else ""

    return f"""
<div class="card">
  {section_num("1.5", "Ablation Study (RF, 5-fold CV)")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:12px">
    Feature groups added incrementally. ΔAUC = change vs previous group.
  </p>
  <table>
    <thead>{header}</thead>
    <tbody>{rows}</tbody>
  </table>
  <div class="finding" style="margin-top:14px">{conclusion}</div>
</div>
"""


def s1_time_split(ts: dict) -> str:
    if not ts:
        return ""
    m = ts["metrics"]
    gap = ts.get("auc_gap", m["auc"] - ts.get("random_cv_auc", 0))
    gap_color = "#34d399" if gap >= 0 else "#f87171"
    gap_sign  = "+" if gap >= 0 else ""
    pos_rate  = ts["test_positive_rate"] * 100
    rand_auc  = ts.get("random_cv_auc", 0)

    if abs(gap) <= 0.02:
        conclusion = (
            "The AUC gap between time-based and random CV is negligible (&lt;0.02), "
            "confirming the model generalises well across the training time window — "
            "no temporal leakage is detected. ✓"
        )
        conclusion_cls = "finding finding-green"
    elif gap < -0.02:
        conclusion = (
            f"Time-based AUC is <strong>{abs(gap):.4f} lower</strong> than random CV AUC, "
            "indicating temporal drift."
        )
        conclusion_cls = "finding finding-warn"
    else:
        conclusion = f"Time-based AUC is <strong>{gap:.4f} higher</strong> than random CV AUC."
        conclusion_cls = "finding"

    return f"""
<div class="card">
  {section_num("1.6", "Time-Aware Split (RF, chronological 80/20)")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:12px">
    Repos sorted by <code>created_at</code>. First {ts['train_size']} repos (before {ts['split_date']}) = train;
    last {ts['test_size']} = test. Simulates predicting repos that didn't exist at training time.
  </p>
  <div class="stats-grid" style="margin-bottom:16px">
    <div class="stat"><div class="stat-value">{m['auc']:.4f}</div><div class="stat-label">Time-split AUC</div></div>
    <div class="stat"><div class="stat-value">{rand_auc:.4f}</div><div class="stat-label">Random CV AUC</div></div>
    <div class="stat"><div class="stat-value" style="color:{gap_color}">{gap_sign}{gap:.4f}</div><div class="stat-label">AUC Gap</div></div>
    <div class="stat"><div class="stat-value">{m['pr_auc']:.4f}</div><div class="stat-label">Time-split PR-AUC</div></div>
    <div class="stat"><div class="stat-value">{pos_rate:.1f}%</div><div class="stat-label">Test Positive Rate</div></div>
    <div class="stat"><div class="stat-value">{ts['test_size']}</div><div class="stat-label">Test Size</div></div>
  </div>
  <div class="{conclusion_cls}">{conclusion}</div>
</div>
"""


def s1_feature_importance(importance: dict, shap_data: dict) -> str:
    rf_feats   = importance.get("RF", [])
    shap_top10 = (shap_data or {}).get("top10", [])
    n_shap     = (shap_data or {}).get("n_samples", "N")

    gini_html = f"""
<div class="col-label">RF Gini Importance (full-data fit)</div>
<p style="color:#475569;font-size:.8rem;margin-bottom:8px">
  Mean decrease in impurity. Fast but biased toward high-cardinality numerics.
</p>
{_importance_table(rf_feats)}"""

    shap_html = f"""
<div class="col-label">SHAP mean |SHAP| (TreeExplainer, {n_shap} samples)</div>
<p style="color:#475569;font-size:.8rem;margin-bottom:8px">
  Sample-level contribution via TreeExplainer; less biased than Gini toward high-cardinality features.
</p>
{_importance_table(shap_top10, "mean_abs_shap") if shap_top10 else "<p style='color:#475569'>Not available.</p>"}"""

    gini_top3 = {f["feature"] for f in rf_feats[:3]}
    shap_top3 = {e["feature"] for e in shap_top10[:3]}
    divergence = gini_top3.symmetric_difference(shap_top3)
    div_note = ""
    if divergence:
        div_note = (
            f'<div class="finding finding-warn" style="margin-top:14px">'
            f'Gini and SHAP diverge on: '
            f'<strong>{", ".join(f"<code>{f}</code>" for f in sorted(divergence))}</strong>. '
            f'Gini inflates importance of continuous numerics (e.g. <code>readme_len_30d</code>). '
            f'Prefer SHAP for interpretation.'
            f'</div>'
        )

    other_html = ""
    for mn in ["XGBoost", "LR"]:
        feats = importance.get(mn, [])
        if feats:
            top3 = " · ".join(f["feature"] for f in feats[:3])
            other_html += f"<p style='color:#64748b;font-size:.82rem;margin-top:6px'>{_badge(mn)} top-3: {top3}</p>"

    return f"""
<div class="card">
  {section_num("1.7", "Feature Importance: RF Gini vs SHAP")}
  <div class="two-col">
    <div>{gini_html}</div>
    <div>{shap_html}</div>
  </div>
  {div_note}
  <div style="margin-top:16px;padding-top:12px;border-top:1px solid #2d3748">
    <span style="color:#64748b;font-size:.82rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em">Other Models</span>
    {other_html}
  </div>
</div>
"""


def s1_language_auc(lang_auc: dict) -> str:
    if not lang_auc:
        return ""
    LANG_COLORS = {"Python": "#3b82f6", "Go": "#06b6d4", "Rust": "#f97316",
                   "JavaScript": "#eab308", "TypeScript": "#8b5cf6"}
    rows = ""
    for lang, d in lang_auc.items():
        n     = d.get("n_samples", d.get("n", 0))
        n_pos = d.get("n_positive", 0)
        note  = d.get("note")
        auc   = d.get("auc")
        color = LANG_COLORS.get(lang, "#94a3b8")
        if note == "insufficient_samples" or auc is None:
            auc_cell  = '<span style="color:#f87171">N/A</span>'
            note_cell = '<span style="color:#f87171;font-size:.8rem">⚠ insufficient samples</span>'
        else:
            std      = d.get("auc_std", 0)
            auc_cell = f'{_pct_bar(auc)} <span style="color:#475569;font-size:.8rem">±{std:.3f}</span>'
            warn     = ' <span style="color:#fbbf24;font-size:.75rem">⚠ low-n</span>' if note == "low_samples" else ""
            note_cell = f'<span style="color:#64748b;font-size:.8rem">{n_pos}/{n} positive{warn}</span>'
        rows += (
            f"<tr><td><span style='color:{color};font-weight:600'>{lang}</span></td>"
            f"<td style='color:#64748b'>{n}</td><td>{auc_cell}</td><td>{note_cell}</td></tr>"
        )

    py = lang_auc.get("Python", {})
    py_auc = py.get("auc")
    py_pos = py.get("n_positive", 0)
    py_n   = py.get("n_samples", py.get("n", 0))
    py_note = ""
    if py_auc is not None and py_auc < 0.65 and py_n > 0:
        py_pos_rate = py_pos / py_n * 100
        py_note = (
            f'<div class="finding finding-warn" style="margin-top:12px">'
            f'<strong>Python AUC anomaly ({py_auc:.4f}):</strong> '
            f'The Python subset has a <strong>{py_pos_rate:.0f}% positive rate</strong> '
            f'({py_pos}/{py_n}), far above the global 20.2%. '
            f'Within this cohort, nearly half the repos already qualify as Top-20%, '
            f'making the classification boundary much harder to learn — '
            f'high-star and low-star Python AI repos overlap heavily in feature space. '
            f'This is a <em>class distribution shift</em>, not a model failure.'
            f'</div>'
        )

    return f"""
<div class="card">
  {section_num("1.8", "Per-Language Analysis (RF, stratified CV)")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:10px">
    RF trained and evaluated within each language subset independently.
  </p>
  <table>
    <thead><tr><th>Language</th><th>Samples</th><th>AUC</th><th>Notes</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  {py_note}
</div>
"""


def s1_top10(top10: list) -> str:
    if not top10:
        return ""
    LANG_EMOJI = {"Python": "🐍", "Go": "🐹", "Rust": "🦀",
                  "JavaScript": "🟨", "TypeScript": "🔷"}
    rows = ""
    for item in top10:
        fn    = item["full_name"]
        url   = f"https://github.com/{fn}"
        lang  = item.get("language", "Other")
        emoji = LANG_EMOJI.get(lang, "📦")
        prob  = item["prob"]
        stars = item["current_stars"]
        tag   = ('<span style="color:#34d399;font-weight:600">✓ Top-20%</span>'
                 if item["is_top20"] else
                 '<span style="color:#f87171">✗ below Top-20%</span>')
        rows += (
            f"<tr>"
            f"<td style='color:#64748b;font-weight:600'>{item['rank']}</td>"
            f"<td><a href='{url}' target='_blank' style='color:#60a5fa;text-decoration:none'>{fn}</a></td>"
            f"<td>{emoji} {lang}</td>"
            f"<td>{_pct_bar(prob)}</td>"
            f"<td>⭐ {stars:,}</td>"
            f"<td>{tag}</td>"
            f"</tr>"
        )
    correct = sum(1 for i in top10 if i["is_top20"])
    return f"""
<div class="card">
  {section_num("1.9", "Top-10 Predicted Rising Stars (OOF, N500)")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:10px">
    Ranked by RF out-of-fold probability across the full 500-repo pool.
    <strong>{correct}/10 confirmed</strong> by actual star count (≥48 stars = Top-20%).
  </p>
  <table>
    <thead><tr><th>#</th><th>Repository</th><th>Language</th><th>Pred. Score</th><th>Current Stars</th><th>Status</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
"""


def s1_key_findings(models: dict, importance: dict, ablation: dict) -> str:
    best_model = max(models, key=lambda n: _get_metric(models[n], "auc"))
    best_auc   = _get_metric(models[best_model], "auc")

    rf_feats = importance.get("RF", [])
    top_feat = rf_feats[0]["feature"] if rf_feats else "unknown"
    top_imp  = rf_feats[0]["importance"] if rf_feats else 0

    d_auc = _get_metric(ablation.get("D_all", {}), "auc")
    c_auc = _get_metric(ablation.get("C_readme", {}), "auc")
    derived_delta = d_auc - c_auc
    readme_jump = _get_metric(ablation.get("C_readme", {}), "auc") - _get_metric(ablation.get("B_activity", {}), "auc")

    findings = [
        (f"<strong>{best_model}</strong> achieves the highest AUC of <strong>{best_auc:.4f}</strong>. "
         f"All three models stay well above random, confirming that strictly first-30-day "
         f"signals are predictive of long-term star growth."),

        (f"The single strongest predictor is <code>{top_feat}</code> (Gini {top_imp:.4f}). "
         f"Within the 19 strict-30d features, this is the dominant early signal of growth "
         f"in this AI/ML repo cohort — interpret it as model attribution, not causal."),

        (f"Adding historical README features (Group C) yields the largest ablation gain "
         f"({_delta(readme_jump)}). "
         f"Derived activity marginal contribution: {_delta(derived_delta)} (Group D vs C). "
         f"Raw 30-day signals + README explain most of the gap."),

        (f"Time-aware split is the deployment-style stress test: the chronological train→test "
         f"AUC gap is bounded and stays close to random-CV AUC. "
         f"Random 5-fold CV remains a reasonable proxy for this single-window dataset."),
    ]
    items = "".join(f'<div class="finding">{f}</div>' for f in findings)
    return f'<div class="card">{section_num("1.10", "Key Findings")}{items}</div>'


# ---------------------------------------------------------------------------
# Part 2 sections
# ---------------------------------------------------------------------------

def s2_extension_strategy() -> str:
    return f"""
<div class="card">
  {section_num("2.1", "Extension Strategy")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:14px">
    The N500 experiment uses a single time window (May–Jun 2025) to avoid cross-batch distribution shift.
    The N1500 study adds two earlier cohorts to test whether scale improves model stability
    — and to study what goes wrong when it doesn't.
  </p>
  <table>
    <thead><tr><th>Batch</th><th>Time Window</th><th>Repos</th><th>is_top20 p80 threshold</th><th>TypeScript strategy</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>mid</strong> (original)</td>
        <td>2025-05-01 → 2025-06-30</td>
        <td>500</td>
        <td>48 stars</td>
        <td>Standard AI keywords</td>
      </tr>
      <tr>
        <td><strong>early1</strong></td>
        <td>2025-03-01 → 2025-04-30</td>
        <td>500</td>
        <td>336 stars</td>
        <td><code>ts_broad</code>: stars:5..500, no keyword filter</td>
      </tr>
      <tr>
        <td><strong>early2</strong></td>
        <td>2025-01-01 → 2025-02-28</td>
        <td>500</td>
        <td>323 stars</td>
        <td><code>ts_broad</code>: stars:5..500, no keyword filter</td>
      </tr>
    </tbody>
  </table>
  <div class="finding" style="margin-top:14px">
    <strong>Design intent</strong>: batch-wise p80 labelling was applied to equalise positive rates across
    cohorts with different star accumulation times. However, this cannot fully neutralise all
    confounders — as the three findings below demonstrate.
  </div>
</div>
"""


def s2_scale_improvement(models_500: dict, models_1500: dict) -> str:
    rows = ""
    for mdl in ["LR", "RF", "XGBoost"]:
        m5  = models_500[mdl]
        m15 = models_1500[mdl]
        for metric, label in [("auc","AUC"), ("pr_auc","PR-AUC"), ("f1","F1")]:
            v5  = _get_metric(m5, metric)
            v15 = _get_metric(m15, metric)
            delta = v15 - v5
            rows += (
                f"<tr>"
                f"<td>{_badge(mdl)}</td><td>{label}</td>"
                f"<td>{v5:.4f}</td><td>{v15:.4f}</td>"
                f"<td>{_delta(delta)}</td>"
                f"</tr>"
            )

    return f"""
<div class="card">
  {section_num("2.2", "Scale Improvement")}
  <p style="color:#64748b;font-size:.85rem;margin-bottom:12px">
    Across all three models and all metrics, N1500 outperforms N500. AUC improvements of +0.03–0.05
    suggest the additional training data provides genuine signal, not just scale noise.
    <strong>However</strong>, the source of improvement is confounded — see Findings below.
  </p>
  <table>
    <thead><tr><th>Model</th><th>Metric</th><th>N500</th><th>N1500</th><th>Δ</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
"""


def s2_finding_sampling_contamination(lang_auc_500: dict, lang_auc_1500: dict, importance_1500: dict) -> str:
    ts_500  = lang_auc_500.get("TypeScript", {})
    ts_1500 = lang_auc_1500.get("TypeScript", {})
    ts_n_500  = ts_500.get("n_samples", ts_500.get("n", 31))
    ts_n_1500 = ts_1500.get("n_samples", ts_1500.get("n", 0))
    ts_pos_1500 = ts_1500.get("n_positive", 0)
    ts_pos_rate = ts_pos_1500 / max(ts_n_1500, 1) * 100

    # Top feature in N1500
    rf_fi = importance_1500.get("RF", [])
    top1_name = rf_fi[0]["feature"] if rf_fi else "N/A"
    top1_imp  = rf_fi[0]["importance"] if rf_fi else 0

    ts_auc_500  = ts_500.get("auc")
    ts_auc_1500 = ts_1500.get("auc")
    ts_auc_str_500  = "N/A (insufficient samples)" if ts_auc_500 is None else f"{ts_auc_500:.4f}"
    ts_auc_str_1500 = f"{ts_auc_1500:.4f}" if ts_auc_1500 else "N/A"

    return f"""
<div class="card-warn">
  <div class="warn-title"><span class="warn-icon">⚠️</span> Finding #1: Sampling Policy Contamination</div>
  <p style="color:#d97706;font-size:.85rem;margin-bottom:14px">
    The <code>ts_broad</code> strategy — designed to fix TypeScript underrepresentation —
    introduced a systematic bias that propagates through the entire model.
  </p>

  <h3 style="color:#fbbf24">What happened</h3>
  <table style="margin-bottom:16px">
    <thead><tr><th>Dimension</th><th>N500</th><th>N1500</th></tr></thead>
    <tbody>
      <tr><td>TypeScript sample count</td><td>{ts_n_500}</td><td><strong>{ts_n_1500}</strong></td></tr>
      <tr><td>TypeScript % of dataset</td><td>6.2%</td><td>15.4%</td></tr>
      <tr><td>TypeScript positive rate (is_top20)</td><td>~20%</td><td><strong style="color:#f87171">{ts_pos_rate:.1f}%</strong></td></tr>
      <tr><td>TypeScript AUC</td><td>{ts_auc_str_500}</td><td>{ts_auc_str_1500}</td></tr>
      <tr><td>#1 RF Gini feature</td><td>readme_len_30d (historically 0.2833)</td><td><strong style="color:#f87171">{top1_name} ({top1_imp:.4f})</strong></td></tr>
    </tbody>
  </table>

  <h3 style="color:#fbbf24">Root cause: three-way confound</h3>
  <ol style="color:#d97706;padding-left:1.4em;line-height:2;font-size:.9rem">
    <li><strong>ts_broad removes the AI-keyword filter</strong> for TypeScript, pulling in any TypeScript repo with 5–500 stars — a much broader population than the AI-focused Python/Go/Rust samples.</li>
    <li><strong>Early cohorts (early1 03~04, early2 01~02) have 17–19 months of star accumulation</strong> by the observation date, inflating absolute star counts vs the 11-month mid cohort.</li>
    <li><strong>Batch-wise p80 labelling sets a higher threshold per batch</strong> (336 and 323 stars vs 48), but the TS repos — pulled from the long-tail of any TypeScript project — happen to cluster above these thresholds at a 65% rate.</li>
  </ol>

  <div class="highlight-box">
    <strong>Consequence:</strong> <code>lang_TypeScript</code> became the #1 Gini and SHAP feature in N1500
    (importance {top1_imp:.4f}), displacing <code>readme_len_30d</code> (historically 0.2833 in N500).
    This is a <em>statistical artifact</em> of the sampling policy, not a causal signal.
    In a real deployment, predicting that "TypeScript repos grow faster" would be wrong —
    it is the population of TS repos sampled that happens to have more stars, not TypeScript itself.
  </div>
</div>
"""


def s2_finding_label_shift() -> str:
    return f"""
<div class="card-warn">
  <div class="warn-title"><span class="warn-icon">⚠️</span> Finding #2: Cross-Batch Label Distribution Shift</div>
  <p style="color:#d97706;font-size:.85rem;margin-bottom:14px">
    Batch-wise p80 labelling was designed to make each cohort's positive rate ~20%.
    It achieves this locally, but the absolute star counts defining "success" differ by 7×
    across batches — the same label token means completely different things.
  </p>

  <h3 style="color:#fbbf24">p80 threshold by batch</h3>
  <table style="margin-bottom:16px">
    <thead><tr><th>Batch</th><th>Window</th><th>Repos</th><th>p80 threshold</th><th>Positive rate</th><th>Observation</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>mid</strong></td><td>2025-05 ~ 06</td><td>500</td>
        <td><strong>48 stars</strong></td><td>20.2%</td>
        <td>~11 months of star accumulation</td>
      </tr>
      <tr>
        <td><strong>early1</strong></td><td>2025-03 ~ 04</td><td>500</td>
        <td><strong style="color:#f87171">336 stars</strong></td><td>20.2%</td>
        <td>~17 months of star accumulation</td>
      </tr>
      <tr>
        <td><strong>early2</strong></td><td>2025-01 ~ 02</td><td>500</td>
        <td><strong style="color:#f87171">323 stars</strong></td><td>20.0%</td>
        <td>~19 months of star accumulation</td>
      </tr>
    </tbody>
  </table>

  <div class="highlight-box">
    <strong>Why this matters:</strong> a model trained on all three batches jointly learns
    to predict <em>"is this repo in the top-20% of its own age cohort?"</em> —
    which is a <em>different task</em> depending on the batch.
    A repo with 100 stars is "Top-20%" in the mid cohort but a clear failure in early1/early2.
    The label is nominally the same but semantically different.
    Batch-wise p80 can equalise positive <em>rates</em> but cannot equalise the
    underlying growth <em>dynamics</em> between cohorts created months apart.
  </div>
</div>
"""


def s2_finding_cv_overestimation(ts_500: dict, ts_1500: dict, models_500: dict, models_1500: dict) -> str:
    rand_500  = _get_metric(models_500["RF"], "auc")
    rand_1500 = _get_metric(models_1500["RF"], "auc")

    m500  = ts_500.get("metrics", {})
    m1500 = ts_1500.get("metrics", {})
    tsauc_500  = m500.get("auc", 0)
    tsauc_1500 = m1500.get("auc", 0)

    gap_500  = tsauc_500 - rand_500
    gap_1500 = tsauc_1500 - rand_1500

    split_500  = ts_500.get("split_date", "?")
    split_1500 = ts_1500.get("split_date", "?")
    test_500   = ts_500.get("test_size", 0)
    test_1500  = ts_1500.get("test_size", 0)

    return f"""
<div class="card-warn">
  <div class="warn-title"><span class="warn-icon">⚠️</span> Finding #3: k-fold CV Overestimates Performance on Multi-Batch Data</div>
  <p style="color:#d97706;font-size:.85rem;margin-bottom:14px">
    Standard k-fold CV randomly shuffles all samples across folds, mixing repos from
    different time periods and star-accumulation stages. When data spans multiple
    non-exchangeable cohorts, CV optimistically overestimates real-world performance.
  </p>

  <h3 style="color:#fbbf24">Time-split AUC vs random CV AUC</h3>
  <table style="margin-bottom:16px">
    <thead><tr><th></th><th>Random CV AUC</th><th>Time-split AUC</th><th>Gap</th><th>Interpretation</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>N500</strong></td>
        <td>{rand_500:.4f}</td>
        <td>{tsauc_500:.4f}</td>
        <td style="color:#34d399;font-weight:700">+{gap_500:.4f}</td>
        <td style="color:#64748b;font-size:.85rem">Negligible — single window, no drift ✓</td>
      </tr>
      <tr>
        <td><strong>N1500</strong></td>
        <td>{rand_1500:.4f}</td>
        <td><strong style="color:#f87171">{tsauc_1500:.4f}</strong></td>
        <td style="color:#f87171;font-weight:700">{gap_1500:.4f}</td>
        <td style="color:#f87171;font-size:.85rem">CV overestimates by {abs(gap_1500):.1%} ⚠</td>
      </tr>
    </tbody>
  </table>
  <p style="color:#64748b;font-size:.82rem;margin-bottom:14px">
    Split dates: N500 = {split_500} (test n={test_500}); N1500 = {split_1500} (test n={test_1500}).
    Repos before split date = train; repos after = test.
  </p>

  <div class="highlight-box">
    <strong>What the gap means:</strong> for N1500, the random k-fold CV reported AUC {rand_1500:.4f},
    but when the model was actually asked to predict on later-created repos (chronological split),
    AUC dropped to {tsauc_1500:.4f} — a <strong>{abs(gap_1500):.1%} overestimation</strong>.
    This happens because CV folds contain repos from different batches mixed together;
    the model sees early1/early2 repos in both train and test sets, and the
    label distribution shifts between batches give it an artificial advantage.
    <br><br>
    N500's gap is only +0.0025 because all 500 repos come from the same two-month window
    and are therefore approximately exchangeable across time. This confirms that
    <em>single-window datasets are not just simpler — they are more methodologically sound
    for CV-based evaluation</em>.
  </div>
</div>
"""


def s2_discussion() -> str:
    return f"""
<div class="card">
  {section_num("2.6", "Discussion: Implications for Open Source Success Prediction")}

  <h3>What this study shows</h3>
  <div class="finding" style="margin-bottom:8px">
    <strong>1. Naive dataset scaling is not equivalent to better science.</strong>
    Adding more data from adjacent time periods improved raw AUC numbers (+0.03–0.05)
    but introduced three distinct methodological problems that make the N1500 results
    harder to interpret and less actionable than N500.
  </div>
  <div class="finding" style="margin-bottom:8px">
    <strong>2. Sampling policy decisions cascade into model behaviour.</strong>
    The <code>ts_broad</code> fix for TypeScript underrepresentation — sensible in isolation —
    combined with longer star-accumulation time to produce a spurious feature signal.
    Data collection and model evaluation are not independent stages.
  </div>
  <div class="finding" style="margin-bottom:8px">
    <strong>3. Label definition must be absolute, not relative-to-cohort.</strong>
    Batch-wise p80 labelling trades one problem (imbalanced positive rates) for another
    (semantically inconsistent labels). For multi-cohort studies, a fixed absolute threshold
    (e.g., 100 stars regardless of cohort) or a growth-rate label (stars/month) would be preferable.
  </div>
  <div class="finding" style="margin-bottom:8px">
    <strong>4. Standard k-fold CV is unreliable for multi-batch data.</strong>
    The N1500 time-split gap of −0.094 means real-world performance would be dramatically
    lower than what CV suggests. Blocked CV (never mixing cohorts in the same fold)
    or leave-one-cohort-out CV would be more honest.
  </div>

  <h3 style="margin-top:18px">Future work</h3>
  <div class="finding finding-green">
    <strong>Recommended directions:</strong> (a) Use a fixed absolute star threshold
    or log-normalised regression target; (b) Apply blocked cross-validation with
    cohort as the blocking variable; (c) Replace <code>ts_broad</code> with
    domain-scoped TS queries (AI-specific TS frameworks); (d) Collect longitudinal
    data (same repos at 3m, 6m, 12m) to study growth trajectories rather than
    cross-sectional snapshots; (e) Explore embedding features from DeepSeek API
    as a future extension — current model already excludes bag-of-words TF-IDF
    to enforce strict 30-day boundedness.
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Pipeline meta sections (decision log / run history)
# ---------------------------------------------------------------------------

def section_decision_log(log: dict) -> str:
    if not log:
        return ""
    decisions = log.get("decisions", [])
    run_at    = log.get("run_at", "")[:16].replace("T", " ") + " UTC"
    ACTION_COLOR = {"execute": "#34d399", "skip": "#64748b", "executed": "#34d399", "skipped": "#64748b"}
    ACTION_ICON  = {"execute": "▶", "skip": "⏭", "executed": "▶", "skipped": "⏭"}
    def _drow(d):
        action = d.get("action") or d.get("decision", "")
        color  = ACTION_COLOR.get(action, "#e2e8f0")
        icon   = ACTION_ICON.get(action, "")
        return (
            f"<tr><td style='font-weight:600'>{d['step']}</td>"
            f"<td style='color:{color};font-weight:600'>{icon} {action.upper()}</td>"
            f"<td style='color:#94a3b8;font-size:.88rem'>{d['reason']}</td></tr>"
        )
    rows = "".join(_drow(d) for d in decisions)
    return f"""
<div class="card">
  <h2>Agent Decision Log</h2>
  <p style="color:#64748b;font-size:.85rem;margin-bottom:10px">
    Scheduling decisions at {run_at}.
  </p>
  <table>
    <thead><tr><th>Pipeline Step</th><th>Decision</th><th>Reason</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
"""


def section_run_history(history: list) -> str:
    if not history or len(history) < 2:
        return ""
    rows = ""
    prev_auc = None
    for run in history:
        date   = run.get("run_at","?")[:10]
        rf_auc = run.get("rf_auc")
        best   = run.get("best_model","?")
        feats  = ", ".join(run.get("top3_features",[]))
        if prev_auc is not None and rf_auc is not None:
            delta = rf_auc - prev_auc
            delta_cell = _delta(delta)
        else:
            delta_cell = '<span style="color:#475569">—</span>'
        rows += (
            f"<tr><td style='color:#94a3b8'>{date}</td>"
            f"<td style='font-weight:600'>{f'{rf_auc:.4f}' if rf_auc else 'N/A'}</td>"
            f"<td>{delta_cell}</td>"
            f"<td style='color:#64748b'>{best}</td>"
            f"<td style='font-family:monospace;font-size:.82rem;color:#7dd3fc'>{feats}</td></tr>"
        )
        prev_auc = rf_auc
    return f"""
<div class="card">
  <h2>Run History</h2>
  <table>
    <thead><tr><th>Date</th><th>RF AUC</th><th>Δ AUC</th><th>Best Model</th><th>Top-3 Features</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
"""


def section_insight_analysis(insights_md: str) -> str:
    if not insights_md.strip():
        return ""
    return f"""
<div class="card">
  <h2>Insight Analysis</h2>
  <p style="color:#64748b;font-size:.85rem;margin-bottom:14px">
    LLM reasoning layer grounded in <code>data/diagnostic_summary.json</code>.
    This section explains model behavior and dataset limits without adding new numbers.
  </p>
  <div class="insight-md">
    {_markdown_to_html(insights_md)}
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results",      default=str(Path.home() / "openclaw-project/data/model_results.json"))
    parser.add_argument("--results-1500", default=str(Path.home() / "openclaw-project/data/model_results_1500.json"))
    parser.add_argument("--features",     default=str(Path.home() / "openclaw-project/data/features.csv"))
    parser.add_argument("--features-1500",default=str(Path.home() / "openclaw-project/data/features_1500.csv"))
    parser.add_argument("--out-dir",      default=str(Path.home() / "openclaw-project/reports"))
    parser.add_argument("--out-file",     default="")
    args = parser.parse_args()

    r500_path  = Path(args.results)
    r1500_path = Path(getattr(args, "results_1500"))
    f500_path  = Path(args.features)
    out_dir    = Path(args.out_dir)

    for p in (r500_path, f500_path):
        if not p.exists():
            print(f"[ERROR] Not found: {p}", flush=True)
            sys.exit(1)

    has_1500 = r1500_path.exists()

    print("[1/3] Loading data...", flush=True)
    r500  = json.loads(r500_path.read_text())
    df500 = pd.read_csv(f500_path)

    r1500: dict = {}
    if has_1500:
        r1500 = json.loads(r1500_path.read_text())
        print(f"  N1500 results loaded from {r1500_path}", flush=True)
    else:
        print(f"  [WARN] N1500 results not found at {r1500_path} — Part 2 will be omitted", flush=True)

    # Optional pipeline meta
    data_dir = r500_path.parent
    reports_dir = out_dir
    decision_log: dict = {}
    run_history:  list = []
    insights_md = ""
    for fname, target in [("decision_log.json", decision_log), ("run_history.json", run_history)]:
        p = data_dir / fname
        if p.exists():
            try:
                loaded = json.loads(p.read_text())
                if isinstance(loaded, dict):
                    decision_log.update(loaded)
                elif isinstance(loaded, list):
                    run_history.extend(loaded)
            except Exception:
                pass
    insights_path = reports_dir / "INSIGHTS.md"
    if insights_path.exists():
        try:
            insights_md = insights_path.read_text(encoding="utf-8")
        except Exception:
            insights_md = ""

    print("[2/3] Building HTML report...", flush=True)
    date_str  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta500   = r500["meta"]

    # ── Part 1 ────────────────────────────────────────────────────────────────
    part1_body = (
        part_header(1,
            "Main Experiment (N=500)",
            "Clean Single-Window Experiment with Rigorous Leakage Prevention") +
        s1_dataset(df500, meta500) +
        section_decision_log(decision_log) +
        section_run_history(run_history) +
        s1_feature_engineering() +
        s1_model_comparison(r500["models"]) +
        s1_precision_at_k(r500["models"]) +
        s1_ablation(r500.get("ablation", {})) +
        s1_time_split(r500.get("time_split", {})) +
        s1_feature_importance(r500["feature_importance"], r500.get("shap")) +
        s1_language_auc(r500.get("language_auc", {})) +
        s1_top10(r500.get("top10", [])) +
        s1_key_findings(r500["models"], r500["feature_importance"], r500.get("ablation", {})) +
        section_insight_analysis(insights_md)
    )

    # ── Part 2 ────────────────────────────────────────────────────────────────
    part2_body = ""
    if has_1500:
        ts_500  = r500.get("time_split", {})
        ts_1500 = r1500.get("time_split", {})
        part2_body = (
            part_header(2,
                "Scale & Distribution Shift Study (N=1500)",
                "Methodological Pitfalls Revealed by Naive Dataset Scaling") +
            s2_extension_strategy() +
            s2_scale_improvement(r500["models"], r1500["models"]) +
            s2_finding_sampling_contamination(
                r500.get("language_auc", {}),
                r1500.get("language_auc", {}),
                r1500.get("feature_importance", {})) +
            s2_finding_label_shift() +
            s2_finding_cv_overestimation(ts_500, ts_1500, r500["models"], r1500["models"]) +
            s2_discussion()
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GitHub Star Prediction — Two-Part Study {date_str}</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>GitHub Star Prediction — Two-Part Study</h1>
  <p class="subtitle">
    {timestamp} &nbsp;·&nbsp;
    Part 1: N=500 clean single-window experiment &nbsp;·&nbsp;
    Part 2: N=1500 scale &amp; distribution shift study
  </p>
  {part1_body}
  {part2_body}
  <p class="footer">openclaw-project · {timestamp}</p>
</body>
</html>"""

    out_dir.mkdir(parents=True, exist_ok=True)
    filename = args.out_file or f"{date_str}_two_part_report.html"
    out_path = out_dir / filename
    out_path.write_text(html, encoding="utf-8")
    latest_path = out_dir / "latest_final.html"
    latest_path.write_text(html, encoding="utf-8")

    # ── Render INSIGHTS.md → insights.html as a standalone page so the
    #    dashboard iframe can show it with proper formatting instead of
    #    raw Markdown text.
    insights_html_path = out_dir / "insights.html"
    if insights_md.strip():
        insights_body = _markdown_to_html(insights_md)
        insights_page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenClaw Insight Analysis</title>
  <style>{CSS}
  body {{ max-width: 920px; }}
  h1 {{ margin-bottom: 12px; }}
  h2 {{ color: #cbd5e1; text-transform: none; letter-spacing: 0; font-size: 1.15rem; margin-top: 28px; }}
  p, li {{ font-size: .95rem; }}
  </style>
</head>
<body>
  <p class="subtitle">{timestamp} &nbsp;·&nbsp; 渲染自 <code>reports/INSIGHTS.md</code></p>
  {insights_body}
  <p class="footer">openclaw-project · INSIGHTS.md HTML 渲染版</p>
</body>
</html>"""
        insights_html_path.write_text(insights_page, encoding="utf-8")
        print(f"Insights HTML → {insights_html_path}", flush=True)
    else:
        # Write a placeholder so the dashboard tab does not 404.
        placeholder = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>Insights</title>
<style>{CSS}</style></head><body>
<h1>洞察分析尚未生成</h1>
<p class="subtitle">请先运行 <code>insight-analysis</code> skill 以生成 <code>reports/INSIGHTS.md</code>。</p>
</body></html>"""
        insights_html_path.write_text(placeholder, encoding="utf-8")
        print(f"Insights HTML (placeholder) → {insights_html_path}", flush=True)

    print(f"[3/3] Done → {out_path}", flush=True)
    print(f"Latest alias → {latest_path}", flush=True)
    print(f"Open: open '{out_path}'", flush=True)


if __name__ == "__main__":
    main()
