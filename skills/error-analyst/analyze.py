#!/usr/bin/env python3
"""
Error Analysis Agent for OpenClaw.

Finds high-confidence false positives (FP) and false negatives (FN) from the
RF model's OOF predictions, then asks an LLM to identify common patterns.
Falls back to a deterministic statistical summary when no API key is set.

Input:
  data/features.csv        -- 500-row feature matrix with is_top20 label
  data/model_results.json  -- must contain oof_probs_rf list (run model-trainer first)

Output:
  data/error_analysis.json
  reports/error_analysis.html
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Load .env before reading env vars (supports OpenRouter and DeepSeek direct)
try:
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).parent.parent))
    from _dotenv import load_dotenv as _load_dotenv
    _loaded = _load_dotenv(_pl.Path(__file__).parent)
    if _loaded:
        print(f"  [env] loaded {_loaded}", flush=True)
except Exception:
    pass

# ── thresholds ──────────────────────────────────────────────────────────────
FP_PROB_THRESHOLD  = 0.65   # predicted ≥ this AND actually negative → FP
FN_PROB_THRESHOLD  = 0.35   # predicted ≤ this AND actually positive → FN
TOP_N              = 15     # how many cases to show / send to LLM

FEATURE_LABEL = {
    "lang_Python": "语言=Python", "lang_JavaScript": "语言=JavaScript",
    "lang_Go": "语言=Go", "lang_Rust": "语言=Rust",
    "lang_TypeScript": "语言=TypeScript", "lang_Other": "语言=其他",
    "is_org": "是否组织账号",
    "commits_30d": "前30天提交数", "issues_30d": "前30天Issue数",
    "prs_30d": "前30天PR数", "contributors_30d": "前30天贡献者数",
    "has_readme_30d": "30天内有README", "readme_len_30d": "README长度",
    "readme_has_image_30d": "README含图片", "readme_has_demo_url_30d": "README含演示链接",
    "activity_total_30d": "总活跃度", "commits_per_contributor_30d": "人均提交",
    "prs_per_issue_30d": "PR/Issue比", "has_pr_activity_30d": "有PR活动",
}

META_COLS = {
    "is_top20", "_created_at", "_full_name", "_language", "_current_stars",
    "_batch", "_readme_source", "_contributors_source",
}

KEY_FEATURES = [
    "commits_30d", "issues_30d", "prs_30d", "contributors_30d",
    "readme_len_30d", "activity_total_30d", "readme_has_demo_url_30d",
    "commits_per_contributor_30d", "has_pr_activity_30d",
]

# ── helpers ──────────────────────────────────────────────────────────────────

def esc(x: Any) -> str:
    return html_lib.escape(str(x))

def fmt(v, n=2):
    try:
        return f"{float(v):.{n}f}"
    except Exception:
        return str(v)


def load_data(features_path: Path, results_path: Path):
    df = pd.read_csv(features_path)
    results = json.loads(results_path.read_text(encoding="utf-8"))
    oof = results.get("oof_probs_rf", [])
    if not oof:
        print("[WARN] oof_probs_rf not found in model_results.json — re-running RF CV...",
              flush=True)
        oof = recompute_oof(df)
    return df, np.array(oof, dtype=float)


def recompute_oof(df: pd.DataFrame) -> list:
    """Fallback: re-run 5-fold RF CV to get OOF probabilities."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold

    feature_names = [c for c in df.columns if c not in META_COLS and not c.startswith("_")]
    X = df[feature_names].values
    y = df["is_top20"].values

    rf  = RandomForestClassifier(n_estimators=200, class_weight="balanced",
                                  random_state=42, n_jobs=-1)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    oof = np.zeros(len(y))
    for tr, val in skf.split(X, y):
        rf.fit(X[tr], y[tr])
        oof[val] = rf.predict_proba(X[val])[:, 1]
    return oof.tolist()


def extract_cases(df: pd.DataFrame, probs: np.ndarray, case_type: str) -> list[dict]:
    """Return top-N FP or FN cases sorted by confidence (most wrong first)."""
    y = df["is_top20"].values
    if case_type == "FP":
        mask  = (probs >= FP_PROB_THRESHOLD) & (y == 0)
        order = np.argsort(probs[mask])[::-1]          # highest prob first
    else:
        mask  = (probs <= FN_PROB_THRESHOLD) & (y == 1)
        order = np.argsort(probs[mask])                # lowest prob first

    idxs  = np.where(mask)[0][order][:TOP_N]
    cases = []
    for i in idxs:
        row = df.iloc[i]
        entry: dict = {
            "rank":          len(cases) + 1,
            "full_name":     str(row.get("_full_name", f"repo_{i}")),
            "language":      str(row.get("_language", "unknown")),
            "current_stars": int(row.get("_current_stars", 0)),
            "prob":          round(float(probs[i]), 4),
            "is_top20":      int(y[i]),
            "features":      {},
        }
        for feat in KEY_FEATURES:
            if feat in df.columns:
                entry["features"][feat] = float(row[feat])
        cases.append(entry)
    return cases


