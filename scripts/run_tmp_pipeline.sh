#!/usr/bin/env bash
# =====================================================================
# OpenClaw · 临时完整本地重跑
#
# 跳过 GitHub 数据采集，固定使用 data/repos_raw_500_strict.jsonl，
# 强制重算后续步骤：
#   特征工程 → 模型训练 → 事实诊断 → 洞察分析 → 错误分析 → 报告生成
#
# 默认输出到 ./tmp/pipeline_latest/，每次运行会先清空该目录。
# 这不会修改正式 data/ 和 reports/ 产物。
#
# 用法：
#   bash scripts/run_tmp_pipeline.sh
#   bash scripts/run_tmp_pipeline.sh tmp/my_experiment
# =====================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
OUT="${1:-$ROOT/tmp/pipeline_latest}"
RAW="$ROOT/data/repos_raw_500_strict.jsonl"
ARTIFACTS="$OUT/model_artifacts"
REPORTS="$OUT/reports"

if [[ ! -f "$RAW" ]]; then
  echo "[ERROR] strict raw data not found: $RAW" >&2
  exit 1
fi

echo "▶ OpenClaw tmp pipeline"
echo "  root: $ROOT"
echo "  raw:  $RAW"
echo "  out:  $OUT"
echo

echo "［reset］清空临时输出目录"
rm -rf "$OUT"
mkdir -p "$ARTIFACTS" "$REPORTS"

echo
echo "［1/6］特征工程"
python3 "$ROOT/skills/feature-extractor/extract.py" \
  --input "$RAW" \
  --output "$OUT/features.csv" \
  --artifacts-dir "$ARTIFACTS"

echo
echo "［2/6］模型训练"
python3 "$ROOT/skills/model-trainer/train.py" \
  --input "$OUT/features.csv" \
  --output "$OUT/model_results.json" \
  --artifacts-dir "$ARTIFACTS"

echo
echo "［3/6］事实诊断"
python3 "$ROOT/skills/diagnostic-builder/diagnose.py" \
  --results "$OUT/model_results.json" \
  --features "$OUT/features.csv" \
  --output "$OUT/diagnostic_summary.json"

echo
echo "［4/6］洞察分析（template，避免依赖 API key）"
python3 "$ROOT/skills/insight-analysis/analyze.py" \
  --diagnostic "$OUT/diagnostic_summary.json" \
  --output "$REPORTS/INSIGHTS.md" \
  --mode template

echo
echo "［5/6］错误案例分析"
python3 "$ROOT/skills/error-analyst/analyze.py" \
  --features "$OUT/features.csv" \
  --results  "$OUT/model_results.json" \
  --out-json "$OUT/error_analysis.json" \
  --out-html "$REPORTS/error_analysis.html"

echo
echo "［6/6］报告生成"
python3 "$ROOT/skills/report-generator/generate.py" \
  --results "$OUT/model_results.json" \
  --features "$OUT/features.csv" \
  --diagnostic "$OUT/diagnostic_summary.json" \
  --out-dir "$REPORTS" \
  --out-file tmp_final.html

echo
echo "✅ tmp pipeline complete"
echo "  features:       $OUT/features.csv"
echo "  results:        $OUT/model_results.json"
echo "  diagnostic:     $OUT/diagnostic_summary.json"
echo "  insights:       $REPORTS/INSIGHTS.md"
echo "  error_analysis: $REPORTS/error_analysis.html"
echo "  report:         $REPORTS/latest_final.html"
