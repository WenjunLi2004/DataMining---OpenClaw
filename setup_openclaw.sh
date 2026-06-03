#!/usr/bin/env bash
# =====================================================================
# OpenClaw · 系统环境搭建脚本 / environment setup
#
# 把仓库里的 skills/ 同步到 ~/.openclaw/workspace/skills/，
# 让 pipeline-orchestrator 和各独立技能脚本能通过默认路径找到它们。
#
# 用法：
#   bash setup_openclaw.sh
#
# 执行完后：
#   bash reproduce.sh              → 最简离线复现（特征+模型+事实诊断）
#   python3 ~/.openclaw/workspace/skills/pipeline-orchestrator/run.py --force-local "开始分析"
#                                  → 完整系统复现（含洞察分析 + HTML 报告 + Console）
# =====================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.openclaw/workspace/skills"

echo "▶ 项目根目录: $ROOT"
echo "▶ 安装目标:   $DEST"
echo

# 1) 确保目标父目录存在
mkdir -p "$HOME/.openclaw/workspace"

# 2) 同步 skills/ 到 ~/.openclaw/workspace/skills/
#    --delete 会移除目标中多余的文件（保持和仓库一致）
if command -v rsync &>/dev/null; then
  rsync -a --exclude='__pycache__' --exclude='*.pyc' "$ROOT/skills/" "$DEST/"
  echo "✓ rsync 同步完成: $DEST"
else
  # 回退到 cp（macOS 自带）
  cp -R "$ROOT/skills/." "$DEST/"
  echo "✓ cp 同步完成: $DEST"
fi
echo

# 3) 如果仓库不在 ~/openclaw-project，提示编排器路径问题
if [ "$ROOT" != "$HOME/openclaw-project" ]; then
  echo "⚠  警告：仓库位于 $ROOT，而编排器默认读写 ~/openclaw-project。"
  echo "   建议把仓库克隆到 ~/openclaw-project，否则 pipeline-orchestrator 会找不到数据文件。"
  echo "   （最简复现 bash reproduce.sh 不受影响，它用相对路径。）"
  echo
fi

# 4) 确认安装结果
echo "已安装的技能："
ls -1 "$DEST/"
echo
echo "接下来可以运行："
echo "  bash reproduce.sh"
echo "    → 最简离线复现（不需要 API key，不联网）"
echo ""
echo "  export DEEPSEEK_API_KEY=sk-...  # 可选；不设会回退确定性模板"
echo "  python3 $DEST/pipeline-orchestrator/run.py --force-local '开始分析'"
echo "    → 完整系统复现（含洞察分析 + HTML 报告 + Console）"
echo ""
echo "  cd ~/openclaw-project && python3 -m http.server 8080 --bind 127.0.0.1"
echo "    → 启动 OpenClaw Console → http://127.0.0.1:8080/dashboard/"
