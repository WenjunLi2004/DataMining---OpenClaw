#!/bin/bash
# OpenClaw Console — one-click launcher
set -e
cd "$(dirname "$0")"   # always run from project root

PORT=8080

echo "🦞 OpenClaw 控制台"
echo "──────────────────────────────"

# Kill any existing server on this port
if lsof -ti:$PORT &>/dev/null; then
  echo "停止已有的 :$PORT 服务..."
  lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
  sleep 0.5
fi

# Start Python HTTP server in background
python3 -m http.server $PORT --bind 127.0.0.1 &>/tmp/openclaw-dashboard.log &
SERVER_PID=$!
echo "HTTP 服务已启动 (PID: $SERVER_PID) → http://localhost:$PORT"
sleep 0.8

# Verify server is up
if ! curl -s http://localhost:$PORT/ &>/dev/null; then
  echo "⚠️  服务可能尚未就绪，请检查 /tmp/openclaw-dashboard.log"
fi

# Open browser
echo ""
echo "正在打开 OpenClaw 控制台..."
open "http://localhost:$PORT/dashboard/"

echo ""
echo "控制台:    http://localhost:$PORT/dashboard/"
echo "别名入口:  http://localhost:$PORT/reports.html"
echo "事件数据:  http://localhost:$PORT/data/pipeline_status.jsonl"
echo "服务日志:  /tmp/openclaw-dashboard.log"
echo ""
echo "触发普通分析:"
echo "  openclaw agent --agent pipeline-orchestrator --local --message '开始分析'"
echo "触发今日雷达:"
echo "  openclaw agent --agent pipeline-orchestrator --local --message '今日雷达'"
echo "强制重算本地分析链路:"
echo "  python3 ~/.openclaw/workspace/skills/pipeline-orchestrator/run.py --force-local '开始分析'"
echo ""
echo "按 Ctrl+C 停止服务。"
echo ""

# Trap Ctrl+C to kill server cleanly
trap "echo ''; echo '正在停止服务...'; kill $SERVER_PID 2>/dev/null; exit 0" INT TERM

# Keep script alive (server runs in background)
wait $SERVER_PID
