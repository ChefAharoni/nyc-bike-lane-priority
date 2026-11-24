"""Write the data contract files (docs/data-contract.md) that the static site reads. Tiles and
snapshots are written elsewhere."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import shapely
from shapely.geometry import mapping

from pipeline.config import BASE_URL, DATASETS
from pipeline.fetch import _get
from pipeline.run import RunResult
from pipeline.totals import area_totals, citywide, empty_totals, unassigned, window_crashes

logger = logging.getLogger(__name__)

SIMPLIFY_FT = 20
CRASH_COLUMNS = ["collision_id", "crash_date", "crash_time", "latitude", "longitude", "on_street_name",
                 "cross_street_name", "matched_street", "segmentid", "match_confidence", "lane_at_crash",
                 "riders_injured", "riders_killed", "bike_types"]
BLOCK_ORDER = ["segmentid", "street", "borough", "current_facility", "tier", "rank", "rank_in_tier", "score",
               "crashes_5y", "injured_5y", "killed_5y", "crashes_no_lane_5y", "crashes_all_years",
               "last_crash_date", "posted_speed", "travel_lanes", "cb", "cd", "area_by_nearest",
               "stretch_id", "mid"]
STRETCH_COLS = ["stretch_id", "street", "borough", "tier", "rank", "from_street", "to_street", "blocks",
                "segmentids", "gap_segmentids", "score", "crashes_5y", "injured_5y", "killed_5y",
                "crashes_no_lane_5y", "last_crash_date", "cbs", "cds", "bbox"]
STREET_COLS = ["street_key", "street", "borough", "tier", "rank", "score", "blocks", "crashes_5y",
               "injured_5y", "killed_5y", "stretch_ids", "cbs", "cds"]


def _py(v):
    """Plain JSON-safe Python value: numpy and pandas scalars become int/float/bool, missing becomes None."""
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_py(x) for x in v]
    if isinstance(v, dict):
        return {k: _py(x) for k, x in v.items()}
    if v is None or v is pd.NA or v is pd.NaT or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer, int)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return float(v)
    return v


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, allow_nan=False, separators=(",", ":"), ensure_ascii=False),
                    encoding="utf-8")


def load_sources(raw_dir: Path | None, session=None) -> dict[str, str]:
    """Last-updated time (ISO UTC) of each dataset, from the Socrata view metadata. Cached in
    raw_dir/sources.json when raw_dir is set."""
    cache = Path(raw_dir) / "sources.json" if raw_dir is not None else None
    if cache is not None and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    session = session or requests.Session()
    out = {}
    for key, ds in DATASETS.items():
        view = _get(session, f"{BASE_URL}/api/views/{ds}.json").json()
        # LION's rowsUpdatedAt is stale (the file is replaced, not updated row by row)
        ts = int(view["viewLastModified" if key == "lion" else "rowsUpdatedAt"])
        out[key] = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out), encoding="utf-8")
    return out


def _block_records(res: RunResult) -> list[dict]:
    b = res.blocks
    g = res.gap_blocks[~res.gap_blocks["segmentid"].isin(set(b["segmentid"]))] if len(res.gap_blocks) else res.gap_blocks
    recs = []
    for r in b.to_dict("records"):
        recs.append({
            "segmentid": str(r["segmentid"]), "street": r["street"], "borough": r["borough"],
            "current_facility": r["current_facility"],
            "tier": r["tier"] if r["priority_rank"] is not None else None,  # tier is null iff unranked
            "rank": r["priority_rank"], "rank_in_tier": r["rank_in_tier"], "score": float(r["score"]),
            "crashes_5y": r["crashes_5y"], "injured_5y": r["injured_5y"], "killed_5y": r["killed_5y"],
            "crashes_no_lane_5y": r["crashes_no_lane_5y"], "crashes_all_years": r["crashes_all_years"],
            "last_crash_date": r["last_crash_date"], "posted_speed": r["posted_speed"],
            "travel_lanes": r["travel_lanes"], "cb": r["cb"], "cd": r["cd"],
            "area_by_nearest": r["area_by_nearest"], "stretch_id": r["stretch_id"],
            "mid": [round(float(r["mid_lon"]), 6), round(float(r["mid_lat"]), 6)],
        })
    for r in g.to_dict("records"):  # gap blocks: no crashes ever, never ranked
        recs.append({
            "segmentid": str(r["segmentid"]), "street": r["street"], "borough": r["borough"],
            "current_facility": r["current_facility"], "tier": None, "rank": None, "rank_in_tier": None,
            "score": 0.0, "crashes_5y": 0, "injured_5y": 0, "killed_5y": 0, "crashes_no_lane_5y": 0,
            "crashes_all_years": 0, "last_crash_date": None, "posted_speed": r.get("posted_speed"),
            "travel_lanes": r.get("travel_lanes"), "cb": r["cb"], "cd": r["cd"],
            "area_by_nearest": bool(r["area_by_nearest"]), "stretch_id": r["stretch_id"],
            "mid": [round(float(r["mid_lon"]), 6), round(float(r["mid_lat"]), 6)],
        })
    recs = [_py(r) for r in recs]
    recs.sort(key=lambda r: (r["rank"] is None, r["rank"] if r["rank"] is not None else 0, r["segmentid"]))
    return [{k: r[k] for k in BLOCK_ORDER} for r in recs]


def _stretch_records(stretches: pd.DataFrame) -> list[dict]:
    """Contract Stretch records: `segmentids` lists every member, gap blocks included (the pipeline
    frame keeps ranked members and gap members apart)."""
    recs = _py(stretches[STRETCH_COLS].to_dict("records"))
    for r in recs:
        r["segmentids"] = sorted(set(r["segmentids"]) | set(r["gap_segmentids"]))
        r["blocks"] = len(r["segmentids"])
    return recs


def _area_features(areas) -> list[dict]:
    """Real boards and districts: simplified in EPSG:2263, then WGS84 with 6-decimal coordinates."""
    real = areas[~areas["is_jia"]].copy()
    real["geometry"] = real.geometry.simplify(SIMPLIFY_FT, preserve_topology=True)
    real = real.to_crs(epsg=4326)
    real["geometry"] = shapely.transform(real.geometry.to_numpy(), lambda xy: np.round(xy, 6))
    return [{"kind": r["kind"], "id": str(r["id"]), "name": r["name"], "borough": r["borough"],
             "geometry": r["geometry"]} for r in real.to_dict("records")]


def _crash_table(res: RunResult) -> pd.DataFrame:
    c = window_crashes(res.enriched, res.window_start)
    types = (res.bike_persons.groupby("collision_id")["bike_type"]
             .agg(lambda s: ";".join(sorted(s.dropna()))))
    def col(name):  # a source column some inputs lack (tiny test data) is written empty
        return c[name] if name in c.columns else pd.Series(None, index=c.index, dtype=object)

    t = pd.DataFrame({
        "collision_id": c["collision_id"], "crash_date": c["crash_date"].str[:10],
        "crash_time": c["crash_time"].astype("string").str.replace(r"^(\d):", r"0\1:", regex=True).str[:5],
        "latitude": c["latitude"], "longitude": c["longitude"],
        "on_street_name": col("on_street_name"), "cross_street_name": col("cross_street_name"),
        "matched_street": c["matched_street"], "segmentid": c["segmentid"],
        "match_confidence": c["match_confidence"], "lane_at_crash": c["lane"],
        "riders_injured": c["riders_injured"], "riders_killed": c["riders_killed"],
        "bike_types": c["collision_id"].map(types), "cb": c["cb"], "cd": c["cd"],
    })
    t = t.sort_values(["crash_date", "crash_time", "collision_id"], kind="stable")
    return t.astype(object).where(t.notna(), "")


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df[CRASH_COLUMNS].to_csv(path, index=False, lineterminator="\n", encoding="utf-8")


def write_contract(res: RunResult, out_dir: Path, sources: dict[str, str] | None = None,
                   built_at: datetime | None = None) -> None:
    """Write meta/areas/blocks/stretches/streets JSON, areas.geojson and the crash CSVs to out_dir.

    meta.unassigned is the community board version (crashes and blocks with no board); the council
    district version differs slightly and is not written. `sources` (dataset key -> ISO time) is
    injectable so tests need no network."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if sources is None:
        sources = load_sources(None)
    built_at = built_at or datetime.now(timezone.utc).replace(microsecond=0)

    per = area_totals(res.enriched, res.blocks, res.stretches, res.window_start)
    city = citywide(res.enriched, res.blocks, res.stretches, res.window_start)
    un = unassigned(res.enriched, res.blocks, res.window_start, "cb")

    counts = dict(res.counts)
    for k in ["crashes", "persons", "vehicles", "routes", "council", "community", "lion"]:
        counts[f"rows_{k}"] = int(res.source_rows.get(k, 0))
    meta = {"data_date": res.data_date.isoformat(), "built_at": built_at.isoformat(),
            "window_start": res.window_start.isoformat(), "recent_start": res.recent_start.isoformat(),
            "sources": sources, "counts": counts, "citywide": city, "unassigned": un}
    _write_json(out / "meta.json", _py(meta))

    feats = _area_features(res.areas)
    areas: dict[str, list] = {"cb": [], "cd": []}
    for f in sorted(feats, key=lambda f: f["id"]):
        x = shapely.get_coordinates(f["geometry"])
        bbox = [float(x[:, 0].min()), float(x[:, 1].min()), float(x[:, 0].max()), float(x[:, 1].max())]
        areas[f["kind"]].append({
            "kind": f["kind"], "id": f["id"], "name": f["name"], "borough": f["borough"], "bbox": bbox,
            "totals": per[f["kind"]].get(f["id"], empty_totals())})
    _write_json(out / "areas.json", _py(areas))
    _write_json(out / "areas.geojson", {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"kind": f["kind"], "id": f["id"], "name": f["name"]},
         "geometry": mapping(f["geometry"])}
        for f in sorted(feats, key=lambda f: (f["kind"], f["id"]))]})

    blocks = _block_records(res)
    _write_json(out / "blocks.json", blocks)
    _write_json(out / "stretches.json", _stretch_records(res.stretches))
    _write_json(out / "streets.json", _py(res.streets[STREET_COLS].to_dict("records")))

    crashes = _crash_table(res)
    _write_csv(out / "crashes/citywide.csv", crashes)
    for kind in ("cb", "cd"):
        for a in areas[kind]:
            _write_csv(out / f"crashes/{kind}-{a['id']}.csv", crashes[crashes[kind] == a["id"]])
    logger.info("wrote data contract to %s", out)
