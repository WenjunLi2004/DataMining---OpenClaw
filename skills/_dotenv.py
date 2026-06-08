"""
Minimal .env loader for OpenClaw skills.
Searches for .env in the project root (walks up from the calling script).
Does NOT override variables already set in the environment.
"""
import os
from pathlib import Path


def load_dotenv(start: Path | None = None) -> Path | None:
    """Load .env file into os.environ (non-overriding).

    Returns the Path of the loaded file, or None if not found.
    """
    search_dirs = []
    if start:
        search_dirs.append(start)
        search_dirs.extend(start.parents)
    # Also try the repo root relative to this file
    search_dirs.append(Path(__file__).parent.parent)

    for d in search_dirs:
        env_file = d / ".env"
        if env_file.is_file():
            _parse(env_file)
            return env_file
    return None


def _parse(path: Path) -> None:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