def cases_to_text(cases: list[dict], case_type: str) -> str:
    lines = []
    label = "假阳性（FP）：预测会火，实际未入Top20%" if case_type == "FP" \
            else "假阴性（FN）：预测不会火，实际进入Top20%"
    lines.append(f"=== {label} （共 {len(cases)} 条）===\n")
    for c in cases:
        feat_str = "  ".join(
            f"{FEATURE_LABEL.get(k, k)}={v:.1f}" for k, v in c["features"].items()
        )
        lines.append(
            f"[#{c['rank']}] {c['full_name']} ({c['language']}) "
            f"| 预测概率={c['prob']:.3f} | 最终stars={c['current_stars']}\n"
            f"  特征: {feat_str}"
        )
    return "\n".join(lines)


# ── LLM call ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "你是一名数据挖掘专家，负责分析机器学习模型的预测错误。"
    "请基于提供的案例数据，给出客观、有依据的分析，不要编造数据中没有的信息。"
    "当前模型只使用 strict-30d 的 19 个结构化特征：语言、owner 类型、前30天 commits/issues/PRs/contributors、"
    "前30天 README 统计与派生活跃度。模型没有使用仓库名、description、topics、TF-IDF、当前 README、"
    "当前 contributors、author_followers、author_public_repos 或 has_license。"
    "因此禁止把错误归因于这些未进入模型的字段。"
)

USER_PROMPT_TEMPLATE = """\
以下是 GitHub 仓库流行度预测模型（随机森林）的预测错误案例。
模型使用仓库**创建后 30 天内**的早期信号预测约一年后是否进入样本前 20%。
模型输入只包含这些 30 天内或历史可回溯的结构化特征：
语言、owner 类型、commits_30d、issues_30d、prs_30d、contributors_30d、
has_readme_30d、readme_len_30d、readme_has_image_30d、readme_has_demo_url_30d、
activity_total_30d、commits_per_contributor_30d、prs_per_issue_30d、has_pr_activity_30d。

请特别注意：
- 不要说模型依赖仓库名、description、topics、TF-IDF 或文本关键词，因为这些没有进入当前模型。
- 不要说模型依赖 author_followers、author_public_repos、当前 README 或当前 contributors，因为这些也没有进入当前模型。
- 改进建议必须是创建后 30 天内可采集、或能在历史 commit / API 中回溯到 30 天窗口内的信号。

{fp_text}

{fn_text}

请分析以下三个问题（每题 150-250 字，总共不超过 800 字）：

1. **假阳性规律**：这些 FP 案例（模型认为会火但实际没火）有什么共同的早期特征？
   模型可能被什么信号"欺骗"了？

2. **假阴性规律**：这些 FN 案例（模型认为不会火但实际火了）有什么特点？
   它们在 30 天内的信号为何偏弱，但最终仍然成功？

3. **改进启示**：这些错误案例对特征工程或数据收集有什么启示？
   有哪些 30 天内可观测的新信号值得尝试加入？

回答时直接给出分析内容，不要重复题目。
"""


def call_llm(fp_text: str, fn_text: str) -> str | None:
    api_key  = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        print("  [WARN] openai package not installed; skipping LLM analysis", flush=True)
        return None

    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = USER_PROMPT_TEMPLATE.format(fp_text=fp_text, fn_text=fn_text)
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=1200,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [WARN] LLM call failed: {e}", flush=True)
        return None


# ── deterministic fallback ────────────────────────────────────────────────────

