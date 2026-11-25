# Data contract

This is the contract between the Python pipeline (which writes the files) and the Svelte site (which reads them).
The TypeScript interfaces in `site/src/lib/types.ts` are the source of truth for shapes; this page says what each
field means. A small complete example set lives in `site/fixtures/data/` (Brooklyn Community Board 9);
`scripts/use_fixtures.sh` copies it to `site/public/data/`, and `site/src/lib/types.test.ts` checks it against the types.

Conventions:
- Everything is written to `site/public/data/` at build time (never committed to `main`).
- Community board ids (`cb`) are `boro_cd` strings (`"309"` = Brooklyn CB 9). Council district ids (`cd`) are council numbers as strings (`"40"`). Both are strings everywhere.
- Dates are ISO `YYYY-MM-DD`; timestamps are ISO 8601 UTC.
- Coordinates are WGS84 `[lon, lat]`; a `bbox` is `[west, south, east, north]`.
- **Ranks in the files are citywide.** The site computes area ranks (spec §6.4).
- Street names are the pipeline's normalized (upper case) street names; the site decides how to display them.
- `borough` is the full name (`"Brooklyn"`).

## Files

| File | Shape | Notes |
|---|---|---|
| `meta.json` | `Meta` | Data date, windows, source times, counts, citywide and unassigned totals. |
| `areas.json` | `Areas` | Every board (`cb`) and district (`cd`) with bbox and totals. |
| `areas.geojson` | FeatureCollection | Area outline polygons (the 59 boards and 51 districts, no parks/airports); feature properties are `kind`, `id`, `name`. The site uses it for the selected area's outline and for the Community Board and Council District boundary layers (one label point per area is computed in the browser by `areaLabelPoints` in `mapstyle.ts`). |
| `blocks.json` | `Block[]` | Contains (a) every block with a placed bike crash in any year and (b) every block referenced by any stretch's `segmentids` or `gap_segmentids`, even if it has zero crashes ever (gap blocks), so the site can always look up a stretch's blocks. Sorted by `rank`, unranked (null) last, then by `segmentid`. |
| `stretches.json` | `Stretch[]` | Sorted by `rank`. |
| `streets.json` | `Street[]` | Whole-street totals, sorted by `rank`. |
| `snapshots/index.json` | `SnapshotIndex` | `dates` newest first; `latest` equals `dates[0]` and the live `meta.json` data date. |
| `snapshots/<date>/{meta,areas,blocks,stretches,streets}.json.gz` | same shapes, gzip-compressed | No geometry, no crash rows. The latest date is also present as a snapshot. The files are gzipped on disk (level 9) because Pages publishes raw files and daily copies of `blocks.json` would pass its size limit. Pages serves them as `application/gzip` without `Content-Encoding`, so the site must decompress them itself (`DecompressionStream('gzip')`). `index.json` stays plain JSON. |
| `crashes/<kind>-<id>.csv`, `crashes/citywide.csv` | CSV | 5-year window, crashes with coordinates only (so row counts match the area totals). |
| `blocks.pmtiles`, `bike_lanes.pmtiles`, `crashes.pmtiles` | vector tiles | See Tiles. |

## Types

### `Facility`, `LaneAtCrash`, `AreaKind`
- `Facility`: a bike facility class, `none | paint | sharrow | protected` (LION/bike-route classes: none, II, III, I).
- `LaneAtCrash`: the facility active when a crash happened, a `Facility` or `unknown` (unmatched crashes and unresolvable cases).
- `AreaKind`: `cb` (community board) or `cd` (council district).

### `AreaTotals`
Totals for one area (or citywide, or unassigned). Counts only crashes and blocks inside the area, so areas of one kind add up to citywide minus `unassigned`.
- `crashes_5y`: bike crashes with coordinates in the 5-year window located in the area (any match confidence, or unmatched).
- `injured_5y`: riders injured in those crashes.
- `killed_5y`: riders killed in those crashes.
- `lane_at_crash_5y`: those crashes split by `LaneAtCrash` (the five values sum to `crashes_5y`).
- `ranked_blocks`: blocks in the area that have a rank.
- `tier1_blocks`: ranked blocks in Tier 1 (no bike lane today).
- `tier2_blocks`: ranked blocks in Tier 2 (paint or sharrow today).
- `stretches`: stretches touching the area.
- `shared_stretches`: stretches touching the area and at least one other area of the same kind. For `citywide` it is the number of stretches touching more than one community board.

