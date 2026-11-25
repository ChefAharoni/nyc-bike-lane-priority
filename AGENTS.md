# Working on NYC Bike Lane Priority

Start here. This file is for anyone (human or coding agent) about to change this project.

## What this is

A free, public, static website, **https://bikelanepriority.org**, that ranks New York City street blocks and whole streets by how urgently they need a protected bike lane. It is built for NYC Community Boards (first audience: Brooklyn Community Board 9, `#/cb/309`), City Council offices and DOT. Visitors need only a link: no login, no server, no cost.

- A Python pipeline (`pipeline/`) downloads public NYC Open Data, decides which crashes are bike crashes, matches each crash to a street block and to the bike lane that was there on the crash date, scores and ranks blocks, combines blocks into stretches and whole streets, assigns everything to Community Boards and Council Districts, and writes JSON, CSV and map tiles.
- A Svelte 5 + MapLibre site (`site/`) displays those files. It never computes new facts; it only sorts, filters, renumbers and sums pipeline rows (in tested code).
- A GitHub Actions workflow runs the pipeline every night, checks the result, stores it on the `data` branch and deploys to GitHub Pages.

## Read these first

| File | What it tells you |
|---|---|
| `AGENTS.md` (this file) | How the project fits together and how to work on it |
| `docs/data-contract.md` | **The interface between pipeline and site.** Every file, field and rule. Change it first, then both sides. |
| `docs/operations.md` | The nightly workflow, the data branch, snapshots, sanity gate, custom domain, first-deploy checklist, sizes |
| `docs/parity.md` | Evidence that the pipeline reproduces the original analysis, plus area, stretch and CB 9 checks |
| `site/src/lib/About.svelte` | The public explanation of every rule. If you change a rule, change this page too. |

## Layout

```
pipeline/            Python package, run as `python -m pipeline`
  config.py          dataset ids, score weights, snap distance, joint-interest-area codes, GAP_BLOCKS
  fetch.py           Socrata paging (retries, count check), candidate crashes, LION download (cache keyed by blobId)
  bike_crashes.py    who counts as a hurt rider (bicycle, e-bike, e-scooter; mopeds excluded)
  matching.py        crash -> LION street block (100 ft snap, street-name tie-break, confidence)
  lane_status.py     lane on that block on the crash date
  scoring.py         5-year window from the data date, harm score, two tiers, citywide rank
  areas.py           Community Board / Council District per block and crash (parks/airports -> nearest board)
  stretches.py       connected runs of one street and tier (bridging up to 2 quiet blocks); whole-street totals
  totals.py          per-area, citywide and unassigned totals (areas + unassigned = citywide, exactly)
  contract.py        writes the files in docs/data-contract.md
  tiles.py           PMTiles via tippecanoe (blocks, bike lanes, crashes)
  snapshots.py       dated gzipped copies + retention
  sanity.py          the gate that blocks a bad nightly pull
  run.py, __main__.py  orchestration and CLI
tests/               pytest, one file per module; tests/test_cli.py covers the sanity exit code
site/
  src/App.svelte     page state, routing, data loading, notices
  src/lib/           components and logic (components live here, not in src/components)
    types.ts         the contract types (mirror of docs/data-contract.md)
    route.ts         hash routing: #/citywide, #/cb/309, #/cd/40, @YYYY-MM-DD, /blocks, /s/<id>, /b/<id>, #/about
    load.ts          loads current data or a gzipped snapshot (nearest earlier date if pruned)
    rank.ts          area filtering and area ranks
    mapstyle.ts      layer ids, colors, feature state, boundary label points
    MapView.svelte   the map; Layers.svelte the layer panel
    report.ts, Report.svelte, ExportDialog.svelte, csv.ts   PDF reports and CSV downloads
    About.svelte     the public "About this data" page
    *.test.ts        vitest; types.test.ts validates fixture or real data against the contract
  e2e/smoke.spec.ts  Playwright smoke test against the real-data build
  fixtures/data/     small hand-made contract data for development and tests
scripts/
  check_branding.sh  banned-terms check (see Rules)
  assemble_site.sh   build the site and copy data into site/dist/data
  use_fixtures.sh    copy fixtures into site/public/data
  cb_walkthrough.py  regenerate the CB 9 walkthrough in docs/parity.md
.github/workflows/   ci.yml (tests, build, branding) and nightly.yml (pipeline, site, deploy)
```

