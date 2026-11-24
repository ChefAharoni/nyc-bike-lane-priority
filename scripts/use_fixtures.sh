#!/usr/bin/env bash
# Copies the fixture data set into site/public/data so `npm run dev` runs without the pipeline.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/site"
rm -rf public/data
mkdir -p public/data
cp -R fixtures/data/. public/data/
echo "fixtures copied to site/public/data"
