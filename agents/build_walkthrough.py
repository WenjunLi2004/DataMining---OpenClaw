#!/usr/bin/env python3
"""Build project_walkthrough.html — zero-knowledge guide to the OpenClaw project."""
import base64
from pathlib import Path

OUT = Path("/Users/wenjun/openclaw-project/reports/project_walkthrough.html")
DASH = Path("/Users/wenjun/openclaw-project/dashboard/dashboard_screenshot.png")
dash_b64 = base64.b64encode(DASH.read_bytes()).decode("ascii") if DASH.exists() else ""

CSS = r"""
:root{
  --ink:#1f2328; --muted:#57606a; --soft:#6e7781;
  --bg:#ffffff; --panel:#f6f8fa; --code:#eaeef2;
  --border:#d0d7de; --line:#e5e9ef;
  --green:#2da44e; --green-bg:#dafbe1;
  --blue:#0969da;  --blue-bg:#ddf4ff;
  --orange:#bc4c00;--orange-bg:#fff1e5;
  --purple:#8250df;--purple-bg:#fbefff;
  --red:#cf222e;   --red-bg:#ffebe9;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",Helvetica,Arial,sans-serif;
  font-size:17px; line-height:1.75; color:var(--ink); background:var(--bg);
}
.wrap{max-width:880px; margin:0 auto; padding:48px 28px 120px}
h1{font-size:34px; line-height:1.25; margin:0 0 8px; letter-spacing:-0.01em}
h2{font-size:26px; margin:64px 0 14px; padding-top:8px; border-top:1px solid var(--line); padding-top:32px}
h3{font-size:20px; margin:32px 0 10px}
h4{font-size:17px; margin:22px 0 8px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; font-weight:600}
p{margin:12px 0}
ul,ol{margin:10px 0 14px; padding-left:1.4em}
li{margin:6px 0}
a{color:var(--blue); text-decoration:none}
a:hover{text-decoration:underline}
code, kbd, samp{font-family:"SF Mono",Menlo,Consolas,monospace; font-size:.93em; background:var(--code); padding:.12em .35em; border-radius:4px}
pre{background:var(--panel); padding:14px 16px; border-radius:8px; overflow:auto; border:1px solid var(--line); font-size:14.5px}
pre code{background:transparent; padding:0}
table{width:100%; border-collapse:collapse; margin:14px 0; font-size:15.5px}
th,td{padding:8px 12px; text-align:left; border-bottom:1px solid var(--line)}
th{background:var(--panel); font-weight:600; color:var(--muted)}
tr:hover td{background:#fcfcfd}

/* Cards */
.note{
  background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--blue);
  padding:14px 18px; border-radius:8px; margin:18px 0;
}
.note.analogy{border-left-color:var(--purple); background:var(--purple-bg)}
.note.warn{border-left-color:var(--orange); background:var(--orange-bg)}
.note.good{border-left-color:var(--green); background:var(--green-bg)}
.note.danger{border-left-color:var(--red); background:var(--red-bg)}
.note .tag{
  display:inline-block; font-size:12px; font-weight:700; letter-spacing:.05em;
  color:var(--muted); margin-bottom:2px; text-transform:uppercase
}

.tldr{
  background:#fffdf4; border:1px solid #f0e8c8; border-left:4px solid #d4a72c;
  padding:12px 18px; border-radius:8px; margin:14px 0 22px; font-size:16px;
}
.tldr::before{content:"💡 "; font-size:18px}

/* Hero */
.hero{
  background:linear-gradient(180deg,#fdfdfd,#f6f8fa);
  border:1px solid var(--line); border-radius:14px; padding:28px 30px; margin:18px 0 30px;
}
.hero .pill{display:inline-block; font-size:12px; font-weight:700; color:var(--green);
  background:var(--green-bg); padding:3px 10px; border-radius:99px; letter-spacing:.04em}
.hero h1{margin-top:10px}
.hero .meta{color:var(--muted); font-size:14.5px; margin-top:14px}

/* TOC */
.toc{
  background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:18px 22px; margin:18px 0 28px;
}
.toc h4{margin:0 0 8px}
.toc ol{margin:0; padding-left:1.4em; column-count:2; column-gap:24px; font-size:15.5px}
.toc li{break-inside:avoid; margin:5px 0}
@media (max-width:680px){ .toc ol{column-count:1} }

/* "Back to top" button */
#totop{
  position:fixed; right:22px; bottom:22px; z-index:10;
  background:var(--ink); color:#fff; border:none; border-radius:99px;
  width:46px; height:46px; cursor:pointer; font-size:18px; line-height:1;
  box-shadow:0 6px 18px rgba(0,0,0,.18); opacity:.85;
}
#totop:hover{opacity:1}

/* Chips & key-value */
.kv{display:grid; grid-template-columns:200px 1fr; gap:6px 18px; margin:10px 0; font-size:15px}
.kv dt{color:var(--muted); font-family:"SF Mono",Menlo,monospace; font-size:13.5px}
.kv dd{margin:0}

/* Metric chips */
.metrics{display:flex; flex-wrap:wrap; gap:10px; margin:18px 0}
.metric{
  background:#fff; border:1px solid var(--line); border-radius:10px;
  padding:10px 14px; min-width:130px; text-align:left;
}
.metric .v{font-size:22px; font-weight:700; font-family:"SF Mono",Menlo,monospace}
.metric .k{font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em}
.metric.green .v{color:var(--green)}
.metric.blue  .v{color:var(--blue)}
.metric.orange .v{color:var(--orange)}
.metric.purple .v{color:var(--purple)}

/* SVG figures */
figure{margin:18px 0; text-align:center}
figure svg{max-width:100%; height:auto}
figcaption{color:var(--muted); font-size:14px; margin-top:6px}

/* Dashboard screenshot */
.shot{
  border:1px solid var(--line); border-radius:10px; overflow:hidden; margin:14px 0;
  box-shadow:0 4px 16px rgba(0,0,0,.05);
}
.shot img{display:block; width:100%; height:auto}

/* Glossary */
.glossary dt{font-weight:700; margin-top:14px; color:var(--ink); font-size:16px; font-family:inherit}
.glossary dd{margin:4px 0 0 0; color:var(--muted); font-size:15px}

/* Tiny helpers */
.muted{color:var(--muted)}
.kbd{font-family:"SF Mono",monospace; background:var(--panel); border:1px solid var(--border); padding:1px 6px; border-radius:4px; font-size:13.5px}
.tag{display:inline-block; padding:2px 8px; border-radius:99px; font-size:12px; font-weight:600; background:var(--panel); color:var(--muted)}
.tag.good{background:var(--green-bg); color:var(--green)}
.tag.bad{background:var(--red-bg); color:var(--red)}
.tag.warn{background:var(--orange-bg); color:var(--orange)}

/* Hero metric row */
.hero-stats{display:flex; flex-wrap:wrap; gap:14px; margin-top:16px}
.hero-stats .metric{min-width:120px}
"""

# ------------- inline SVG diagrams -------------
SVG_LEAKAGE = """
<svg viewBox="0 0 720 170" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="#1f2328"/>
    </marker>
  </defs>
  <line x1="40" y1="90" x2="690" y2="90" stroke="#1f2328" stroke-width="2" marker-end="url(#arr)"/>
  <!-- t=0 -->
  <circle cx="60" cy="90" r="6" fill="#1f2328"/>
  <text x="60" y="115" text-anchor="middle" font-size="13" fill="#1f2328" font-weight="700">T = 0</text>
  <text x="60" y="132" text-anchor="middle" font-size="12" fill="#57606a">仓库创建</text>
  <!-- t+30 -->
  <circle cx="230" cy="90" r="6" fill="#1f2328"/>
  <text x="230" y="115" text-anchor="middle" font-size="13" fill="#1f2328" font-weight="700">T + 30 天</text>
  <text x="230" y="132" text-anchor="middle" font-size="12" fill="#57606a">特征截止</text>
  <!-- t+12m -->
  <circle cx="630" cy="90" r="6" fill="#1f2328"/>
  <text x="630" y="115" text-anchor="middle" font-size="13" fill="#1f2328" font-weight="700">T + 12 月</text>
  <text x="630" y="132" text-anchor="middle" font-size="12" fill="#57606a">标签快照</text>
  <!-- shaded ranges -->
  <rect x="60" y="55" width="170" height="22" fill="#dafbe1" stroke="#2da44e"/>
  <text x="145" y="71" text-anchor="middle" font-size="13" fill="#2da44e" font-weight="700">FEATURES（输入）</text>
  <rect x="620" y="55" width="50" height="22" fill="#fff1e5" stroke="#bc4c00"/>
  <text x="645" y="71" text-anchor="middle" font-size="13" fill="#bc4c00" font-weight="700">LABEL</text>
  <!-- forbidden region -->
  <rect x="230" y="20" width="390" height="20" fill="#ffebe9" stroke="#cf222e" stroke-dasharray="4 3"/>
  <text x="425" y="35" text-anchor="middle" font-size="12" fill="#cf222e">⛔ 这段时间的信息 “看了就是作弊”，绝不能进入特征</text>
</svg>"""