### `Meta`
- `data_date`: the latest crash date in the pull; the windows are anchored to it.
- `built_at`: when the pipeline ran.
- `window_start`: first day of the 5-year window (first of the data date's month, minus 5 years).
- `recent_start`: first day of the full-weight 2-year window (minus 2 years).
- `sources`: last-updated time per raw source, keys `crashes, persons, vehicles, routes, council, community, lion`.
- `counts`: integer counters from the run. Keys: `candidate_crashes, bike_riders, riders_killed, bike_crashes, match_high, match_medium, match_low, unmatched_no_coords, unmatched_too_far, lane_none, lane_paint, lane_sharrow, lane_protected, lane_unknown, blocks, ranked_blocks, tier1_blocks, tier2_blocks, stretches`, plus raw row counts per source as `rows_<source>` (`rows_crashes, rows_persons, rows_vehicles, rows_routes, rows_council, rows_community, rows_lion`). Over all years: `match_*` + `unmatched_*` = `bike_crashes`, and the five `lane_*` values also sum to `bike_crashes`.
- `citywide`: `AreaTotals` over everything.
- `unassigned`: `AreaTotals` for crashes with coordinates that fall in no area polygon, and ranked blocks with no area. This is the community board version (kind `cb`); the council district version differs slightly and is not written. `stretches` and `shared_stretches` are 0.

### `Area`
- `kind`: `cb` or `cd`.
- `id`: the area id string.
- `name`: display name, e.g. `Brooklyn CB 9`, `Council District 40`.
- `borough`: borough name for boards; `null` for council districts.
- `bbox`: bounding box of the outline; must equal the bounds of this area's polygon in `areas.geojson`.
- `totals`: `AreaTotals` for the area.

### `Areas`
- `cb`, `cd`: arrays of `Area`, sorted by `id`.

### `Block`
One street block (LION segment): a block with a placed crash in any year, or a gap block of a stretch.
- `segmentid`: LION segment id (string, 7 digits); also the feature id in `blocks.pmtiles`.
- `street`: normalized street name.
- `borough`: borough name or `null`.
- `current_facility`: today's bike facility on the block.
- `tier`: 1 (no lane), 2 (paint or sharrow), or `null` when not ranked (protected, or zero score). Rule: `tier`, `rank` and `rank_in_tier` are all null together or all set together; an unranked block never carries a tier, whatever its current facility. Use `current_facility` for the lane today.
- `rank`: citywide rank among ranked blocks (tier, then score, killed, crashes, segmentid), or `null`.
- `rank_in_tier`: rank within its tier, or `null`.
- `score`: priority score, 0 for unranked blocks. Sum over crashes in the window (`window_start` onward) that matched at high or medium confidence and whose lane at crash time was none, paint or sharrow, of harm (killed × 10 + injured) times a weight of 1.0 on or after `recent_start`, else 0.5 (spec §5).
- `crashes_5y`: scored crashes on the block: window crashes matched at high or medium confidence whose lane at crash time was none, paint or sharrow (the same crashes that feed `score`).
- `injured_5y`: riders injured in those scored crashes.
- `killed_5y`: riders killed in those scored crashes.
- `crashes_no_lane_5y`: those scored crashes where no bike lane existed at crash time.
- `crashes_all_years`: bike crashes on the block in all years.
- `last_crash_date`: date of the latest crash on the block (any year), or `null`.
- `posted_speed`: posted speed limit in mph, or `null`.
- `travel_lanes`: number of travel lanes, or `null`.
- `cb`: community board id by block midpoint (joint interest areas reassigned to the nearest board), or `null`.
- `cd`: council district id by block midpoint, or `null`.
- `area_by_nearest`: `true` when `cb` was assigned by nearest board because the midpoint fell in a joint interest area.
- `stretch_id`: the stretch containing the block (ranked members and gap members), or `null`.
- `mid`: block midpoint `[lon, lat]`.

### `Stretch`
A run of connected ranked blocks on one street and tier (plus bridged gap blocks).
- `stretch_id`: `"S" + min(ranked segmentids)`.
- `street`: normalized street name.
- `borough`: borough name.
- `tier`: 1 or 2.
- `rank`: citywide stretch rank (tier, then score, killed, crashes, stretch id).
- `from_street`: cross street at one end, or `null`.
- `to_street`: cross street at the other end, or `null`.
- `blocks`: number of member blocks, **including** gap blocks (`segmentids.length`).
- `segmentids`: all member segment ids, ranked blocks and gap blocks.
- `gap_segmentids`: the subset of `segmentids` that are bridged zero-score gap blocks.
- `score`: sum of member block scores.
- `crashes_5y`, `injured_5y`, `killed_5y`, `crashes_no_lane_5y`: sums over the member blocks.
- `last_crash_date`: latest crash date over the members, or `null`.
- `cbs`: community board ids the stretch touches (sorted); stretches are never split at area boundaries.
- `cds`: council district ids it touches (sorted).
- `bbox`: bounding box of the member blocks.

### `Street`
Whole-street totals: ranked blocks grouped by street, borough and tier.
- `street_key`: `borough + "|" + normalized name + "|" + tier`, e.g. `Brooklyn|EMPIREBOULEVARD|1` (the pipeline's normalized name drops spaces and expands abbreviations).
- `street`: normalized street name.
- `borough`: borough name.
- `tier`: 1 or 2.
- `rank`: citywide street rank (tier, then score, killed, crashes, street key).
- `score`: sum of the ranked blocks' scores.
- `blocks`: number of **ranked** blocks (gap blocks are not counted).
- `crashes_5y`, `injured_5y`, `killed_5y`: sums over the ranked blocks.
- `stretch_ids`: the street's stretches in this tier (sorted).
- `cbs`, `cds`: area ids touched by those stretches (sorted).

### `SnapshotIndex`
- `latest`: the newest snapshot date.
- `dates`: all kept snapshot dates, newest first.

## Crash CSV

`crashes/<kind>-<id>.csv` (for example `cb-309.csv`, `cd-40.csv`) and `crashes/citywide.csv`. One row per bike crash in the 5-year window that has coordinates, sorted by date. A crash belongs to an area file by point in polygon. Columns:

`collision_id` (NYPD collision id), `crash_date`, `crash_time` (`HH:MM`), `latitude`, `longitude`, `on_street_name`, `cross_street_name` (as reported), `matched_street` (street of the matched block, empty when unmatched), `segmentid` (matched block, empty when unmatched), `match_confidence` (`high | medium | low | unmatched`), `lane_at_crash` (a `LaneAtCrash`), `riders_injured`, `riders_killed`, `bike_types` (one entry per hurt rider, separated by `;`, from `bicycle | e-bike | e-scooter`).

## Tiles

All three are vector tiles built with tippecanoe (`pipeline/tiles.py`). The map draws nothing for a layer below its minimum zoom, so the minimums must stay at or below the citywide view (about z8.7 on phones).
- `blocks.pmtiles`, layer `blocks`, zoom 8 to 12 (overzoomed above 12): every LION snap-layer block (not only those in `blocks.json`). Property `segmentid` (string); use it as `promoteId`. Priority colors come from feature state set by the site, so the same tiles serve every snapshot. Every ranked block is present from z12; z8 to z11 are thinned in dense areas.
- `bike_lanes.pmtiles`, layer `lanes`, from zoom 8: current bike routes. Properties `facility` (`protected | paint | sharrow`) and `onoff` (`ON | OFF`).
- `crashes.pmtiles`, layer `crashes`, from zoom 10 (the site shows dots from z12): 5-year crashes with coordinates. Properties `collision_id`, `date`, `lane` (a `LaneAtCrash`), `injured`, `killed`, `street`, `segmentid` (empty when unmatched).

## Fixture notes

`site/fixtures/data/` is a hand-made example, not real data. Streets are drawn as simple lines near Empire Blvd, Nostrand Av, Utica Av and Rogers Av; boards and districts are rectangles. It has 12 blocks (9 ranked, one gap block, two protected-lane blocks), 4 stretches (Empire Blvd is shared by boards 308, 309 and 317 and districts 35 and 40; Utica Av is Tier 2), 3 streets, and an older snapshot `2026-11-23`. Crash CSVs exist for every fixture area and for `citywide`. Regenerate tiles from `site/fixtures/src/*.geojson` with `scripts/make_fixture_tiles.sh`.