def deterministic_analysis(fp_cases: list[dict], fn_cases: list[dict]) -> str:
    """Produce a simple statistical summary without any LLM."""
    def avg(cases, feat):
        vals = [c["features"].get(feat, 0) for c in cases if feat in c["features"]]
        return np.mean(vals) if vals else 0

    fp_commits  = avg(fp_cases,  "commits_30d")
    fn_commits  = avg(fn_cases,  "commits_30d")
    fp_issues   = avg(fp_cases,  "issues_30d")
    fn_issues   = avg(fn_cases,  "issues_30d")
    fp_readme   = avg(fp_cases,  "readme_len_30d")
    fn_readme   = avg(fn_cases,  "readme_len_30d")
    fp_stars    = np.mean([c["current_stars"] for c in fp_cases]) if fp_cases else 0
    fn_stars    = np.mean([c["current_stars"] for c in fn_cases]) if fn_cases else 0

    return f"""### 1. 假阳性规律（统计摘要，无 LLM）

FP 案例（{len(fp_cases)} 个）的早期信号较强但最终未入 Top 20%：
平均前 30 天提交 {fp_commits:.1f} 次、Issue {fp_issues:.1f} 个、README 长度 {fp_readme:.0f} 字符，
最终平均 star 数仅 {fp_stars:.0f}。早期活跃度高但可能缺乏持续维护或社区运营，
导致模型被"冲刺型"活跃信号误导。需要注意，当前模型没有使用仓库名、描述或文本向量，
所以这里的误判应优先理解为结构化早期行为信号不足以代表长期社区采用。

### 2. 假阴性规律（统计摘要，无 LLM）

FN 案例（{len(fn_cases)} 个）早期信号偏弱但最终进入 Top 20%：
平均前 30 天提交 {fn_commits:.1f} 次、Issue {fn_issues:.1f} 个、README 长度 {fn_readme:.0f} 字符，
最终平均 star 数 {fn_stars:.0f}。这类项目可能在 30 天窗口后才受到关注，
或因某次外部传播（博客、媒体报道）导致突发增长，早期信号无法预测。

### 3. 改进启示（统计摘要，无 LLM）

可考虑引入以下补充信号：
- 第 15-30 天相比第 1-14 天的增量活跃度（趋势特征）
- Issue / PR 的响应速度、关闭率和讨论长度
- README 在前 30 天内的变化量，而不仅是第 30 天快照
- 30 天窗口内是否出现 release、tag、CI 配置或测试目录
- 30 天窗口内是否被其他仓库引用或依赖（需要可回溯的历史数据源）

（设置 DEEPSEEK_API_KEY 后可获得 LLM 深度分析。）
"""


# ── HTML generation ───────────────────────────────────────────────────────────

CSS = """
:root{--bg:#fbfcfe;--ink:#232a31;--muted:#5d6977;--line:#e1e8f0;--soft:#f4f7fb;
  --card:#fff;--green:#2ca25f;--blue:#1f76d3;--orange:#f28500;--red:#d92d20;
  --shadow:0 10px 30px rgba(31,41,55,.06);}
*{box-sizing:border-box;}
body{margin:0;color:var(--ink);background:var(--bg);line-height:1.7;
  font-family:"LXGW WenKai","霞鹜文楷","PingFang SC","Microsoft YaHei",-apple-system,sans-serif;}
.layout{display:flex;align-items:flex-start;}
nav.side{position:sticky;top:0;align-self:flex-start;width:220px;min-width:220px;
  height:100vh;overflow-y:auto;padding:24px 16px;border-right:1px solid var(--line);background:#fff;}
nav.side .brand{font-weight:900;font-size:1rem;margin-bottom:4px;}
nav.side .brand small{display:block;color:var(--muted);font-weight:600;font-size:.72rem;margin-top:4px;}
nav.side ol{list-style:none;margin:16px 0 0;padding:0;}
nav.side li{margin:2px 0;}
nav.side a{display:block;color:#334155;font-weight:700;font-size:.84rem;padding:6px 10px;border-radius:8px;}
nav.side a:hover{background:var(--soft);text-decoration:none;}
main{flex:1;max-width:940px;margin:0 auto;padding:38px 42px 80px;}
h1{font-size:1.9rem;margin:0 0 6px;}
h2{font-size:1.25rem;margin:34px 0 10px;padding-top:6px;}
h2 .n{display:inline-flex;align-items:center;justify-content:center;width:1.6rem;height:1.6rem;
  background:var(--ink);color:#fff;border-radius:7px;font-size:.9rem;margin-right:9px;vertical-align:middle;}
h3{font-size:1rem;margin:20px 0 8px;color:var(--ink);}
p{margin:8px 0;}ul{margin:8px 0 8px 4px;padding-left:20px;}li{margin:4px 0;}
.sub{color:var(--muted);font-size:.93rem;}
.tag{display:inline-block;background:#eaf6ef;color:var(--green);border:1px solid #bfe3cd;
  border-radius:999px;padding:3px 12px;font-weight:800;font-size:.78rem;}
.callout{border:1px solid var(--line);border-left:5px solid var(--blue);background:#f5f9ff;
  border-radius:12px;padding:14px 18px;margin:14px 0;}
.callout.g{border-left-color:var(--green);background:#f1faf4;}
.callout.r{border-left-color:var(--red);background:#fef4f3;}
.callout.o{border-left-color:var(--orange);background:#fff8ef;}
table{width:100%;border-collapse:collapse;margin:12px 0;background:#fff;
  border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:.9rem;}
th,td{padding:10px 13px;border-bottom:1px solid var(--line);text-align:left;}
th{background:var(--soft);font-weight:800;color:#334155;}
tr:last-child td{border-bottom:0;}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;}
.fp-badge{display:inline-block;background:#fef4f3;color:var(--red);border:1px solid #fca5a5;
  border-radius:999px;padding:1px 8px;font-size:.78rem;font-weight:700;}
.fn-badge{display:inline-block;background:#f1faf4;color:var(--green);border:1px solid #86efac;
  border-radius:999px;padding:1px 8px;font-size:.78rem;font-weight:700;}
.analysis-body{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:22px 26px;margin:16px 0;white-space:pre-wrap;font-size:.93rem;line-height:1.75;}
footer{margin-top:42px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--muted);font-size:.83rem;}
@media(max-width:820px){nav.side{display:none;}main{padding:22px;}}
"""