Gitignored working directories: `raw/` (parquet cache of NYC downloads), `.cache/lion/` (street map file), `data_out/` (pipeline output), `site/public/data/`, `site/dist/`.

## Everyday commands

```
uv sync                                   # Python deps (Python 3.12)
uv run pytest -q                          # pipeline tests (no network)
npm --prefix site ci                      # site deps (Node 22+)

# Real data, first run downloads everything (about 15 minutes); later runs reuse raw/ and .cache/lion (about 1.5 minutes)
uv run python -m pipeline --out data_out --raw raw --lion-cache .cache/lion --snapshots data_out/snapshots

# Site with fixtures
scripts/use_fixtures.sh && npm --prefix site run dev
# Site with real data
cp -R data_out/. site/public/data/ && npm --prefix site run dev

cd site
npx vitest run                            # unit tests + contract check on fixtures
CONTRACT_DIR=../data_out npx vitest run src/lib/types.test.ts   # contract check on real data
npm run check                             # svelte-check + tsc, must be 0 errors
npm run build
npm run e2e                               # needs data_out/ and Google Chrome

scripts/check_branding.sh                 # must exit 0 before every commit
```

## How to make a change

1. Read the relevant section of `docs/data-contract.md` and the module you are changing.
2. If a pipeline output changes shape or meaning, update the contract doc, `site/src/lib/types.ts`, the fixtures in `site/fixtures/data/` (and their snapshot `.json.gz` copies), and the validator in `types.test.ts`, all in the same change.
3. Write or update the test first, then the code. Pipeline tests never touch the network (patch `requests` to raise).
4. Run the checks in "Everyday commands". For map or layout changes, look at the result in a browser with real data, on desktop and at a 390 x 844 phone size.
5. If you changed a rule a reader would care about, update `About.svelte` and, where relevant, `report.ts` (the methods paragraph).
6. Commit with a clear message. Pushing to `main` deploys the site (a site-only rebuild from the data branch). Pipeline changes take effect at the next nightly run, or run the workflow by hand: `gh workflow run nightly -R ChefAharoni/nyc-bike-lane-priority`.

## Rules that must not break

- **Accuracy first.** The crash definition, matching, lane-at-crash-time, scoring and tiers reproduce a hand-validated analysis (`docs/parity.md`). Do not change them without re-running the parity comparison and recording it there.
- **Every Tier 1 item ranks above every Tier 2 item**, in every list, map and report. `tier` is null exactly when `rank` is null.
- **No number on the site that the pipeline did not compute.** The site may sort, filter, renumber and sum pipeline rows in tested functions.
- **Never write NaN** into JSON; use null.
- **Areas add up.** Area totals count only what is inside the area, and areas plus `unassigned` equal citywide, exactly. Stretches are never split at boundaries; they carry tags for every area they touch.
- **Banned terms.** `scripts/check_branding.sh` fails the build if the repo, the built site, the data or a commit message contains any term from a private list. The list is stored only in the GitHub secret `BRANDING_PATTERNS` (Actions and Dependabot) and in a local file outside this repository (`../nyc-bike-lane-priority-reference/branding_terms.txt`). Never add the patterns to this repository, never print them, and never weaken the check. Without patterns the script exits 2 (fails closed).
- **Plain language** in everything a visitor reads; no em dashes in site copy.
- **The site is independent.** It must never look like an official city or DOT site.

## Things that have bitten before

