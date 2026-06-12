#!/usr/bin/env bash
# Regenerate stories_data.js for index.html.
# Run: ./build_index.sh   (do not use python3 on this file)
# Or:  python3 build_index.py
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
BOOKSTORIES="$(cd "$ROOT/../bookstories" && pwd)"

if [[ ! -f "$BOOKSTORIES/scripts/build_index.py" ]]; then
  echo "error: expected $BOOKSTORIES/scripts/build_index.py" >&2
  echo "Clone bookstories next to openscienceworks, or set BOOKSTORIES to its path." >&2
  exit 1
fi

export OSW_DIR="$ROOT"
exec python3 "$BOOKSTORIES/scripts/build_index.py" "$@"