def build_html(fp_cases: list[dict], fn_cases: list[dict],
               analysis_text: str, used_llm: bool) -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    method_tag = "LLM 深度分析" if used_llm else "确定性统计摘要（未配置 API Key）"

    def case_rows(cases, badge_class, badge_label):
        rows = ""
        for c in cases:
            feats = "  ".join(
                f"{FEATURE_LABEL.get(k,k).split('=')[-1]}={v:.1f}"
                for k, v in c["features"].items()
                if k in ("commits_30d","issues_30d","contributors_30d","readme_len_30d","activity_total_30d")
            )
            name_esc = esc(c['full_name'])
            rows += (f"<tr>"
                     f"<td>#{c['rank']}</td>"
                     f"<td><a href='https://github.com/{name_esc}' target='_blank'>{name_esc}</a></td>"
                     f"<td>{esc(c['language'])}</td>"
                     f"<td class='num'>{fmt(c['prob'],3)}</td>"
                     f"<td class='num'>{c['current_stars']}</td>"
                     f"<td class='sub' style='font-size:.82rem'>{esc(feats)}</td>"
                     f"</tr>")
        return rows

    fp_rows = case_rows(fp_cases, "fp-badge", "FP")
    fn_rows = case_rows(fn_cases, "fn-badge", "FN")

    # Convert analysis_text markdown-ish to safe HTML
    analysis_html = esc(analysis_text).replace("### ", "<strong>").replace("\n\n", "</strong>\n\n")

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenClaw · 错误分析 {date}</title>
<style>{CSS}</style></head>
<body><div class="layout">
<nav class="side">
  <div class="brand">OpenClaw<small>错误案例分析</small></div>
  <ol>
    <li><a href="#summary">1. 概览</a></li>
    <li><a href="#fp">2. 假阳性案例（FP）</a></li>
    <li><a href="#fn">3. 假阴性案例（FN）</a></li>
    <li><a href="#analysis">4. 模式分析</a></li>
  </ol>
