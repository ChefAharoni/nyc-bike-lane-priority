import csv
import dataclasses
import json
from datetime import datetime, timezone

import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString

from pipeline.contract import CRASH_COLUMNS, load_sources, write_contract
from pipeline.run import run
from test_run import raw_and_lion  # noqa: F401  (pytest fixture)

# Field names of the interfaces in site/src/lib/types.ts, kept here on purpose.
TOTALS = ["crashes_5y", "injured_5y", "killed_5y", "lane_at_crash_5y", "ranked_blocks", "tier1_blocks",
          "tier2_blocks", "stretches", "shared_stretches"]
META = ["data_date", "built_at", "window_start", "recent_start", "sources", "counts", "citywide", "unassigned"]
AREA = ["kind", "id", "name", "borough", "bbox", "totals"]
BLOCK = ["segmentid", "street", "borough", "current_facility", "tier", "rank", "rank_in_tier", "score",
         "crashes_5y", "injured_5y", "killed_5y", "crashes_no_lane_5y", "crashes_all_years",
         "last_crash_date", "posted_speed", "travel_lanes", "cb", "cd", "area_by_nearest", "stretch_id", "mid"]
STRETCH = ["stretch_id", "street", "borough", "tier", "rank", "from_street", "to_street", "blocks",
           "segmentids", "gap_segmentids", "score", "crashes_5y", "injured_5y", "killed_5y",
           "crashes_no_lane_5y", "last_crash_date", "cbs", "cds", "bbox"]
STREET = ["street_key", "street", "borough", "tier", "rank", "score", "blocks", "crashes_5y", "injured_5y",
          "killed_5y", "stretch_ids", "cbs", "cds"]
SOURCES = {k: "2026-11-01T00:00:00+00:00" for k in
           ("crashes", "persons", "vehicles", "routes", "council", "community", "lion")}


def _no_nan(token):
    raise ValueError(f"non-finite number {token}")


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=_no_nan)


@pytest.fixture
def result(tmp_path, raw_and_lion):  # noqa: F811
    raw, lion_path = raw_and_lion
    from datetime import date
    return run(tmp_path / "out", raw, tmp_path / "lion_cache", date(2026, 11, 15), lion_path=lion_path)


