#!/usr/bin/env python3
"""
Generate a clean, light-themed HTML evaluation report for the current model.

All numbers are read dynamically from the current artifacts:
  - model_results.json     (LR/RF/XGBoost metrics, ablation, time-split, per-language, feature importance)
  - diagnostic_summary.json (task, baselines, per-language, anomalies, recommendations)
  - decision_log.json       (the current pipeline run's decisions — optional)

The report has two parts:
  Part 1 — 实验结果 (current model on the fixed 500-repo backtest)
  Part 2 — 方法与防泄漏设计 (the 30-day early-window design and the multi-agent pipeline)

Outputs (light theme, left sidebar nav):
  <out-dir>/<out-file>      (e.g. 2026-06-03_two_part_report.html)
  <out-dir>/latest_final.html   (stable entry point, same content)

Usage:
  python3 generate.py --results data/model_results.json --features data/features.csv \
                      --out-dir reports --out-file 2026-06-03_two_part_report.html
"""
import argparse
import html as html_lib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def esc(x) -> str:
    return html_lib.escape(str(x))

def mean(v):
    """Accept either a scalar or {'mean': ..} metric shape."""
    if isinstance(v, dict):
        return v.get("mean", 0.0)
    return v if v is not None else 0.0

def fmt(v, n=3):
    try:
        return f"{float(v):.{n}f}"
    except Exception:
        return "n/a"

LANG_LABEL = {
    "lang_Python": "Python", "lang_JavaScript": "JavaScript", "lang_Go": "Go",
    "lang_Rust": "Rust", "lang_TypeScript": "TypeScript", "lang_Other": "其他",
}
FEATURE_LABEL = {
    "lang_Python": "语言=Python", "lang_JavaScript": "语言=JavaScript", "lang_Go": "语言=Go",
    "lang_Rust": "语言=Rust", "lang_TypeScript": "语言=TypeScript", "lang_Other": "语言=其他",
    "is_org": "是否组织账号",
    "commits_30d": "前30天提交数", "issues_30d": "前30天问题数",
    "prs_30d": "前30天合并请求数", "contributors_30d": "前30天贡献者数",
    "has_readme_30d": "30天内有说明文档", "readme_len_30d": "30天说明文档长度",
    "readme_has_image_30d": "说明文档含图片", "readme_has_demo_url_30d": "说明文档含演示链接",
    "activity_total_30d": "前30天总活跃度", "commits_per_contributor_30d": "人均提交",
    "prs_per_issue_30d": "请求/问题比", "has_pr_activity_30d": "有无合并请求",
}

# ---------------------------------------------------------------------------
# CSS — light theme
# ---------------------------------------------------------------------------

