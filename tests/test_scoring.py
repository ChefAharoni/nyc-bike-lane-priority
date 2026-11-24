from datetime import date

import pandas as pd
import shapely
from shapely.geometry import LineString, mapping
import json

from pipeline.scoring import current_facility, score_blocks, scoring_windows

W, R = date(2021, 11, 1), date(2024, 11, 1)


def _crash(cid, sid, date_="2025-01-10", inj=1, killed=0, conf="high", prot="None"):
    return {"collision_id": cid, "crash_date": f"{date_}T00:00:00.000", "segmentid": sid,
            "match_confidence": conf, "protection_class": prot,
            "riders_injured": inj, "riders_killed": killed}


def _lion(sid, lboro="3", street="MAIN STREET"):
    line = LineString([(-73.95, 40.65), (-73.95, 40.651)])
    return {"segmentid": sid, "street": street, "featuretyp": "0", "lboro": lboro,
            "posted_speed": "25", "number_travel_lanes": "2", "geometry": json.dumps(mapping(line))}


def _route(sid, cls):
    return {"segmentid": sid, "onoffst": "ON", "status": "Current", "facilitycl": cls}


def _run(crashes, sids, routes=(), lboro="3"):
    lion = pd.DataFrame([_lion(s, lboro) for s in sids], dtype=object)
    r = pd.DataFrame(list(routes) or [{"segmentid": None, "onoffst": None, "status": None, "facilitycl": None}],
                     dtype=object)
    out = score_blocks(pd.DataFrame(crashes, dtype=object), lion, r, W, R)
    return out.set_index("segmentid")


def test_windows():
    assert scoring_windows(date(2026, 11, 15)) == (date(2021, 11, 1), date(2024, 11, 1))
    assert scoring_windows(date(2027, 1, 3)) == (date(2022, 1, 1), date(2025, 1, 1))


def test_harm_weights():
    out = _run([_crash(1, "0000001", "2025-01-10", inj=0, killed=1), _crash(2, "0000001", "2022-01-10", inj=1)], ["0000001"])
    assert out.loc["0000001", "score"] == 10.5
    assert out.loc["0000001", "killed_5y"] == 1 and out.loc["0000001", "crashes_5y"] == 2


def test_low_confidence_and_protected_not_scored():
    out = _run([_crash(1, "0000001", conf="low"), _crash(2, "0000001", prot="Protected"),
                _crash(3, "0000001", prot="Unknown"), _crash(4, "0000001", date_="2020-01-01")], ["0000001"])
    assert out.loc["0000001", "score"] == 0 and out.loc["0000001", "crashes_5y"] == 0
    assert out.loc["0000001", "crashes_all_years"] == 4
    assert pd.isna(out.loc["0000001", "priority_rank"])


def test_tier1_above_tier2():
    out = _run([_crash(1, "0000001", inj=100), _crash(2, "0000002", inj=1)], ["0000001", "0000002"], routes=[_route("0000001", "II")])
    assert out.loc["0000001", "tier"] == 2 and out.loc["0000002", "tier"] == 1
    assert out.loc["0000002", "priority_rank"] == 1 and out.loc["0000001", "priority_rank"] == 2
    assert out.loc["0000001", "rank_in_tier"] == 1 and out.loc["0000001", "current_facility"] == "paint"


def test_tie_breakers():
    crashes = [_crash(1, "0000004", inj=10), _crash(2, "0000003", inj=0, killed=1),
               _crash(3, "0000002", inj=5), _crash(4, "0000002", inj=5), _crash(5, "0000001", inj=5), _crash(6, "0000001", inj=5),
               _crash(7, "0000005", inj=10)]
    out = _run(crashes, [f"000000{i}" for i in range(1, 6)])
    # all score 10: C has a death, A/B have 2 crashes (A first by id), then D/E (D first)
    ranked = out.sort_values("priority_rank").index.tolist()
    assert ranked == ["0000003", "0000001", "0000002", "0000004", "0000005"]


def test_zero_score_unranked():
    out = _run([_crash(1, "0000001", inj=0)], ["0000001"])
    assert pd.isna(out.loc["0000001", "priority_rank"]) and pd.isna(out.loc["0000001", "rank_in_tier"])


def test_protected_today_unranked():
    out = _run([_crash(1, "0000001")], ["0000001"], routes=[_route("0000001", "I")])
    assert out.loc["0000001", "current_facility"] == "protected" and pd.isna(out.loc["0000001", "tier"])
    assert pd.isna(out.loc["0000001", "priority_rank"])


def test_borough_from_int_lboro():
    for v in ["3", 3, "3.0"]:
        assert _run([_crash(1, "0000001")], ["0000001"], lboro=v).loc["0000001", "borough"] == "Brooklyn"


def test_output_types():
    out = score_blocks(pd.DataFrame([_crash(1, "0000001")], dtype=object),
                       pd.DataFrame([_lion("0000001")], dtype=object),
                       pd.DataFrame([_route("0000001", "II")], dtype=object), W, R)
    row = out.iloc[0]
    assert type(row["tier"]) is int and type(row["priority_rank"]) is int and type(row["posted_speed"]) is int
    assert type(row["score"]) is float and type(row["mid_lat"]) is float
    assert row["last_crash_date"] == "2025-01-10"
    assert isinstance(row["geometry"], shapely.LineString)
    assert 40.65 < row["mid_lat"] < 40.651


def test_current_facility_pads_and_dedupes():
    r = pd.DataFrame([_route(" 145699", "I"), _route("0145699", "II")], dtype=object)
    assert current_facility(r).to_dict() == {"0145699": "protected"}
