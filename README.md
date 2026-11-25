# NYC Bike Lane Priority

A static website that ranks New York City streets by how urgently they need protected bike lanes. It is built from public crash, street-network and bike-route data. You can look at the whole city, one Community Board or one Council District, see the worst stretches on a map, open a street for details, and export a report for DOT or a board meeting.

Live site: **https://bikelanepriority.org** (for example, Brooklyn Community Board 9: https://bikelanepriority.org/#/cb/309). The data refreshes every night at 2 am Eastern (3 am in summer). How the numbers are made is explained on the site's "About this data" page.

**Working on the code? Start with [`AGENTS.md`](AGENTS.md).**

## What the site does

- Ranks street blocks, stretches (connected runs of one street) and whole streets for protected lanes. Streets with no bike lane always rank above streets with only paint or sharrows.
- Switches between Community Boards and Council Districts. Streets that cross several boards are shown whole and tagged with every board they touch.
- Map layers: priority streets, bike lanes today, bike crashes, the selected area's outline, and every Community Board and Council District boundary.
- A detail panel for each street or block, shareable links, dated snapshots of earlier rankings, and printable reports (DOT summary or board view) with CSV downloads.

## How it works

- `pipeline/` (Python) downloads the data, matches each bike crash to a street block and the bike lane that was there on that date, scores and ranks the blocks, joins them into stretches and whole streets, and writes JSON, CSV and map tiles to `data_out/`.
- `site/` (Svelte and MapLibre) is the website. It reads those files and runs entirely in the browser.
- `.github/workflows/nightly.yml` runs the pipeline every night, checks the result, keeps the data on the `data` branch and deploys to GitHub Pages.

## Quick start

```
uv sync
uv run pytest -q
uv run python -m pipeline --out data_out --raw raw --lion-cache .cache/lion --snapshots data_out/snapshots

npm --prefix site ci
cp -R data_out/. site/public/data/
npm --prefix site run dev
```

The first pipeline run downloads everything from NYC Open Data and takes about 15 minutes; later runs reuse the cache. Tests, the browser smoke test and the rules for changing things are in `AGENTS.md`.

## Docs

- [`AGENTS.md`](AGENTS.md): how the project fits together and how to work on it
- [`docs/data-contract.md`](docs/data-contract.md): the files the pipeline writes and the site reads
- [`docs/operations.md`](docs/operations.md): nightly workflow, data branch, snapshots, sanity gate, custom domain
- [`docs/parity.md`](docs/parity.md): checks against the original analysis, areas, stretches and a CB 9 walkthrough

## Data sources

NYC Open Data: Motor Vehicle Collisions (crashes, persons, vehicles), NYC Bike Routes, LION street network, City Council Districts and Community Districts. Basemap by OpenFreeMap, data from OpenStreetMap.

## License

MIT (see `LICENSE`).
