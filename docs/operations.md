# Operations

## Pipeline run

```
uv run python -m pipeline --out data_out --raw raw --lion-cache .cache/lion --snapshots data_out/snapshots \
  [--previous-meta <last deployed meta.json>] [--no-tiles]
```

Order: run, write the contract files, sanity check, tiles, snapshot (write, prune, index). Exit code 3 means the
sanity check failed: each reason is printed on its own line on stderr, and no tiles or snapshot are written. A
`--previous-meta` path that does not exist counts as a first run (absolute bounds only). The check reads the area
ids from the `areas.json` next to the given meta file.

Snapshot files are `snapshots/<date>/{meta,areas,blocks,stretches,streets}.json.gz` (gzip level 9, mtime 0, so
repeatable); `index.json` is plain JSON. One snapshot is 1.53 MB, so 90 daily snapshots are about 138 MB plus a
small monthly tail, well under the 1 GB Pages limit (plain copies would have been about 17.5 MB each, 1.57 GB).

Tiles need `tippecanoe` on PATH (built with v2.79). Snapshots: everything under 90 days old is kept; older
ones keep only the earliest snapshot of each calendar month.

The LION download cache is keyed on the dataset's `blobId` (its `rowsUpdatedAt` is stale), and
`meta.sources.lion` is the dataset's `viewLastModified`.

## Reference run (2026-11-24, data_date 2026-11-21, local, cached sources and LION)

Runtime: about 76 s wall clock (matching and contract about 65 s, tiles about 7 s).

| File | Raw bytes | gzip -9 bytes |
| --- | ---: | ---: |
| blocks.json | 13,327,721 | 950,232 |
| stretches.json | 3,257,876 | 470,902 |
| streets.json | 839,884 | not measured |
| areas.json | 39,113 | not measured |
| areas.geojson | 625,159 | not measured |
| meta.json | 1,433 | not measured |
| blocks.pmtiles | 5,406,846 (from z8; 4,416,644 when it started at z10) | not measured |
| bike_lanes.pmtiles | 1,016,769 (from z8; 795,759 at z10) | not measured |
| crashes.pmtiles | 4,595,338 | 4,561,019 |
| crashes/ (112 CSVs) | about 13 MB total | not measured |
| snapshots/2026-11-21/ (5 gzipped JSON files) | 1,528,970 | already gzip |

`data_out` is about 45 MB in total: 1.5 MB is the one snapshot and the rest is the live set. `blocks.json` is over
the 10 MB raw target; that is accepted because Pages serves gzip (0.95 MB). PMTiles are already compressed, so
gzip gains nothing on them.

Tiles check (2026-11-24): `blocks.pmtiles` was decoded at z10, z11 and z12 for the Brooklyn CB 9 box
(-73.963081, 40.654839, -73.92835, 40.671622; 291 ranked blocks have a midpoint in it) and across the whole city at z12.
Before: z10 and z11 each held 164 of the 291 ranked blocks (127 dropped by `--drop-densest-as-needed`, which only
thins the two lowest zooms), z12 held all 291, but one ranked block citywide (0354377, Longwood Avenue, rank 1771,
about 1.5 m long) was missing at z12 because the default 12 bit tile precision collapsed it to a point. After: the blocks
layer is built with `-d14` (14 bit tile precision), which keeps every ranked block at z12 (17,210 of 17,210; 147,217 of
147,218 blocks, the last one a zero-length segment), at a cost of 4,204,190 to 4,416,644 bytes (after: z10 154, z11 164, z12 291 of 291 in the CB 9 box). `--no-feature-limit`
was tried and rejected: tippecanoe then skips the z11 tiles (over 500 KB) and the layer loses its z12 tiles. Known
limit: at z10 and z11 the density drop still removes about 44% of the ranked blocks in a dense box such as CB 9; the
priority layer is drawn from those tiles when zoomed out, so a zoomed-out map is a thinned view, and every block
appears from z12.

Notes: blocks and lanes use `-Z8` (since 2026-11-25; before that they started at z10 and the citywide view, about z8.7 on phones and z9.6 on desktop, showed no priority streets at all); crashes use `-Z10` (the site shows crash dots from z12); `blocks.pmtiles` holds 147,217 of the 147,218 snap-layer blocks (the missing one has zero length) and its maximum
zoom is 12 (the client overzooms). All three tile files start with the `PMTiles` magic bytes.

