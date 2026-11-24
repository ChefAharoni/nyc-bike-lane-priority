#!/usr/bin/env bash
# Builds the three fixture .pmtiles from the GeoJSON sources in site/fixtures/src (needs tippecanoe).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/site/fixtures"

command -v tippecanoe >/dev/null || { echo "tippecanoe not found (brew install tippecanoe)" >&2; exit 1; }

# Fixed -z14 instead of -zg: with so few features -zg picks z3, which is too coarse to draw streets.
# <source file> <layer name>; the output is data/<source file>.pmtiles
for pair in "blocks:blocks" "bike_lanes:lanes" "crashes:crashes"; do
  src="${pair%%:*}"; layer="${pair##*:}"
  tippecanoe -q -z14 --drop-densest-as-needed --force -l "$layer" \
    -o "data/$src.pmtiles" "src/$src.geojson"
done
