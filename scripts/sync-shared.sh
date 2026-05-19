#!/usr/bin/env bash
# Sync the canonical _shared.py across every skill's scripts/ folder.
#
# Each skill vendors its own copy of _shared.py so that the skill works
# standalone when installed via `npx skills add psyduckler/aeo-skills --skill X`.
# This script keeps them all in sync.
#
# Usage:
#   ./scripts/sync-shared.sh                    # use first found _shared.py as source
#   ./scripts/sync-shared.sh path/to/source.py  # use specific source
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $# -ge 1 ]]; then
  SOURCE="$1"
else
  # Use the first _shared.py we find as the canonical
  SOURCE="$(find . -path './*/scripts/_shared.py' | head -n1)"
fi

if [[ ! -f "$SOURCE" ]]; then
  echo "Error: source $SOURCE not found" >&2
  exit 1
fi

echo "Source: $SOURCE"
count=0
for target in */scripts/_shared.py; do
  if [[ "$(realpath "$target")" != "$(realpath "$SOURCE")" ]]; then
    cp "$SOURCE" "$target"
    echo "  → $target"
    count=$((count + 1))
  fi
done
echo "Synced $count file(s)."