## Before the first deploy

Do these once, in order. Pushing `main` starts the workflows, so set everything up before the first push:

1. Create the GitHub repository, empty (do not push yet).
2. Settings, Secrets and variables, Actions: add the repository secret `BRANDING_PATTERNS`. Its value is the
   banned-term list, one regex per line (the non-comment lines of the local reference file
   `../nyc-bike-lane-priority-reference/branding_terms.txt`). The patterns are deliberately not stored anywhere in this
   repository. Without the secret `scripts/check_branding.sh` exits 2 ("branding patterns not configured") and the
   `branding` job, the live-data scan and the site assembly all fail; it never passes silently.
3. Settings, Secrets and variables, Dependabot: add the same `BRANDING_PATTERNS` secret (Dependabot pull requests
   cannot read Actions secrets, so without it their branding check fails).
4. Settings, Pages, Source: choose "GitHub Actions".
5. Settings, Environments: confirm the `github-pages` environment allows deployments from `main` (the default
   rule does; a custom branch rule must include `main`).
6. Optional: add the secret `SOCRATA_APP_TOKEN` to raise the NYC Open Data rate limit.
7. Push `main`. This starts the first nightly run (no `data` branch yet, so only the absolute sanity bounds
   apply). Watch each job (`pipeline`, `site`, `deploy`, `close-sanity-issue`). The first run takes about 20
   minutes because nothing is cached yet.

### Custom domain

The site is served at `https://bikelanepriority.org` (registered and DNS-hosted at Cloudflare). Setup, for reference:

- Cloudflare DNS, all "DNS only" (grey cloud): four `A` records for the apex to `185.199.108.153`,
  `185.199.109.153`, `185.199.110.153`, `185.199.111.153`, and `CNAME www` to `chefaharoni.github.io`.
- The repository's Pages custom domain is `bikelanepriority.org` with "Enforce HTTPS" on
  (`gh api -X PUT repos/ChefAharoni/nyc-bike-lane-priority/pages -f cname=bikelanepriority.org`, then
  `-F https_enforced=true` once the certificate is issued).
- The site uses relative paths and hash routing, so nothing in the code depends on the domain.

**If the domain is ever dropped or expires:** remove the custom domain first (Settings, Pages, Custom domain,
Remove, or `gh api -X PUT repos/ChefAharoni/nyc-bike-lane-priority/pages -f cname=`). While a custom domain is set,
`chefaharoni.github.io/nyc-bike-lane-priority` redirects to it, so a lapsed domain would take the site offline.
Removing it restores the `github.io` address. Also delete the DNS records so the name can't point at someone
else's Pages site.

### Branding check configuration

`scripts/check_branding.sh [paths...]` takes its patterns from, in order: the env var `BRANDING_PATTERNS`
(newline-separated regexes), the file named by `BRANDING_PATTERNS_FILE`, or the local reference file
`../nyc-bike-lane-priority-reference/branding_terms.txt` (skipped when `BRANDING_NO_LOCAL_FALLBACK=1`, which the
checks use to test the fail-closed path). Blank lines and `#` lines are ignored. Exit 0 = clean, 1 = hit, 2 = no
patterns configured or a scan error. Workflows pass `secrets.BRANDING_PATTERNS` only to the steps that scan.

## Nightly workflow

`.github/workflows/nightly.yml` runs at 07:00 UTC every day (2 am EST, 3 am EDT), on manual dispatch, and on every
push to `main`. Concurrency group `nightly` with no cancelling: one run executes and at most one waits; a newer
waiting run replaces an older waiting one.

Four jobs, each with only the permissions it needs (the workflow default is none): `pipeline` (contents and issues
write, actions write for the monthly re-enable; 45 minute timeout; the token is only in the steps that call gh or
push), `site` (contents read; runs `npm ci` and the build), `deploy` (pages and id-token write; only runs
`actions/deploy-pages`) and `close-sanity-issue` (issues write). Third party actions are pinned to major versions,
except `setup-uv` which is pinned to a commit SHA, as is the tippecanoe source build; Dependabot (weekly) proposes
updates.

