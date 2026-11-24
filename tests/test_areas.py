import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, box, mapping

from pipeline.areas import assign_blocks, assign_crashes, assign_points, load_areas

import json


def _row(code, minx, maxx, key="boro_cd"):
    g = gpd.GeoSeries([box(minx, 40.60, maxx, 40.70)], crs="EPSG:4326").iloc[0]
    return {key: code, "the_geom": json.dumps(mapping(g))}


def _areas():
    community = pd.DataFrame([_row("309", -74.00, -73.95), _row("355", -73.95, -73.93),
                              _row("308", -73.93, -73.90), _row("101", -73.80, -73.79)])
    council = pd.DataFrame([_row("40.0", -74.00, -73.95, "coundist")])
    return load_areas(council, community)


def _pts(coords, index=None):
    return gpd.GeoSeries([Point(x, y) for x, y in coords], index=index, crs="EPSG:4326").to_crs(2263)


def test_names():
    a = _areas().set_index(["kind", "id"])
    assert a.loc[("cb", "309"), "name"] == "Brooklyn CB 9"
    assert a.loc[("cb", "101"), "name"] == "Manhattan CB 1"
    assert a.loc[("cb", "355"), "is_jia"] and not a.loc[("cb", "309"), "is_jia"]
    assert a.loc[("cb", "355"), "name"] == "Brooklyn park/airport area 355"
    assert a.loc[("cd", "40"), "name"] == "Council District 40" and a.loc[("cd", "40"), "borough"] is None
    assert a.crs.to_epsg() == 2263


def test_point_in_polygon():
    r = assign_points(_pts([(-73.97, 40.65)]), _areas())
    assert r.iloc[0].cb == "309" and r.iloc[0].cd == "40" and not r.iloc[0].area_by_nearest


def test_point_in_jia_goes_to_nearest_real_board():
    r = assign_points(_pts([(-73.944, 40.65), (-73.936, 40.65)]), _areas())
    assert list(r.cb) == ["309", "308"] and r.area_by_nearest.all()
    assert list(r.cd) == [None, None]  # JIA rule is cb only; cd 40 is far away


def test_point_near_but_outside_within_500ft():
    r = assign_points(_pts([(-74.0005, 40.65)]), _areas())  # about 140 ft west of 309
    assert r.iloc[0].cb == "309" and r.iloc[0].cd == "40" and not r.iloc[0].area_by_nearest


def test_point_far_outside_is_none():
    r = assign_points(_pts([(-73.70, 40.65)]), _areas())
    assert r.iloc[0].cb is None and r.iloc[0].cd is None and not r.iloc[0].area_by_nearest


def test_indices_preserved():
    idx = [7, 3, 5]
    # third point sits exactly on the 309/355 shared edge
    pts = _pts([(-73.97, 40.65), (-73.80 - 0.005, 40.65), (-73.95, 40.65)], index=idx)
    r = assign_points(pts, _areas())
    assert list(r.index) == idx and r.index.is_unique
    assert r.loc[7, "cb"] == "309" and r.loc[5, "cb"] == "309"


def test_blocks_and_crashes():
    a = _areas()
    blocks = pd.DataFrame({"mid_lat": [40.65, float("nan")], "mid_lon": [-73.97, -73.97]}, index=[4, 2])
    b = assign_blocks(blocks, a)
    assert list(b.index) == [4, 2] and b.loc[4, "cb"] == "309" and b.loc[2, "cb"] is None
    crashes = pd.DataFrame({"latitude": ["40.65", "0", None, "40.65"],
                            "longitude": ["-73.97", "0", None, "-70.0"]})
    c = assign_crashes(crashes, a)
    assert list(c.cb) == ["309", None, None, None] and list(c.cd) == ["40", None, None, None]