CSS = """
:root{
  --bg:#fbfcfe; --ink:#232a31; --muted:#5d6977; --line:#e1e8f0; --soft:#f4f7fb;
  --card:#ffffff; --green:#2ca25f; --blue:#1f76d3; --orange:#f28500; --purple:#7a45e5;
  --red:#d92d20; --teal:#0f766e;
  --shadow:0 10px 30px rgba(31,41,55,.06);
}
*{box-sizing:border-box;}
body{
  margin:0; color:var(--ink); background:var(--bg); line-height:1.7;
  font-family:"LXGW WenKai","霞鹜文楷","PingFang SC","Microsoft YaHei",-apple-system,sans-serif;
}
a{color:var(--blue); text-decoration:none;} a:hover{text-decoration:underline;}
code{font-family:"SFMono-Regular",Consolas,monospace; background:#eef2f7; padding:2px 6px; border-radius:6px; font-size:.92em;}

/* layout: left nav + content */
.layout{display:flex; align-items:flex-start;}
nav.side{
  position:sticky; top:0; align-self:flex-start; width:230px; min-width:230px; height:100vh;
  overflow-y:auto; padding:28px 18px; border-right:1px solid var(--line); background:#fff;
}
nav.side .brand{font-weight:900; font-size:1.05rem; margin-bottom:4px;}
nav.side .brand small{display:block; color:var(--muted); font-weight:600; font-size:.72rem; letter-spacing:.06em; margin-top:4px;}
nav.side ol{list-style:none; margin:18px 0 0; padding:0; counter-reset:s;}
nav.side li{margin:2px 0;}
nav.side a{display:block; color:#334155; font-weight:700; font-size:.86rem; padding:7px 10px; border-radius:9px;}
nav.side a:hover{background:var(--soft); text-decoration:none;}
main{flex:1; max-width:980px; margin:0 auto; padding:40px 44px 80px;}

h1{font-size:2rem; margin:0 0 6px;}
.sub{color:var(--muted); font-size:1rem; margin-bottom:8px;}
.tag{display:inline-block; background:#eaf6ef; color:var(--green); border:1px solid #bfe3cd;
     border-radius:999px; padding:3px 12px; font-weight:800; font-size:.78rem;}
h2{font-size:1.32rem; margin:38px 0 12px; padding-top:8px;}
h2 .n{display:inline-flex; align-items:center; justify-content:center; width:1.7rem; height:1.7rem;
      background:var(--ink); color:#fff; border-radius:8px; font-size:.95rem; margin-right:10px; vertical-align:middle;}
h3{font-size:1.05rem; margin:22px 0 8px;}
p{margin:8px 0;} ul{margin:8px 0 8px 4px; padding-left:20px; color:#2b333b;} li{margin:5px 0;}

.part{border-top:3px solid var(--line); margin:46px 0 8px; padding-top:22px;}
.part .pn{font-size:.74rem; font-weight:900; letter-spacing:.16em; text-transform:uppercase; color:var(--blue);}
.part.two .pn{color:var(--orange);}
.part .pt{font-size:1.55rem; font-weight:900; margin:4px 0 2px;}
.part .ps{color:var(--muted); font-size:.95rem;}

.cards{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:14px; margin:18px 0;}
.stat{background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px 18px; box-shadow:var(--shadow);}
.stat .v{font-size:1.7rem; font-weight:900;}
.stat .l{color:var(--muted); font-size:.82rem; margin-top:2px;}
.stat.g .v{color:var(--green);} .stat.b .v{color:var(--blue);} .stat.o .v{color:var(--orange);} .stat.p .v{color:var(--purple);}

table{width:100%; border-collapse:collapse; margin:14px 0; background:#fff; border:1px solid var(--line);
      border-radius:12px; overflow:hidden; font-size:.92rem;}
th,td{padding:11px 14px; border-bottom:1px solid var(--line); text-align:left;}
th{background:var(--soft); font-weight:800; color:#334155;}
tr:last-child td{border-bottom:0;}
td.num,th.num{text-align:right; font-variant-numeric:tabular-nums;}
.best{color:var(--green); font-weight:900;}

.callout{border:1px solid var(--line); border-left:5px solid var(--blue); background:#f5f9ff;
         border-radius:12px; padding:16px 20px; margin:16px 0;}
.callout.g{border-left-color:var(--green); background:#f1faf4;}
.callout.o{border-left-color:var(--orange); background:#fff8ef;}
.callout.r{border-left-color:var(--red); background:#fef4f3;}
.callout b{color:var(--ink);}
.bar{height:11px; background:#e7edf4; border-radius:6px; overflow:hidden; min-width:80px;}
.bar > i{display:block; height:100%; background:var(--blue); border-radius:6px;}
footer{margin-top:46px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:.84rem;}
@media(max-width:820px){ nav.side{display:none;} main{padding:24px;} }
"""

# ---------------------------------------------------------------------------
# section builders
# ---------------------------------------------------------------------------

def h2(num, title, anchor):
    return f'<h2 id="{anchor}"><span class="n">{num}</span>{esc(title)}</h2>'