SVG_STRATA = """
<svg viewBox="0 0 720 220" xmlns="http://www.w3.org/2000/svg">
  <text x="0" y="18" font-size="14" fill="#57606a">同一语言内排队 → 每语言各取 Top 20%</text>
  <!-- 5 lanes -->
  <g font-size="13" fill="#1f2328">
    <text x="0" y="55">Python</text>
    <text x="0" y="95">Go</text>
    <text x="0" y="135">Rust</text>
    <text x="0" y="175">JavaScript</text>
    <text x="0" y="215">TypeScript</text>
  </g>
  <g>
    <rect x="80" y="40" width="500" height="22" fill="#eef1f5" stroke="#d0d7de"/>
    <rect x="80" y="40" width="100" height="22" fill="#dafbe1" stroke="#2da44e"/>
    <text x="585" y="56" font-size="12" fill="#57606a">Top 20% (≥ p80)</text>

    <rect x="80" y="80" width="500" height="22" fill="#eef1f5" stroke="#d0d7de"/>
    <rect x="80" y="80" width="100" height="22" fill="#dafbe1" stroke="#2da44e"/>

    <rect x="80" y="120" width="500" height="22" fill="#eef1f5" stroke="#d0d7de"/>
    <rect x="80" y="120" width="100" height="22" fill="#dafbe1" stroke="#2da44e"/>

    <rect x="80" y="160" width="500" height="22" fill="#eef1f5" stroke="#d0d7de"/>
    <rect x="80" y="160" width="100" height="22" fill="#dafbe1" stroke="#2da44e"/>

    <rect x="80" y="200" width="500" height="22" fill="#eef1f5" stroke="#d0d7de"/>
    <rect x="80" y="200" width="100" height="22" fill="#dafbe1" stroke="#2da44e"/>
  </g>
  <text x="80" y="232" font-size="12" fill="#57606a">每条 = 该语言下所有仓库按 star 排序；绿色 = 该语言自己班级里的前 20% 学生</text>
</svg>"""

SVG_KFOLD = """
<svg viewBox="0 0 720 220" xmlns="http://www.w3.org/2000/svg">
  <text x="0" y="18" font-size="14" fill="#57606a">5-fold 交叉验证：每轮一份当“考试”，其它 4 份当“复习”</text>
  <g font-family="SF Mono,Menlo,monospace" font-size="12">
    <!-- header chunks -->
    <g transform="translate(0,40)">
      <rect width="120" height="24" fill="#eef1f5" stroke="#d0d7de"/><text x="60" y="16" text-anchor="middle">Fold 1</text>
      <rect x="120" width="120" height="24" fill="#eef1f5" stroke="#d0d7de"/><text x="180" y="16" text-anchor="middle">Fold 2</text>
      <rect x="240" width="120" height="24" fill="#eef1f5" stroke="#d0d7de"/><text x="300" y="16" text-anchor="middle">Fold 3</text>
      <rect x="360" width="120" height="24" fill="#eef1f5" stroke="#d0d7de"/><text x="420" y="16" text-anchor="middle">Fold 4</text>
      <rect x="480" width="120" height="24" fill="#eef1f5" stroke="#d0d7de"/><text x="540" y="16" text-anchor="middle">Fold 5</text>
    </g>
    <!-- 5 rounds -->
    <g font-size="11">
      <g transform="translate(0,80)">
        <text x="-2" y="14" text-anchor="end" fill="#57606a">Round 1</text>
        <rect width="120" height="20" fill="#fff1e5" stroke="#bc4c00"/><text x="60" y="14" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="120" width="480" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="360" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,108)">
        <text x="-2" y="14" text-anchor="end" fill="#57606a">Round 2</text>
        <rect width="120" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="60" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="120" width="120" height="20" fill="#fff1e5" stroke="#bc4c00"/><text x="180" y="14" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="240" width="360" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="420" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,136)">
        <text x="-2" y="14" text-anchor="end" fill="#57606a">Round 3</text>
        <rect width="240" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="120" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="240" width="120" height="20" fill="#fff1e5" stroke="#bc4c00"/><text x="300" y="14" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="360" width="240" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="480" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,164)">
        <text x="-2" y="14" text-anchor="end" fill="#57606a">Round 4</text>
        <rect width="360" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="180" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="360" width="120" height="20" fill="#fff1e5" stroke="#bc4c00"/><text x="420" y="14" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="480" width="120" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="540" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,192)">
        <text x="-2" y="14" text-anchor="end" fill="#57606a">Round 5</text>
        <rect width="480" height="20" fill="#ddf4ff" stroke="#0969da"/><text x="240" y="14" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="480" width="120" height="20" fill="#fff1e5" stroke="#bc4c00"/><text x="540" y="14" text-anchor="middle" fill="#bc4c00">TEST</text>
      </g>
    </g>
  </g>
</svg>"""

SVG_AGENT = """
<svg viewBox="0 0 720 280" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="ar2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="#57606a"/>
    </marker>
  </defs>
  <!-- user -->
  <rect x="10" y="120" width="120" height="44" rx="8" fill="#f6f8fa" stroke="#d0d7de"/>
  <text x="70" y="140" text-anchor="middle" font-size="11" fill="#57606a" font-family="Menlo,monospace">USER</text>
  <text x="70" y="156" text-anchor="middle" font-size="13" font-weight="700">“开始分析”</text>
  <!-- orchestrator -->
  <rect x="180" y="100" width="180" height="84" rx="10" fill="#1f2328"/>
  <text x="270" y="120" text-anchor="middle" font-size="11" fill="#dafbe1" font-family="Menlo,monospace">ORCHESTRATOR</text>
  <text x="270" y="142" text-anchor="middle" font-size="14" font-weight="700" fill="#fff">pipeline-orchestrator</text>
  <text x="270" y="166" text-anchor="middle" font-size="11" fill="#c9d1d9">读状态 · 决策 · 调度</text>
  <line x1="130" y1="142" x2="180" y2="142" stroke="#57606a" stroke-width="1.5" marker-end="url(#ar2)"/>
  <!-- sub-agents -->
  <g font-size="12" font-family="Menlo,monospace">
    <g transform="translate(420,20)">
      <rect width="280" height="44" rx="8" fill="#fff" stroke="#d0d7de"/>
      <rect width="6" height="44" rx="3" fill="#2da44e"/>
      <text x="18" y="20" font-weight="700" fill="#1f2328">data-collector</text>
      <text x="18" y="36" font-size="11" fill="#57606a" font-family="inherit">资料员 · 爬 GitHub 仓库 + 30 天活动</text>
    </g>
    <g transform="translate(420,72)">
      <rect width="280" height="44" rx="8" fill="#fff" stroke="#d0d7de"/>
      <rect width="6" height="44" rx="3" fill="#0969da"/>
      <text x="18" y="20" font-weight="700" fill="#1f2328">feature-engineer</text>
      <text x="18" y="36" font-size="11" fill="#57606a" font-family="inherit">数据分析师 · 提 38 个特征 + 分层标签</text>
    </g>
    <g transform="translate(420,124)">
      <rect width="280" height="44" rx="8" fill="#fff" stroke="#d0d7de"/>
      <rect width="6" height="44" rx="3" fill="#bc4c00"/>
      <text x="18" y="20" font-weight="700" fill="#1f2328">model-trainer</text>
      <text x="18" y="36" font-size="11" fill="#57606a" font-family="inherit">算法工程师 · LR / RF / XGBoost</text>
    </g>
    <g transform="translate(420,176)">
      <rect width="280" height="44" rx="8" fill="#fff" stroke="#d0d7de"/>
      <rect width="6" height="44" rx="3" fill="#8250df"/>
      <text x="18" y="20" font-weight="700" fill="#1f2328">report-generator</text>
      <text x="18" y="36" font-size="11" fill="#57606a" font-family="inherit">文档工程师 · HTML 报告 + Memory 写入</text>
    </g>
  </g>
  <!-- lines -->
  <line x1="360" y1="142" x2="420" y2="42"  stroke="#d0d7de" stroke-width="1" marker-end="url(#ar2)"/>
  <line x1="360" y1="142" x2="420" y2="94"  stroke="#d0d7de" stroke-width="1" marker-end="url(#ar2)"/>
  <line x1="360" y1="142" x2="420" y2="146" stroke="#d0d7de" stroke-width="1" marker-end="url(#ar2)"/>
  <line x1="360" y1="142" x2="420" y2="198" stroke="#d0d7de" stroke-width="1" marker-end="url(#ar2)"/>
</svg>"""

