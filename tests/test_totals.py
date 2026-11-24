from datetime import date

import pandas as pd
import pytest

from pipeline.totals import LANES, area_totals, citywide, unassigned

WS = date(2021, 11, 1)


def _crash(cid, day, cb, cd, lane="none", inj=1, killed=0, lat="40.7", lon="-73.9"):
    return {"collision_id": cid, "crash_date": f"{day}T00:00:00.000", "latitude": lat, "longitude": lon,
            "riders_injured": inj, "riders_killed": killed, "facility_at_crash": lane, "cb": cb, "cd": cd,
            "match_confidence": "low"}


@pytest.fixture
def crashes():
    return pd.DataFrame([
        _crash("a", "2024-01-01", "309", "40", "none", 2, 1),
        _crash("b", "2024-02-01", "309", "40", "paint"),
        _crash("c", "2024-03-01", "308", "40", "protected"),
        _crash("d", "2025-03-01", "308", "35", "unknown", 0, 0),
        _crash("e", "2025-04-01", None, "35", "sharrow"),
        _crash("f", "2025-05-01", "309", None, "none"),
        _crash("g", "2025-06-01", None, None, "none"),
        _crash("old", "2019-01-01", "309", "40", "none", 5, 5),            # before the window
        _crash("nocoord", "2024-05-01", "309", "40", "none", lat=None, lon=None),
    ], dtype=object)


@pytest.fixture
def blocks():
    def b(sid, rank, tier, cb, cd):
        return {"segmentid": sid, "priority_rank": rank, "tier": tier, "cb": cb, "cd": cd}
    return pd.DataFrame([
        b("1", 1, 1, "309", "40"), b("2", 2, 1, "308", "40"), b("3", 3, 2, "308", "35"),
        b("4", 4, 2, None, "35"), b("5", None, None, "309", "40"), b("6", 5, 1, "309", None),
    ], dtype=object)


@pytest.fixture
def stretches():
    return pd.DataFrame([
        {"stretch_id": "S1", "cbs": ["308", "309"], "cds": ["40"]},
        {"stretch_id": "S2", "cbs": ["308"], "cds": ["35", "40"]},
        {"stretch_id": "S3", "cbs": [], "cds": ["35"]},
    ])


def _flat(t):
    out = {k: v for k, v in t.items() if k != "lane_at_crash_5y"}
    out.update({f"lane_{k}": v for k, v in t["lane_at_crash_5y"].items()})
    return out


def test_areas_plus_unassigned_equal_citywide(crashes, blocks, stretches):
    per = area_totals(crashes, blocks, stretches, WS)
    city = _flat(citywide(crashes, blocks, stretches, WS))
    crash_block = [k for k in city if k not in ("stretches", "shared_stretches")]
    assert city["crashes_5y"] == 7 and city["ranked_blocks"] == 5
    for kind in ("cb", "cd"):
        un = _flat(unassigned(crashes, blocks, WS, kind))
        for key in crash_block:
            total = sum(_flat(t)[key] for t in per[kind].values()) + un[key]
            assert total == city[key], (kind, key)
        assert un["stretches"] == 0 and un["shared_stretches"] == 0
    assert unassigned(crashes, blocks, WS, "cb")["crashes_5y"] == 2   # e and g


def test_shared_counts(crashes, blocks, stretches):
    per = area_totals(crashes, blocks, stretches, WS)
    assert per["cb"]["308"]["stretches"] == 2 and per["cb"]["308"]["shared_stretches"] == 1
    assert per["cb"]["309"]["stretches"] == 1 and per["cb"]["309"]["shared_stretches"] == 1
    assert per["cd"]["40"]["stretches"] == 2 and per["cd"]["40"]["shared_stretches"] == 1
    assert per["cd"]["35"]["stretches"] == 2 and per["cd"]["35"]["shared_stretches"] == 1
    city = citywide(crashes, blocks, stretches, WS)
    assert city["stretches"] == 3 and city["shared_stretches"] == 1   # only S1 touches >1 board


def test_window_respected(crashes, blocks, stretches):
    per = area_totals(crashes, blocks, stretches, WS)
    t = per["cb"]["309"]
    # a, b, f only: not "old" (before window), not "nocoord" (no coordinates)
    assert t["crashes_5y"] == 3 and t["injured_5y"] == 4 and t["killed_5y"] == 1
    assert t["lane_at_crash_5y"] == {"none": 2, "paint": 1, "sharrow": 0, "protected": 0, "unknown": 0}
    assert list(t["lane_at_crash_5y"]) == LANES
    assert sum(t["lane_at_crash_5y"].values()) == t["crashes_5y"]
    assert t["ranked_blocks"] == 2 and t["tier1_blocks"] == 2 and t["tier2_blocks"] == 0
    later = area_totals(crashes, blocks, stretches, date(2025, 1, 1))
    assert later["cb"]["309"]["crashes_5y"] == 1