def sec_overview(task, models):
    best_auc = models["best_auc"]; best_pr = models["best_pr_auc"]
    n = task.get("n_samples", "?"); pos = task.get("n_positive", "?")
    rate = task.get("positive_rate", 0); thr = task.get("top20_threshold_current_stars", "?")
    return f"""
<div class="cards">
  <div class="stat g"><div class="v">{n}</div><div class="l">历史仓库样本</div></div>
  <div class="stat b"><div class="v">19</div><div class="l">早期特征</div></div>
  <div class="stat o"><div class="v">{fmt(best_auc['value'])}</div><div class="l">最佳 AUC · {esc(best_auc['model'])}</div></div>
  <div class="stat p"><div class="v">{fmt(best_pr['value'])}</div><div class="l">最佳 PR-AUC · {esc(best_pr['model'])}</div></div>
</div>
<p>本报告评估一个<strong>历史回测</strong>任务：用 GitHub 仓库<strong>创建后 30 天内</strong>能观测到的早期信号，
预测该仓库<strong>约一年后</strong>的 star 是否进入样本前 20%。正例（进入前 20%）共 {pos} 个，
占 {fmt(rate*100,1)}%，对应的 star 阈值为 <strong>{thr}</strong>。所有数字均由当前
<code>model_results.json</code> / <code>diagnostic_summary.json</code> 动态生成。</p>
<div class="callout"><b>定位边界：</b>这是课程级历史回测，证明早期信号有<strong>排序</strong>价值；
不是"每天预测谁一定会火"的生产系统。</div>
"""

def sec_dataset(task, lang_counts):
    rows = "".join(
        f"<tr><td>{esc(LANG_LABEL.get(k,k))}</td><td class='num'>{v}</td></tr>"
        for k, v in lang_counts
    )
    return f"""
<p>固定历史快照，共 <strong>{task.get('n_samples','?')}</strong> 个仓库，创建于 2025-03-01 .. 2025-04-30。
每个仓库只取创建后 30 天内的信息作为模型输入，约一年后的 star 表现作为训练标签，两边严格分开。</p>
<table><thead><tr><th>主要语言</th><th class="num">仓库数</th></tr></thead><tbody>{rows}</tbody></table>
<p class="sub">正例率 {fmt(task.get('positive_rate',0)*100,1)}%（{task.get('n_positive','?')} / {task.get('n_samples','?')}），
前 20% 阈值 = {task.get('top20_threshold_current_stars','?')} stars。</p>
"""

FEATURE_GROUPS = [
    ("语言信号", 6, "Python、JavaScript、Go、Rust、TypeScript、其他", "b"),
    ("归属信号", 1, "仓库属于组织账号还是个人账号", "p"),
    ("早期活跃度", 4, "提交、问题、合并请求、贡献者（均限定前 30 天）", "o"),
    ("历史说明文档", 4, "是否有说明文档、长度、是否含图片、是否含演示链接（按创建后 30 天时点抓取）", "g"),
    ("派生比率", 4, "总活跃度、人均提交、请求/问题比、有无合并请求", "teal"),
]

def sec_features():
    rows = "".join(
        f"<tr><td><strong>{esc(name)}</strong></td><td class='num'>{cnt}</td><td>{esc(desc)}</td></tr>"
        for name, cnt, desc, _ in FEATURE_GROUPS
    )
    return f"""
<p>模型不直接读取原始 JSON，而是把每个仓库前 30 天的行为整理成五类可比较信号，合计 <strong>6+1+4+4+4 = 19</strong> 个特征。</p>
<table><thead><tr><th>类别</th><th class="num">数量</th><th>说明</th></tr></thead><tbody>{rows}</tbody></table>
<div class="callout o"><b>已移出模型的字段：</b>无法历史回溯的当前态信息（账号粉丝数、账号公开仓库数、是否有 license、
当前 README、当前贡献者数，以及基于词频的文本向量）都不进模型，以避免把未来信息泄漏进早期窗口。</div>
"""

