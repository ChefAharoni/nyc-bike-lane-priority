import pandas as pd

from pipeline.lane_status import enrich, facility_on, on_street_routes


def _route(sid, cls="II", onoff="ON", status="Current", inst="2020-01-01T00:00:00.000", ret=None, ft="Standard"):
    return {"segmentid": sid, "onoffst": onoff, "facilitycl": cls, "status": status,
            "instdate": inst, "ret_date": ret, "ft_facilit": ft, "tf_facilit": None}


def _routes(*rows):
    return pd.DataFrame(list(rows), dtype=object)


def _crash(cid, date="2022-06-01T00:00:00.000"):
    return {"collision_id": cid, "crash_date": date, "latitude": None, "longitude": None,
            "on_street_name": "MAIN ST"}


def _match(cid, sid="0000001", tie=None, conf="high", reason="snapped"):
    return {"collision_id": cid, "segmentid": sid, "matched_street": "MAIN STREET", "tie_segmentid": tie,
            "match_distance_ft": 5.0, "match_confidence": conf, "match_reason": reason,
            "name_source": "on", "candidates": 1}


def _run(crashes, matches, routes):
    return enrich(pd.DataFrame(crashes, dtype=object), pd.DataFrame(matches, dtype=object), routes).set_index("collision_id")


def test_on_street_routes_pads_ids():
    r = on_street_routes(_routes(_route(" 12")))
    assert r["segmentid"].tolist() == ["0000012"]


def test_lane_installed_after_crash_is_none():
    out = _run([_crash("1", "2019-06-01T00:00:00.000")], [_match("1")], _routes(_route("0000001")))
    assert out.loc["1", "facility_at_crash"] == "none"
    assert out.loc["1", "protection_class"] == "None"


def test_active_lane_reports_detail_and_install_date():
    out = _run([_crash("1")], [_match("1")], _routes(_route("1")))
    row = out.loc["1"]
    assert row["facility_at_crash"] == "paint"
    assert row["facility_detail"] == "Standard"
    assert row["lane_installed"] == "2020-01-01"
    assert row["protection_class"] == "Unprotected"
    assert row["crash_year"] == 2022


def test_retired_before_crash_is_none_retired_after_counts():
    routes = _routes(_route("0000001", status="Retired", ret="2023-01-01T00:00:00.000"))
    out = _run([_crash("1", "2022-06-01T00:00:00.000"), _crash("2", "2023-06-01T00:00:00.000")],
               [_match("1"), _match("2")], routes)
    assert out.loc["1", "facility_at_crash"] == "paint"
    assert out.loc["2", "facility_at_crash"] == "none"


def test_retired_without_date_never_counts():
    routes = _routes(_route("0000001", status="Retired", ret=None))
    out = _run([_crash("1")], [_match("1")], routes)
    assert out.loc["1", "facility_at_crash"] == "none"


def test_off_street_route_ignored():
    out = _run([_crash("1")], [_match("1")], _routes(_route("0000001", onoff="OFF")))
    assert out.loc["1", "facility_at_crash"] == "none"


def test_overlap_strongest_wins():
    routes = _routes(_route("0000001", cls="II"), _route("0000001", cls="I", ft="Protected Path"))
    out = _run([_crash("1")], [_match("1")], routes)
    assert out.loc["1", "facility_at_crash"] == "protected"
    assert out.loc["1", "protection_class"] == "Protected"
    assert out.loc["1", "facility_detail"] == "Protected Path"


def test_corner_blocks_differ_downgrades():
    routes = _routes(_route("0000001", cls="I"))
    out = _run([_crash("1")], [_match("1", tie="0000002")], routes)
    row = out.loc["1"]
    assert row["tie_facility"] == "none"
    assert row["match_confidence"] == "medium"
    assert row["match_reason"] == "corner_blocks_differ"


def test_corner_blocks_agree_keeps_confidence():
    routes = _routes(_route("0000001"), _route("0000002"))
    out = _run([_crash("1")], [_match("1", tie="0000002")], routes)
    assert out.loc["1", "tie_facility"] == "paint"
    assert out.loc["1", "match_confidence"] == "high"


def test_unmatched_is_unknown():
    m = _match("1", sid=None, conf="unmatched", reason="no_candidates")
    out = _run([_crash("1")], [m], _routes(_route("0000001")))
    row = out.loc["1"]
    assert row["facility_at_crash"] == "unknown"
    assert row["protection_class"] == "Unknown"
    assert row["lane_installed"] is None


def test_no_nan_and_platform_columns_dropped():
    out = enrich(pd.DataFrame([_crash("1"), _crash("2", None)], dtype=object),
                 pd.DataFrame([_match("1"), _match("2", sid=None, conf="unmatched")], dtype=object),
                 _routes(_route("0000001")))
    assert "location" not in out.columns and "crash_title" not in out.columns
    row2 = out[out["collision_id"] == "2"].iloc[0]
    assert row2["crash_year"] is None
    assert not any(isinstance(v, float) and v != v for v in out.to_numpy().ravel())
