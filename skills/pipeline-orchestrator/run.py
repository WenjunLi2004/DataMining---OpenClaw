#!/usr/bin/env python3
"""
pipeline-orchestrator skill entry point.

Reads the DeepSeek API key from ~/.openclaw/openclaw.json (fallback: env),
then invokes ~/openclaw-project/agents/orchestrator.py which runs the full
ML pipeline via DeepSeek Tool Use:
  JSONL → feature-extractor → model-trainer → report-generator → HTML report
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


ORCHESTRATOR = Path.home() / "openclaw-project/agents/orchestrator.py"
PROJECT_DIR = Path.home() / "openclaw-project"
OPENCLAW_CFG = Path.home() / ".openclaw/openclaw.json"
DEFAULT_DASHBOARD_PORT = 8080


def _api_key_from_config() -> Optional[str]:
    """Extract DeepSeek API key from openclaw.json providers block."""
    try:
        cfg = json.loads(OPENCLAW_CFG.read_text())
        providers = cfg.get("models", {}).get("providers", {})
        return providers.get("deepseek", {}).get("apiKey")
    except Exception:
        return None


def resolve_api_key(required: bool = True) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY") or _api_key_from_config()
    if required and not key:
        print(
            "[pipeline-orchestrator] ERROR: No DEEPSEEK_API_KEY found.\n"
            "  Set via: export DEEPSEEK_API_KEY=sk-...\n"
            "  Or configure it in ~/.openclaw/openclaw.json → models.providers.deepseek.apiKey",
            flush=True,
        )
        sys.exit(1)
    if not key:
        print(
            "[pipeline-orchestrator] No DEEPSEEK_API_KEY found; deterministic force mode "
            "will use template-based insight analysis.",
            flush=True,
        )
    return key


def _url_ok(url: str, timeout: float = 0.8) -> bool:
    result = subprocess.run(
        ["curl", "-fsS", "--max-time", str(timeout), url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def ensure_dashboard(port: int = DEFAULT_DASHBOARD_PORT, open_browser: bool = True) -> str:
    """Start the local OpenClaw Console server if needed, then optionally open it."""
    url = f"http://127.0.0.1:{port}/dashboard/"
    public_url = f"http://localhost:{port}/dashboard/"

    if _url_ok(url):
        print(f"[pipeline-orchestrator] Dashboard already running: {public_url}", flush=True)
    else:
        log_path = Path("/tmp/openclaw-dashboard.log")
        pid_path = PROJECT_DIR / "data/dashboard_server.pid"
        log = open(log_path, "a", encoding="utf-8")
        proc = subprocess.Popen(
            ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1"],
            cwd=PROJECT_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pid_path.write_text(str(proc.pid), encoding="utf-8")

        for _ in range(20):
            if _url_ok(url, timeout=0.3):
                break
            time.sleep(0.1)

        if _url_ok(url):
            print(
                f"[pipeline-orchestrator] Dashboard started: {public_url} "
                f"(pid={proc.pid}, log={log_path})",
                flush=True,
            )
        else:
            print(
                f"[pipeline-orchestrator] WARN: Dashboard server did not respond on :{port}; "
                f"check {log_path}",
                flush=True,
            )

    if open_browser:
        try:
            subprocess.run(["open", public_url], timeout=5)
            print(f"[pipeline-orchestrator] Opened Console: {public_url}", flush=True)
        except Exception as exc:
            print(f"[pipeline-orchestrator] WARN: could not open browser: {exc}", flush=True)
    return public_url


def main():
    parser = argparse.ArgumentParser(description="pipeline-orchestrator skill runner")
    parser.add_argument(
        "message",
        nargs="?",
        default="开始分析",
        help="Message to pass to orchestrator (default: 开始分析)",
    )
    parser.add_argument("--no-dashboard", action="store_true",
                        help="Do not auto-start the OpenClaw Console server")
    parser.add_argument("--no-open-dashboard", action="store_true",
                        help="Start dashboard server but do not open the browser")
    parser.add_argument("--dashboard-port", type=int, default=DEFAULT_DASHBOARD_PORT,
                        help="Dashboard HTTP port (default: 8080)")
    parser.add_argument("--force-local", action="store_true",
                        help="Force feature/model/diagnostic/insight/report recomputation without recollecting GitHub raw data")
    parser.add_argument("--force-full", action="store_true",
                        help=("Force the full chain INCLUDING GitHub recollection. "
                              "By default the canonical data/repos_raw_500_strict.jsonl is preserved and the new "
                              "snapshot lands in data/repos_raw_500_strict_force_<timestamp>.jsonl. "
                              "Pass --force-full-overwrite to actually overwrite the canonical snapshot."))
    parser.add_argument("--force-full-overwrite", action="store_true",
                        help="Only meaningful with --force-full: overwrite the canonical historical snapshot "
                             "(reproducibility of past course experiments will be broken).")
    args = parser.parse_args()

    if not ORCHESTRATOR.exists():
        print(f"[pipeline-orchestrator] ERROR: Orchestrator not found: {ORCHESTRATOR}", flush=True)
        sys.exit(1)

    deterministic_force = args.force_local or args.force_full
    api_key = resolve_api_key(required=not deterministic_force)
    if not args.no_dashboard:
        ensure_dashboard(args.dashboard_port, open_browser=not args.no_open_dashboard)

    print(f"[pipeline-orchestrator] Launching ML pipeline: {args.message!r}", flush=True)
    print(f"[pipeline-orchestrator] Orchestrator: {ORCHESTRATOR}", flush=True)
    print("", flush=True)

    env = {**os.environ}
    if api_key:
        env["DEEPSEEK_API_KEY"] = api_key
    if args.force_full:
        env["OPENCLAW_FORCE_FULL"] = "1"
        if args.force_full_overwrite:
            env["OPENCLAW_FORCE_FULL_OVERWRITE"] = "1"
            print(
                "[pipeline-orchestrator] ⚠️  --force-full-overwrite ENABLED. "
                "The canonical data/repos_raw_500_strict.jsonl will be overwritten. "
                "This is NOT recommended for project demonstrations.",
                flush=True,
            )
        else:
            print(
                "[pipeline-orchestrator] --force-full will recollect to a sibling file "
                "(data/repos_raw_500_strict_force_<timestamp>.jsonl). Canonical snapshot preserved.",
                flush=True,
            )
    elif args.force_local:
        env["OPENCLAW_FORCE_LOCAL"] = "1"
    elif args.force_full_overwrite:
        print(
            "[pipeline-orchestrator] WARN: --force-full-overwrite has no effect without --force-full",
            flush=True,
        )
    result = subprocess.run(
        ["python3", str(ORCHESTRATOR), args.message],
        env=env,
        timeout=600,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