</nav>
<main>
  <span class="tag">{esc(method_tag)}</span>
  <h1>模型错误案例分析</h1>
  <p class="sub">分析随机森林（RF）模型的高置信度预测错误，找出模型的系统性盲区。</p>

  <h2 id="summary"><span class="n">1</span>概览</h2>
  <p>OOF 预测概率阈值：FP ≥ {FP_PROB_THRESHOLD}（预测为正但实际为负），FN ≤ {FN_PROB_THRESHOLD}（预测为负但实际为正）。</p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0;">
    <div style="background:#fef4f3;border:1px solid #fca5a5;border-radius:14px;padding:18px 20px;">
      <div style="font-size:1.8rem;font-weight:900;color:var(--red)">{len(fp_cases)}</div>
      <div class="sub">高置信度假阳性（FP）<br>模型预测会火 · 实际未火</div>
    </div>
    <div style="background:#f1faf4;border:1px solid #86efac;border-radius:14px;padding:18px 20px;">
      <div style="font-size:1.8rem;font-weight:900;color:var(--green)">{len(fn_cases)}</div>
      <div class="sub">高置信度假阴性（FN）<br>模型预测不会火 · 实际火了</div>
    </div>
  </div>
  <div class="callout o"><b>为什么分析错误案例很重要？</b>
  高置信度的错误揭示了模型的系统性盲区——这些是模型"最确定"却预测错的样本，
  往往指向特征设计中未捕获的真实信号。</div>

  <h2 id="fp"><span class="n">2</span>假阳性案例（FP）<span class="fp-badge">预测会火 · 实际没火</span></h2>
  <p>预测概率 ≥ {FP_PROB_THRESHOLD}，但 <code>is_top20=0</code>，按预测概率从高到低排序。</p>
  <table><thead><tr>
    <th>#</th><th>仓库</th><th>语言</th>
    <th class="num">预测概率</th><th class="num">最终star</th><th>关键特征</th>
  </tr></thead><tbody>{fp_rows}</tbody></table>

  <h2 id="fn"><span class="n">3</span>假阴性案例（FN）<span class="fn-badge">预测不会火 · 实际火了</span></h2>
  <p>预测概率 ≤ {FN_PROB_THRESHOLD}，但 <code>is_top20=1</code>，按预测概率从低到高排序。</p>
  <table><thead><tr>
    <th>#</th><th>仓库</th><th>语言</th>
    <th class="num">预测概率</th><th class="num">最终star</th><th>关键特征</th>
  </tr></thead><tbody>{fn_rows}</tbody></table>

  <h2 id="analysis"><span class="n">4</span>模式分析</h2>
  <p class="sub">分析方法：{esc(method_tag)}</p>
  <div class="analysis-body">{analysis_html}</div>
  <div class="callout g"><b>OpenClaw 价值体现：</b>这类错误分析需要跨样本的推理能力——
  纯统计工具可以找出哪些样本预测错了，但无法从 15 个 FP 案例里归纳出"被冲刺型活跃度误导"
  这类模式。这正是将大模型引入分析链路的意义所在。</div>

  <footer>由 error-analyst 生成 · {now}</footer>
</main>
</div></body></html>"""


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenClaw error analyst")
    parser.add_argument("--features",  default=str(Path.home() / "openclaw-project/data/features.csv"))
    parser.add_argument("--results",   default=str(Path.home() / "openclaw-project/data/model_results.json"))
    parser.add_argument("--out-json",  default=str(Path.home() / "openclaw-project/data/error_analysis.json"))
    parser.add_argument("--out-html",  default=str(Path.home() / "openclaw-project/reports/error_analysis.html"))
    args = parser.parse_args()

    features_path = Path(args.features).expanduser()
    results_path  = Path(args.results).expanduser()
    out_json      = Path(args.out_json).expanduser()
    out_html      = Path(args.out_html).expanduser()

    for p in (features_path, results_path):
        if not p.exists():
            print(f"[ERROR] not found: {p}", flush=True)
            sys.exit(1)

    print("[1/4] Loading features and OOF probabilities...", flush=True)
    df, oof_probs = load_data(features_path, results_path)
    y = df["is_top20"].values
    print(f"  {len(df)} samples | OOF probs loaded (min={oof_probs.min():.3f} max={oof_probs.max():.3f})",
          flush=True)

    print("[2/4] Extracting FP / FN cases...", flush=True)
    fp_cases = extract_cases(df, oof_probs, "FP")
    fn_cases = extract_cases(df, oof_probs, "FN")
    print(f"  FP: {len(fp_cases)} cases (prob ≥ {FP_PROB_THRESHOLD}, is_top20=0)", flush=True)
    print(f"  FN: {len(fn_cases)} cases (prob ≤ {FN_PROB_THRESHOLD}, is_top20=1)", flush=True)

    print("[3/4] Generating analysis...", flush=True)
    fp_text = cases_to_text(fp_cases, "FP")
    fn_text = cases_to_text(fn_cases, "FN")
    llm_text = call_llm(fp_text, fn_text)
    used_llm = llm_text is not None
    if used_llm:
        print("  LLM analysis complete.", flush=True)
    else:
        print("  No API key — using deterministic fallback.", flush=True)
        llm_text = deterministic_analysis(fp_cases, fn_cases)

    print("[4/4] Writing outputs...", flush=True)
    result = {
        "fp_threshold": FP_PROB_THRESHOLD,
        "fn_threshold": FN_PROB_THRESHOLD,
        "fp_cases": fp_cases,
        "fn_cases": fn_cases,
        "analysis": llm_text,
        "used_llm": used_llm,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  JSON → {out_json}", flush=True)

    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(
        build_html(fp_cases, fn_cases, llm_text, used_llm),
        encoding="utf-8",
    )
    print(f"  HTML → {out_html}", flush=True)
    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