1. Check out `main`. Fetch the `data` branch into `data-branch/` if it exists. If it exists it must contain
   `latest/meta.json`, `latest/areas.json` and `snapshots/index.json`; if any is missing the job fails loudly rather
   than treating the run as a first run. The lookup also fails closed: only "no such branch" (ls-remote exit 2)
   is a first run; any other lookup error fails the job, so a network blip cannot overwrite the data branch.
2. Install uv, run `uv sync`, install tippecanoe (the apt package if it is 2.17 or newer, otherwise build tag 2.79.0
   from source; the build is cached by version). Cache `.cache/lion` keyed on the street map file's `blobId`.
3. Run `python -m pipeline --out data_out --lion-cache .cache/lion --snapshots data-branch/snapshots
   --previous-meta data-branch/latest/meta.json`. The previous meta is left out on the first run (no `data` branch)
   and when `force` is set.
4. Exit code 3 (sanity failure): the job opens an issue labeled `nightly-sanity` with the reasons (or comments on the
   open one), skips everything after, and fails. Nothing is deployed and the `data` branch is untouched. On a later
   passing run the issue is closed automatically.
5. On success the `data` branch is replaced by one orphan commit (force-pushed, message `data: <data_date>`) holding
   `latest/` (the full data contract output) and `snapshots/` (`index.json` plus dated folders). History never grows;
   the branch is about 44 MB plus 1.5 MB per retained snapshot.
   Right after the pipeline, `scripts/check_branding.sh data_out` scans the new data. Exit 1 (a hit) is handled like a
   sanity failure: the `nightly-sanity` issue is filed or updated (without repeating the matched text), nothing is
   published, the job fails. Exit 2 (patterns not configured) fails loudly with no issue.
6. In the `site` job, before the build, `CONTRACT_DIR=data-in/latest CONTRACT_SNAPSHOTS_DIR=data-in/snapshots npx vitest
   run src/lib/types.test.ts` checks the data against the contract (shapes, sort orders, cross references, recomputed
   scores). A violation fails the job, so nothing is deployed. Then `scripts/assemble_site.sh <latest_dir> <snapshots_dir>` builds `site/dist`, copies the data to `dist/data/` and
   the snapshots to `dist/data/snapshots/`, and runs `scripts/check_branding.sh site/dist`. The result is uploaded
   and deployed to GitHub Pages.

The pipeline job hands `latest/` and `snapshots/` to the `site` job as an artifact. The sanity issue is closed by
the last job, only after a successful deploy.

A push to `main` skips steps 2 to 5 and rebuilds the site from the `data` branch's current `latest/` and
`snapshots/` (if there is no `data` branch yet it runs the full pipeline).

Two things to know. The `data` branch is published before the site is built and deployed, so a site build or
deploy failure leaves the data branch one day ahead of the live site (the next push or nightly run catches up).
And only exit code 3 files an issue: an outage (a source API down, a crash, a timeout) fails the run red without one,
so watch the Actions tab or enable failure notifications.

### Rerun, and overriding a sanity failure

Rerun: Actions, nightly, Run workflow. A failed run can also be re-run from its page.

A sanity failure means the new numbers moved more than the allowed bounds against the last deployed data (or broke
an absolute bound). First read the reasons in the issue. If it is a real problem upstream (a truncated download, a
changed column) wait for the source or fix the pipeline. If the change is legitimate, for example a new street map
release that changes block counts, run the workflow manually with `force` set to true. That run passes no
`--previous-meta`, so only the first-run absolute bounds apply, and the result becomes the new baseline. Do not leave
`force` on: it is a per-run input and defaults to false.

Retention: snapshots are written to `data-branch/snapshots` and pruned by the pipeline (all kept for 90 days, then
one per calendar month), so the pruned set is what the next orphan commit carries. Deployed size is about 42 MB of
live data plus the snapshots (about 138 MB for 90 days), under the 1 GB Pages limit.

### The 60 day rule

GitHub disables scheduled workflows in public repositories after 60 days without repository activity. The nightly
push to the `data` branch is expected to count as activity, so this should not trigger. As a belt and braces step,
the scheduled run on the 1st of each month calls (unconditionally; it is a harmless no-op when the workflow is enabled)
`gh api -X PUT repos/{owner}/{repo}/actions/workflows/nightly.yml/enable` (the job has `actions: write`). That only
helps if the workflow is still running: a disabled workflow cannot re-enable itself. The reliable fix, if GitHub
disables the schedule anyway, is the manual button: Actions, nightly, Enable workflow.