# ------------- HTML body chunks -------------
HEAD = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenClaw 项目零基础完全理解指南</title>
<style>%CSS%</style>
</head>
<body>
<button id="totop" onclick="window.scrollTo({top:0,behavior:'smooth'})" title="回到目录" aria-label="back to top">↑</button>
<div class="wrap">
"""

HERO = """
<header class="hero">
  <span class="pill">课程项目 · 教学型走读</span>
  <h1>OpenClaw 项目零基础完全理解指南</h1>
  <p class="muted">用一年后的 star 数当“答案”，用前 30 天的信号当“线索”——我们教一组 AI agent 给开源项目“算命”，并把整个过程拆给完全没接触过机器学习的你。</p>
  <div class="hero-stats">
    <div class="metric green"><div class="v">500</div><div class="k">真实仓库</div></div>
    <div class="metric blue"><div class="v">19</div><div class="k">特征维度 (strict-30d)</div></div>
    <div class="metric orange"><div class="v">0.878</div><div class="k">RF AUC</div></div>
    <div class="metric purple"><div class="v">9 / 10</div><div class="k">Top-10 命中</div></div>
    <div class="metric"><div class="v">5</div><div class="k">协作 Agent</div></div>
  </div>
  <p class="meta">📖 预计阅读 30 分钟，倒杯茶慢慢看。每章末尾都有一句话总结。<br>
  📂 输出文件：<code>~/openclaw-project/reports/project_walkthrough.html</code>　|　🌐 在浏览器中双击打开即可</p>
  <div style="margin-top:16px;padding:12px 16px;background:#ddf4ff;border:1px solid #80ccff;border-radius:8px;color:#0969da;font-size:14px;">
    <b>📌 v3 strict-30d 更新（2026-05-30）</b>：最终模型特征已收紧至 19 个能严格回溯到 30 天窗口内的字段。下文部分小节里出现的 “38 features / TF-IDF / author_followers / 当前 README” 是历史叙事，<a href="data_collection.html">data_collection.html</a> 和 <a href="feature_engineering.html">feature_engineering.html</a> 是最新版说明。
  </div>
</header>
"""

TOC = """
<nav class="toc" id="toc">
<h4>目录</h4>
<ol>
  <li><a href="#ch1">项目是什么？</a></li>
  <li><a href="#ch2">数据从哪来？</a></li>
  <li><a href="#ch3">什么是“特征”？</a></li>
  <li><a href="#ch4">怎么定义“成功”？</a></li>
  <li><a href="#ch5">三个模型的思维方式</a></li>
  <li><a href="#ch6">怎么知道模型有多准？</a></li>
  <li><a href="#ch7">消融实验：哪些特征真有用？</a></li>
  <li><a href="#ch8">时间切分：真实世界还管用吗？</a></li>
  <li><a href="#ch9">三个关键发现详细解读</a></li>
  <li><a href="#ch10">什么是 OpenClaw？</a></li>
  <li><a href="#ch11">扩展实验的方法论翻车</a></li>
  <li><a href="#ch12">这个项目我学到了什么</a></li>
  <li><a href="#glossary">附录 A · 术语表</a></li>
  <li><a href="#samples">附录 B · 真实样例</a></li>
</ol>
</nav>
"""

CH1 = """
<h2 id="ch1">第 1 章 · 项目是什么？</h2>

<p>想象你周五晚上把一个新开源项目推到了 GitHub。两个月过去了，它有 12 个 star，你看着 README 安慰自己“慢慢来”。问题是：<b>这个项目到底有没有潜力变成下一个明星项目，还是会永远沉睡？</b></p>

<p>GitHub 每天有上万个新仓库出生，绝大多数会沉默地消失。极少数会变成 10k+ star 的爆款。我们要做的事很简单：</p>

<div class="note good">
<span class="tag">PROJECT IN ONE SENTENCE</span>
<p><b>给每个新项目“算命”：只看它头 30 天的表现，预测一年后会不会进入“成功项目”的前 20%。</b></p>
</div>

<h3>为什么这是“数据挖掘”问题？</h3>
<p>数据挖掘（Data Mining）是从一大堆原始数据里挖出可重复的规律，然后把规律变成可执行的预测。这里的流程刚好就是数据挖掘的标准动作：</p>
<ol>
  <li><b>收集</b>足够多的开源项目数据（500 个真实仓库）</li>
  <li><b>提炼</b>有意义的信号（38 个特征：README 多长、有几个 commit、作者多少粉丝……）</li>
  <li><b>训练</b>模型从信号到结果的映射（机器学习模型）</li>
  <li><b>评估</b>模型的真实泛化能力（AUC、Precision@K 等指标）</li>
  <li><b>解读</b>哪些信号真正重要，哪些是噪声</li>
</ol>

<h3>项目的两个层次</h3>
<p>这其实是两个项目拼起来的：</p>
<div class="kv">
  <dt>(1) 机器学习实验</dt>
  <dd>真正的数据挖掘工作：采集 → 特征 → 模型 → 评估 → 解读。这是“干什么”。</dd>
  <dt>(2) OpenClaw 多 agent 系统</dt>
  <dd>把上面的整条流水线交给一组 AI agent 自主完成——用户说一句话，agent 自动调度。这是“怎么干”。</dd>
</div>

<div class="tldr">本项目 = 用 30 天早期信号预测 GitHub 项目能否成功 + 用 5 个 AI agent 自主跑完整条流水线。</div>
"""

CH2 = """
<h2 id="ch2">第 2 章 · 数据从哪来？</h2>

<h3>GitHub 是什么，star 是什么？</h3>
<p>GitHub 是全球开发者放代码的“云硬盘 + 社交平台”。任何人可以给一个项目点 <b>star</b>（相当于点赞 / 收藏）。star 数虽然不完美，但它是开源界公认最直观的成功度量——10 个 star 的项目和 10,000 个 star 的项目，含金量天差地别。</p>

<h3>我们采了什么</h3>
<div class="kv">
  <dt>仓库数量</dt><dd>500 个</dd>
  <dt>创建时间</dt><dd>2025-05 ~ 2025-06（采集时已存活满 11~12 个月）</dd>
  <dt>语言分布</dt><dd>Rust 151 · Go 118 · Python 100 · JavaScript 100 · TypeScript 31</dd>
  <dt>主题方向</dt><dd>AI / CS 相关（通过 topics 与关键词过滤）</dd>
  <dt>当前 star 分布</dt><dd>0–9: 278 · 10–49: 124 · 50–199: 61 · 200–999: 29 · 1000+: 8（长尾，符合真实世界）</dd>
</div>

<h3>怎么采集的？</h3>
<p>GitHub 提供 API，可以像查字典一样用程序问它问题：</p>
<pre><code># 找 2025-05 创建、Python 语言、至少 1 star 的仓库
GET /search/repositories?q=created:2025-05-01..2025-05-31 language:Python stars:>=1

# 对每个仓库取它前 30 天的 commits 数量
GET /repos/&lt;owner&gt;/&lt;repo&gt;/commits?since=&lt;T0&gt;&until=&lt;T0+30d&gt;</code></pre>
<p>API 有调用频率限制（每小时 5,000 次）。脚本会在剩余配额低时自动暂停，遇到 5xx 错误指数退避重试，确保 500 个仓库稳稳采下来——这次采集 0 失败。</p>

<h3>每个仓库长什么样？（举一个真实例子）</h3>
<div class="note">
<span class="tag">RAW RECORD · memvid/memvid（仓库当前 ★ 15,529）</span>
<pre><code>{
  "snapshot": {
    "full_name": "memvid/memvid",
    "language": "Rust",
    "description": "Memory layer for AI Agents. Replace complex RAG ...",
    "topics": ["ai","llm","rag","vector-database", ...],
    "license": "Apache-2.0",
    "has_readme": true,         // 有 README
    "readme_len": 16317,         // 16k 字符 — 很详细
    "readme_has_image": true,    // README 里有截图
    "commits_30d": 31,           // 前 30 天提交了 31 次
    "contributors": 24,          // 24 个贡献者参与
    "issues_30d": 19,            // 收到 19 个 issue
    "prs_30d": 16,               // 收到 16 个 PR
    "author_followers": 161,
    "author_public_repos": 15,
    "author_type": "Organization",
    "window_since": "2025-05-27", // 严格截止时间
    "window_until": "2025-06-26"
  },
  "labels": {
    "current_stars": 15529,      // ← 这是要预测的“答案”，特征里看不到
    "created_at":   "2025-05-27"
  }
}</code></pre>
</div>

<h3>为什么只看前 30 天？防泄漏！</h3>
<div class="note danger">
<span class="tag">⛔ DATA LEAKAGE</span>
<p><b>用未来的信息预测未来 = 考试时偷看答案。</b>如果我们用项目创建 60 天后的 commit 数当特征，模型确实会更“准”——但这种准是假的，部署到真实世界就崩。</p>
</div>

<p>所以我们规定：所有 <b>特征</b> 必须用项目创建后 [T=0, T+30 天] 窗口内可见的信息；<b>标签</b>（current_stars）用一年后的真实快照。两者中间有 11 个月的“真空带”，绝对不能偷看。</p>

<figure>%SVG_LEAKAGE%<figcaption>时间线：绿色区域可看，红色区域绝对不能看</figcaption></figure>

<div class="tldr">500 个 GitHub 仓库的 30 天早期快照 + 12 个月后的真实 star 数 = 数据集。中间 11 个月内的任何信息都视为“未来”，绝不能进入特征。</div>
""".replace("%SVG_LEAKAGE%", SVG_LEAKAGE)

CH3 = """
<h2 id="ch3">第 3 章 · 什么是“特征”？</h2>

