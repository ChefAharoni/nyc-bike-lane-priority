#!/usr/bin/env bash
# Build the site and bundle the data next to it.
# Usage: scripts/assemble_site.sh <latest_dir> <snapshots_dir>
#   <latest_dir>     the data contract output (meta.json, areas.json, ..., *.pmtiles, crashes/)
#   <snapshots_dir>  snapshots/ (index.json and dated .json.gz folders)
# Optional: SITE_BUILD_ARGS="--mode test" passes extra flags to the site build (the e2e run uses it to expose window.__map).
# Result: site/dist with data/ and data/snapshots/ inside it. Exit 1 on a missing input or a branding hit.
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: $0 <latest_dir> <snapshots_dir>" >&2
  exit 2
fi
ROOT=$(git rev-parse --show-toplevel)
LATEST=$(cd "$1" && pwd)
SNAPS=$(cd "$2" && pwd)

[ -f "$LATEST/meta.json" ] || { echo "missing $LATEST/meta.json" >&2; exit 1; }
[ -f "$SNAPS/index.json" ] || { echo "missing $SNAPS/index.json" >&2; exit 1; }

cd "$ROOT/site"
npm ci
npm run build -- ${SITE_BUILD_ARGS:-}

DIST="$ROOT/site/dist"
rm -rf "$DIST/data"
mkdir -p "$DIST/data/snapshots"
# Everything except a snapshots/ folder that may sit inside the latest dir.
for f in "$LATEST"/*; do
  [ "$(basename "$f")" = "snapshots" ] && continue
  cp -R "$f" "$DIST/data/"
done
cp -R "$SNAPS"/. "$DIST/data/snapshots/"

cd "$ROOT"
scripts/check_branding.sh site/dist
echo "assembled site/dist ($(du -sh site/dist | cut -f1))"