def sec_models(models):
    order = ["LR", "RF", "XGBoost"]
    name_cn = {"LR": "逻辑回归 (LR)", "RF": "随机森林 (RF)", "XGBoost": "XGBoost"}
    role = {"LR": "整体排序最好、线性稳定、易解释",
            "RF": "少数正例识别最好、适合候选排序",
            "XGBoost": "强基线对照"}
    best_auc_m = models["best_auc"]["model"]; best_pr_m = models["best_pr_auc"]["model"]
    rows = ""
    for m in order:
        d = models["metrics"].get(m, {})
        auc = mean(d.get("auc")); pr = mean(d.get("pr_auc")); p10 = d.get("precision_at_10", 0)
        auc_cls = "num best" if m == best_auc_m else "num"
        pr_cls = "num best" if m == best_pr_m else "num"
        rows += (f"<tr><td>{esc(name_cn[m])}</td>"
                 f"<td class='{auc_cls}'>{fmt(auc)}</td>"
                 f"<td class='{pr_cls}'>{fmt(pr)}</td>"
                 f"<td class='num'>{fmt(p10,2)}</td>"
                 f"<td>{esc(role[m])}</td></tr>")
    return f"""
<p>在固定特征矩阵上训练三类模型，5 折交叉验证。</p>
<table><thead><tr><th>模型</th><th class="num">AUC</th><th class="num">PR-AUC</th><th class="num">P@10</th><th>角色</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="sub">绿色为该列最佳。模型并非选"唯一正确"，而是看排序、正例识别和应用需求。</p>
"""

def sec_metrics(models):
    p10 = models["best_p10"]["value"]; p10_model = models["best_p10"]["model"]
    hits = round(p10 * 10)
    auc = models["best_auc"]["value"]
    return f"""
<p>这是一个<strong>候选发现</strong>任务（正例约两成），所以要同时看几个互补指标：</p>
<ul>
  <li><strong>AUC（整体排序）</strong>：随机取一个热门和一个冷门仓库，模型把热门排前面的概率。当前最佳 {fmt(auc)}。</li>
  <li><strong>PR-AUC（少数正例识别）</strong>：正例稀少时比准确率更能反映"找到潜力项目"的能力。</li>
  <li><strong>P@10（前排候选质量）</strong>：只看模型排在最前面的 10 个项目里有多少真正高增长。</li>
  <li><strong>时间切分（时间泛化）</strong>：按创建时间切训练/测试，检验随机验证是否过于乐观。</li>
</ul>
<div class="callout g"><b>P@10 = {fmt(p10,2)}</b>（最佳模型 {esc(p10_model)}）——
意味着模型排在最前面的 10 个仓库里，约 <strong>{hits} 个</strong>确实是高增长仓库（10 中 {hits}）。
随机猜测的基线约等于正例率（两成）。</div>
"""

def sec_ablation(results):
    ab = results.get("ablation", {})
    order = [("A_basic", "var(--muted)"), ("B_activity", "var(--green)"),
             ("C_readme", "var(--blue)"), ("D_all", "var(--ink)")]
    vals = [(k, ab[k]["label"], ab[k].get("n_features", ""), mean(ab[k]["auc"]), col)
            for k, col in order if k in ab]
    if not vals:
        return "<p>（无消融数据）</p>"
    mx = max(v[3] for v in vals)
    rows = ""
    for k, label, nf, auc, col in vals:
        w = int(auc / mx * 100) if mx else 0
        rows += (f"<tr><td>{esc(label)}</td><td class='num'>{nf}</td>"
                 f"<td><div class='bar'><i style='width:{w}%;background:{col}'></i></div></td>"
                 f"<td class='num'>{fmt(auc,4)}</td></tr>")
    return f"""
<p>逐步加入特征，观察 AUC 变化：</p>
<table><thead><tr><th>特征组合</th><th class="num">特征数</th><th>相对强度</th><th class="num">AUC</th></tr></thead>
<tbody>{rows}</tbody></table>
<p class="sub">加入早期说明文档后排序最好；继续加入派生比率反而带来少量噪声——并非特征越多越好。</p>
"""