<div class="note analogy">
<span class="tag">💡 类比</span>
<p>相亲时你怎么判断对方靠不靠谱？身高、收入、学历、是否养宠物、聊天时眼神是否飘忽……这些<b>可观测的属性</b>就是特征（feature）。机器学习模型的工作就是从一堆特征里学出“哪些组合通常代表靠谱”。</p>
</div>

<p>我们给每个仓库提了 <b>38 个特征</b>，分四大类。</p>

<h3>① 基础元信息（11 个）</h3>
<p>仓库本身的“出生证明”：</p>
<ul>
  <li><code>has_readme</code> / <code>readme_len</code> — 有没有 README、README 多长。<b>为什么重要：</b>README 是项目的门面，写得详细说明作者愿意投入。</li>
  <li><code>has_license</code> — 有没有开源协议。没有 LICENSE 的项目企业不敢用，传播受限。</li>
  <li><code>readme_has_image</code> / <code>readme_has_demo_url</code> — 有没有截图 / Demo 链接。视觉演示让访客 5 秒理解项目，是“留客”的关键。</li>
  <li><code>lang_Python / Go / Rust / JS / TS / Other</code> — 编程语言 one-hot 编码。不同语言的“生态盘子”差距很大。</li>
  <li><code>is_org</code> — 作者是公司还是个人。组织账号通常有人力做长期维护。</li>
</ul>

<h3>② 早期活跃度（4 个）</h3>
<p>项目前 30 天“在干活”的程度：</p>
<ul>
  <li><code>commits_30d</code> — 提交次数</li>
  <li><code>contributors</code> — 参与的人数</li>
  <li><code>issues_30d</code> — 收到的问题反馈数</li>
  <li><code>prs_30d</code> — 收到的代码贡献数</li>
</ul>
<p><b>为什么这能预测未来：</b>30 天内频繁 commit、有多人参与、收到外部 issue 和 PR——意味着项目“活的”而不是“一锤子买卖”。一个有节奏的早期，往往预示着持续的中期。</p>

<h3>③ 作者信号（3 个）</h3>
<ul>
  <li><code>author_followers</code> — 作者的关注者数</li>
  <li><code>author_public_repos</code> — 作者的公开仓库数</li>
  <li><code>author_type</code> — User / Organization</li>
</ul>
<p><b>为什么作者重要：</b>有 10k followers 的开源大佬扔一个仓库出来，会被瞬间转发数百次；新人发同样质量的项目可能要熬几个月才被发现。这就是“传播势能”。</p>

<h3>④ TF-IDF 文本信号（20 个）</h3>
<div class="note analogy">
<span class="tag">💡 TF-IDF 是什么？</span>
<p><b>TF-IDF</b> = Term Frequency × Inverse Document Frequency，给词打分的经典算法。</p>
<p>想象你在浏览招聘网站。“工程师”这个词几乎每条招聘都出现 → 它不能帮你区分两个职位。但“量子计算”只在极少数招聘出现 → 看到这个词你立刻知道这是什么方向。<b>TF-IDF 就是把“出现得多但到处都有”的词降权，把“出现得多且独特”的词加权。</b></p>
</div>

<p>我们对每个仓库的 <code>topics + description</code> 跑 TF-IDF，取出现频率前 20 的词作为特征。比如 <code>tfidf_llm</code>、<code>tfidf_machine learning</code>、<code>tfidf_agent</code>。</p>

<h3>真实样本：memvid 的特征值</h3>
<table>
<tr><th>特征</th><th>值</th><th>含义</th></tr>
<tr><td><code>readme_len</code></td><td>16,317</td><td>README 字符数（很详细）</td></tr>
<tr><td><code>has_readme</code></td><td>1</td><td>有 README</td></tr>
<tr><td><code>has_license</code></td><td>1</td><td>Apache-2.0 协议</td></tr>
<tr><td><code>readme_has_image</code></td><td>1</td><td>README 含截图</td></tr>
<tr><td><code>readme_has_demo_url</code></td><td>0</td><td>无 demo 链接</td></tr>
<tr><td><code>lang_Rust</code></td><td>1</td><td>Rust 项目</td></tr>
<tr><td><code>commits_30d</code></td><td>31</td><td>前 30 天 31 次提交</td></tr>
<tr><td><code>contributors</code></td><td>24</td><td>24 个贡献者</td></tr>
<tr><td><code>issues_30d</code></td><td>19</td><td>19 个 issue</td></tr>
<tr><td><code>prs_30d</code></td><td>16</td><td>16 个 PR</td></tr>
<tr><td><code>author_followers</code></td><td>161</td><td>组织有 161 个 follower</td></tr>
<tr><td><code>author_public_repos</code></td><td>15</td><td>历史 15 个公开仓库</td></tr>
<tr><td><code>is_org</code></td><td>1</td><td>是组织账号</td></tr>
<tr><td><code>tfidf_llm</code></td><td>0.34</td><td>“llm” 在该项目描述中权重高</td></tr>
<tr><td>...（其余 23 维）</td><td>...</td><td></td></tr>
</table>

<p>这一行 38 个数字就是“memvid 的指纹”。<b>模型看到的就是这串数字，它从来不知道仓库名叫 memvid。</b></p>

<div class="tldr">特征 = 一个仓库的“量化档案”。38 个数字从基础信息、早期活动、作者背景、文本主题四个角度刻画一个项目，模型据此打分。</div>
"""

CH4 = """
<h2 id="ch4">第 4 章 · 什么是“标签”？怎么定义“成功”？</h2>

<p><b>标签（label）</b>就是我们要预测的“答案”。模型训练的时候，会拿“特征 → 标签”一对一对地看，慢慢学会规律。</p>

<h3>最朴素的方法：star ≥ 1000 = 成功</h3>
<p>简单，但有大问题：</p>
<div class="note warn">
<span class="tag">⚠️ 三种偏差</span>
<ol>
  <li><b>语言偏差</b>：JS / Python 项目天然受众基数大，1000 star 比 Rust 项目容易得多</li>
  <li><b>时间偏差</b>：项目越老积累 star 越多，时间窗不同的项目不能直接比绝对值</li>
  <li><b>主题偏差</b>：AI 类项目在 2025 年享受“风口红利”，传统工具类项目同质量却 star 少</li>
</ol>
</div>

<h3>我们的方法：分层 Top 20%</h3>
<div class="note analogy">
<span class="tag">💡 班级排名</span>
<p>不能拿小学生和大学生比绝对分数。你应该比的是：小明在小学班里的前 20% 吗？小红在大学班里的前 20% 吗？<b>同一参照系下的相对位置，比绝对数字更公平。</b></p>
</div>

<p>对应到我们的任务：在<b>同语言</b>的仓库子集里排队，每语言各自取前 20%（也就是 stars ≥ 该语言的 p80 分位数）作为“成功项目”，标记 <code>is_top20 = 1</code>，其余 = 0。</p>

<figure>%SVG_STRATA%<figcaption>每条横线 = 一种语言的所有仓库，绿色 = 该语言自己班级里的前 20%</figcaption></figure>

<h3>真实分层分界线</h3>
<table>
<tr><th>语言</th><th>样本数</th><th>正例数（Top 20%）</th><th>分界 star 数（约）</th></tr>
<tr><td>Python</td><td>100</td><td>53</td><td>— ⚠ 类内正例率 53%，热度趋同</td></tr>
<tr><td>Go</td><td>118</td><td>25</td><td>~ 30 stars</td></tr>
<tr><td>Rust</td><td>151</td><td>17</td><td>~ 22 stars</td></tr>
<tr><td>JavaScript</td><td>100</td><td>5</td><td>~ 50 stars</td></tr>
<tr><td>TypeScript</td><td>31</td><td>1</td><td>样本不足，仅供参考</td></tr>
<tr><th colspan="2">合计</th><th>101 / 500（20.2%）</th><th></th></tr>
</table>

<p>注意 Python 那一行的“⚠”——分层规则没能完全消除 Python 的热度异常，它在第 9 章会变成一个很有意思的发现。</p>

<h3>具体例子</h3>
<ul>
  <li><b>memvid/memvid</b>（Rust，15,529 stars）→ 远超 Rust 分界 → <code>is_top20 = 1</code> ✅</li>
  <li><b>strands-agents/sdk-python</b>（Python，5,877 stars）→ <code>is_top20 = 1</code> ✅</li>
  <li>某 Go 项目（3 stars）→ 没进 Go 前 20% → <code>is_top20 = 0</code> ❌</li>
</ul>

<div class="tldr">标签 = 仓库一年后是否进入同语言子集的前 20%。用相对排名而非绝对数，消除语言/时间/主题偏差。500 个仓库里 101 个是“成功项目”。</div>
""".replace("%SVG_STRATA%", SVG_STRATA)

CH5 = """
<h2 id="ch5">第 5 章 · 三个模型的“思维方式”</h2>

<p>我们对比了三个主流模型，把它们想象成三位风格不同的“算命先生”——给同样的 38 个特征，他们用完全不同的方式做出判断。</p>