def test_contract_files_exist_and_parse(tmp_path, result):
    out = tmp_path / "contract"
    write_contract(result, out, sources=SOURCES, built_at=datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc))
    for name in ["meta.json", "areas.json", "areas.geojson", "blocks.json", "stretches.json", "streets.json",
                 "crashes/citywide.csv", "crashes/cb-101.csv", "crashes/cd-40.csv"]:
        assert (out / name).exists(), name

    meta = _load(out / "meta.json")
    assert list(meta) == META and list(meta["citywide"]) == TOTALS and list(meta["unassigned"]) == TOTALS
    assert meta["built_at"] == "2026-11-24T12:00:00+00:00" and meta["sources"] == SOURCES
    assert meta["data_date"] == "2025-03-01" and meta["window_start"] == "2020-03-01"
    for k in ["rows_crashes", "rows_persons", "rows_vehicles", "rows_routes", "rows_council",
              "rows_community", "rows_lion", "stretches"]:
        assert isinstance(meta["counts"][k], int), k
    assert meta["counts"]["rows_lion"] == 2 and meta["counts"]["rows_council"] == 1

    areas = _load(out / "areas.json")
    assert sorted(areas) == ["cb", "cd"] and len(areas["cb"]) == 1 and len(areas["cd"]) == 1
    assert list(areas["cb"][0]) == AREA and list(areas["cb"][0]["totals"]) == TOTALS
    assert areas["cb"][0]["name"] == "Manhattan CB 1" and areas["cb"][0]["borough"] == "Manhattan"
    assert areas["cd"][0]["name"] == "Council District 40" and areas["cd"][0]["borough"] is None

    geo = _load(out / "areas.geojson")
    assert len(geo["features"]) == 2
    for f in geo["features"]:
        assert list(f["properties"]) == ["kind", "id", "name"]
        a = next(a for a in areas[f["properties"]["kind"]] if a["id"] == f["properties"]["id"])
        pts = shapely.get_coordinates(shapely.geometry.shape(f["geometry"]))
        assert a["bbox"] == [pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()]
        assert all(round(v, 6) == v for v in pts.ravel())

    blocks = _load(out / "blocks.json")
    assert len(blocks) == 2 and all(list(b) == BLOCK for b in blocks)
    ranks = [b["rank"] for b in blocks]
    ranked = [r for r in ranks if r is not None]
    assert ranks[:len(ranked)] == ranked == sorted(ranked)
    assert all(isinstance(b["score"], (int, float)) and len(b["mid"]) == 2 for b in blocks)
    assert all((b["tier"] is None) == (b["rank"] is None) == (b["rank_in_tier"] is None) for b in blocks)
    for s in _load(out / "stretches.json"):
        assert list(s) == STREET[:0] + STRETCH
    for s in _load(out / "streets.json"):
        assert list(s) == STREET

    with open(out / "crashes/citywide.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == CRASH_COLUMNS and len(rows) - 1 == meta["citywide"]["crashes_5y"]
    dates = [r[1] for r in rows[1:]]
    assert dates == sorted(dates)
    with open(out / "crashes/cb-101.csv", newline="", encoding="utf-8") as f:
        assert len(list(csv.reader(f))) - 1 == areas["cb"][0]["totals"]["crashes_5y"]


def test_gap_blocks_are_written_and_sorted_last(tmp_path, result):
    gap = pd.DataFrame([{
        "segmentid": "0000099", "street": "BROADWAY", "borough": "Manhattan", "current_facility": "none",
        "cb": "101", "cd": "40", "geometry": shapely.from_geojson(json.dumps(
            {"type": "LineString", "coordinates": [[-74.0, 40.7], [-74.0, 40.71]]})),
        "mid_lat": 40.705, "mid_lon": -74.0, "area_by_nearest": False, "stretch_id": "S0000001",
        "posted_speed": pd.NA, "travel_lanes": 2,
    }])
    res = dataclasses.replace(result, gap_blocks=gap)
    write_contract(res, tmp_path / "c", sources=SOURCES)
    blocks = _load(tmp_path / "c/blocks.json")
    assert [b["segmentid"] for b in blocks][-1] == "0000099"
    g = blocks[-1]
    assert g["rank"] is None and g["tier"] is None and g["rank_in_tier"] is None and g["score"] == 0
    assert g["crashes_all_years"] == 0 and g["last_crash_date"] is None
    assert g["posted_speed"] is None and g["travel_lanes"] == 2 and g["mid"] == [-74.0, 40.705]
    assert g["stretch_id"] == "S0000001" and g["cb"] == "101" and g["area_by_nearest"] is False


def test_unranked_block_has_no_tier_even_with_internal_tier(tmp_path, result):
    b = result.blocks.copy()
    assert b["tier"].notna().any()
    b.loc[b.index[0], ["priority_rank", "rank_in_tier"]] = [None, None]  # tier column stays set internally
    write_contract(dataclasses.replace(result, blocks=b), tmp_path / "c", sources=SOURCES)
    blocks = _load(tmp_path / "c/blocks.json")
    unranked = [x for x in blocks if x["rank"] is None]
    assert unranked and all(x["tier"] is None and x["rank_in_tier"] is None for x in unranked)
    assert all(x["tier"] in (1, 2) for x in blocks if x["rank"] is not None)


def test_load_sources_uses_cache_and_converts_dates(tmp_path):
    calls = []

    class Resp:
        status_code = 200

        def __init__(self, ts):
            self.ts = ts
        def raise_for_status(self): pass
        def json(self): return {"rowsUpdatedAt": self.ts, "viewLastModified": self.ts + 86400}

    class Session:
        def get(self, url, params=None, headers=None, timeout=None):
            calls.append(url)
            return Resp(1762000000)

    s = load_sources(tmp_path, session=Session())
    assert len(calls) == 7 and s["lion"] == "2025-11-02T12:26:40+00:00" and s["routes"] == "2025-11-01T12:26:40+00:00"
    assert json.loads((tmp_path / "sources.json").read_text()) == s
    assert load_sources(tmp_path, session=Session()) == s and len(calls) == 7  # served from the cache


def test_stretch_segmentids_include_gap_blocks():
    from pipeline.contract import _stretch_records
    st = pd.DataFrame([{c: None for c in STRETCH} | {
        "stretch_id": "S1", "segmentids": ["0000003", "0000001"], "gap_segmentids": ["0000002"], "blocks": 3}])
    rec = _stretch_records(st)[0]
    assert rec["segmentids"] == ["0000001", "0000002", "0000003"] and rec["gap_segmentids"] == ["0000002"]
    assert rec["blocks"] == len(rec["segmentids"])
