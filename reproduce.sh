#!/usr/bin/env bash
# =====================================================================
# OpenClaw · 一键复现脚本 / one-command reproduction
#
# 从固定历史快照 data/repos_raw_500_strict.jsonl 重新生成
#   特征 → 模型指标 → 事实诊断
# 并和仓库里已提交的 data/model_results.json 对比，确认数字一致。
#
# 输出写到 ./repro/（已被 .gitignore 忽略），不会改动已提交文件。
# 可在任意克隆位置运行（不依赖 ~/openclaw-project）。
#
#   用法:  bash reproduce.sh
# =====================================================================
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
OUT="$ROOT/repro"
mkdir -p "$OUT/artifacts"

echo "▶ 项目根目录: $ROOT"
echo "▶ 输出目录:   $OUT  (临时, 不进 git)"
echo

echo "［1/3］特征工程  feature-extractor  (固定 strict 快照 → 19 个特征)"
python3 skills/feature-extractor/extract.py \
  --input  "$ROOT/data/repos_raw_500_strict.jsonl" \
  --output "$OUT/features.csv" \
  --artifacts-dir "$OUT/artifacts"
echo

echo "［2/3］模型训练  model-trainer  (LR / RF / XGBoost · 5 折交叉验证)"
python3 skills/model-trainer/train.py \
  --input  "$OUT/features.csv" \
  --output "$OUT/model_results.json" \
  --artifacts-dir "$OUT/artifacts" >/dev/null
echo "      done."
echo

echo "［3/3］事实诊断  diagnostic-builder  (baseline / ablation / anomaly)"
python3 skills/diagnostic-builder/diagnose.py \
  --results  "$OUT/model_results.json" \
  --features "$OUT/features.csv" \
  --output   "$OUT/diagnostic_summary.json" >/dev/null
echo "      done."
echo

echo "═══ 复现结果 vs 仓库已提交结果 ═══"
python3 - "$OUT/model_results.json" "$ROOT/data/model_results.json" <<'PY'
import json, sys
new = json.load(open(sys.argv[1]))
ref = json.load(open(sys.argv[2]))
def m(d, model, k):
    v = d["models"][model][k]
    return v["mean"] if isinstance(v, dict) else v
print(f"  {'metric':14}{'committed':>11}{'reproduced':>12}   match")
ok = True
for model in ("LR", "RF", "XGBoost"):
    for k in ("auc", "pr_auc"):
        a, b = m(ref, model, k), m(new, model, k)
        good = abs(a - b) < 2e-3
        ok = ok and good
        print(f"  {model+'.'+k:14}{a:>11.4f}{b:>12.4f}   {'✓' if good else '✗ DIFF'}")
print()
print("  → 期望: LR AUC≈0.883 · RF PR-AUC≈0.662 · P@10≈0.80 · 时间切分 gap≈+0.0004")
print("  ✅ 复现成功，数字与仓库一致。" if ok else "  ⚠️ 出现偏差，请检查依赖版本 / Python 环境。")
PY

echo
echo "（可选）洞察 + 报告:"
echo "  export DEEPSEEK_API_KEY=sk-...   # 不设也行，会回退到确定性模板"
echo "  python3 skills/insight-analysis/analyze.py"
echo "  python3 skills/report-generator/generate.py"
echo "提示: 完整链路的洞察/报告步骤默认读写 ~/openclaw-project/，"
echo "      因此跑完整 orchestrator 时建议把仓库克隆到 ~/openclaw-project。"