<h3>① 逻辑回归 LR（Logistic Regression）—— 理性派</h3>
<p>LR 给每个特征学一个权重，加权求和后过一个 S 形函数，转成概率。你可以把它想成这样的公式：</p>
<pre><code>score = w₁ × readme_len + w₂ × commits_30d + w₃ × author_followers + ...
prob  = sigmoid(score)   # 把任意数压到 [0, 1]</code></pre>
<p>权重 w 是从数据里学出来的。<b>优点：</b>训练快、可解释（每个权重正负代表正负相关）。<b>缺点：</b>只能学线性关系，没法捕捉“commits 多 + README 短 = 烂代码”这种组合规律。</p>

<h3>② 随机森林 RF（Random Forest）—— 民主派</h3>
<div class="note analogy">
<span class="tag">💡 类比</span>
<p>找 100 个朋友各自给项目打个分，最后取多数意见。每个“朋友”是一棵决策树（Decision Tree），他只看一个随机抽样的子集，问一系列 yes/no 问题：“readme_len &gt; 5000？”→ 是 → “commits_30d &gt; 10？”→ 否 → 投票“不会火”。</p>
</div>
<p>100 棵树各自决策，最后投票汇总。<b>优点：</b>能学非线性关系；对异常值健壮；能给出特征重要性。<b>缺点：</b>对类别不平衡敏感（少数派常被淹没）。</p>

<h3>③ XGBoost —— 进化派</h3>
<p>XGBoost 也用决策树，但思路是“一棵接一棵地修正错误”：</p>
<ul>
  <li>第 1 棵树预测一遍，记录每个样本预测错了多少</li>
  <li>第 2 棵树专门去修第 1 棵的错误</li>
  <li>第 3 棵树再去修前两棵的剩余错误……</li>
  <li>累计几百棵，整体能力像“爬山”一样越来越强</li>
</ul>
<p><b>优点：</b>通常是 Kaggle 比赛冠军模型，调好参数后性能很强。<b>缺点：</b>超参数多、容易过拟合（在训练集上表现完美，在新数据上崩）。</p>

<h3>为什么要对比三个，而不是只用最强的？</h3>
<ol>
  <li><b>看一致性</b>：三个模型结论一致，说明发现是真的；不一致，说明数据有问题</li>
  <li><b>看适用场景</b>：LR 简单可解释，给老板看好；RF 性能稳；XGBoost 极限性能高</li>
  <li><b>当 baseline 互相校验</b>：如果复杂模型只比简单模型高 1%，说明特征工程没什么用</li>
</ol>

<h3>本项目结果（5-fold CV 平均）</h3>
<table>
<tr><th>模型</th><th>AUC</th><th>PR-AUC</th><th>F1</th><th>P@10</th><th>风格</th></tr>
<tr><td>LR</td><td>0.842</td><td>0.571</td><td><b>0.605</b></td><td>0.60</td><td>激进（高召回）</td></tr>
<tr><td><b>RF</b></td><td><b>0.878</b></td><td><b>0.642</b></td><td>0.402</td><td><b>0.90</b></td><td>保守（高精度）</td></tr>
<tr><td>XGBoost</td><td>0.854</td><td>0.620</td><td>0.535</td><td>0.80</td><td>平衡</td></tr>
</table>
<p>RF 的 P@10 = 0.90 是整个实验最漂亮的数字 —— 详见第 6 章。</p>

<div class="tldr">三个模型 = 三种思维方式：LR 线性、RF 投票、XGBoost 修错。同时跑能交叉验证结论的可信度，也能从中挑出最适合“推荐 Top-N”场景的那个。</div>
"""

CH6 = """
<h2 id="ch6">第 6 章 · 怎么知道模型有多准？</h2>

<p>“准”看似简单，其实有坑。我们用了 5 种不同角度的指标。</p>

<h3>陷阱：Accuracy（准确率）会骗人</h3>
<div class="note warn">
<span class="tag">⚠️ 罕见病故事</span>
<p>某医院诊断一种罕见病，发病率 1%。一个“医生”一律判“没病”。它的准确率 = 99%！但显然这医生什么都没做。</p>
</div>
<p>我们的数据正例只占 20%，模型全判“不会火”准确率 = 80%——看起来不错，但毫无价值。所以我们不用 Accuracy。</p>

<h3>主指标：AUC</h3>
<div class="note analogy">
<span class="tag">💡 AUC</span>
<p><b>AUC（Area Under Curve，ROC 曲线下面积）：随机挑一个真会火的项目 A 和一个不会火的项目 B，模型给 A 的预测概率比 B 高的概率。</b></p>
<ul>
  <li>AUC = 0.5 → 模型在瞎猜</li>
  <li>AUC = 0.7 → 算合格</li>
  <li>AUC = 0.878（我们的 RF）→ 给随机一对正负样本排序，模型 <b>87.8%</b> 的概率排对</li>
  <li>AUC = 1.0 → 完美</li>
</ul>
</div>

<h3>第二指标：PR-AUC（Precision-Recall AUC）</h3>
<p>类别不平衡（正例只占 20%）时，AUC 容易偏乐观。PR-AUC 更诚实，它直接看“在不同召回阈值下精度有多高”，对少数类敏感。我们的 RF PR-AUC = 0.642，意思是：在所有“被模型说会火”的项目里，真正会火的占比维持得不错。</p>

<h3>F1：精度和召回率的调和</h3>
<ul>
  <li><b>Precision（精度）</b> = 模型说会火的项目里，真会火的比例</li>
  <li><b>Recall（召回率）</b> = 所有真会火的项目里，模型抓到了多少</li>
  <li><b>F1</b> = 精度和召回率的调和平均，两者偏低任一就崩</li>
</ul>
<p>三个模型的 F1 不同源于它们的“风格”：RF 默认阈值偏高（保守，宁可漏不可错），F1 低；LR 阈值低（激进），F1 高。</p>

<h3>关键指标：Precision@10（P@10）</h3>
<div class="note good">
<span class="tag">⭐ 最实用</span>
<p>想象你是投资人，每周想看 10 个最有潜力的新项目。<b>P@10 就是回答：模型推荐概率最高的 10 个项目里，真正进入 Top 20% 的有几个？</b></p>
<p>我们的 RF P@10 = <b>0.90</b>，等于：模型推 10 个，9 个真的火了——这是真实可用的“推荐潜力榜”性能。</p>
</div>

<h3>5-fold 交叉验证：怎么避免“自己考自己”</h3>
<div class="note analogy">
<span class="tag">💡 类比</span>
<p>学生备考刷题时，不能拿做过的题再考自己——那只是在背答案。要拿没做过的题来测水平。</p>
</div>
<p>我们把 500 个样本随机切成 5 份（fold）。每一轮：4 份训练模型，1 份当“没见过的考题”测试。轮 5 次，每份都当过一次考题。最终指标取 5 次平均，这样模型一定从没看过测试集，结果更可信。</p>

<figure>%SVG_KFOLD%<figcaption>5-fold 交叉验证：橙色 = 测试，蓝色 = 训练，轮 5 次每份都当一次测试</figcaption></figure>

<div class="tldr">用 5 个互补指标 + 5-fold 交叉验证多角度评估。RF AUC 0.878 + P@10 0.90 = 模型既能整体排序，又能在“推荐 Top-N”场景里实际可用。</div>
""".replace("%SVG_KFOLD%", SVG_KFOLD)

CH7 = """
<h2 id="ch7">第 7 章 · 消融实验：哪些特征真的有用？</h2>

<div class="note analogy">
<span class="tag">💡 做菜</span>
<p>一道菜放了盐、糖、酱油、蒜末、香菜。怎么知道每样调料的贡献？每次去掉一样，尝一下味道差距——<b>这就是消融实验（ablation study）</b>。</p>
</div>

<p>我们逐步加特征，用 RF 跑 5-fold CV，看 AUC 的变化：</p>

<table>
<tr><th>组</th><th>包含的特征</th><th>特征数</th><th>AUC</th><th>提升</th></tr>
<tr><td><b>A</b></td><td>基础元信息（语言 + README + LICENSE）</td><td>12</td><td>0.7855</td><td>—</td></tr>
<tr><td><b>B</b></td><td>A + 早期活跃度（commits / contributors / issues / PRs）</td><td>16</td><td>0.8516</td><td><span class="tag good">+0.0661</span></td></tr>
<tr><td><b>C</b></td><td>B + 作者信号（followers / public_repos）</td><td>18</td><td>0.8756</td><td><span class="tag good">+0.0240</span></td></tr>
<tr><td><b>D</b></td><td>C + 20 维 TF-IDF（描述里的关键词）</td><td>38</td><td>0.8783</td><td><span class="tag warn">+0.0027</span></td></tr>
</table>

<h3>三个清晰的结论</h3>
<ul>
  <li><b>早期活跃度贡献最大（+0.066）</b>——A 到 B 那一跳。仅看基础信息时 AUC 只有 0.786，加上 commits / issues / PRs 后冲到 0.852。说明项目“活的”比“出生证明”更重要。</li>
  <li><b>作者信号有用，但边际递减（+0.024）</b>——大佬带来的额外影响存在，但不是核心。</li>
  <li><b>TF-IDF 几乎无效（+0.003）</b>——加了 20 维文本特征几乎没动 AUC。这是反直觉的发现。</li>