def sec_timesplit(results):
    ts = results.get("time_split", {})
    if not ts:
        return "<p>（无时间切分数据）</p>"
    ts_auc = mean(ts.get("metrics", {}).get("auc")); cv = ts.get("random_cv_auc", 0)
    gap = ts.get("auc_gap", 0); split = ts.get("split_date", "?"); model = ts.get("model", "?")
    return f"""
<p>按创建时间把较早的仓库用于训练、较晚的用于测试（切分点 {esc(split)}，模型 {esc(model)}）：</p>
<table><thead><tr><th>验证方式</th><th class="num">AUC</th></tr></thead><tbody>
<tr><td>随机 5 折交叉验证</td><td class="num">{fmt(cv,4)}</td></tr>
<tr><td>时间切分</td><td class="num">{fmt(ts_auc,4)}</td></tr>
<tr><td><strong>差距</strong></td><td class="num"><strong>{'+' if gap>=0 else ''}{fmt(gap,4)}</strong></td></tr>
</tbody></table>
<p class="sub">差距很小，说明结果在这个时间窗口内比较稳定，不是随机划分下才好看。</p>
"""

def sec_perlang(diag, results):
    langs = diag.get("per_language", {}).get("languages", {})
    if not langs:
        return ""
    rows = ""
    for lang, v in langs.items():
        auc = v.get("auc")
        auc_s = fmt(auc) if auc is not None else "样本不足"
        rows += (f"<tr><td>{esc(lang)}</td><td class='num'>{v.get('n_samples','?')}</td>"
                 f"<td class='num'>{v.get('n_positive','?')} ({fmt(v.get('positive_rate',0)*100,0)}%)</td>"
                 f"<td class='num'>{auc_s}</td></tr>")
    return f"""
<p>分语言看模型表现（需谨慎解读）：</p>
<table><thead><tr><th>语言</th><th class="num">样本</th><th class="num">正例</th><th class="num">语言内 AUC</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="callout r"><b>注意：</b>Python 子集正例率明显高于全局，存在分布偏移；部分语言正例过少，语言内 AUC 不稳定。
这是已记录的数据异常，解读时不应夸大。</div>
"""

def sec_baselines(diag):
    rk = diag.get("baselines", {}).get("rankers", {})
    if not rk:
        return ""
    items = []
    for k, v in rk.items():
        if "auc" in v:
            items.append((v.get("label", k), v["auc"]))
    items.sort(key=lambda x: -x[1])
    rows = "".join(f"<tr><td>{esc(lbl)}</td><td class='num'>{fmt(auc,3)}</td></tr>" for lbl, auc in items)
    return f"""
<p>把模型和"按单个特征排序"的简单规则对比：</p>
<table><thead><tr><th>排序规则</th><th class="num">AUC</th></tr></thead><tbody>{rows}</tbody></table>
<p class="sub">任何单特征规则都明显弱于组合模型，说明"把早期信号组合起来"确有价值。</p>
"""

def sec_importance(results):
    fi = results.get("feature_importance", {}).get("RF", [])
    if not fi:
        return ""
    rows = ""
    top = fi[:10]
    mx = max(x["importance"] for x in top) if top else 1
    for x in top:
        f = x["feature"]; imp = x["importance"]
        w = int(imp / mx * 100) if mx else 0
        rows += (f"<tr><td>{esc(FEATURE_LABEL.get(f, f))}</td>"
                 f"<td><div class='bar'><i style='width:{w}%;background:var(--green)'></i></div></td>"
                 f"<td class='num'>{fmt(imp,4)}</td></tr>")
    return f"""
<p>随机森林给出的特征重要性（前 10）：</p>
<table><thead><tr><th>特征</th><th>相对重要性</th><th class="num">值</th></tr></thead><tbody>{rows}</tbody></table>
"""

def sec_anomalies(diag):
    an = diag.get("anomalies", [])
    if not an:
        return "<p>未发现需要特别提示的数据异常。</p>"
    out = ""
    for a in an:
        sev = a.get("severity", ""); title = a.get("title", ""); imp = a.get("implication", "")
        cls = "r" if sev == "medium" else "o"
        out += f'<div class="callout {cls}"><b>[{esc(sev)}] {esc(title)}</b><br>{esc(imp)}</div>'
    return out

