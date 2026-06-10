#!/usr/bin/env zsh
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="${1:-$ROOT/reports/Presentation.pptx}"
BACKUP_DIR="${2:-$ROOT/autosave_backups/Presentation}"
INTERVAL="${AUTOSAVE_INTERVAL_SECONDS:-15}"
base_name="$(basename "$SOURCE" .pptx)"

mkdir -p "$BACKUP_DIR"

last_sig=""

while true; do
  if [[ -f "$SOURCE" ]]; then
    sig="$(stat -f '%m:%z' "$SOURCE" 2>/dev/null || true)"
    if [[ -n "$sig" && "$sig" != "$last_sig" ]]; then
      stamp="$(date '+%Y%m%d_%H%M%S')"
      cp -p "$SOURCE" "$BACKUP_DIR/${base_name}_$stamp.pptx"
      last_sig="$sig"
      find "$BACKUP_DIR" -name "${base_name}_*.pptx" -type f -mtime +7 -delete
      printf '[%s] backed up %s\n' "$(date '+%F %T')" "$SOURCE"
    fi
  fi
  sleep "$INTERVAL"
done
