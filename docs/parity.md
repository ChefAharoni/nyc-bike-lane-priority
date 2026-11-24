# Parity against the original results

Run date: 2026-11-24, `uv run python -m pipeline --out data_out --raw raw --as-of 2026-11-15 --no-tiles`, real NYC Open Data and LION.
Rule: every count within 0.5% and the #1 block and score exact. No rule was tuned to fit.

| Measure | Count key | Expected | Actual | Diff | Result |
|---|---|---:|---:|---:|---|
| Candidate crashes | `candidate_crashes` | 82,756 | 82,857 | +0.12% | PASS |
| Bike riders | `bike_riders` | 82,592 | 82,717 | +0.15% | PASS |
| Riders killed | `riders_killed` | 385 | 385 | +0.00% | PASS |
| Bike crashes | `bike_crashes` | 81,024 | 81,146 | +0.15% | PASS |
| Match high | `match_high` | 65,604 | 65,709 | +0.16% | PASS |
| Match medium | `match_medium` | 8,305 | 8,319 | +0.17% | PASS |
| Match low | `match_low` | 1,439 | 1,439 | +0.00% | PASS |
| Unmatched, no coordinates | `unmatched_no_coords` | 5,433 | 5,436 | +0.06% | PASS |
| Unmatched, no street within 30 m | `unmatched_too_far` | 243 | 243 | +0.00% | PASS |
| Lane none | `lane_none` | 53,731 | 53,806 | +0.14% | PASS |
| Lane paint | `lane_paint` | 11,179 | 11,200 | +0.19% | PASS |
| Lane protected | `lane_protected` | 5,344 | 5,357 | +0.24% | PASS |
| Lane sharrow | `lane_sharrow` | 5,094 | 5,104 | +0.20% | PASS |
| Lane unknown | `lane_unknown` | 5,676 | 5,679 | +0.05% | PASS |
| Blocks | `blocks` | 30,231 | 30,263 | +0.11% | PASS |
| Ranked blocks | `ranked_blocks` | 17,119 | 17,162 | +0.25% | PASS |
| Tier 1 ranked | `tier1_blocks` | 13,095 | 13,127 | +0.24% | PASS |
| Tier 2 ranked | `tier2_blocks` | 4,024 | 4,035 | +0.27% | PASS |
| #1 block segmentid | | 0145699 | 0145699 | exact | PASS |
| #1 block street | | EAST 14 STREET | EAST 14 STREET | exact | PASS |
| #1 block score | | 15.5 | 15.5 | exact | PASS |

**Overall: PASS. Every count is within 0.5% (largest +0.27%) and the #1 block and score are exact.**

The expected match_high and match_medium are the original analysis's post-downgrade counts, from the same snapshot as the other rows. The earlier expectation (68,395 and 5,514) used the pre-downgrade counts, which were recorded before the corner-block downgrade (`corner_blocks_differ`, 2,800 crashes here).

| Informational: pre-downgrade | Expected | Actual | Diff |
|---|---:|---:|---:|
| High before downgrade (actual 65,709 + 2,800) | 68,395 | 68,509 | +0.17% |
| Medium before downgrade (actual 8,319 - 2,800) | 5,514 | 5,519 | +0.09% |

## Known sources of the small differences

- All counts are slightly higher (about 0.1% to 0.27%): NYPD adds late reports and revisions to crashes dated on or before 2026-11-15 after the original pull.
- Lane counts and block counts move with the crash counts. DOT bike route edits since the original run can also shift a few crashes between lane classes.
- Killed riders (385), low-confidence matches (1,439) and unmatched with no street within 30 m (243) are identical.

## Areas

Community board (cb) and council district (cd) assignment, run on the cached sources with `--as-of 2026-11-15`. This is new logic with no original to compare against.

| Check | Value |
|---|---:|
| Blocks | 30,263 |
| Blocks with null cb | 0 |
| Blocks with null cd | 0 |
| Blocks with area_by_nearest = True (midpoint inside a park/airport area, assigned to the nearest real board) | 285 |
| Blocks in CB 309 | 349 |
| Distinct cb / cd ids on blocks | 59 / 51 |
| Crashes with null cb and null cd (no usable coordinates) | 5,437 |

The original's 28 null-borough blocks do not recur here: every block midpoint is inside a board or within 500 ft of one, and park/airport midpoints go to the nearest real board.

## Stretch check

Stretches and whole-street totals on the cached sources with `--as-of 2026-11-15`, `GAP_BLOCKS = 2`. New logic with no original to compare against; please eyeball the Brooklyn CB 9 (`309`) stretches below. `None` means the end node has no named cross street other than the street itself (rail lines and alleys are ignored). The `#` is the citywide stretch rank.