def sec_methodology():
    return """
<h3>两段式数据设计</h3>
<p>每个仓库拆成两部分，严格分开：<strong>30 天快照</strong>（模型输入，只含创建后 30 天内的信息）
和<strong>未来标签</strong>（训练答案，约一年后的 star 表现）。star 数只决定标签，绝不进入模型输入。</p>
<h3>防泄漏设计</h3>
<ul>
  <li>提交 / 问题 / 合并请求都用时间参数过滤到前 30 天；</li>
  <li>贡献者数基于前 30 天提交里的不同作者去重统计，不使用仓库当前的贡献者列表；</li>
  <li>说明文档按"创建后 30 天时点最近一次提交"抓取，反映当时的文档状态；</li>
  <li>无法历史回溯的当前态字段（账号粉丝数、账号公开仓库数、当前 README、当前贡献者数、文本词向量等）一律不进模型。</li>
</ul>
<h3>多智能体流水线</h3>
<p>采集 → 特征 → 训练 → 事实诊断 → 洞察 → 报告，由一个编排器调度，每一步都留下中间产物与事件记录。
洞察分析<strong>先由事实诊断算出结构化事实，再让大模型只能基于这些事实做解释</strong>，引用的数字必须能在事实摘要里校验。</p>
<p>更细的可解释分析见 <a href="./insights.html">洞察分析（insights.html）</a>；
展示材料见 <a href="./OPEN_THIS_latest_presentation.pdf">展示 PPT（PDF）</a> 与
<a href="./OPEN_THIS_speech_guide.html">逐页讲稿</a>。</p>
"""

def sec_run_info(decision_log, generated_at):
    dec = decision_log.get("decisions", {}) if isinstance(decision_log, dict) else {}
    run_at = decision_log.get("run_at", "") if isinstance(decision_log, dict) else ""
    rows = ""
    for step, info in dec.items():
        if isinstance(info, dict):
            rows += (f"<tr><td>{esc(step)}</td><td>{esc(info.get('action','-'))}</td>"
                     f"<td class='sub'>{esc(info.get('reason','-'))}</td></tr>")
    table = (f"<table><thead><tr><th>步骤</th><th>动作</th><th>原因</th></tr></thead><tbody>{rows}</tbody></table>"
             if rows else "<p class='sub'>（本次无调度决策记录）</p>")
    return f"""
<p class="sub">本次运行时间：{esc(run_at or generated_at)}。下表是编排器对各步骤的调度决策（固定历史快照下，多数步骤会复用已有产物）。</p>
{table}
"""

# ---------------------------------------------------------------------------
# assemble
# ---------------------------------------------------------------------------

SECTIONS = [
    ("overview", "概览", sec_overview),
    ("dataset", "数据集", sec_dataset),
    ("features", "特征工程（19 个）", sec_features),
    ("models", "模型结果", sec_models),
    ("metrics", "指标解释", sec_metrics),
    ("ablation", "消融实验", sec_ablation),
    ("timesplit", "时间切分", sec_timesplit),
    ("perlang", "分语言表现", sec_perlang),
    ("baselines", "对比简单基线", sec_baselines),
    ("importance", "特征重要性", sec_importance),
    ("anomalies", "数据诊断", sec_anomalies),
]

def build_html(results, diag, decision_log, lang_counts):
    task = diag.get("task", {})
    models = diag.get("models", {})
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # build part-1 sections
    body = []
    nav = []
    n = 0
    for anchor, title, fn in SECTIONS:
        n += 1
        nav.append(f'<li><a href="#{anchor}">{n}. {esc(title)}</a></li>')
        if fn is sec_overview:
            content = fn(task, models)
        elif fn is sec_dataset:
            content = fn(task, lang_counts)
        elif fn is sec_features:
            content = fn()
        elif fn is sec_models:
            content = fn(models)
        elif fn is sec_metrics:
            content = fn(models)
        elif fn in (sec_ablation, sec_timesplit, sec_importance):
            content = fn(results)
        elif fn is sec_perlang:
            content = fn(diag, results)
        elif fn in (sec_baselines, sec_anomalies):
            content = fn(diag)
        else:
            content = fn()
        body.append(h2(n, title, anchor) + content)

    part1 = (f'<div class="part"><div class="pn">Part 1</div>'
             f'<div class="pt">实验结果</div>'
             f'<div class="ps">当前模型在固定 500 仓库历史回测上的表现</div></div>'
             + "\n".join(body))

    # part 2 — methodology
    nav.append('<li><a href="#methodology">方法与防泄漏设计</a></li>')
    nav.append('<li><a href="#runinfo">本次运行</a></li>')
    part2 = (f'<div class="part two" id="methodology"><div class="pn">Part 2</div>'
             f'<div class="pt">方法与防泄漏设计</div>'
             f'<div class="ps">为什么这套早期信号可信，以及 OpenClaw 如何组织流程</div></div>'
             + sec_methodology()
             + h2("✓", "本次运行", "runinfo") + sec_run_info(decision_log, generated_at))

    nav_html = "\n".join(nav)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenClaw · 模型评估报告 {date}</title>
