import json
from datetime import date

import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import LineString, Point, box, mapping

from pipeline import fetch
from pipeline.run import COUNT_KEYS, run

X0, Y0 = 987000.0, 210000.0


def _latlon(x, y):
    p = gpd.GeoSeries([Point(x, y)], crs="EPSG:2263").to_crs(4326).iloc[0]
    return str(p.y), str(p.x)


def _crash(cid, date_, xy=None, on=None):
    lat, lon = (None, None) if xy is None else _latlon(*xy)
    return {"collision_id": cid, "crash_date": f"{date_}T00:00:00.000", "crash_time": "10:00",
            "latitude": lat, "longitude": lon, "on_street_name": on, "off_street_name": None,
            "inclusion_reason": "cyclist_count"}


def _person(cid, date_, injury="Injured", ptype="Bicyclist", vid="v1"):
    return {"collision_id": cid, "person_id": f"p-{cid}", "vehicle_id": f"{vid}-{cid}",
            "crash_date": f"{date_}T00:00:00.000", "person_type": ptype, "person_injury": injury}


def _vehicle(cid, vtype, date_, vid="v1"):
    return {"collision_id": cid, "unique_id": f"{vid}-{cid}", "vehicle_type": vtype,
            "crash_date": f"{date_}T00:00:00.000"}


def _area(key, code):
    g = gpd.GeoSeries([box(X0 - 600, Y0 - 600, X0 + 600, Y0 + 600)], crs="EPSG:2263").to_crs(4326).iloc[0]
    return {key: code, "the_geom": json.dumps(mapping(g))}


@pytest.fixture
def raw_and_lion(tmp_path):
    d1, d2, d3 = "2024-06-01", "2025-03-01", "2026-11-20"
    crashes = [
        _crash("1", d1, (X0 + 200, Y0 + 5), "BROADWAY"),
        _crash("2", d2, (X0 + 100, Y0 - 5), "BROADWAY"),
        _crash("3", d1),                                       # no coordinates
        _crash("4", d1, (X0 + 4000, Y0 + 4000), "BROADWAY"),   # nothing within range
        _crash("5", d3, (X0 + 100, Y0), "BROADWAY"),           # after as_of
        _crash("6", d1, (X0 + 5, Y0 + 200), "WEST 20 STREET"), # on a painted block
        _crash("7", d1, (X0 + 150, Y0), "BROADWAY"),           # moped, not a bike crash
    ]
    persons = [
        _person("1", d1), _person("2", d2, "Killed"), _person("3", d1), _person("4", d1),
        _person("5", d3), _person("6", d1), _person("7", d1, ptype="Other Motorized"),
    ]
    vehicles = [_vehicle(c, "Bike", d1) for c in "123456"] + [_vehicle("7", "Moped", d1)]
    routes = [{"segmentid": "0000002", "onoffst": "ON", "status": "Current", "facilitycl": "II",
               "instdate": "2020-01-01T00:00:00.000", "ret_date": None,
               "ft_facilit": "Standard", "tf_facilit": None}]
    raw = tmp_path / "raw"
    raw.mkdir()
    for name, rows in [("crashes", crashes), ("persons", persons), ("vehicles", vehicles),
                       ("routes", routes), ("council", [_area("coundist", "40")]), ("community", [_area("boro_cd", "101")])]:
        pd.DataFrame(rows, dtype=object).to_parquet(raw / f"{name}.parquet", index=False)

    cols = {k: ["0", "0"] for k in fetch.LION_KEEP if k not in ("Street", "SegmentID", "RB_Layer", "FeatureTyp")}
    lion = gpd.GeoDataFrame(
        {**cols, "SegmentID": ["0000001", "0000002"], "Street": ["BROADWAY", "WEST 20 STREET"],
         "FeatureTyp": ["0", "0"], "RB_Layer": ["B", "B"], "NonPed": ["", ""], "LBoro": [1, 1]},
        geometry=[LineString([(X0 - 500, Y0), (X0 + 500, Y0)]), LineString([(X0, Y0 - 500), (X0, Y0 + 500)])],
        crs="EPSG:2263")
    path = tmp_path / "lion.gpkg"
    lion.to_file(path, layer="lion", driver="GPKG")
    return raw, path


def test_run_on_fixtures(tmp_path, raw_and_lion, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(requests.Session, "request", boom)
    monkeypatch.setattr(requests, "get", boom)
    raw, lion_path = raw_and_lion

    res = run(tmp_path / "out", raw, tmp_path / "lion_cache", date(2026, 11, 15), lion_path=lion_path)
    c = res.counts
    assert set(c) == set(COUNT_KEYS)
    assert c["candidate_crashes"] == 6 and c["bike_riders"] == 5 and c["riders_killed"] == 1
    assert c["bike_crashes"] == 5
    assert c["bike_crashes"] == (c["match_high"] + c["match_medium"] + c["match_low"]
                                 + c["unmatched_no_coords"] + c["unmatched_too_far"])
    assert c["unmatched_no_coords"] == 1 and c["unmatched_too_far"] == 1
    assert c["bike_crashes"] == (c["lane_none"] + c["lane_paint"] + c["lane_sharrow"]
                                 + c["lane_protected"] + c["lane_unknown"])
    assert c["lane_paint"] == 1 and c["lane_unknown"] == 2
    assert res.data_date == date(2025, 3, 1)
    assert res.window_start == date(2020, 3, 1) and res.recent_start == date(2023, 3, 1)
    assert c["blocks"] == len(res.blocks) == 2
    assert set(res.areas["kind"]) == {"cb", "cd"}
    assert {"cb", "cd", "area_by_nearest"} <= set(res.blocks.columns)
    assert list(res.blocks["cb"]) == ["101", "101"] and list(res.blocks["cd"]) == ["40", "40"]
    assert {"cb", "cd"} <= set(res.enriched.columns)
    assert res.enriched.loc[res.enriched["collision_id"] == "3", ["cb", "cd"]].isna().all().all()
    assert c["stretches"] == len(res.stretches) and {"stretch_id"} <= set(res.blocks.columns)
    assert set(res.streets.columns) >= {"street_key", "stretch_ids"} and "segmentid" in res.gap_blocks.columns
