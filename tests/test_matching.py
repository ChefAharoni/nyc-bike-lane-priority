import geopandas as gpd
import pandas as pd
import pytest
import shapely
from shapely.geometry import LineString, Point

from pipeline.matching import load_segments, match, norm_street

# Origin in EPSG:2263 feet (Manhattan-ish); two streets cross at (X0, Y0).
X0, Y0 = 987000.0, 210000.0


def _geojson(*coords):
    g = gpd.GeoSeries([LineString(coords)], crs="EPSG:2263").to_crs(4326)
    return shapely.to_geojson(g.values[0])


def _seg(sid, street, coords, nonped="", rb="B"):
    return {"segmentid": sid, "street": street, "featuretyp": "0", "rb_layer": rb, "nonped": nonped,
            "lboro": "1", "nodeidfrom": "1", "nodeidto": "2", "geometry": _geojson(*coords)}


def _lion(rows, index=None):
    df = pd.DataFrame(rows, dtype=object)
    if index is not None:
        df.index = index
    return df


def _latlon(x, y):
    p = gpd.GeoSeries([Point(x, y)], crs="EPSG:2263").to_crs(4326).iloc[0]
    return str(p.y), str(p.x)


def _crash(cid, x=None, y=None, on=None, off=None):
    lat, lon = (None, None) if x is None else _latlon(x, y)
    return {"collision_id": cid, "latitude": lat, "longitude": lon,
            "on_street_name": on, "off_street_name": off}


def _no_nan(df):
    # None is fine (JSON null); a float NaN is not
    return not any(isinstance(v, float) and v != v for v in df.to_numpy().ravel())


def _crashes(rows, index=None):
    df = pd.DataFrame(rows, dtype=object)
    if index is not None:
        df.index = index
    return df


@pytest.fixture
def grid():
    return _lion([
        _seg("0000001", "BROADWAY", [(X0 - 500, Y0), (X0 + 500, Y0)]),
        _seg("0000002", "WEST 20 STREET", [(X0, Y0 - 500), (X0, Y0 + 500)]),
    ])


def test_norm_street():
    assert norm_street("E 14th St") == "EAST14STREET"
    assert norm_street("DE KALB AVE") == norm_street("DEKALB AVENUE") == "DEKALBAVENUE"
    assert norm_street("ST NICHOLAS AVE") == "SAINTNICHOLASAVENUE"
    assert norm_street("34-09  83 STREET", address=True) == "83STREET"
    assert norm_street(None) is None


def test_load_segments_tolerates_null_nonped():
    lion = _lion([_seg("0000001", "BROADWAY", [(X0, Y0), (X0 + 100, Y0)], nonped=None),
                  _seg("0000002", "BROADWAY", [(X0, Y0), (X0 + 100, Y0)], nonped=" V ")])
    segs = load_segments(lion)
    assert segs.crs.to_epsg() == 2263
    assert list(segs.columns[:4]) == ["segmentid", "street", "nonped", "names"]
    assert pd.isna(segs["nonped"].iloc[0]) and segs["nonped"].iloc[1] == "V"


def test_intersection_crash_takes_named_street(grid):
    out = match(_crashes([_crash("c1", X0, Y0, on="WEST 20 STREET")]), load_segments(grid))
    r = out.iloc[0]
    assert (r["segmentid"], r["match_confidence"], r["match_reason"]) == ("0000002", "high", "name_and_distance")
    assert r["matched_street"] == "WEST 20 STREET" and r["name_source"] == "on_street"


def test_closer_other_street_gives_medium(grid):
    # 40 ft from the named street (x = X0), 5 ft from the cross street (y = Y0)
    out = match(_crashes([_crash("c1", X0 + 40, Y0 + 5, on="WEST 20 STREET")]), load_segments(grid))
    r = out.iloc[0]
    assert (r["segmentid"], r["match_confidence"], r["match_reason"]) == ("0000002", "medium", "name_farther")
    assert r["candidates"] == 2


def test_no_name_gives_low_and_avoids_highway():
    lion = _lion([
        _seg("0000001", "FDR DRIVE", [(X0 - 500, Y0), (X0 + 500, Y0)], nonped="V"),
        _seg("0000002", "BROADWAY", [(X0 - 500, Y0 + 30), (X0 + 500, Y0 + 30)]),
    ])
    out = match(_crashes([_crash("c1", X0, Y0 + 5)]), load_segments(lion))
    r = out.iloc[0]
    assert (r["segmentid"], r["match_confidence"], r["match_reason"], r["name_source"]) == \
        ("0000002", "low", "nearest_only", "none")


def test_corner_tie_keeps_other_block():
    lion = _lion([
        _seg("0000001", "BROADWAY", [(X0 - 500, Y0), (X0, Y0)]),
        _seg("0000002", "BROADWAY", [(X0, Y0), (X0 + 500, Y0)]),
    ])
    out = match(_crashes([_crash("c1", X0, Y0, on="BROADWAY")]), load_segments(lion))
    r = out.iloc[0]
    assert r["match_confidence"] == "high"
    assert {r["segmentid"], r["tie_segmentid"]} == {"0000001", "0000002"}


def test_unmatched_reasons(grid):
    out = match(_crashes([_crash("c1"), _crash("c2", X0 + 200, Y0 + 200, on="BROADWAY")]), load_segments(grid))
    assert out["match_reason"].tolist() == ["no_coordinates", "no_street_within_30m"]
    assert out["match_confidence"].tolist() == ["unmatched", "unmatched"]
    assert out["candidates"].tolist() == [0, 0]
    assert _no_nan(out)
    assert out.loc[0, "segmentid"] is None and out.loc[1, "tie_segmentid"] is None


def test_matched_rows_have_no_nan(grid):
    out = match(_crashes([_crash("c1", X0, Y0, on="BROADWAY")]), load_segments(grid))
    assert _no_nan(out)
    assert out.loc[0, "tie_segmentid"] is None


def test_index_alignment():
    # Several well-separated blocks, listed in a shuffled order with a non-default index in both inputs
    n = 6
    rows = [_seg(f"{i + 1:07d}", f"STREET {i}", [(X0, Y0 + i * 1000), (X0 + 500, Y0 + i * 1000)])
            for i in range(n)]
    lion = _lion(rows[::-1], index=[40, 7, 99, 3, 12, 55])
    # include a duplicate (other roadbed) of one segment so drop_duplicates leaves a gap in the index
    dup = _lion([_seg("0000003", "STREET 2", [(X0, Y0 + 2000), (X0 + 500, Y0 + 2000)])], index=[41])
    lion = pd.concat([lion.iloc[:2], dup, lion.iloc[2:]])
    crashes = _crashes([_crash(f"c{i}", X0 + 250, Y0 + i * 1000 + 3) for i in range(n)],
                       index=[5, 2, 100, 0, 17, 9])
    out = match(crashes, load_segments(lion))
    assert out["collision_id"].tolist() == [f"c{i}" for i in range(n)]
    assert out["segmentid"].tolist() == [f"{i + 1:07d}" for i in range(n)]
    assert out["matched_street"].tolist() == [f"STREET {i}" for i in range(n)]
