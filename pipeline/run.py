"""Run the whole pipeline: fetch, bike crashes, match, lane status, score."""
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.areas import assign_blocks, assign_crashes, load_areas
from pipeline.bike_crashes import build_bike_crashes, build_bike_persons
from pipeline.fetch import SOURCES, download_lion, fetch_sources, read_lion
from pipeline.lane_status import enrich
from pipeline.matching import load_segments, match
from pipeline.scoring import current_facility, score_blocks, scoring_windows
from pipeline.stretches import build_stretches, street_totals

logger = logging.getLogger(__name__)

COUNT_KEYS = [
    "candidate_crashes", "bike_riders", "riders_killed", "bike_crashes",
    "match_high", "match_medium", "match_low", "unmatched_no_coords", "unmatched_too_far",
    "lane_none", "lane_paint", "lane_sharrow", "lane_protected", "lane_unknown",
    "blocks", "ranked_blocks", "tier1_blocks", "tier2_blocks", "stretches",
]


@dataclass
class RunResult:
    bike_persons: pd.DataFrame
    bike_crashes: pd.DataFrame
    enriched: pd.DataFrame
    blocks: pd.DataFrame
    stretches: pd.DataFrame
    streets: pd.DataFrame
    gap_blocks: pd.DataFrame
    areas: gpd.GeoDataFrame
    data_date: date
    window_start: date
    recent_start: date
    counts: dict[str, int] = field(default_factory=dict)
    source_rows: dict[str, int] = field(default_factory=dict)  # raw row count per source, for meta.json
    routes: pd.DataFrame | None = None  # raw bike routes, for tiles
    segments: gpd.GeoDataFrame | None = None  # LION snap layer (EPSG:2263), for tiles


def _as_of_filter(df: pd.DataFrame, as_of: date | None) -> pd.DataFrame:
    if as_of is None:
        return df
    return df[df["crash_date"].str[:10] <= as_of.isoformat()].reset_index(drop=True)


def _count(series: pd.Series, value) -> int:
    return int((series == value).sum())


def _with_lion_attrs(gap_blocks: pd.DataFrame, lion: pd.DataFrame) -> pd.DataFrame:
    """Add posted_speed and travel_lanes (Int64, null when LION has none) to the gap blocks."""
    snap = lion.drop_duplicates("segmentid").set_index("segmentid")
    out = gap_blocks.copy()
    for col, src in (("posted_speed", "posted_speed"), ("travel_lanes", "number_travel_lanes")):
        out[col] = pd.to_numeric(out["segmentid"].map(snap[src]), errors="coerce").astype("Int64")
    return out


def run(out_dir: Path, raw_dir: Path | None, lion_cache: Path, as_of: date | None = None,
        lion_path: Path | None = None) -> RunResult:
    """lion_path overrides the LION download (tests)."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    src = fetch_sources(raw_dir)
    crashes = _as_of_filter(src["crashes"], as_of)
    persons = _as_of_filter(src["persons"], as_of)
    vehicles = _as_of_filter(src["vehicles"], as_of)
    routes = src["routes"]

    bike_persons = build_bike_persons(persons, vehicles)
    bike_crashes = build_bike_crashes(bike_persons, crashes)
    if bike_crashes.empty:
        raise ValueError("no bike crashes found")

    lion = read_lion(lion_path if lion_path is not None else download_lion(lion_cache))
    segments = load_segments(lion)
    m = match(bike_crashes, segments)
    enriched = enrich(bike_crashes, m, routes)

    data_date = date.fromisoformat(bike_crashes["crash_date"].str[:10].max())
    window_start, recent_start = scoring_windows(data_date)
    blocks = score_blocks(enriched, lion, routes, window_start, recent_start)
    areas = load_areas(src["council"], src["community"])
    blocks = assign_blocks(blocks, areas)
    enriched = assign_crashes(enriched, areas)
    stretches, seg_to_stretch, gap_blocks = build_stretches(
        blocks, lion, current_facility(routes), areas=areas)
    gap_blocks = _with_lion_attrs(gap_blocks, lion)
    streets = street_totals(blocks, stretches)
    blocks["stretch_id"] = blocks["segmentid"].map(seg_to_stretch).astype(object)
    blocks["stretch_id"] = blocks["stretch_id"].where(blocks["stretch_id"].notna(), None)

    conf, reason, lane = enriched["match_confidence"], enriched["match_reason"], enriched["facility_at_crash"]
    rank = pd.to_numeric(blocks["priority_rank"])
    tier = pd.to_numeric(blocks["tier"])
    counts = {
        "candidate_crashes": len(crashes),
        "bike_riders": len(bike_persons),
        "riders_killed": _count(bike_persons["person_injury"], "Killed"),
        "bike_crashes": len(bike_crashes),
        "match_high": _count(conf, "high"),
        "match_medium": _count(conf, "medium"),
        "match_low": _count(conf, "low"),
        "unmatched_no_coords": _count(reason, "no_coordinates"),
        "unmatched_too_far": _count(reason, "no_street_within_30m"),
        "lane_none": _count(lane, "none"),
        "lane_paint": _count(lane, "paint"),
        "lane_sharrow": _count(lane, "sharrow"),
        "lane_protected": _count(lane, "protected"),
        "lane_unknown": _count(lane, "unknown"),
        "blocks": len(blocks),
        "ranked_blocks": int(rank.notna().sum()),
        "tier1_blocks": int(((tier == 1) & rank.notna()).sum()),
        "tier2_blocks": int(((tier == 2) & rank.notna()).sum()),
        "stretches": len(stretches),
    }
    assert list(counts) == COUNT_KEYS
    source_rows = {name: len(src[name]) for name in SOURCES} | {"lion": len(lion)}
    return RunResult(bike_persons, bike_crashes, enriched, blocks, stretches, streets, gap_blocks, areas,
                     data_date, window_start, recent_start, counts, source_rows, routes, segments)