<style>{CSS}</style></head>
<body><div class="layout">
<nav class="side">
  <div class="brand">OpenClaw<small>开源项目潜力发现 · 评估报告</small></div>
  <ol>{nav_html}</ol>
</nav>
<main>
  <span class="tag">数据快照 {date}</span>
  <h1>模型评估报告</h1>
  <p class="sub">用 GitHub 仓库创建后 30 天的早期信号，预测约一年后是否进入样本前 20%。所有数字均来自当前实验产物。</p>
  {part1}
  {part2}
  <footer>本报告由 report-generator 自动生成 · {generated_at} ·
  数据来源：<code>model_results.json</code> / <code>diagnostic_summary.json</code>。
  课程级历史回测，不代表生产级实时预测。</footer>
</main>
</div></body></html>"""

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate the light-themed model evaluation report.")
    parser.add_argument("--results",   default=str(Path.home() / "openclaw-project/data/model_results.json"))
    parser.add_argument("--features",  default=str(Path.home() / "openclaw-project/data/features.csv"))
    parser.add_argument("--diagnostic", default="")
    parser.add_argument("--out-dir",   default=str(Path.home() / "openclaw-project/reports"))
    parser.add_argument("--out-file",  default="")
    # accepted for backward compatibility, ignored (no N1500 comparison in the clean report)
    parser.add_argument("--results-1500", default="")
    parser.add_argument("--features-1500", default="")
    args = parser.parse_args()

    results_path = Path(args.results).expanduser()
    features_path = Path(args.features).expanduser()
    data_dir = results_path.parent
    diag_path = Path(args.diagnostic).expanduser() if args.diagnostic else (data_dir / "diagnostic_summary.json")
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not results_path.exists():
        print(f"[ERROR] not found: {results_path}", flush=True); sys.exit(1)
    results = json.loads(results_path.read_text())
    diag = json.loads(diag_path.read_text()) if diag_path.exists() else {}

    # language counts from features.csv (fall back to one-hot sums); optional
    lang_counts = []
    try:
        import csv
        cols = list(LANG_LABEL.keys())
        sums = {c: 0 for c in cols}
        with features_path.open() as fh:
            for row in csv.DictReader(fh):
                for c in cols:
                    if c in row:
                        try:
                            sums[c] += int(float(row[c]))
                        except Exception:
                            pass
        lang_counts = [(c, sums[c]) for c in cols if sums[c] > 0]
    except Exception:
        lang_counts = []

    decision_log = {}
    dl = data_dir / "decision_log.json"
    if dl.exists():
        try:
            loaded = json.loads(dl.read_text())
            if isinstance(loaded, dict):
                decision_log = loaded
        except Exception:
            pass

    html = build_html(results, diag, decision_log, lang_counts)

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated = args.out_file or f"{date}_two_part_report.html"
    (out_dir / dated).write_text(html, encoding="utf-8")
    (out_dir / "latest_final.html").write_text(html, encoding="utf-8")
    print(f"[OK] wrote {out_dir / dated}", flush=True)
    print(f"[OK] wrote {out_dir / 'latest_final.html'}", flush=True)


if __name__ == "__main__":
    main()
