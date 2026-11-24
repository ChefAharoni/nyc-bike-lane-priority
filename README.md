# NYC Bike Lane Priority

A static website that ranks New York City streets by how urgently they need protected bike lanes. It is built from public crash, street-network and bike-route data. You can look at the whole city, one community board or one council district, see the worst stretches on a map, open a street for details, and export a summary report.

Live URL: (pending first deploy)

## How it works

- `pipeline/` (Python) downloads the data, matches each bike crash to a street block and the bike lane that was there, scores and ranks the blocks, joins them into stretches and whole streets, and writes JSON and map tiles to `data_out/`.
- `site/` (Svelte and MapLibre) is the website. It reads those files and runs entirely in the browser.
- `scripts/assemble_site.sh` builds the site and copies the data next to it in `site/dist`.

## Run the pipeline

```
uv sync
uv run pytest -q
uv run python -m pipeline --help
```

The checks against the original results are in `docs/parity.md`.

## Run the site

```
npm --prefix site install
npm --prefix site run dev
```

To try it with real data, run the pipeline first, then `scripts/assemble_site.sh data_out data_out/snapshots` and `npm --prefix site run preview`.

## Tests

```
cd site
npx vitest run     # unit tests
npm run check      # type check
npm run e2e        # browser smoke test
```

`npm run e2e` needs `data_out/` from a pipeline run and Google Chrome installed. It builds the real-data site into `site/dist` (in a test mode that exposes the map to the test), serves it and drives it in Chrome: Brooklyn CB 9, layer switches, detail, export, the unknown-area notice and a phone-sized screen. It is not part of the CI workflow because CI has no real data.

## Nightly deploy

A GitHub Actions workflow refreshes the data every night, stores it on the `data` branch and deploys the site to GitHub Pages. See `docs/operations.md` for how it works, how to rerun it and what to do after a sanity failure.