```
citywide stretches 7827 streets 3395 gap blocks 5090
largest: NOSTRAND AVENUE Brooklyn 63 KINGS HIGHWAY -> None gaps 23
blocks>=30: 20 max 63 median 1.0
CB309 stretches 81
EMPIRE
  #414 T1 EMPIRE BOULEVARD: FLATBUSH AVENUE -> BEDFORD AVENUE, 7 blocks (2 gap), score 7.5, cbs ['309']
  #6394 T2 EMPIRE BOULEVARD: BEDFORD AVENUE -> UTICA AVENUE, 15 blocks (6 gap), score 18.5, cbs ['309']
NOSTRAND
  #6 T1 NOSTRAND AVENUE: KINGS HIGHWAY -> None, 63 blocks (23 gap), score 54.5, cbs ['308', '309', '314', '315', '317', '318']
UTICA
  #54 T1 UTICA AVENUE: EMPIRE BOULEVARD -> FULTON STREET, 25 blocks (9 gap), score 27.5, cbs ['303', '308', '309']
  #6724 T2 UTICA AVENUE: EAST NEW YORK AVENUE -> EMPIRE BOULEVARD, 2 blocks (0 gap), score 3.5, cbs ['309', '317']
top 10 CB309
  #3 T1 FLATBUSH AVENUE: STEPHENS COURT -> MAPLE STREET, 33 blocks (6 gap), score 58.0, cbs ['309', '314']
  #6 T1 NOSTRAND AVENUE: KINGS HIGHWAY -> None, 63 blocks (23 gap), score 54.5, cbs ['308', '309', '314', '315', '317', '318']
  #27 T1 EASTERN PARKWAY: None -> None, 17 blocks (3 gap), score 36.5, cbs ['308', '309', '316']
  #54 T1 UTICA AVENUE: EMPIRE BOULEVARD -> FULTON STREET, 25 blocks (9 gap), score 27.5, cbs ['303', '308', '309']
  #62 T1 ROGERS AVENUE: NEWKIRK AVENUE -> STERLING STREET, 25 blocks (7 gap), score 24.5, cbs ['309', '317']
  #92 T1 ALBANY AVENUE: SNYDER AVENUE -> CROWN STREET, 18 blocks (7 gap), score 20.0, cbs ['309', '317']
  #152 T1 NEW YORK AVENUE: None -> HERKIMER STREET, 25 blocks (11 gap), score 15.0, cbs ['303', '308', '309']
  #155 T1 NEW YORK AVENUE: CHURCH AVENUE -> EAST NEW YORK AVENUE, 13 blocks (2 gap), score 14.5, cbs ['309', '317']
  #175 T1 ROGERS AVENUE: CARROLL STREET -> BERGEN STREET, 13 blocks (5 gap), score 13.5, cbs ['308', '309']
  #216 T1 OCEAN AVENUE: PARKSIDE AVENUE -> FLATBUSH AVENUE, 5 blocks (0 gap), score 12.0, cbs ['309']
```

Citywide: 7,827 stretches, 3,395 street rows, 5,090 bridged gap blocks. Median stretch is 1 block; 20 stretches have 30 or more blocks. Nothing spans a whole borough, so `GAP_BLOCKS` stays at 2.

## CB 9 walkthrough

Generated 2026-11-24 from `data_out` (the same files the site serves) with `python3 scripts/cb_walkthrough.py data_out`, for a sanity read. Rows are formatted as the site shows them: a missing street end reads "continues", and the board tags list CB 9 first, then the other boards the stretch touches. A stretch spans several boards, so its crash count covers the whole stretch, not only the part inside CB 9 (CB 9 itself has 544 crashes counted).

### Brooklyn CB 9 totals (areas.json)

- crashes_5y: 544
- injured_5y: 557
- killed_5y: 2
- ranked_blocks: 236
- tier1_blocks: 186
- tier2_blocks: 50
- stretches: 81
- shared_stretches: 24
- lane_at_crash_5y: {'none': 377, 'paint': 143, 'sharrow': 16, 'protected': 2, 'unknown': 6}
- check: stretches in stretches.json for this board = 81, shared = 24

### Top 5 stretches

| # | Street | From → to | Tier | Blocks | Crashes counted | Score | Board tags |
|---:|---|---|---|---:|---:|---:|---|
| 1 | Flatbush Avenue | Stephens Court → Maple Street | T1 | 33 | 90 | 58.0 | CB 9 / CB 14 |
| 2 | Nostrand Avenue | Kings Highway → continues | T1 | 63 | 85 | 54.5 | CB 9 / CB 8 / CB 14 / CB 15 / CB 17 / CB 18 |
| 3 | Eastern Parkway | continues → continues | T1 | 17 | 43 | 36.5 | CB 9 / CB 8 / CB 16 |
| 4 | Utica Avenue | Empire Boulevard → Fulton Street | T1 | 25 | 40 | 27.5 | CB 9 / CB 3 / CB 8 |
| 5 | Rogers Avenue | Newkirk Avenue → Sterling Street | T1 | 25 | 35 | 24.5 | CB 9 / CB 17 |

### Shared stretches: 24 in total, first 10 by CB 9 rank

| CB 9 rank | Street | From → to | Tier | Blocks | Score | Also in |
|---:|---|---|---|---:|---:|---|
| 1 | Flatbush Avenue | Stephens Court → Maple Street | T1 | 33 | 58.0 | CB 14 |
| 2 | Nostrand Avenue | Kings Highway → continues | T1 | 63 | 54.5 | CB 8, CB 14, CB 15, CB 17, CB 18 |
| 3 | Eastern Parkway | continues → continues | T1 | 17 | 36.5 | CB 8, CB 16 |
| 4 | Utica Avenue | Empire Boulevard → Fulton Street | T1 | 25 | 27.5 | CB 3, CB 8 |
| 5 | Rogers Avenue | Newkirk Avenue → Sterling Street | T1 | 25 | 24.5 | CB 17 |
| 6 | Albany Avenue | Snyder Avenue → Crown Street | T1 | 18 | 20.0 | CB 17 |
| 7 | New York Avenue | continues → Herkimer Street | T1 | 25 | 15.0 | CB 3, CB 8 |
| 8 | New York Avenue | Church Avenue → East New York Avenue | T1 | 13 | 14.5 | CB 17 |
| 9 | Rogers Avenue | Carroll Street → Bergen Street | T1 | 13 | 13.5 | CB 8 |
| 11 | Clarkson Avenue | Flatbush Avenue → New York Avenue | T1 | 4 | 10.5 | CB 17 |