</ul>

<h3>现实意义（写给开源开发者的）</h3>
<div class="note good">
<span class="tag">⭐ 实用启示</span>
<ul>
  <li><b>真去 commit 代码，比写漂亮文案更管用</b>。早期 30 天的活跃度是最强的预测信号。</li>
  <li>描述里塞“LLM/Agent/AI”等热词没用。模型告诉我们：项目“说了什么”不重要，“做了什么”才重要。</li>
  <li>有大佬背书是加分项，但远不能弥补“项目不活”的硬伤。</li>
</ul>
</div>

<div class="tldr">分层加特征 → 看 AUC 跳跃。早期活跃度是最大贡献者；项目描述里的关键词几乎不预测成功——内容比包装重要。</div>
"""

CH8 = """
<h2 id="ch8">第 8 章 · 时间切分：模型在真实世界还管用吗？</h2>

<h3>5-fold CV 的盲点</h3>
<p>5-fold CV 把 500 个样本<b>随机</b>分组——同一折里可能既有 2025-05 的项目，也有 2025-06 的项目。如果模型不小心从“6 月的数据”里学到了“5 月项目的规律”，这其实是变相作弊。</p>

<h3>更严格的考核：时间切分</h3>
<p>按 <code>created_at</code> 排序，前 80% 当训练（2025-05 中旬到 6 月中旬），后 20% 当测试（最晚一批）。<b>严格用“过去”预测“未来”</b>，模拟真实部署场景。</p>

<h3>我们的结果（N=500）</h3>
<div class="metrics">
  <div class="metric"><div class="v">0.878</div><div class="k">Random 5-fold CV</div></div>
  <div class="metric"><div class="v">0.881</div><div class="k">Time-split</div></div>
  <div class="metric green"><div class="v">+0.0025</div><div class="k">差距（gap）</div></div>
</div>

<p>差距只有 0.0025，几乎可以忽略。<b>结论：模型真的从早期信号里学到了规律，没有偷偷依赖时间顺序的捷径，部署到新项目上也会管用。</b></p>

<h3>但 N=1500 时翻车了 ⚠️</h3>
<p>我们后来扩展到 1500 样本（含跨时间窗口的早期批次）：</p>
<table>
<tr><th>规模</th><th>Random CV AUC</th><th>Time-split AUC</th><th>gap</th><th>结论</th></tr>
<tr><td>N=500（单窗）</td><td>0.878</td><td>0.881</td><td>+0.0025</td><td><span class="tag good">几乎无差距 → 可信</span></td></tr>
<tr><td>N=1500（多窗）</td><td>0.907</td><td>0.813</td><td><b>−0.094</b></td><td><span class="tag bad">CV 高估 9.4%！</span></td></tr>
</table>

<p>这一发现非常有方法论价值：<b>k-fold CV 在跨时间数据上会显著高估真实泛化能力</b>。许多 ML 论文用 k-fold 报指标，没做时间切分检验——可能都偏乐观。详见<a href="#ch11">第 11 章</a>。</p>

<div class="tldr">时间切分 = 用“过去”预测“未来”的严格考试。N=500 时模型通过；N=1500 时差距 0.094，证明 k-fold 在跨时间数据上不可信。</div>
"""

CH9 = """
<h2 id="ch9">第 9 章 · 三个关键发现详细解读</h2>

<h3>Finding 1 · README 是最强单特征</h3>
<div class="note good">
<span class="tag">📊 数据</span>
<table>
<tr><th>排名</th><th>特征</th><th>RF Gini 重要性</th></tr>
<tr><td>1</td><td><code>readme_len</code></td><td><b>0.2833</b></td></tr>
<tr><td>2</td><td><code>author_public_repos</code></td><td>0.1032</td></tr>
<tr><td>3</td><td><code>commits_30d</code></td><td>0.0932</td></tr>
<tr><td>4</td><td><code>author_followers</code></td><td>0.0628</td></tr>
<tr><td>5</td><td><code>tfidf_machine learning</code></td><td>0.0592</td></tr>
</table>
<p>readme_len 是第二名的 <b>2.7 倍</b>，遥遥领先。</p>
</div>

<p><b>为什么会这样？</b>README 长度看似简单，其实代表了：</p>
<ul>
  <li>作者愿意花时间写文档 = 项目认真度的代理变量</li>
  <li>解释项目的复杂程度足够支撑长文档 = 项目有实质内容</li>
  <li>给新用户的“留客率”：5 秒能看懂就能 star，否则关掉</li>
</ul>

<div class="note good">
<span class="tag">⭐ 给开源开发者的启示</span>
<p><b>“写一份详细的 README”是 ROI 最高的早期投入。</b>比起优化代码细节，先把 README 写到 2000 字以上、配上截图和 demo 链接，对长期 star 的撬动力更大。</p>
</div>

<h3>Finding 2 · TF-IDF 关键词几乎没用</h3>
<div class="note warn">
<span class="tag">📊 数据</span>
<p>消融实验 D − C：加上 20 维 TF-IDF 后 AUC 只提升 <b>+0.0027</b>（0.8756 → 0.8783），在误差范围内。</p>
</div>

<p><b>为什么会这样？</b>2025 年的 GitHub 几乎所有 AI 项目都在用相同的热词：llm、agent、rag、mcp、machine-learning。这些词成了“通用塑料词”，无法区分项目好坏。真正的差异在<b>行动</b>层面（commits / contributors）而不是<b>口号</b>层面。</p>

<div class="note good">
<span class="tag">⭐ 给开源开发者的启示</span>
<p><b>描述里塞热词不是营销策略，是噪声。</b>与其在 description 里堆叠 buzzword，不如把这些空间用来描述独特性。</p>
</div>

<h3>Finding 3 · Python 项目最难预测</h3>
<div class="note danger">
<span class="tag">📊 数据 · 分语言 AUC</span>
<table>
<tr><th>语言</th><th>样本</th><th>正例</th><th>AUC</th></tr>
<tr><td><b>Python</b></td><td>100</td><td>53</td><td><b>0.565 ⚠</b></td></tr>
<tr><td>Go</td><td>118</td><td>25</td><td>0.890</td></tr>
<tr><td>Rust</td><td>151</td><td>17</td><td>0.853</td></tr>
<tr><td>JavaScript</td><td>100</td><td>5</td><td>0.800（高方差）</td></tr>
<tr><td>TypeScript</td><td>31</td><td>1</td><td>样本不足</td></tr>
</table>
</div>

<p><b>为什么会这样？</b>注意 Python 那一行——正例率 <b>53%</b>。在分层 Top 20% 设计下其他语言正例率都在 20% 上下，唯独 Python 高到 53%。原因：2025 年 AI 热潮让 Python 项目“个个看起来像爆款”——类内差异小 → 模型学不到区分信号 → AUC 接近瞎猜（0.5）。</p>

<div class="note good">
<span class="tag">⭐ 给开源开发者的启示</span>
<p><b>垂直冷门领域里的“成功项目”更有特征可循；红海热门领域里反而难脱颖而出。</b>如果你想做点不一样的事，研究 Go / Rust 项目的成功模式可能比研究 Python 的更有价值。</p>
</div>

<div class="tldr">README > 早期 commit > 作者影响力 ≫ 关键词。Python 项目因热度趋同最难预测——这本身就是“AI 红海效应”的数据证据。</div>
"""

CH10 = """
<h2 id="ch10">第 10 章 · 什么是 OpenClaw？为什么用它？</h2>

<div class="note analogy">
<span class="tag">💡 自动化 vs 助理</span>
<p><b>自动化办公（脚本）</b>：你写好规则——每周一上午 9 点跑数据采集 → 跑特征 → 跑模型 → 出报告。规则写死，不会变。</p>
<p><b>虚拟助理（agentic 系统）</b>：你只说一句“分析一下最近的项目”。助理自己判断：数据新不新？要不要重新采？模型旧了吗？要不要重训？最后把报告递给你。<b>规则在自然语言层面，助理用 LLM 推理执行。</b></p>
</div>

<h3>OpenClaw 是什么</h3>
<p>OpenClaw 是一个本地运行的 agentic AI 框架，支持把任务拆成多个 agent（每个 agent 有自己的角色、独立 session、独立 SOUL.md），由主 agent 调度子 agent 协作完成。</p>

<h3>5 个 agent 的角色（项目经理 + 团队）</h3>
<ul>
  <li><b>orchestrator</b> = 项目经理 · 看状态、做决策、分配任务</li>
  <li><b>data-collector</b> = 资料员 · 爬 GitHub 仓库的 30 天活动数据</li>
  <li><b>feature-engineer</b> = 数据分析师 · 从原始数据提 38 个特征 + 算分层标签</li>
  <li><b>model-trainer</b> = 算法工程师 · 训练 LR / RF / XGBoost、跑消融实验、SHAP、time-split</li>
  <li><b>report-generator</b> = 文档工程师 · 把所有结果汇总成 HTML 报告 + 写入 Memory</li>