- **GitHub Actions expressions:** a skipped step's outputs are null, and `null == '0'` is true. Gate pipeline-only steps on `steps.mode.outputs.run_pipeline == 'true'` as well as on their exit codes.
- **The street map file (LION)**: its metadata date never changes. The cache is keyed on the file's `blobId`.
- **Snapshots are gzipped** (`data/snapshots/<date>/<name>.json.gz`). The site checks the gzip magic bytes, because some servers decompress them on the way.
- **MapLibre in production builds** needs its worker URL set explicitly (`?url` import plus `setWorkerUrl` in `MapView.svelte`). The dev server hides this; `npm run e2e` catches it.
- **`window.__map`** exists only in dev and `--mode test` builds, for the e2e test. Production builds must not expose it.
- **Map tile zooms:** blocks and lanes start at zoom 8, crashes at 10 (the site shows dots from 12). The citywide view sits at about z8.7 on phones and z9.6 on desktop; below the tile minimum, layers draw nothing.
- **The first nightly run after a big legitimate change** (for example a new street map release) can trip the sanity gate. Rerun with the `force` input; see `docs/operations.md`.

## Current status and next steps (updated 2026-11-25)

Update this section at the end of every working session, so the next person can pick up without context.

**State:** live and healthy at https://bikelanepriority.org. Nightly runs, CI and deploys pass. Latest data date 2026-11-21 (81,269 bike crashes, 17,210 ranked blocks, 7,837 stretches).

**Recent changes (newest first):**
- Dependabot action upgrades merged: checkout v7, cache v6, upload-artifact v7, download-artifact v8, upload-pages-artifact v5 (release notes reviewed; none affect this workflow). A manual full nightly run (`gh run list -R ChefAharoni/nyc-bike-lane-priority --workflow nightly`, dispatched 2026-11-25) was started to exercise them; confirm it passed.
- Community Board and Council District boundary layers (off by default, one label per area from z11).
- Street and lane tiles start at zoom 8, so the citywide view shows the priority streets.
- Push-only nightly runs no longer run pipeline-only steps (the `null == '0'` expression bug).
- Custom domain `bikelanepriority.org` with HTTPS.

**Next steps:**
1. Confirm the manual nightly run above passed; if a step failed, read `gh run view <id> --log-failed` and fix forward.
2. Dependabot will open pull requests for `actions/setup-node` and `actions/deploy-pages` (still on v4, Node 20 deprecation warnings). Read the major-version release notes against how `nightly.yml` uses them, merge, then run the nightly by hand and watch it.

**Known follow-ups (small, not urgent):**
- Workflow: the real-data contract check runs after the `data` branch is published (a contract bug would become the next night's baseline); a banned-term hit prints the matched line in the job log; the fetch retries don't cover a truncated response body (`ChunkedEncodingError`); the optional Socrata token is forwarded through the street-map file redirect.
- Map: z10 to z11 tiles are thinned in dense areas (every ranked block appears from z12); a very large board on a narrow phone may fit below z12.
- Site: board tags drop the borough in area mode ("CB 9"); the Whole streets and Shared-only toggles are not kept in links; title-casing mangles names such as "MLK"; a trailing bad URL segment (`/s` with no id) is dropped silently.
- Pipeline: a Y-shaped stretch reports only two of its three ends in from/to; `tests` lack a few edge cases (pandas `str` dtype, CLI error paths).

## Deploy and infrastructure

- Repository: `github.com/ChefAharoni/nyc-bike-lane-priority`. Pages source: GitHub Actions. Custom domain `bikelanepriority.org` (DNS at Cloudflare, HTTPS enforced). Details and the "if the domain lapses" steps are in `docs/operations.md`.
- Nightly cron `0 7 * * *` UTC (2 am Eastern in winter, 3 am in summer). A sanity failure opens a `nightly-sanity` issue and deploys nothing.
- The `data` branch is rewritten as a single commit every night (`latest/` and `snapshots/`). Never commit to it by hand.
- Dependabot opens weekly pull requests for workflow actions. CI does not run the nightly workflow, so check the release notes of major-version bumps before merging, then watch the next nightly run.
