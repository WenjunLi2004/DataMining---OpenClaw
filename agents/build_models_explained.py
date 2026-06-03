#!/usr/bin/env python3
"""Build models_and_results_explained.html — deep-dive on the three ML models
and every experiment metric used in the OpenClaw project. Written for someone
who roughly knows what "linear regression" and "decision tree" mean but is new
to XGBoost and to most evaluation metrics.
"""
from pathlib import Path

OUT = Path("/Users/wenjun/openclaw-project/reports/models_and_results_explained.html")

# ── CSS ───────────────────────────────────────────────────────────────────────
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
  --gold:#9a6700;  --gold-bg:#fff8c5;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB",Helvetica,Arial,sans-serif;
  font-size:17px; line-height:1.78; color:var(--ink); background:var(--bg);
}
.wrap{max-width:900px; margin:0 auto; padding:48px 28px 140px}
h1{font-size:34px; line-height:1.25; margin:0 0 8px; letter-spacing:-0.01em}
h2{font-size:26px; margin:64px 0 14px; padding-top:32px; border-top:1px solid var(--line)}
h3{font-size:20px; margin:32px 0 10px}
h4{font-size:17px; margin:22px 0 8px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; font-weight:600}
p{margin:12px 0}
ul,ol{margin:10px 0 14px; padding-left:1.4em}
li{margin:6px 0}
a{color:var(--blue); text-decoration:none}
a:hover{text-decoration:underline}
code, kbd, samp{font-family:"SF Mono",Menlo,Consolas,monospace; font-size:.93em; background:var(--code); padding:.1em .35em; border-radius:4px}
pre{background:var(--panel); padding:14px 16px; border-radius:8px; overflow:auto; border:1px solid var(--line); font-size:14.5px}
pre code{background:transparent; padding:0}
table{width:100%; border-collapse:collapse; margin:14px 0; font-size:15.5px}
th,td{padding:8px 12px; text-align:left; border-bottom:1px solid var(--line)}
th{background:var(--panel); font-weight:600; color:var(--muted)}
tr:hover td{background:#fcfcfd}
.note{
  background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--blue);
  padding:14px 18px; border-radius:8px; margin:18px 0;
}
.note.analogy{border-left-color:var(--purple); background:var(--purple-bg)}
.note.warn{border-left-color:var(--orange); background:var(--orange-bg)}
.note.good{border-left-color:var(--green); background:var(--green-bg)}
.note.danger{border-left-color:var(--red); background:var(--red-bg)}
.note.math{border-left-color:var(--gold); background:var(--gold-bg)}
.note .tag{display:inline-block; font-size:12px; font-weight:700; letter-spacing:.05em; color:var(--muted); margin-bottom:2px; text-transform:uppercase}
.tldr{
  background:#fffdf4; border:1px solid #f0e8c8; border-left:4px solid #d4a72c;
  padding:12px 18px; border-radius:8px; margin:18px 0 22px; font-size:16px;
}
.tldr::before{content:"💡 "; font-size:18px}
.hero{
  background:linear-gradient(180deg,#fdfdfd,#f6f8fa);
  border:1px solid var(--line); border-radius:14px; padding:28px 30px; margin:18px 0 30px;
}
.hero .pill{display:inline-block; font-size:12px; font-weight:700; color:var(--green);
  background:var(--green-bg); padding:3px 10px; border-radius:99px; letter-spacing:.04em}
.hero h1{margin-top:10px}
.hero .meta{color:var(--muted); font-size:14.5px; margin-top:14px}
.toc{background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:18px 22px; margin:18px 0 28px}
.toc h4{margin:0 0 8px}
.toc ol{margin:0; padding-left:1.4em; column-count:2; column-gap:24px; font-size:15.5px}
.toc li{break-inside:avoid; margin:5px 0}
@media (max-width:680px){ .toc ol{column-count:1} }
#totop{position:fixed; right:22px; bottom:22px; z-index:10; background:var(--ink); color:#fff; border:none; border-radius:99px; width:46px; height:46px; cursor:pointer; font-size:18px; line-height:1; box-shadow:0 6px 18px rgba(0,0,0,.18); opacity:.85}
#totop:hover{opacity:1}
.eq{font-family:"SF Mono",Menlo,monospace; background:var(--gold-bg); padding:10px 14px; border-radius:6px; display:block; text-align:center; margin:10px 0; border:1px solid #e6d99a; font-size:15px}
figure{margin:18px 0; text-align:center}
figure svg{max-width:100%; height:auto; border:1px solid var(--line); border-radius:6px; padding:6px; background:#fff}
figcaption{color:var(--muted); font-size:14px; margin-top:6px}
.tag{display:inline-block; padding:2px 8px; border-radius:99px; font-size:12px; font-weight:600; background:var(--panel); color:var(--muted)}
.tag.good{background:var(--green-bg); color:var(--green)}
.tag.bad{background:var(--red-bg); color:var(--red)}
.tag.warn{background:var(--orange-bg); color:var(--orange)}
.tag.blue{background:var(--blue-bg); color:var(--blue)}
.tag.purple{background:var(--purple-bg); color:var(--purple)}
.metrics{display:flex; flex-wrap:wrap; gap:10px; margin:18px 0}
.metric{background:#fff; border:1px solid var(--line); border-radius:10px; padding:10px 14px; min-width:130px}
.metric .v{font-size:22px; font-weight:700; font-family:"SF Mono",Menlo,monospace}
.metric .k{font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em}
.metric.green .v{color:var(--green)}
.metric.blue  .v{color:var(--blue)}
.metric.orange .v{color:var(--orange)}
.metric.purple .v{color:var(--purple)}
.muted{color:var(--muted)}
"""

# ── inline SVG diagrams ──────────────────────────────────────────────────────
SVG_LR = """
<svg viewBox="0 0 600 300" xmlns="http://www.w3.org/2000/svg">
  <text x="300" y="22" text-anchor="middle" font-size="13" fill="#57606a">逻辑回归 = 在特征空间画一条直线，sigmoid 把距离变成概率</text>
  <!-- axes -->
  <line x1="60" y1="260" x2="540" y2="260" stroke="#1f2328" stroke-width="1.5"/>
  <line x1="60" y1="50" x2="60" y2="260" stroke="#1f2328" stroke-width="1.5"/>
  <text x="540" y="278" font-size="12" fill="#57606a">readme_len</text>
  <text x="68" y="60" font-size="12" fill="#57606a">commits_30d</text>
  <!-- positive samples (top20) -->
  <g fill="#2da44e" opacity="0.9">
    <circle cx="420" cy="80" r="6"/><circle cx="480" cy="120" r="6"/>
    <circle cx="380" cy="100" r="6"/><circle cx="450" cy="160" r="6"/>
    <circle cx="500" cy="90" r="6"/>
  </g>
  <!-- negative samples -->
  <g fill="#cf222e" opacity="0.7">
    <circle cx="120" cy="220" r="6"/><circle cx="180" cy="240" r="6"/>
    <circle cx="200" cy="200" r="6"/><circle cx="150" cy="230" r="6"/>
    <circle cx="220" cy="245" r="6"/><circle cx="260" cy="215" r="6"/>
    <circle cx="100" cy="190" r="6"/>
  </g>
  <!-- decision boundary -->
  <line x1="100" y1="260" x2="540" y2="60" stroke="#0969da" stroke-width="2.5" stroke-dasharray="6 4"/>
  <text x="350" y="190" font-size="13" fill="#0969da" font-weight="700">决策线 w·x + b = 0</text>
  <text x="350" y="207" font-size="11" fill="#0969da">距线越远 → sigmoid 越接近 0 或 1</text>
  <!-- legend -->
  <circle cx="80" cy="35" r="5" fill="#2da44e"/><text x="90" y="39" font-size="11" fill="#1f2328">正例 (top 20%)</text>
  <circle cx="200" cy="35" r="5" fill="#cf222e"/><text x="210" y="39" font-size="11" fill="#1f2328">负例</text>
</svg>"""

SVG_TREE = """
<svg viewBox="0 0 640 280" xmlns="http://www.w3.org/2000/svg">
  <text x="320" y="22" text-anchor="middle" font-size="13" fill="#57606a">一棵决策树 = 一串 yes/no 问题，每条路径走向一片叶子</text>
  <!-- root -->
  <rect x="220" y="40" width="200" height="42" rx="6" fill="#fff" stroke="#1f2328" stroke-width="1.5"/>
  <text x="320" y="60" text-anchor="middle" font-size="13" font-weight="700">readme_len &gt; 5000?</text>
  <text x="320" y="76" text-anchor="middle" font-size="10" fill="#57606a">根节点 (root)</text>
  <!-- branches -->
  <text x="240" y="105" font-size="12" fill="#57606a">否</text>
  <line x1="260" y1="82" x2="120" y2="125" stroke="#57606a" stroke-width="1.5"/>
  <text x="395" y="105" font-size="12" fill="#57606a">是</text>
  <line x1="380" y1="82" x2="520" y2="125" stroke="#57606a" stroke-width="1.5"/>
  <!-- left mid -->
  <rect x="20" y="125" width="200" height="42" rx="6" fill="#fff" stroke="#1f2328" stroke-width="1.5"/>
  <text x="120" y="145" text-anchor="middle" font-size="12" font-weight="700">commits_30d &gt; 10?</text>
  <text x="120" y="161" text-anchor="middle" font-size="10" fill="#57606a">中间节点</text>
  <!-- right mid -->
  <rect x="420" y="125" width="200" height="42" rx="6" fill="#fff" stroke="#1f2328" stroke-width="1.5"/>
  <text x="520" y="145" text-anchor="middle" font-size="12" font-weight="700">author_followers &gt; 200?</text>
  <text x="520" y="161" text-anchor="middle" font-size="10" fill="#57606a">中间节点</text>
  <!-- leaves -->
  <line x1="60" y1="167" x2="40" y2="210" stroke="#57606a"/>
  <line x1="180" y1="167" x2="200" y2="210" stroke="#57606a"/>
  <line x1="460" y1="167" x2="440" y2="210" stroke="#57606a"/>
  <line x1="580" y1="167" x2="600" y2="210" stroke="#57606a"/>
  <g font-size="11" font-weight="700">
    <rect x="0" y="210" width="80" height="36" rx="6" fill="#ffebe9" stroke="#cf222e"/>
    <text x="40" y="225" text-anchor="middle" fill="#cf222e">叶: 不会火</text>
    <text x="40" y="240" text-anchor="middle" font-size="10" fill="#57606a">p≈0.05</text>
    <rect x="160" y="210" width="80" height="36" rx="6" fill="#fff1e5" stroke="#bc4c00"/>
    <text x="200" y="225" text-anchor="middle" fill="#bc4c00">叶: 中等</text>
    <text x="200" y="240" text-anchor="middle" font-size="10" fill="#57606a">p≈0.18</text>
    <rect x="400" y="210" width="80" height="36" rx="6" fill="#fff1e5" stroke="#bc4c00"/>
    <text x="440" y="225" text-anchor="middle" fill="#bc4c00">叶: 中等</text>
    <text x="440" y="240" text-anchor="middle" font-size="10" fill="#57606a">p≈0.42</text>
    <rect x="560" y="210" width="80" height="36" rx="6" fill="#dafbe1" stroke="#2da44e"/>
    <text x="600" y="225" text-anchor="middle" fill="#2da44e">叶: 会火</text>
    <text x="600" y="240" text-anchor="middle" font-size="10" fill="#57606a">p≈0.82</text>
  </g>
</svg>"""

SVG_RF = """
<svg viewBox="0 0 640 220" xmlns="http://www.w3.org/2000/svg">
  <text x="320" y="22" text-anchor="middle" font-size="13" fill="#57606a">随机森林 = 100 棵互相独立的决策树，每棵投一票，多数胜</text>
  <!-- 5 mini trees -->
  <g font-size="10" text-anchor="middle">
    <g transform="translate(40,60)">
      <circle cx="40" cy="0" r="8" fill="#fff" stroke="#1f2328"/>
      <line x1="35" y1="6" x2="15" y2="35" stroke="#57606a"/>
      <line x1="45" y1="6" x2="65" y2="35" stroke="#57606a"/>
      <circle cx="15" cy="40" r="6" fill="#2da44e"/>
      <circle cx="65" cy="40" r="6" fill="#cf222e"/>
      <text x="40" y="65" fill="#2da44e" font-weight="700">→ 是</text>
      <text x="40" y="80" fill="#57606a">Tree 1</text>
    </g>
    <g transform="translate(160,60)">
      <circle cx="40" cy="0" r="8" fill="#fff" stroke="#1f2328"/>
      <line x1="35" y1="6" x2="15" y2="35" stroke="#57606a"/>
      <line x1="45" y1="6" x2="65" y2="35" stroke="#57606a"/>
      <circle cx="15" cy="40" r="6" fill="#2da44e"/>
      <circle cx="65" cy="40" r="6" fill="#2da44e"/>
      <text x="40" y="65" fill="#2da44e" font-weight="700">→ 是</text>
      <text x="40" y="80" fill="#57606a">Tree 2</text>
    </g>
    <g transform="translate(280,60)">
      <circle cx="40" cy="0" r="8" fill="#fff" stroke="#1f2328"/>
      <line x1="35" y1="6" x2="15" y2="35" stroke="#57606a"/>
      <line x1="45" y1="6" x2="65" y2="35" stroke="#57606a"/>
      <circle cx="15" cy="40" r="6" fill="#cf222e"/>
      <circle cx="65" cy="40" r="6" fill="#cf222e"/>
      <text x="40" y="65" fill="#cf222e" font-weight="700">→ 否</text>
      <text x="40" y="80" fill="#57606a">Tree 3</text>
    </g>
    <g transform="translate(400,60)">
      <circle cx="40" cy="0" r="8" fill="#fff" stroke="#1f2328"/>
      <line x1="35" y1="6" x2="15" y2="35" stroke="#57606a"/>
      <line x1="45" y1="6" x2="65" y2="35" stroke="#57606a"/>
      <circle cx="15" cy="40" r="6" fill="#2da44e"/>
      <circle cx="65" cy="40" r="6" fill="#cf222e"/>
      <text x="40" y="65" fill="#2da44e" font-weight="700">→ 是</text>
      <text x="40" y="80" fill="#57606a">Tree 4</text>
    </g>
    <g transform="translate(520,60)">
      <circle cx="40" cy="0" r="8" fill="#fff" stroke="#1f2328"/>
      <line x1="35" y1="6" x2="15" y2="35" stroke="#57606a"/>
      <line x1="45" y1="6" x2="65" y2="35" stroke="#57606a"/>
      <circle cx="15" cy="40" r="6" fill="#2da44e"/>
      <circle cx="65" cy="40" r="6" fill="#2da44e"/>
      <text x="40" y="65" fill="#2da44e" font-weight="700">→ 是</text>
      <text x="40" y="80" fill="#57606a">Tree 5</text>
    </g>
  </g>
  <!-- voting box -->
  <rect x="220" y="160" width="200" height="48" rx="8" fill="#dafbe1" stroke="#2da44e"/>
  <text x="320" y="180" text-anchor="middle" font-size="14" font-weight="700" fill="#2da44e">投票: 4 是 / 1 否</text>
  <text x="320" y="198" text-anchor="middle" font-size="12" fill="#1f2328">最终预测: 会火 (p = 0.80)</text>
  <!-- arrows -->
  <g stroke="#57606a" stroke-width="1">
    <line x1="80" y1="148" x2="280" y2="160" stroke-dasharray="3 3"/>
    <line x1="200" y1="148" x2="290" y2="160" stroke-dasharray="3 3"/>
    <line x1="320" y1="148" x2="320" y2="160" stroke-dasharray="3 3"/>
    <line x1="440" y1="148" x2="350" y2="160" stroke-dasharray="3 3"/>
    <line x1="560" y1="148" x2="360" y2="160" stroke-dasharray="3 3"/>
  </g>
</svg>"""

SVG_BOOST = """
<svg viewBox="0 0 640 240" xmlns="http://www.w3.org/2000/svg">
  <text x="320" y="22" text-anchor="middle" font-size="13" fill="#57606a">XGBoost = 一棵接一棵地修正错误。每棵新树只学“前面所有树加起来错了多少”</text>
  <!-- truth -->
  <text x="20" y="60" font-size="12" font-weight="700" fill="#1f2328">真值</text>
  <g font-size="11" text-anchor="middle">
    <circle cx="100" cy="60" r="14" fill="#dafbe1" stroke="#2da44e"/><text x="100" y="64">1</text>
    <circle cx="180" cy="60" r="14" fill="#dafbe1" stroke="#2da44e"/><text x="180" y="64">1</text>
    <circle cx="260" cy="60" r="14" fill="#ffebe9" stroke="#cf222e"/><text x="260" y="64">0</text>
    <circle cx="340" cy="60" r="14" fill="#ffebe9" stroke="#cf222e"/><text x="340" y="64">0</text>
    <circle cx="420" cy="60" r="14" fill="#dafbe1" stroke="#2da44e"/><text x="420" y="64">1</text>
    <circle cx="500" cy="60" r="14" fill="#ffebe9" stroke="#cf222e"/><text x="500" y="64">0</text>
  </g>
  <!-- prediction after tree 1 -->
  <text x="20" y="110" font-size="12" font-weight="700" fill="#0969da">第 1 棵树后</text>
  <g font-size="10" text-anchor="middle" fill="#0969da">
    <text x="100" y="110">0.6</text>
    <text x="180" y="110">0.4</text>
    <text x="260" y="110">0.3</text>
    <text x="340" y="110">0.2</text>
    <text x="420" y="110">0.5</text>
    <text x="500" y="110">0.4</text>
  </g>
  <!-- residuals -->
  <text x="20" y="135" font-size="11" fill="#bc4c00">残差 (truth − pred)</text>
  <g font-size="10" text-anchor="middle" fill="#bc4c00">
    <text x="100" y="135">+0.4</text>
    <text x="180" y="135">+0.6</text>
    <text x="260" y="135">-0.3</text>
    <text x="340" y="135">-0.2</text>
    <text x="420" y="135">+0.5</text>
    <text x="500" y="135">-0.4</text>
  </g>
  <!-- tree 2 learns residuals -->
  <text x="20" y="170" font-size="12" font-weight="700" fill="#8250df">第 2 棵树学残差</text>
  <text x="320" y="170" text-anchor="middle" font-size="11" fill="#8250df">→ 输出 ≈ +0.3 / +0.5 / −0.2 / −0.15 / +0.4 / −0.3</text>
  <!-- prediction after tree 2 -->
  <text x="20" y="205" font-size="12" font-weight="700" fill="#2da44e">2 棵树合计后</text>
  <g font-size="10" text-anchor="middle" fill="#2da44e">
    <text x="100" y="205">0.85</text>
    <text x="180" y="205">0.90</text>
    <text x="260" y="205">0.10</text>
    <text x="340" y="205">0.05</text>
    <text x="420" y="205">0.85</text>
    <text x="500" y="205">0.10</text>
  </g>
  <text x="320" y="232" text-anchor="middle" font-size="12" font-style="italic" fill="#57606a">每加一棵树，预测就靠近真值一点 ← 这就是 "Gradient Boosting"</text>
</svg>"""

SVG_KFOLD = """
<svg viewBox="0 0 640 200" xmlns="http://www.w3.org/2000/svg">
  <text x="320" y="22" text-anchor="middle" font-size="13" fill="#57606a">5-fold 交叉验证：每轮一份当“考试”，其余 4 份当“复习”，轮 5 次</text>
  <g font-family="SF Mono,Menlo,monospace" font-size="11">
    <g transform="translate(0,40)">
      <rect width="120" height="22" fill="#eef1f5" stroke="#d0d7de"/><text x="60" y="16" text-anchor="middle">Fold 1</text>
      <rect x="120" width="120" height="22" fill="#eef1f5" stroke="#d0d7de"/><text x="180" y="16" text-anchor="middle">Fold 2</text>
      <rect x="240" width="120" height="22" fill="#eef1f5" stroke="#d0d7de"/><text x="300" y="16" text-anchor="middle">Fold 3</text>
      <rect x="360" width="120" height="22" fill="#eef1f5" stroke="#d0d7de"/><text x="420" y="16" text-anchor="middle">Fold 4</text>
      <rect x="480" width="120" height="22" fill="#eef1f5" stroke="#d0d7de"/><text x="540" y="16" text-anchor="middle">Fold 5</text>
    </g>
    <g font-size="10">
      <g transform="translate(0,72)">
        <rect width="120" height="18" fill="#fff1e5" stroke="#bc4c00"/><text x="60" y="13" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="120" width="480" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="360" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,96)">
        <rect width="120" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="60" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="120" width="120" height="18" fill="#fff1e5" stroke="#bc4c00"/><text x="180" y="13" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="240" width="360" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="420" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,120)">
        <rect width="240" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="120" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="240" width="120" height="18" fill="#fff1e5" stroke="#bc4c00"/><text x="300" y="13" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="360" width="240" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="480" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,144)">
        <rect width="360" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="180" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="360" width="120" height="18" fill="#fff1e5" stroke="#bc4c00"/><text x="420" y="13" text-anchor="middle" fill="#bc4c00">TEST</text>
        <rect x="480" width="120" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="540" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
      </g>
      <g transform="translate(0,168)">
        <rect width="480" height="18" fill="#ddf4ff" stroke="#0969da"/><text x="240" y="13" text-anchor="middle" fill="#0969da">TRAIN</text>
        <rect x="480" width="120" height="18" fill="#fff1e5" stroke="#bc4c00"/><text x="540" y="13" text-anchor="middle" fill="#bc4c00">TEST</text>
      </g>
    </g>
  </g>
</svg>"""

SVG_ROC = """
<svg viewBox="0 0 640 280" xmlns="http://www.w3.org/2000/svg">
  <text x="320" y="22" text-anchor="middle" font-size="13" fill="#57606a">ROC 曲线 = 模型在所有可能阈值下的真阳率 vs 假阳率轨迹</text>
  <!-- axes -->
  <line x1="80" y1="240" x2="560" y2="240" stroke="#1f2328" stroke-width="1.5"/>
  <line x1="80" y1="240" x2="80" y2="50" stroke="#1f2328" stroke-width="1.5"/>
  <text x="320" y="265" text-anchor="middle" font-size="12" fill="#57606a">False Positive Rate (误报率)</text>
  <text x="50" y="145" text-anchor="middle" font-size="12" fill="#57606a" transform="rotate(-90 50 145)">True Positive Rate (召回率)</text>
  <!-- axis ticks -->
  <text x="80" y="255" text-anchor="middle" font-size="10" fill="#57606a">0</text>
  <text x="320" y="255" text-anchor="middle" font-size="10" fill="#57606a">0.5</text>
  <text x="560" y="255" text-anchor="middle" font-size="10" fill="#57606a">1.0</text>
  <text x="65" y="244" text-anchor="end" font-size="10" fill="#57606a">0</text>
  <text x="65" y="50" text-anchor="end" font-size="10" fill="#57606a">1.0</text>
  <!-- diagonal (random) -->
  <line x1="80" y1="240" x2="560" y2="50" stroke="#d0d7de" stroke-width="1.5" stroke-dasharray="4 3"/>
  <text x="470" y="115" font-size="11" fill="#57606a">瞎猜的 ROC (AUC=0.5)</text>
  <!-- AUC curve (good model) -->
  <path d="M 80 240 Q 100 80, 240 65 T 560 50" fill="none" stroke="#2da44e" stroke-width="3"/>
  <path d="M 80 240 Q 100 80, 240 65 T 560 50 L 560 240 Z" fill="#2da44e" fill-opacity="0.12"/>
  <text x="220" y="155" font-size="12" fill="#2da44e" font-weight="700">RF 的 ROC (AUC = 0.878)</text>
  <text x="220" y="170" font-size="11" fill="#57606a">曲线下面积越大 → 排序越准</text>
</svg>"""

# ── HTML chunks ───────────────────────────────────────────────────────────────
HEAD = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>三个模型 + 实验结果概念精讲 · OpenClaw 项目</title>
<style>%CSS%</style>
</head>
<body>
<button id="totop" onclick="window.scrollTo({top:0,behavior:'smooth'})" title="回到顶部" aria-label="back to top">↑</button>
<div class="wrap">
"""

HERO = """
<header class="hero">
  <span class="pill">深度概念精讲 · 35 分钟阅读</span>
  <h1>三个模型 + 实验结果概念精讲</h1>
  <p class="muted">从你已经知道的"线性回归画线 / 决策树问 yes-no"出发，把 OpenClaw 项目用到的 LR / RF / XGBoost 三个模型彻底讲透，再把每一个实验指标和实验结果对应到具体数字。</p>
  <p class="meta">📂 输出文件：<code>~/openclaw-project/reports/models_and_results_explained.html</code><br>
  🌐 在浏览器中打开。每章末尾都有"一句话总结"，可以先扫总结决定是否要读细节。</p>
  <div style="margin-top:16px;padding:12px 16px;background:#ddf4ff;border:1px solid #80ccff;border-radius:8px;color:#0969da;font-size:14px;">
    <b>📌 v3 strict-30d 更新（2026-05-30）</b>：最终模型只使用 19 个能严格回溯到 30 天内的特征（语言/owner、30d 活跃度、历史 30d README、派生比率）。下文里 “38 features / TF-IDF / author_followers / 当前 README / readme_len 是最强特征” 等是历史叙事，最新特征清单见 <a href="feature_engineering.html">feature_engineering.html</a>。
  </div>
</header>
"""

TOC = """
<nav class="toc" id="toc">
<h4>目录</h4>
<ol>
  <li><a href="#m1">模型 ① · 逻辑回归 LR</a></li>
  <li><a href="#m2">模型 ② · 随机森林 RF</a></li>
  <li><a href="#m3">模型 ③ · XGBoost</a></li>
  <li><a href="#m4">三模型对比与选择</a></li>
  <li><a href="#e1">指标 ① · Accuracy 的陷阱</a></li>
  <li><a href="#e2">指标 ② · Precision / Recall / F1</a></li>
  <li><a href="#e3">指标 ③ · AUC（ROC 曲线下面积）</a></li>
  <li><a href="#e4">指标 ④ · PR-AUC</a></li>
  <li><a href="#e5">指标 ⑤ · Precision@K</a></li>
  <li><a href="#e6">指标 ⑥ · 5-fold 交叉验证</a></li>
  <li><a href="#r1">结果 ① · 主对比表</a></li>
  <li><a href="#r2">结果 ② · 消融实验</a></li>
  <li><a href="#r3">结果 ③ · 时间切分验证</a></li>
  <li><a href="#r4">结果 ④ · 分语言 AUC</a></li>
  <li><a href="#r5">结果 ⑤ · 特征重要性（Gini vs SHAP）</a></li>
  <li><a href="#r6">结果 ⑥ · Top-10 推荐验证</a></li>
  <li><a href="#r7">结果 ⑦ · Today Radar 动态阈值</a></li>
</ol>
</nav>
"""

# Models part
M1 = """
<h2 id="m1">模型 ① · 逻辑回归 LR（Logistic Regression）</h2>

<h3>名字误导：它不是回归，是分类</h3>
<p>"Logistic Regression" 字面上像在做回归（预测一个连续数），但实际上它是一个 <b>二分类</b> 模型——输出一个 0 到 1 之间的概率，然后用 0.5 作为分界。"Regression" 是历史名称问题，因为它内部确实在拟合一条线性公式。</p>

<h3>它在做什么：画一条线 + 把距离变成概率</h3>
<p>给每个特征一个权重 <code>w</code>，加上一个偏置 <code>b</code>，加权求和：</p>
<span class="eq">score = w₁ · readme_len + w₂ · commits_30d + w₃ · author_followers + ... + b</span>
<p>这一步的输出是一个普通实数，可以是 −5、可以是 +20。然后通过 <b>sigmoid 函数</b> 压到 [0, 1]：</p>
<span class="eq">P(top20 = 1) = sigmoid(score) = 1 / (1 + e<sup>−score</sup>)</span>

<div class="note math">
<span class="tag">为什么 sigmoid</span>
<p>当 score = 0 → sigmoid = 0.5（模型完全不确定）。score = +5 → sigmoid ≈ 0.99（高置信"会火"）。score = −5 → sigmoid ≈ 0.01（高置信"不会火"）。S 型曲线让"非常确定"和"非常不确定"自然区分开。</p>
</div>

<figure>%SVG_LR%</figure>

<h3>权重 w 的物理含义</h3>
<ul>
  <li><b>正权重</b>：该特征越大 → P(top20) 越高。比如如果 LR 学出 w(readme_len) = +0.3，说明 README 越长越可能进 Top 20%。</li>
  <li><b>负权重</b>：该特征越大 → P(top20) 越低。</li>
  <li><b>权重大小</b>：绝对值大代表该特征对决策影响大。</li>
</ul>

<h3>训练：最小化"对数损失"（log loss）</h3>
<p>训练过程就是找一组 w 让所有训练样本的预测概率尽可能贴近真实标签：</p>
<ul>
  <li>真实是正例（is_top20=1）时，希望预测 P 越接近 1 越好</li>
  <li>真实是负例（is_top20=0）时，希望预测 P 越接近 0 越好</li>
</ul>
<p>用梯度下降（gradient descent）迭代调整 w，让总损失最小。这是凸优化问题，全局最优解唯一，所以 LR 训练既快又稳定。</p>

<h3>优点 / 缺点</h3>
<table>
<tr><th>优点</th><th>缺点</th></tr>
<tr>
  <td>训练极快（500 样本 × 38 特征几秒搞定）<br>
      权重直接可解释（每个特征贡献多大一目了然）<br>
      数据量小也能用<br>
      作为 baseline 不会过拟合</td>
  <td>只能学线性关系<br>
      没法捕捉"特征 A 高 + 特征 B 低"这种组合规律<br>
      对特征尺度敏感（需要标准化）<br>
      对异常值敏感</td>
</tr>
</table>

<h3>本项目里 LR 的表现</h3>
<div class="metrics">
  <div class="metric blue"><div class="v">0.842</div><div class="k">AUC</div></div>
  <div class="metric"><div class="v">0.605</div><div class="k">F1</div></div>
  <div class="metric orange"><div class="v">0.742</div><div class="k">Recall</div></div>
  <div class="metric"><div class="v">0.516</div><div class="k">Precision</div></div>
  <div class="metric"><div class="v">0.60</div><div class="k">P@10</div></div>
</div>
<p>LR 的 Recall 在三个模型中最高（0.742）但 Precision 偏低（0.516），说明它"激进"——倾向于把不确定的样本也判为正例，所以漏掉的少（高召回），但误报的多（低精度）。</p>

<div class="tldr">逻辑回归 = 给每个特征学一个权重 → 加权求和 → sigmoid 转概率。简单、可解释、训练快，但只能学线性关系。本项目里 AUC 0.842，最激进。</div>
""".replace("%SVG_LR%", SVG_LR)

M2 = """
<h2 id="m2">模型 ② · 随机森林 RF（Random Forest）</h2>

<h3>第一步：先理解一棵决策树</h3>
<p>决策树就是一连串的 yes/no 判断，把数据从根节点一直分到叶子节点。每个内部节点问一个问题（"readme_len &gt; 5000?"），样本根据答案走左边或右边。最后落到的叶子节点给出预测概率。</p>

<figure>%SVG_TREE%</figure>

<h3>决策树怎么"学"</h3>
<p>训练时算法贪心地搜索：</p>
<ol>
  <li>对所有特征 × 所有可能的阈值，算"如果按这个条件切一刀，分出来的两堆样本在标签上有多干净"</li>
  <li>选最干净的那个切法作为当前节点</li>
  <li>对左右两堆样本递归重复，直到达到深度上限或一堆里全是同一类</li>
</ol>
<p>"干净程度"用 <b>Gini 不纯度</b>衡量：一堆全是正例 → Gini = 0（完全纯）；一半正一半负 → Gini = 0.5（最不纯）。</p>

<h3>单棵树的致命问题：高方差</h3>
<div class="note warn">
<span class="tag">过拟合风险</span>
<p>同样 500 个样本，如果你抽 95% 训练第一棵树，再抽另一个 95% 训练第二棵树，两棵树的结构可能差很多。这意味着<b>训练数据稍微一变，模型就大变</b> → 过拟合。</p>
</div>

<h3>随机森林的两个"随机"</h3>
<p>把一棵不稳定的树变成稳定的森林，靠两个独立的随机化：</p>
<ol>
  <li><b>Bootstrap 行抽样</b>：每棵树用一个"有放回抽样"的训练子集（约 63% 不重复样本）。每棵树看的训练数据都不一样。</li>
  <li><b>Feature 列抽样</b>：每个节点在选切分条件时，<b>不</b>看全部 38 个特征，只看随机选出的子集（通常 √38 ≈ 6 个）。这强制不同的树关注不同的信号。</li>
</ol>
<p>训练 100 棵这样的树后，新样本进来 → 每棵树投一票 → 多数胜（或对概率求平均）。</p>

<figure>%SVG_RF%</figure>

<div class="note analogy">
<span class="tag">💡 类比</span>
<p>陪审团比单个法官更可靠，不是因为陪审员个个聪明，而是因为<b>他们的错误不一样</b>——只要大多数人独立判断、各自的偏见相互抵消，群体的平均比个人更准。这就是"集成学习"（ensemble learning）的本质。</p>
</div>

<h3>优点 / 缺点</h3>
<table>
<tr><th>优点</th><th>缺点</th></tr>
<tr>
  <td>能学非线性 + 特征组合（"long README 且 commits 多 → 极可能爆款"）<br>
      对异常值健壮<br>
      不需要特征标准化<br>
      能给出特征重要性<br>
      调参简单（默认参数就能用）</td>
  <td>训练 100 棵树比 LR 慢 ~50 倍<br>
      模型本身难解释（不能像 LR 那样"读权重"）<br>
      对类别不平衡的少数类有偏差<br>
      预测概率不是真正的概率（是投票频率）</td>
</tr>
</table>

<h3>本项目里 RF 的表现</h3>
<div class="metrics">
  <div class="metric green"><div class="v">0.878</div><div class="k">AUC（最高）</div></div>
  <div class="metric"><div class="v">0.402</div><div class="k">F1</div></div>
  <div class="metric"><div class="v">0.298</div><div class="k">Recall</div></div>
  <div class="metric green"><div class="v">0.627</div><div class="k">Precision</div></div>
  <div class="metric green"><div class="v">0.90</div><div class="k">P@10（最高）</div></div>
</div>
<p>RF 跟 LR 形成鲜明对比："保守"——默认 0.5 阈值下 Recall 只有 0.298，但被它打上正例的样本有 62.7% 真的是。这种特性让它在 Top-10 推荐场景下达到 P@10 = 0.90，是三个模型里最高的。</p>

<div class="tldr">随机森林 = 100 棵互相独立的决策树 + 投票。每棵树用不同数据 + 不同特征训练，错误相互抵消。本项目里 AUC 0.878（最高），P@10 0.90（最高），但 Recall 偏低（保守派）。</div>
""".replace("%SVG_TREE%", SVG_TREE).replace("%SVG_RF%", SVG_RF)

M3 = """
<h2 id="m3">模型 ③ · XGBoost（重点讲）</h2>

<p>这是你最不熟的模型。它和 RF 看起来都用决策树，但底层<b>训练逻辑完全不一样</b>。</p>

<h3>核心思想：Boosting ≠ Bagging</h3>
<table>
<tr><th></th><th>Random Forest (Bagging)</th><th>XGBoost (Boosting)</th></tr>
<tr><td><b>训练方式</b></td><td>100 棵树<b>并行</b>，互相不知道彼此</td><td>一棵接一棵<b>串行</b>，新树依赖旧树</td></tr>
<tr><td><b>每棵树学什么</b></td><td>独立预测标签</td><td>预测"前面所有树合起来还差多少"</td></tr>
<tr><td><b>合并方式</b></td><td>投票 / 求平均</td><td>所有树的输出相加</td></tr>
<tr><td><b>树的大小</b></td><td>深、复杂（每棵都强）</td><td>浅、简单（每棵都弱，叠加变强）</td></tr>
</table>

<h3>逐步剖析：XGBoost 怎么训练</h3>
<p>用一个简化例子。假设有 6 个样本，真实标签是 1, 1, 0, 0, 1, 0。</p>

<h4>步骤 1 · 初始预测</h4>
<p>所有样本给一个相同的初始预测，通常是训练集正例率。本项目是 20.2% → 初始预测全部 = 0.2。</p>

<h4>步骤 2 · 第 1 棵树学"残差"</h4>
<p>残差 = 真实标签 − 当前预测：</p>
<pre>真实:  1    1    0    0    1    0
预测: 0.2  0.2  0.2  0.2  0.2  0.2
残差: +0.8 +0.8 -0.2 -0.2 +0.8 -0.2</pre>
<p>第 1 棵树不学"标签是 0 还是 1"，而是<b>学这些残差</b>——它的目标变成了一个回归问题。训练完后第 1 棵树对每个样本输出 ≈ +0.4, +0.6, −0.2, −0.15, +0.5, −0.3（树是浅的，所以学得不完美）。</p>

<h4>步骤 3 · 更新预测</h4>
<p>新预测 = 旧预测 + 学习率 × 第 1 棵树的输出。常用学习率 = 0.1：</p>
<pre>预测: 0.2 + 0.1×0.4 = 0.24
      0.2 + 0.1×0.6 = 0.26
      0.2 + 0.1×(-0.2) = 0.18
      ...</pre>

<h4>步骤 4 · 第 2 棵树学新残差</h4>
<p>用更新后的预测重新算残差，第 2 棵树继续学这些残差。重复几百次。每一轮整个集成都朝"减少损失"的方向走一小步。</p>

<figure>%SVG_BOOST%</figure>

<div class="note math">
<span class="tag">为什么叫 "Gradient" Boosting</span>
<p>在数学上，"残差 = 真实 − 预测" 是<b>平方损失函数</b>对预测的负梯度。对于分类任务，损失函数是 log-loss，对应的"梯度"不是简单的 truth − pred，而是更通用的形式。所以 XGBoost 实际上是"沿损失函数的梯度方向逐步下降"——这就是名字 "Gradient Boosting" 的来源。把"损失函数"换一下，它就能做回归、排序、分位数预测等各种任务。</p>
</div>

<h3>XGBoost 的 "X" — 工程优化</h3>
<p>梯度提升不是 XGBoost 发明的（早在 1999 年就有了），但 XGBoost (2016) 加了一堆工程优化让它实用起来：</p>
<ul>
  <li><b>正则化</b>：在损失函数里加上对树复杂度的惩罚，控制过拟合（这是 GBDT 没有的）</li>
  <li><b>稀疏感知</b>：对缺失值有特殊处理</li>
  <li><b>并行分裂选择</b>：虽然树之间串行，但每棵树内"选择最佳切分点"可以并行</li>
  <li><b>缓存优化</b>：用直方图近似切分，跑大数据集快几个数量级</li>
  <li><b>剪枝</b>：用 max_depth、min_child_weight 这些超参防止单棵树过深</li>
</ul>
<p>这就是为什么 XGBoost 在 Kaggle 比赛长期称霸——同样的算法思想，加上更稳的实现 + 更细的调参空间。</p>

<h3>关键超参（实际项目要调的就这几个）</h3>
<table>
<tr><th>参数</th><th>含义</th><th>典型值</th></tr>
<tr><td><code>n_estimators</code></td><td>树的数量</td><td>100 – 1000</td></tr>
<tr><td><code>learning_rate</code></td><td>每棵树的"步幅"，越小越稳但需要更多树</td><td>0.01 – 0.3</td></tr>
<tr><td><code>max_depth</code></td><td>单棵树的最大深度</td><td>3 – 8</td></tr>
<tr><td><code>subsample</code></td><td>每棵树用多少比例的行</td><td>0.7 – 1.0</td></tr>
<tr><td><code>colsample_bytree</code></td><td>每棵树用多少比例的列</td><td>0.7 – 1.0</td></tr>
<tr><td><code>reg_alpha / reg_lambda</code></td><td>L1 / L2 正则化强度</td><td>0 – 10</td></tr>
</table>
<p>本项目用了 sklearn 风格的默认参数 + <code>n_estimators=200, max_depth=5</code>，没做超参搜索。</p>

<h3>优点 / 缺点</h3>
<table>
<tr><th>优点</th><th>缺点</th></tr>
<tr>
  <td>对结构化数据（表格类）几乎是 SOTA<br>
      捕捉复杂非线性 + 特征交互<br>
      自带缺失值处理<br>
      给特征重要性<br>
      调好后比 RF 还稳</td>
  <td>超参多、调参成本高<br>
      训练比 RF 慢<br>
      解释比 LR 难（要看 SHAP）<br>
      数据量小（&lt; 1000 行）容易过拟合<br>
      对特征尺度不敏感但对极端值敏感</td>
</tr>
</table>

<h3>本项目里 XGBoost 的表现</h3>
<div class="metrics">
  <div class="metric blue"><div class="v">0.854</div><div class="k">AUC（中间）</div></div>
  <div class="metric"><div class="v">0.536</div><div class="k">F1（中间）</div></div>
  <div class="metric"><div class="v">0.534</div><div class="k">Recall（中间）</div></div>
  <div class="metric"><div class="v">0.555</div><div class="k">Precision</div></div>
  <div class="metric"><div class="v">0.80</div><div class="k">P@10</div></div>
</div>
<p>XGBoost 是"<b>平衡派</b>"：Precision (0.555) 和 Recall (0.534) 接近，F1 中间。AUC 0.854 略低于 RF (0.878)，但 P@20 = 0.85 是三个模型中最高的。500 样本对 XGBoost 来说偏少，没体现它的真正实力。</p>

<div class="tldr">XGBoost = 几百棵浅树串行训练，每棵学"还差多少"。一步一步逼近真实标签。性能强但调参成本高，本项目里 AUC 0.854（中间）、Precision/Recall 最均衡。</div>
""".replace("%SVG_BOOST%", SVG_BOOST)

M4 = """
<h2 id="m4">三模型对比与选择</h2>

<h3>核心区别一张表</h3>
<table>
<tr><th></th><th>LR</th><th>RF</th><th>XGBoost</th></tr>
<tr><td><b>能学的关系</b></td><td>线性</td><td>非线性 + 简单组合</td><td>非线性 + 复杂组合</td></tr>
<tr><td><b>训练方式</b></td><td>梯度下降</td><td>100 棵独立树投票</td><td>几百棵串行树叠加</td></tr>
<tr><td><b>可解释性</b></td><td>★★★（直接读权重）</td><td>★★（特征重要性）</td><td>★（需要 SHAP）</td></tr>
<tr><td><b>调参成本</b></td><td>低</td><td>低</td><td>高</td></tr>
<tr><td><b>训练速度</b></td><td>极快</td><td>快</td><td>中</td></tr>
<tr><td><b>过拟合风险</b></td><td>低（凸优化）</td><td>低（投票平均）</td><td>中（需要正则）</td></tr>
<tr><td><b>本项目 AUC</b></td><td>0.842</td><td><b>0.878</b></td><td>0.854</td></tr>
<tr><td><b>"性格"</b></td><td>激进（高 Recall）</td><td>保守（高 P@10）</td><td>平衡</td></tr>
</table>

<h3>为什么我们要跑三个，不直接用最强的</h3>
<ol>
  <li><b>校验一致性</b>：如果三个差异巨大的模型在某个特征上结论一致（比如都认为 readme_len 重要），说明这个结论是真的。</li>
  <li><b>看适用场景</b>：不同业务目标用不同模型。"推 10 个候选给老板" → 选 RF（高 P@10）。"尽量不漏正例" → 选 LR（高 Recall）。"平衡" → 选 XGBoost。</li>
  <li><b>用简单模型当 baseline</b>：如果 XGBoost 只比 LR 高 1%，说明特征工程没什么作用，应该回去做特征。</li>
</ol>

<div class="tldr">LR 线性、RF 投票、XGBoost 串行修错。三者性格各异 → 同跑能交叉校验结论可信度，也能根据业务场景挑用。</div>
"""

# Metrics part
E1 = """
<h2 id="e1">指标 ① · Accuracy 的陷阱</h2>

<p>最直觉的"准确率"就是预测对的样本占比：</p>
<span class="eq">Accuracy = (预测对的样本数) / (总样本数)</span>

<div class="note danger">
<span class="tag">⚠️ 陷阱：罕见病故事</span>
<p>假设一种病的发病率是 1%。一个"医生"对所有病人都说"你没病"。他的 Accuracy = 99%！看起来很神，但实际上他什么都没做。</p>
</div>

<p>本项目正例率 20.2%，全部预测"不会火"的傻瓜模型 Accuracy = 79.8%——看起来不算差，但实际无用。<b>所以本项目根本不报 Accuracy</b>，用更精细的指标。</p>

<div class="tldr">类别不平衡时 Accuracy 会骗你。本项目正例 20% → Accuracy 不可信，弃用。</div>
"""

E2 = """
<h2 id="e2">指标 ② · Precision / Recall / F1</h2>

<h3>混淆矩阵（confusion matrix）</h3>
<p>分类的结果有四种情况：</p>
<table>
<tr><th></th><th>模型说"会火"</th><th>模型说"不会火"</th></tr>
<tr><td><b>真的会火</b></td><td><span class="tag good">True Positive (TP)</span><br>抓到了</td><td><span class="tag warn">False Negative (FN)</span><br>漏报了</td></tr>
<tr><td><b>真的不会火</b></td><td><span class="tag bad">False Positive (FP)</span><br>误报了</td><td><span class="tag good">True Negative (TN)</span><br>正确忽略</td></tr>
</table>

<h3>Precision（精度）</h3>
<span class="eq">Precision = TP / (TP + FP)</span>
<p>"被模型说会火的项目里，<b>真的会火的比例</b>。" 高 Precision = 模型说话很谨慎，宁可漏不可错。</p>

<h3>Recall（召回率）</h3>
<span class="eq">Recall = TP / (TP + FN)</span>
<p>"所有真的会火的项目里，<b>被模型抓到的比例</b>。" 高 Recall = 模型敢说，宁可错不可漏。</p>

<div class="note analogy">
<span class="tag">💡 类比</span>
<p>渔民撒网。Precision 高 = 网眼大，捞上来的鱼几乎都是大鱼，但很多大鱼漏过去了。Recall 高 = 网眼小，每条大鱼都抓到了，但网里夹了一堆小鱼。这两个指标互相拉锯。</p>
</div>

<h3>F1：在精度和召回率之间找平衡</h3>
<span class="eq">F1 = 2 × Precision × Recall / (Precision + Recall)</span>
<p>F1 是 Precision 和 Recall 的<b>调和平均</b>。它的特点是只要任一个偏低就会拉低 F1。所以 F1 高 = Precision 和 Recall 都还可以。</p>

<h3>三模型在这三个指标上的对比</h3>
<table>
<tr><th>模型</th><th>Precision</th><th>Recall</th><th>F1</th><th>性格</th></tr>
<tr><td>LR</td><td>0.516</td><td><b>0.742</b></td><td><b>0.605</b></td><td>激进，敢说，多误报</td></tr>
<tr><td>RF</td><td><b>0.627</b></td><td>0.298</td><td>0.402</td><td>保守，少说，但说得准</td></tr>
<tr><td>XGBoost</td><td>0.555</td><td>0.534</td><td>0.536</td><td>平衡</td></tr>
</table>

<div class="tldr">Precision = 模型说 yes 的样本里多少是真 yes；Recall = 真 yes 里被模型抓住多少；F1 = 两者的调和平均。本项目 LR 高 Recall 低 Precision，RF 反之，XGBoost 居中。</div>
"""

E3 = """
<h2 id="e3">指标 ③ · AUC（ROC 曲线下面积）</h2>

<h3>问题：上面的 Precision / Recall 都依赖一个"阈值"</h3>
<p>模型输出的是概率，比如 0.34。我们设阈值 = 0.5，则 0.34 &lt; 0.5 → 预测"不会火"。但阈值是人为定的，不同阈值会得到完全不同的 Precision/Recall 组合：</p>
<ul>
  <li>阈值 = 0.3 → 更多样本被判正例 → Recall ↑，Precision ↓</li>
  <li>阈值 = 0.7 → 更少样本被判正例 → Precision ↑，Recall ↓</li>
</ul>
<p><b>AUC 让我们不依赖任何特定阈值评价模型。</b></p>

<h3>ROC 曲线</h3>
<p>ROC（Receiver Operating Characteristic）曲线的画法：</p>
<ol>
  <li>把测试集所有样本按模型输出的概率从高到低排序</li>
  <li>把阈值从 1.0 一路降到 0.0，每个阈值都计算一对 (FPR, TPR)
    <ul>
      <li>FPR = False Positive Rate = FP / (FP + TN)（误报率）</li>
      <li>TPR = True Positive Rate = Recall = TP / (TP + FN)</li>
    </ul>
  </li>
  <li>把所有 (FPR, TPR) 点连成曲线</li>
</ol>

<figure>%SVG_ROC%</figure>

<h3>AUC 是这条曲线下的面积</h3>
<ul>
  <li>AUC = 1.0 → 完美：存在一个阈值能完美区分正负</li>
  <li>AUC = 0.5 → 模型在瞎猜（曲线 = 对角线）</li>
  <li>AUC = 0.878 → 本项目 RF 的 AUC</li>
</ul>

<div class="note math">
<span class="tag">AUC 的概率解释（最容易记的版本）</span>
<p>"<b>随机挑一个正样本和一个负样本，模型给正样本的概率高于负样本的概率</b>"，这个事件发生的概率就是 AUC。</p>
<p>所以 RF 的 AUC = 0.878 意思是："如果我随便挑一个会火的项目 A 和一个不会火的项目 B，给 RF 打分，A 的分数比 B 高的概率是 87.8%。"——这种<b>排序质量</b>的度量与具体阈值无关。</p>
</div>

<h3>为什么 AUC 是主指标</h3>
<ul>
  <li>不依赖阈值，对模型本身排序能力的纯净度量</li>
  <li>类别不平衡时仍然有意义</li>
  <li>同一个模型不同阈值下，AUC 不变</li>
</ul>

<div class="tldr">AUC = 模型对一对正负样本排对的概率。不依赖阈值。0.5 是瞎猜，1.0 是完美。本项目主指标。</div>
""".replace("%SVG_ROC%", SVG_ROC)

E4 = """
<h2 id="e4">指标 ④ · PR-AUC（Precision-Recall 曲线下面积）</h2>

<h3>AUC 的盲点</h3>
<p>AUC 在类别不平衡严重时会过于乐观。原因：ROC 曲线的 x 轴是 FPR = FP / (FP + TN)，TN（True Negatives）会很大（因为负例多），即使 FP 数量不少，FPR 看起来也很低，曲线就显得"好看"。</p>

<h3>PR 曲线：直接看 Precision 和 Recall 的关系</h3>
<p>PR 曲线把阈值扫一遍，得到每个阈值下的 (Recall, Precision)，连成曲线。PR-AUC = 这条曲线下的面积。</p>

<table>
<tr><th>对比</th><th>ROC-AUC</th><th>PR-AUC</th></tr>
<tr><td>横轴</td><td>FPR（依赖大量负例）</td><td>Recall</td></tr>
<tr><td>纵轴</td><td>TPR</td><td>Precision</td></tr>
<tr><td>对不平衡敏感吗</td><td>弱（被 TN 稀释）</td><td>强（直接反映 Precision）</td></tr>
<tr><td>瞎猜的基准</td><td>恒定 0.5</td><td>等于正例率（本项目 0.202）</td></tr>
</table>

<div class="note">
<span class="tag">读 PR-AUC 的方法</span>
<p>PR-AUC 没有 0.5 这种天然基准。本项目正例率 20.2%，瞎猜的 PR-AUC ≈ 0.202。所以 RF 的 PR-AUC = 0.642 意味着比瞎猜好 3 倍多。</p>
</div>

<h3>三模型 PR-AUC 对比</h3>
<table>
<tr><th>模型</th><th>PR-AUC</th><th>相对瞎猜 (0.202) 的倍数</th></tr>
<tr><td>LR</td><td>0.571</td><td>2.83×</td></tr>
<tr><td><b>RF</b></td><td><b>0.642</b></td><td>3.18×</td></tr>
<tr><td>XGBoost</td><td>0.620</td><td>3.07×</td></tr>
</table>

<div class="tldr">PR-AUC = Precision-Recall 曲线下面积。对类别不平衡更敏感、更诚实。本项目正例率 20%，瞎猜 PR-AUC ≈ 0.2；RF 0.642 ≈ 3.2× 瞎猜。</div>
"""

E5 = """
<h2 id="e5">指标 ⑤ · Precision@K（Top-K 精度）</h2>

<h3>实用问题：我每天只看 10 个项目</h3>
<p>AUC、F1 都看的是整个数据集。但很多业务场景只关心"<b>排在最前面的几个</b>"：</p>
<ul>
  <li>推荐系统：给用户推荐 10 个商品</li>
  <li>反欺诈：人工审核前 100 个最可疑的交易</li>
  <li>本项目：给老板看 10 个潜力项目</li>
</ul>

<h3>定义</h3>
<span class="eq">P@K = (前 K 个预测里的真阳数) / K</span>
<p>把模型对测试集所有样本的预测概率从高到低排序，取前 K 个，看其中有多少是真正的正例。</p>

<h3>P@10 = 0.9 意味着什么</h3>
<p>本项目 RF 在 5-fold OOF（out-of-fold，每个样本都用没见过它的模型来预测）排序的前 10 名里，9 个真的是 Top-20% 的成功项目。换句话说：</p>
<div class="note good">
<span class="tag">⭐ 最实用的指标</span>
<p><b>"模型推 10 个，9 个真的火了。"</b> 这是直接能用的可解释指标，比"AUC 0.878"对一般人友好一万倍。</p>
</div>

<h3>三模型 P@10 / P@20 对比</h3>
<table>
<tr><th>模型</th><th>P@10</th><th>P@20</th><th>解读</th></tr>
<tr><td>LR</td><td>0.60</td><td>0.75</td><td>前 10 太激进，扩到 20 反而稳</td></tr>
<tr><td><b>RF</b></td><td><b>0.90</b></td><td>0.75</td><td>头部极准，往后掉</td></tr>
<tr><td>XGBoost</td><td>0.80</td><td><b>0.85</b></td><td>头部和扩展都稳，可能 K 越大越好</td></tr>
</table>

<div class="tldr">P@K = 排序前 K 个里的真正例占比。"推 10 个真火 9 个"。本项目 RF P@10 = 0.90 是最强可讲数字。</div>
"""

E6 = """
<h2 id="e6">指标 ⑥ · 5-fold 交叉验证（5-fold CV）</h2>

<h3>问题：直接用训练集评估自己 = 作弊</h3>
<p>模型在训练集上的表现总是偏好（过拟合可能让训练 AUC 接近 1.0），不反映真实泛化能力。常见做法：把数据切成训练集（80%）和测试集（20%）。但测试集只有一份，每次切法不同 → 评估结果有噪声。</p>

<h3>5-fold CV：让每个样本都当一次"测试集"</h3>
<ol>
  <li>把 500 个样本随机切成 5 份（每份 100 个）</li>
  <li>第 1 轮：fold 1 当测试，fold 2-5 当训练 → 训练一个模型 → 测试得到一组指标</li>
  <li>第 2 轮：fold 2 当测试，其余训练</li>
  <li>...重复 5 轮，每份都当过一次测试</li>
  <li>把 5 个测试指标平均，作为最终评估</li>
</ol>

<figure>%SVG_KFOLD%</figure>

<div class="note">
<span class="tag">好处</span>
<ul>
  <li>每个样本都被预测过 → 没有"幸运的切法"</li>
  <li>5 轮均值 ± 标准差能反映稳定性</li>
  <li>对 500 这种中小数据集尤其重要</li>
</ul>
</div>

<h3>本项目的 5-fold 标准差</h3>
<table>
<tr><th>模型</th><th>AUC 平均</th><th>AUC 标准差</th></tr>
<tr><td>LR</td><td>0.842</td><td>± 0.028</td></tr>
<tr><td>RF</td><td>0.878</td><td>± 0.042</td></tr>
<tr><td>XGBoost</td><td>0.854</td><td>± 0.051</td></tr>
</table>
<p>RF 的 AUC 在 5 折间从约 0.84 浮动到约 0.92，相对稳定。XGBoost 的标准差略大（0.051），说明对训练折比较敏感（500 样本不足以让它发挥得稳）。</p>

<div class="tldr">5-fold CV = 数据切 5 份，每份轮流当测试，5 个测试指标平均。让评估更稳定、避免单次切分的运气。</div>
""".replace("%SVG_KFOLD%", SVG_KFOLD)

# Results part
R1 = """
<h2 id="r1">结果 ① · 三模型主对比表（最重要的一张表）</h2>

<table>
<tr><th>模型</th><th>AUC</th><th>PR-AUC</th><th>F1</th><th>Precision</th><th>Recall</th><th>P@10</th><th>P@20</th></tr>
<tr><td>LR</td><td>0.842</td><td>0.571</td><td><b>0.605</b></td><td>0.516</td><td><b>0.742</b></td><td>0.60</td><td>0.75</td></tr>
<tr><td><b>RF</b></td><td><b>0.878</b></td><td><b>0.642</b></td><td>0.402</td><td><b>0.627</b></td><td>0.298</td><td><b>0.90</b></td><td>0.75</td></tr>
<tr><td>XGBoost</td><td>0.854</td><td>0.620</td><td>0.536</td><td>0.555</td><td>0.534</td><td>0.80</td><td><b>0.85</b></td></tr>
</table>

<h3>怎么读这张表</h3>
<ul>
  <li><b>排序能力（AUC, PR-AUC）：RF 最强</b>。RF 在两个指标上都是第一，说明它能把候选按"有多可能成为爆款"排得最准。</li>
  <li><b>分类质量（F1, Precision, Recall）：LR 高 Recall + RF 高 Precision</b>。这反映了两个模型不同的默认阈值行为。</li>
  <li><b>Top-N 推荐（P@10, P@20）：RF 在头部、XGBoost 在 P@20</b>。最强 Top-10 推荐选 RF，扩展到 Top-20 也行的话 XGBoost 更稳。</li>
</ul>

<h3>为什么 RF 的 F1 这么低（0.402）但 AUC 最高（0.878）？</h3>
<div class="note">
<p>这不是矛盾，是<b>阈值选择</b>问题。F1 用的是默认阈值 0.5，这个阈值对 RF 来说偏保守——它倾向于不轻易给 0.5+ 的高分。如果调阈值到 0.3，RF 的 Recall 会大幅上升、F1 也会上升。但本项目报的是默认阈值数字，所以呈现出"RF 排序很强但默认阈值下分类指标一般"的现象。</p>
<p><b>结论</b>：用 RF 做 ranking（推荐 Top-N）很合适；用 RF 做强制二分类时要重新调阈值。</p>
</div>

<div class="tldr">RF 排序最强（AUC 0.878 / P@10 0.90），LR 召回最强（Recall 0.742），XGBoost 最均衡。三个模型各有最优场景。</div>
"""

R2 = """
<h2 id="r2">结果 ② · 消融实验（哪些特征真有用？）</h2>

<h3>什么是消融实验</h3>
<p>消融（ablation）= "去掉一部分看效果差距"。我们不是去掉，而是反着做："只用基础特征 → 一点点加更多 → 看 AUC 怎么涨"。涨得多的那次说明加的特征有用，涨得少的说明加进去白搭。</p>

<h3>四组实验</h3>
<table>
<tr><th>组</th><th>包含</th><th>特征数</th><th>RF AUC</th><th>相比上一组提升</th></tr>
<tr><td>A</td><td>基础元信息（README + 协议 + 语言 + 组织标识）</td><td>12</td><td>0.7855</td><td>—</td></tr>
<tr><td>B</td><td>A + 早期活跃度（commits / contributors / issues / PRs）</td><td>16</td><td>0.8516</td><td><span class="tag good">+0.0661 ⭐ 最大跳跃</span></td></tr>
<tr><td>C</td><td>B + 作者信号（followers / public_repos）</td><td>18</td><td>0.8756</td><td><span class="tag good">+0.0240</span></td></tr>
<tr><td>D</td><td>C + 全部 TF-IDF（描述里的关键词）</td><td>38</td><td>0.8783</td><td><span class="tag warn">+0.0027 几乎为零</span></td></tr>
</table>

<h3>三个清晰结论</h3>
<ol>
  <li><b>早期活跃度贡献最大</b>：A → B 单次跳 +0.066。仅看基础信息时 RF AUC 才 0.79；加上 30 天 commit / issue / PR 之后立刻冲到 0.85。说明"项目活不活"比"项目长什么样"更重要。</li>
  <li><b>作者信号有用但边际递减</b>：B → C 提升 +0.024。大佬背书有效果，但远不能弥补"项目本身不活"的硬伤。</li>
  <li><b>TF-IDF 几乎无效</b>：C → D 提升只有 +0.0027。加 20 维文本特征几乎没动 AUC。<b>项目描述里堆砌 "LLM/Agent/AI" 关键词没用</b>。这是反直觉的发现。</li>
</ol>

<div class="note good">
<span class="tag">⭐ 给开源开发者的启示</span>
<p>真去 commit 代码、回应 issue、收 PR — 这些"行动信号"比写漂亮的描述、堆砌热词、追风口更能预测长期成功。"做了什么"远比"说了什么"重要。</p>
</div>

<div class="tldr">早期活跃度贡献 +0.066（最大），TF-IDF 关键词贡献 +0.003（几乎为零）。"做了什么"胜过"说了什么"。</div>
"""

R3 = """
<h2 id="r3">结果 ③ · 时间切分验证（time-split）</h2>

<h3>为什么 5-fold CV 还不够严格</h3>
<p>5-fold CV 是<b>随机</b>切分，意味着同一折里可能混着 5 月初创建的仓库和 6 月底创建的仓库。如果模型从"6 月的项目里"学到了"5 月项目的规律"，这其实是一种隐性<b>时间泄漏</b>——真实部署时不存在这种"看到未来"的便利。</p>

<h3>更严格的考核：按时间切</h3>
<ol>
  <li>把 500 个仓库按 <code>created_at</code> 排序</li>
  <li>前 80%（最早的 400 个）当训练集</li>
  <li>后 20%（最晚的 100 个）当测试集</li>
  <li>严格"用过去预测未来"</li>
</ol>
<p>切分点：2025-06-19。</p>

<h3>结果</h3>
<div class="metrics">
  <div class="metric"><div class="v">0.878</div><div class="k">Random CV AUC</div></div>
  <div class="metric"><div class="v">0.881</div><div class="k">Time-split AUC</div></div>
  <div class="metric green"><div class="v">+0.0025</div><div class="k">差距</div></div>
</div>
<p>差距只有 0.0025（千分之 2.5），几乎可以忽略。</p>

<div class="note good">
<span class="tag">关键结论</span>
<p>这说明<b>模型真的从早期信号里学到了规律</b>，没有偷偷依赖时间顺序的捷径。把它部署到新仓库上也会管用——至少在同一时间段内。</p>
</div>

<h3>对照：N=1500 实验里 time-split 暴跌</h3>
<p>顺带说一下我们做过的扩展实验：把数据扩到 1500（含 2025-01~02 和 2025-03~04 两个早期批次）。结果：</p>
<table>
<tr><th>规模</th><th>Random CV AUC</th><th>Time-split AUC</th><th>差距</th></tr>
<tr><td>N=500（单窗口）</td><td>0.878</td><td>0.881</td><td><span class="tag good">+0.0025</span></td></tr>
<tr><td>N=1500（跨窗口）</td><td>0.907</td><td>0.813</td><td><span class="tag bad">−0.094</span></td></tr>
</table>
<p>N=1500 时差距 9.4 个百分点——意味着 k-fold CV 在跨时间数据上<b>会显著高估</b>真实泛化能力。这是个有方法论价值的发现：很多 ML 论文只报 k-fold 数字，可能都偏乐观。</p>

<div class="tldr">N=500 时 time-split AUC ≈ random CV → 模型可信。N=1500 跨时间窗口时 time-split 暴跌 0.094 → 警示 k-fold 在跨时数据上会骗你。</div>
"""

R4 = """
<h2 id="r4">结果 ④ · 分语言 AUC</h2>

<h3>把测试集按语言切开看 AUC</h3>
<table>
<tr><th>语言</th><th>样本数</th><th>正例数</th><th>AUC</th><th>解读</th></tr>
<tr><td><b>Python</b></td><td>100</td><td>53</td><td><b>0.565 ⚠</b></td><td>异常低</td></tr>
<tr><td>Go</td><td>118</td><td>25</td><td>0.890</td><td>最好</td></tr>
<tr><td>Rust</td><td>151</td><td>17</td><td>0.853</td><td>很好</td></tr>
<tr><td>JavaScript</td><td>100</td><td>5</td><td>0.800 ± 0.37</td><td>高方差（样本少）</td></tr>
<tr><td>TypeScript</td><td>31</td><td>1</td><td>样本不足</td><td>结论无效</td></tr>
</table>

<h3>Python AUC = 0.565 是怎么回事</h3>
<p>注意 Python 的<b>正例率 53%</b>——其他语言只有 ~20%。Python 在分层 Top-20% 设计下应该也是 20% 正例，怎么变成 53%？</p>

<div class="note warn">
<span class="tag">原因解释</span>
<p>分层逻辑是 "<b>同 batch</b> 内 p80"，所以 Python 子集占整个数据集的 100/500 = 20%。但因为 AI 热潮，<b>整个数据集的 Top 20%（也就是 stars 最高的 100 个）大部分都是 Python 项目</b>。所以 Python 子集里有 53% 是 Top 20%，远高于其他语言。</p>
<p>这意味着 Python 类内"成功项目"和"普通项目"之间的差异变小了——它们都"长得像 AI 爆款"。模型学不到能区分它们的特征，AUC 接近瞎猜（0.5）。</p>
</div>

<div class="note good">
<span class="tag">⭐ 启示</span>
<p>"热门红海赛道"反而最难预测谁会火。Go / Rust 这种相对垂直的语言，成功项目和不成功项目特征差异大、更容易建模。如果你想做差异化竞争，垂直冷门领域可能比追风口更有研究价值。</p>
</div>

<div class="tldr">Python AUC 仅 0.565（接近瞎猜），因为 AI 热潮让 Python 项目"个个看起来像爆款"，类内差异小。Go/Rust AUC 都在 0.85+，是更适合建模的赛道。</div>
"""

R5 = """
<h2 id="r5">结果 ⑤ · 特征重要性（Gini vs SHAP）</h2>

<h3>"特征重要性"有两种主流算法</h3>
<p>它们衡量的不是同一件事，所以结果常常<b>不一致</b>。这是正常的，理解每种方法的含义比追求"哪个对"更重要。</p>

<h3>方法 1 · RF Gini 重要性</h3>
<p>每次决策树分裂时，会让"不纯度（Gini）"下降一些。把所有树中所有节点用到某特征带来的"Gini 下降"加起来，归一化，就是该特征的 Gini 重要性。</p>

<table>
<tr><th>排名</th><th>特征</th><th>Gini 重要性</th></tr>
<tr><td>1</td><td><code>readme_len</code></td><td><b>0.283</b></td></tr>
<tr><td>2</td><td><code>author_public_repos</code></td><td>0.103</td></tr>
<tr><td>3</td><td><code>commits_30d</code></td><td>0.093</td></tr>
<tr><td>4</td><td><code>author_followers</code></td><td>0.063</td></tr>
<tr><td>5</td><td><code>tfidf_machine learning</code></td><td>0.059</td></tr>
</table>
<p>readme_len 是第二名的 2.7 倍——遥遥领先。</p>

<h3>方法 2 · SHAP（Shapley Additive exPlanations）</h3>
<p>SHAP 来自博弈论，问的是：<b>"在每个具体样本的预测中，每个特征贡献了多少分？"</b> 计算方式：考虑所有可能的特征组合，看加入某特征后预测的平均变化。复杂得多，但更"诚实"。</p>

<table>
<tr><th>排名</th><th>特征</th><th>mean &#124;SHAP&#124;</th></tr>
<tr><td>1</td><td><code>lang_Python</code></td><td><b>0.072</b></td></tr>
<tr><td>2</td><td><code>contributors</code></td><td>0.054</td></tr>
<tr><td>3</td><td><code>author_followers</code></td><td>0.053</td></tr>
<tr><td>4</td><td><code>readme_len</code></td><td>0.047</td></tr>
<tr><td>5</td><td><code>readme_has_image</code></td><td>0.031</td></tr>
</table>

<h3>两者为什么不一致</h3>
<ul>
  <li><b>Gini 偏向高基数连续特征</b>：readme_len 取值范围从 0 到 30000+，决策树有更多机会用它做切分点，Gini 累计就高。</li>
  <li><b>SHAP 看的是边际贡献</b>：lang_Python 是个 0/1 的二值特征，但因为"Python" 整个亚群表现独特（见 §结果 ④），它对单样本预测的影响很大。</li>
</ul>

<div class="note">
<span class="tag">怎么用</span>
<ul>
  <li>想知道"模型整体最依赖谁" → 看 Gini</li>
  <li>想知道"为什么这个样本被预测为 0.8" → 看 SHAP</li>
  <li>两者结合看，比单一指标更稳</li>
</ul>
</div>

<div class="tldr">Gini 衡量分裂贡献（偏向连续高基数特征），SHAP 衡量边际贡献（更公平）。本项目两种方法都把 readme_len、commits、author 三类放在前列，但精确排名不同——这是方法差异，不是矛盾。</div>
"""

R6 = """
<h2 id="r6">结果 ⑥ · Top-10 推荐验证（最有可视化效果的结果）</h2>

<h3>用 OOF（Out-Of-Fold）预测筛 Top-10</h3>
<p>5-fold CV 跑完后，每个样本都有一次"被没见过它的模型预测的概率"。把所有 500 个样本按概率降序排，取前 10 个 → 这就是"模型最看好的 10 个项目"。</p>

<h3>实际榜单</h3>
<table>
<tr><th>排名</th><th>仓库</th><th>语言</th><th>预测概率</th><th>当前 star</th><th>真的 Top 20%?</th></tr>
<tr><td>#1</td><td>strands-agents/agent-builder</td><td>Python</td><td>0.945</td><td>414</td><td>✅</td></tr>
<tr><td>#2</td><td>strands-agents/sdk-python</td><td>Python</td><td>0.900</td><td>5,877</td><td>✅</td></tr>
<tr><td>#3</td><td>strands-agents/tools</td><td>Python</td><td>0.815</td><td>1,057</td><td>✅</td></tr>
<tr><td>#4</td><td>Thinklab-SJTU/ML4CO-Bench-101</td><td>Python</td><td>0.790</td><td>46</td><td>❌（False Positive）</td></tr>
<tr><td>#5</td><td>strands-agents/mcp-server</td><td>Python</td><td>0.780</td><td>282</td><td>✅</td></tr>
<tr><td>#6</td><td>memvid/memvid</td><td>Rust</td><td>0.775</td><td><b>15,529</b></td><td>✅</td></tr>
<tr><td>#7</td><td>strands-agents/samples</td><td>Python</td><td>0.760</td><td>758</td><td>✅</td></tr>
<tr><td>#8</td><td>Dogiye12/Agricultural-Yield-Forecasting</td><td>Python</td><td>0.725</td><td>58</td><td>✅</td></tr>
<tr><td>#9</td><td>llm-d/llm-d-router</td><td>Go</td><td>0.700</td><td>193</td><td>✅</td></tr>
<tr><td>#10</td><td>TimeCopilot/timecopilot</td><td>Python</td><td>0.695</td><td>472</td><td>✅</td></tr>
</table>

<p><b>9 / 10 命中</b> → P@10 = 0.90</p>

<h3>两个最有意思的样本</h3>
<div class="note good">
<span class="tag">🏆 memvid/memvid (#6, 15,529 stars)</span>
<p>模型只看到它前 30 天的数据就给出 0.775 的高分。一年后它真的成了 Top 20% 的爆款。这是模型"从早期信号识别后来真爆款"的最有说服力案例。</p>
</div>

<div class="note warn">
<span class="tag">❌ Thinklab-SJTU/ML4CO-Bench-101 (#4, 46 stars · False Positive)</span>
<p>表面信号都很强：README 长（12,617 字符）、commits_30d=33、author 是名校组织（834 followers）。但 contributors 只有 2 个、外部 issue 数 = 0、PR 数 = 1 — 是"一个人闷头写"的项目。模型被表面活跃度骗了，没看穿"独角戏"。这正是 Precision 不会等于 100% 的原因。</p>
</div>

<div class="tldr">前 10 个模型最看好的仓库里有 9 个真的成功了（P@10 = 0.90）。memvid 是最好的命中案例；ML4CO 是 false positive。</div>
"""

R7 = """
<h2 id="r7">结果 ⑦ · Today Radar 动态阈值</h2>

<h3>背景：把模型应用到"今天的新仓库"</h3>
<p>训练完模型，复用到最近 30-45 天前创建的新仓库（保证它们有完整 30 天观察窗），给每个新仓库打一个 attention_score（注意力分数）。然后给打分一个"动作"标签：</p>
<ul>
  <li><code>deep_dive</code>（深入研究）：分数最高的一档</li>
  <li><code>try</code>（试用）：值得关注</li>
  <li><code>watch</code>（观察）：可以加入观察列表</li>
  <li><code>ignore</code>（忽略）：不用看</li>
</ul>

<h3>原版本：魔法数字</h3>
<p>之前阈值是 0.75 / 0.60 / 0.40 三个数字——没有数据依据，纯拍脑袋。</p>

<h3>新版本：基于训练集分布</h3>
<p>训练完 RF 后，让它对全部 500 个训练样本输出预测概率，取这些概率的 p80 / p60 / p40 三个分位数作为阈值：</p>

<table>
<tr><th>动作</th><th>阈值</th><th>含义</th></tr>
<tr><td><code>deep_dive</code></td><td>≥ 0.597 (= p80)</td><td>新样本得分 ≥ 训练集前 20% → 强力推荐</td></tr>
<tr><td><code>try</code></td><td>0.070 – 0.597 (p60–p80)</td><td>得分高于训练集中位数附近 → 值得试</td></tr>
<tr><td><code>watch</code></td><td>0.030 – 0.070 (p40–p60)</td><td>得分中等偏下 → 加观察列表</td></tr>
<tr><td><code>ignore</code></td><td>&lt; 0.030 (= p40)</td><td>得分低于训练集 40% → 不用看</td></tr>
</table>

<h3>为什么这样更靠谱</h3>
<ul>
  <li><b>有数据依据</b>：每个阈值都对应训练集分布的一个百分位</li>
  <li><b>"deep_dive" 的语义清晰</b>：等价于"这个新仓库的分数和训练集里真正成功的 Top 20% 一样高"</li>
  <li><b>抗模型漂移</b>：未来如果重新训练模型（用不同数据），阈值会自动跟着变，不需要手动重新拍数字</li>
</ul>

<h3>当前 Today Radar 输出（offline 测试）</h3>
<table>
<tr><th>排名</th><th>仓库</th><th>语言</th><th>分数</th><th>动作</th></tr>
<tr><td>#1</td><td>run-llama/ParseBench</td><td>Python</td><td>0.795</td><td><span class="tag good">deep_dive</span></td></tr>
<tr><td>#2</td><td>SeanFDZ/macmind</td><td>Python</td><td>0.355</td><td><span class="tag blue">try</span></td></tr>
<tr><td>#3</td><td>gryszzz/OpenThymos</td><td>Rust</td><td>0.315</td><td><span class="tag blue">try</span></td></tr>
<tr><td>#4</td><td>dmriding/kaio</td><td>Rust</td><td>0.300</td><td><span class="tag blue">try</span></td></tr>
<tr><td>#5</td><td>Suraj-G-Rao/My-Portfolio</td><td>JavaScript</td><td>0.215</td><td><span class="tag blue">try</span></td></tr>
</table>

<div class="note warn">
<span class="tag">⚠️ 重要声明</span>
<p>Today Radar 是<b>候选清单 (candidate shortlist)</b>，不是已验证的未来预测。这些仓库才存活 30-45 天，真正的"是否进入 Top 20%"标签要 1 年后才能算。</p>
<p>正确的验证方式：保存今天的候选名单 → 1 年后回来看这 5 个仓库实际 star 增长 → 与模型预测对比。这是论文的"未来工作"之一。</p>
</div>

<div class="tldr">Today Radar 动作阈值 = 训练集预测概率的 p80/p60/p40 分位数（0.597 / 0.070 / 0.030），不是魔法数字。语义清晰：deep_dive 等价于"得分和训练集 Top 20% 一样高"。</div>
"""

FOOT = """
<hr style="border:none;border-top:1px solid var(--line); margin:60px 0 24px">
<p class="muted" style="text-align:center; font-size:14px;">
基于 OpenClaw Multi-Agent 的开源项目潜力发现系统 · 三模型 + 实验结果概念精讲<br>
数据来源 <code>data/model_results.json</code> + <code>data/diagnostic_summary.json</code> + <code>data/model_artifacts/model_schema.json</code>
</p>
</div>
</body>
</html>
"""

html = (
    HEAD.replace("%CSS%", CSS)
    + HERO + TOC
    + M1 + M2 + M3 + M4
    + E1 + E2 + E3 + E4 + E5 + E6
    + R1 + R2 + R3 + R4 + R5 + R6 + R7
    + FOOT
)

OUT.write_text(html, encoding="utf-8")
print(f"Written: {OUT}  ({OUT.stat().st_size:,} bytes)")