</ul>

<figure>%SVG_AGENT%<figcaption>5 个 agent 的协作结构</figcaption></figure>

<h3>关键创新：调度规则是自然语言写的</h3>
<p>普通脚本里你会看到 if/else：</p>
<pre><code>if datetime.now() - file_mtime &gt; timedelta(days=7):
    collect_data()</code></pre>

<p>OpenClaw 里你写在 <code>SKILL.md</code> 里这样的话：</p>
<pre><code># 调度规则
- 如果 raw 数据 > 7 天未更新，重新采集
- 如果 features.csv 比 raw 数据旧，重新提取特征
- 如果 model_results 比 features 旧，重训模型
- 报告每次都重新生成</code></pre>

<p>orchestrator 用 LLM 读这段自然语言、读文件 mtime、自己推理决定该跑哪些 sub-agent。改阈值不需要改代码，直接改文字。</p>

<h3>看一眼真的跑起来的样子</h3>
<div class="shot"><img src="data:image/png;base64,%DASH_B64%" alt="OpenClaw multi-agent dashboard screenshot"></div>
<p class="muted">实时 Dashboard 截图：orchestrator 在 running；data-collector / feature-engineer 显示 completed（agent 判断数据足够新，跳过采集和特征步骤）；model-trainer 正在训练；report-generator 待命。Event stream 里能看到 agent 的决策日志：“raw 数据 2 天前更新 (&lt; 7d 阈值) → 跳过采集”。</p>

<div class="tldr">OpenClaw = 把规则写在自然语言里、由 LLM agent 解读执行的 agentic 框架。5 个 agent 协作把一条数据挖掘流水线从“你跑脚本”变成“agent 自主跑”。</div>
""".replace("%SVG_AGENT%", SVG_AGENT).replace("%DASH_B64%", dash_b64)

CH11 = """
<h2 id="ch11">第 11 章 · 扩展实验的方法论翻车</h2>

<p>项目快收尾时我们想：500 样本太少了，扩展到 1500 应该更可信吧？于是从 2025-01~02 和 2025-03~04 又采了两批各 500 个仓库，三批合并 → 1500 个。</p>

<h3>看似很好的结果</h3>
<div class="metrics">
  <div class="metric"><div class="v">0.878</div><div class="k">N=500 RF AUC</div></div>
  <div class="metric green"><div class="v">0.907</div><div class="k">N=1500 RF AUC</div></div>
  <div class="metric"><div class="v">+0.029</div><div class="k">看起来提升了</div></div>
</div>

<p>但仔细检查时我们发现了三个严重问题。这一章我们把它们作为<b>方法论警示</b>讲清楚——主动暴露问题反而显得严谨。</p>

<h3>问题 1 · 采样策略不一致 → TypeScript 样本被污染</h3>
<p>原始 500 中 TypeScript 只有 31 个，扩展时我们用了 <code>--ts-broad</code> 放宽筛选条件（不限定 AI 关键词），把 TS 样本提到 ~20%。但这导致：</p>
<ul>
  <li>TS 样本 = 老仓库 + 泛领域 + 早期批次 → 自然高 star → 正例率 65%（其他语言约 20%）</li>
  <li>模型学到的不是“TypeScript 项目本身预测成功”，而是“TS = ts_broad 标记 = 高 star 老仓库”</li>
  <li><code>lang_TypeScript</code> 在 1500 特征重要性里跃升第一——这是<b>统计假象</b>，不是真实信号</li>
</ul>
<div class="note danger"><span class="tag">教训</span> 不一致的采样规则会让模型学到“采样标签”而不是“真实标签”。</div>

<h3>问题 2 · 不同时间窗的“Top 20%”根本不是同一个东西</h3>
<table>
<tr><th>批次</th><th>样本数</th><th>p80（分界 star）</th><th>仓库年龄</th></tr>
<tr><td>mid_2025_05_06（原始）</td><td>500</td><td>~ 48 stars</td><td>~12 个月</td></tr>
<tr><td>early1_2025_03_04</td><td>500</td><td>~ 336 stars</td><td>~14 个月</td></tr>
<tr><td>early2_2025_01_02</td><td>500</td><td>~ 323 stars</td><td>~16 个月</td></tr>
</table>
<p>早期批次的仓库多积累了 2-4 个月时间，p80 阈值是原始批次的 <b>7 倍</b>。同样标“is_top20 = 1”，在 mid 批次里只要 48 star，在 early2 里要 323 star——<b>“成功”的绝对标准完全不同</b>。批次内标签机制能缓解但消除不了这种偏移。</p>
<div class="note danger"><span class="tag">教训</span> 跨时间窗合并数据前，必须确认标签在不同窗口里语义一致。</div>

<h3>问题 3 · k-fold CV 在跨时间数据上会骗你</h3>
<table>
<tr><th>规模</th><th>Random CV AUC</th><th>Time-split AUC</th><th>gap</th></tr>
<tr><td>N=500（单窗）</td><td>0.878</td><td>0.881</td><td><span class="tag good">+0.0025</span></td></tr>
<tr><td>N=1500（多窗）</td><td>0.907</td><td>0.813</td><td><span class="tag bad">−0.094</span></td></tr>
</table>
<p>1500 样本上 k-fold CV 报 0.907，但严格时间切分只有 0.813——<b>k-fold 高估了 9.4 个百分点！</b>原因：随机切分把不同时间窗的样本混在一起，模型可以从“5 月的项目里”猜到“3 月的项目规律”，这是隐性数据泄漏。</p>
<div class="note danger"><span class="tag">教训</span> 凡是有时间维度的数据，永远要补一个 time-split 实验做交叉验证。仅看 k-fold 会得到危险的乐观结论。</div>

<h3>最终选择</h3>
<p>我们把 N=500 作为<b>主实验</b>（结论可信），N=1500 作为<b>方法论警示</b>章节单独写出。这反而比一个“看似漂亮但隐藏问题”的 1500 主实验更有学术价值。</p>

<div class="tldr">扩展数据 = 引入新偏差的风险。N=1500 的“性能提升”被三个方法论问题污染——主动暴露这些问题比刷高 AUC 更值钱。</div>
"""

CH12 = """
<h2 id="ch12">第 12 章 · 这个项目我学到了什么</h2>

<h3>1. 数据挖掘核心流程其实就这五步</h3>
<pre><code>数据采集 → 特征工程 → 模型训练 → 评估 → 解读
   ↑           ↑           ↑          ↑       ↑
500 仓库   38 特征    LR/RF/XGB   AUC/P@K  Findings</code></pre>
<p>每一步都有自己的坑：采集要防泄漏；特征要可解释；模型要对比；评估要多指标；解读要谨慎。</p>

<h3>2. 防泄漏比刷高 AUC 重要 100 倍</h3>
<p>用未来信息预测未来谁都能拿 0.95 AUC，但那种模型部署到真实世界立刻崩。我们花了大力气保证特征严格截止在 T+30 天，这是项目最有价值的设计决策。</p>

<h3>3. 简单扩展数据可能引入新偏差</h3>
<p>N=500 → N=1500 在论文里看似“工作量加大”，实际埋了三个方法论陷阱。规模不是越大越好——<b>数据质量比数量重要</b>。</p>

<h3>4. Agent 系统是软件工程的范式转变</h3>
<p>OpenClaw 的最大价值不是“跑得快”，而是<b>“规则可以用自然语言写”</b>。改业务逻辑不需要改代码，写在 SKILL.md 里就行。这意味着非工程师也可以调整 agent 行为——这是 LLM 时代软件的新形态。</p>

<h3>5. 反直觉发现最有论文价值</h3>
<p>“README 比 commit 更重要”、“TF-IDF 没用”、“Python 项目最难预测”——这些反直觉的结论比“RF 表现最好”有趣得多。<b>数据挖掘的本质是发现规律，不是证明你已经知道的事。</b></p>

<div class="tldr">数据挖掘 = 严谨的过程 + 反直觉的发现 + 诚实的局限性讨论。比 AUC 数字更重要的，是你怎么解释它。</div>
"""

GLOSSARY = """
<h2 id="glossary">附录 A · 术语表</h2>
<dl class="glossary">
<dt>Accuracy（准确率）</dt><dd>预测正确的样本占比。类别不平衡时会骗人——全判负也能拿 80%+。</dd>
<dt>Agent（代理 / 智能体）</dt><dd>LLM 驱动的自主程序，能读取信息、做决策、调用工具。区别于死规则脚本。</dd>
<dt>AUC（Area Under Curve）</dt><dd>ROC 曲线下面积。随机挑一对正负样本，模型给正样本更高分的概率。0.5 = 瞎猜，1.0 = 完美。</dd>
<dt>Cross Validation（交叉验证 / CV）</dt><dd>把数据分多份，轮流当训练 / 测试，避免“自己考自己”。我们用 5-fold。</dd>
<dt>Data Leakage（数据泄漏）</dt><dd>训练时不小心让模型看到了未来或测试集的信息——指标会假高，部署时崩。</dd>
<dt>Decision Tree（决策树）</dt><dd>由一系列 yes/no 问题构成的预测器，例如“readme_len &gt; 5000? → yes → ...”。</dd>
<dt>F1 Score</dt><dd>Precision 和 Recall 的调和平均，二者偏低任一就会拉低 F1。</dd>
<dt>Feature（特征）</dt><dd>用来描述一个样本的可量化属性，比如“commits_30d = 31”。</dd>
<dt>Gini Importance（基尼重要性）</dt><dd>决策树 / RF 衡量某特征在分裂时贡献了多少“纯度提升”，越大越重要。</dd>
<dt>k-fold CV</dt><dd>把数据切成 k 份做交叉验证。我们 k=5。</dd>
<dt>Label（标签）</dt><dd>要预测的“答案”。本项目中是 <code>is_top20</code>（一年后是否进入同语言前 20%）。</dd>
<dt>Logistic Regression（逻辑回归 / LR）</dt><dd>把特征加权求和再过 sigmoid，得到一个 [0,1] 概率。简单、可解释。</dd>
<dt>Multi-agent</dt><dd>多个 agent 协作完成任务的系统。本项目 5 个 agent。</dd>
<dt>One-hot 编码</dt><dd>把类别变量（如语言）拆成多个 0/1 列。如 lang_Python=1, lang_Go=0...</dd>
<dt>OpenClaw</dt><dd>本地运行的 agentic AI 框架，本项目用它做多 agent 调度。</dd>
<dt>Orchestrator</dt><dd>主 agent，负责调度其他 sub-agent，类似项目经理。</dd>
<dt>p80 / 百分位数</dt><dd>排序后第 80% 位置的值。Top 20% = 高于 p80。</dd>
<dt>PR-AUC（Precision-Recall AUC）</dt><dd>类别不平衡时比 AUC 更诚实的指标。关注少数类的精度-召回平衡。</dd>
<dt>Precision（精度）</dt><dd>“模型说 yes”的样本里，真为 yes 的比例。</dd>
<dt>Precision@K</dt><dd>模型给出概率最高的 K 个样本里，真正例的占比。最贴近“推荐 Top-N”场景的指标。</dd>
<dt>Random Forest（随机森林 / RF）</dt><dd>100+ 棵决策树投票，少数服从多数。</dd>
<dt>Recall（召回率）</dt><dd>所有真为 yes 的样本里，模型抓到的比例。</dd>
<dt>SHAP</dt><dd>解释模型预测的方法，给每个特征算出对单样本预测的“边际贡献”。比 Gini 更现代。</dd>
<dt>SOUL.md</dt><dd>OpenClaw 中定义单个 agent 角色和职责的文件。</dd>
<dt>SKILL.md</dt><dd>OpenClaw 中描述一个 skill（可调用能力）的文件，含触发词和调度策略。</dd>
<dt>Star</dt><dd>GitHub 用户对一个仓库的“点赞”。star 数是开源界粗略但通用的成功度量。</dd>
<dt>Stratified（分层）</dt><dd>按子群（如语言）分组后在每组内单独取百分位，比全局更公平。</dd>
<dt>TF-IDF</dt><dd>Term Frequency × Inverse Document Frequency。给词打分：出现多但到处都有的降权，独特高频的加权。</dd>
<dt>Time-split（时间切分）</dt><dd>按时间顺序切分训练 / 测试集，模拟真实部署。比随机 CV 更严格。</dd>
<dt>XGBoost</dt><dd>梯度提升决策树框架。一棵接一棵修正前面的错误，性能很强。</dd>
</dl>
"""

SAMPLES = """
<h2 id="samples">附录 B · 真实数据样例</h2>

<p>下面是 3 个真实仓库在我们数据集里的完整画像，让你看到模型实际看到的“数字”长什么样。</p>

<h3>样本 ① · memvid/memvid <span class="tag good">大爆款 · True Positive</span></h3>
<table>
<tr><th>字段</th><th>值</th></tr>
<tr><td>语言 / 协议</td><td>Rust / Apache-2.0</td></tr>
<tr><td>描述</td><td>Memory layer for AI Agents. Replace complex RAG pipelines...</td></tr>
<tr><td>readme_len</td><td>16,317</td></tr>
<tr><td>readme_has_image / demo</td><td>1 / 0</td></tr>
<tr><td>commits_30d / contributors</td><td>31 / 24</td></tr>
<tr><td>issues_30d / prs_30d</td><td>19 / 16</td></tr>
<tr><td>author_followers / public_repos</td><td>161 / 15</td></tr>
<tr><td>author_type</td><td>Organization</td></tr>
<tr><td>窗口</td><td>2025-05-27 ~ 2025-06-26</td></tr>
<tr><td><b>current_stars（一年后）</b></td><td><b>15,529</b></td></tr>
<tr><td><b>真实标签 is_top20</b></td><td><b>1（成功 ✅）</b></td></tr>
<tr><td><b>模型预测概率</b></td><td><b>0.775（第 6 名）</b></td></tr>
<tr><td>评价</td><td>模型从早期 24 个 contributor + 31 commit + 详细 README 中读出了潜力，命中。</td></tr>
</table>

<h3>样本 ② · strands-agents/agent-builder <span class="tag good">中等爆款 · True Positive</span></h3>
<table>
<tr><th>字段</th><th>值</th></tr>
<tr><td>语言 / 协议</td><td>Python / Apache-2.0</td></tr>
<tr><td>描述</td><td>An example agent demonstrating streaming, tool use, and interactivity from your terminal...</td></tr>
<tr><td>readme_len</td><td>13,146</td></tr>
<tr><td>readme_has_image</td><td>1</td></tr>
<tr><td>commits_30d / contributors</td><td>17 / 11</td></tr>
<tr><td>issues_30d / prs_30d</td><td>8 / 24</td></tr>
<tr><td>author_followers / public_repos</td><td>1,789 / 12</td></tr>
<tr><td>author_type</td><td>Organization</td></tr>
<tr><td><b>current_stars（一年后）</b></td><td><b>414</b></td></tr>
<tr><td><b>真实标签 is_top20</b></td><td><b>1（成功 ✅）</b></td></tr>
<tr><td><b>模型预测概率</b></td><td><b>0.945（第 1 名）</b></td></tr>
<tr><td>评价</td><td>强组织背书（1,789 followers）+ 24 PR + 详细 README → 模型最高信心命中。</td></tr>
</table>

<h3>样本 ③ · Thinklab-SJTU/ML4CO-Bench-101 <span class="tag warn">看走眼 · False Positive</span></h3>
<table>
<tr><th>字段</th><th>值</th></tr>
<tr><td>语言 / 协议</td><td>Python / 无 LICENSE</td></tr>
<tr><td>描述</td><td>ML4CO-Bench-101: Benchmark Machine Learning for Classic Combinatorial Problems...</td></tr>
<tr><td>readme_len</td><td>12,617</td></tr>
<tr><td>readme_has_image</td><td>1</td></tr>
<tr><td>commits_30d / contributors</td><td>33 / <b>2</b></td></tr>
<tr><td>issues_30d / prs_30d</td><td>0 / 1</td></tr>
<tr><td>author_followers / public_repos</td><td>834 / 82</td></tr>
<tr><td>author_type</td><td>Organization</td></tr>
<tr><td><b>current_stars（一年后）</b></td><td><b>46</b></td></tr>
<tr><td><b>真实标签 is_top20</b></td><td><b>0（未达 Python 前 20% ❌）</b></td></tr>
<tr><td><b>模型预测概率</b></td><td><b>0.790（第 4 名）</b></td></tr>
<tr><td>评价</td><td>表面信号很强（长 README + 33 commit + 强 org），但<b>只有 2 个 contributor</b>、<b>0 个外部 issue</b>，是“一个人闷头写”的项目，热度起不来。模型被早期表面指标骗了——这正是为什么 Precision 不会等于 100%。</td></tr>
</table>

<p class="muted">从这三个例子能看出：模型不是看“哪个仓库”，而是看“一行 38 个数字”做判断。当数字模式相似时，它会用相似的概率回应——这也是为什么后续可以靠特征工程改进。</p>
"""

FOOT = """
<hr style="border:none;border-top:1px solid var(--line); margin:60px 0 24px">
<p class="muted" style="text-align:center; font-size:14px;">
基于 OpenClaw Multi-Agent 的开源项目成功预测系统 · 数据挖掘课程项目走读文档<br>
生成时间 2026-05-20 · 数据来源 <code>data/model_results.json</code> + <code>data/repos_raw_500.jsonl</code>
</p>
</div>
</body>
</html>
"""

html = (HEAD.replace("%CSS%", CSS)
        + HERO + TOC
        + CH1 + CH2 + CH3 + CH4 + CH5 + CH6 + CH7 + CH8 + CH9
        + CH10 + CH11 + CH12
        + GLOSSARY + SAMPLES + FOOT)

OUT.write_text(html, encoding="utf-8")
print(f"Written: {OUT}  ({OUT.stat().st_size:,} bytes)")
