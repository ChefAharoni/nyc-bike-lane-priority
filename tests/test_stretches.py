import json

import pandas as pd
from shapely.geometry import LineString, mapping

from pipeline.stretches import build_stretches, street_totals

IDS = ["0000001", "0000002", "0000003", "0000004", "0000005", "0000006"]  # A..F, nodes 1..7


def _line(i):
    return LineString([(-73.95 + i * 0.001, 40.65), (-73.95 + (i + 1) * 0.001, 40.65)])


def _lion(streets=None, extra=()):
    rows = []
    for i, sid in enumerate(IDS):
        rows.append({"segmentid": sid, "street": (streets or {}).get(sid, "EMPIRE BLVD"), "lboro": "3",
                     "nodeidfrom": str(i + 1), "nodeidto": str(i + 2), "featuretyp": "0", "rb_layer": "B",
                     "geometry": json.dumps(mapping(_line(i)))})
    rows += list(extra)
    return pd.DataFrame(rows)


def _block(i, tier=1, score=10.0, street="EMPIRE BLVD", cb="309", cd="40", killed=0, crashes=2):
    return {"segmentid": IDS[i], "street": street, "borough": "Brooklyn", "tier": tier,
            "priority_rank": i + 1, "score": score, "crashes_5y": crashes, "injured_5y": crashes,
            "killed_5y": killed, "crashes_no_lane_5y": crashes, "last_crash_date": f"2026-01-0{i + 1}",
            "cb": cb, "cd": cd, "geometry": _line(i)}


def _run(ranked, current=None, lion=None, gap_blocks=2, blocks=None):
    b = pd.DataFrame(blocks if blocks is not None else [_block(i) for i in ranked])
    cur = pd.Series(current or {}, dtype=object)
    return build_stretches(b, lion if lion is not None else _lion(), cur, gap_blocks=gap_blocks)


def test_connected_ranked_blocks_form_one_stretch():
    st, m, gaps = _run([0, 1])
    assert len(st) == 1 and st.iloc[0].blocks == 2 and st.iloc[0].stretch_id == "S0000001"
    assert st.iloc[0].segmentids == IDS[:2] and st.iloc[0].gap_segmentids == []
    assert set(m.index) == set(IDS[:2]) and gaps.empty
    assert st.iloc[0].to_street is None and st.iloc[0].from_street is None


def test_two_gap_blocks_bridged():
    st, m, gaps = _run([0, 3])
    assert len(st) == 1
    s = st.iloc[0]
    assert s.blocks == 4 and s.gap_segmentids == [IDS[1], IDS[2]] and s.segmentids == IDS[:2][:1] + [IDS[3]]
    assert s.score == 20.0 and s.crashes_5y == 4
    assert set(m.index) == set(IDS[:4]) and set(gaps["segmentid"]) == {IDS[1], IDS[2]}
    assert {"street", "borough", "current_facility", "cb", "cd", "geometry", "mid_lat", "mid_lon"} <= set(gaps.columns)
    assert list(gaps["current_facility"]) == ["none", "none"]


def test_three_gap_blocks_split():
    st, _, gaps = _run([0, 4])
    assert len(st) == 2 and gaps.empty


def test_tier_change_splits():
    st, *_ = _run(None, blocks=[_block(0, tier=1), _block(1, tier=2)], current={IDS[1]: "paint"})
    assert len(st) == 2 and sorted(st["tier"]) == [1, 2] and st.iloc[0].tier == 1


def test_paint_gap_bridges_tier2():
    b = [_block(0, tier=2), _block(2, tier=2)]
    cur = {IDS[0]: "paint", IDS[1]: "sharrow", IDS[2]: "paint"}
    st, *_ = _run(None, blocks=b, current=cur)
    assert len(st) == 1 and st.iloc[0].gap_segmentids == [IDS[1]]


def test_protected_block_breaks_stretch():
    st, m, _ = _run([0, 2], current={IDS[1]: "protected"})
    assert len(st) == 2 and IDS[1] not in m.index


def test_spellings_grouped():
    lion = _lion({IDS[0]: "EMPIRE BOULEVARD"})
    b = [_block(0, street="EMPIRE BOULEVARD"), _block(1), _block(2)]
    st, *_ = _run(None, blocks=b, lion=lion)
    assert len(st) == 1 and st.iloc[0].street == "EMPIRE BLVD"


def test_boundary_not_split():
    st, *_ = _run(None, blocks=[_block(0, cb="308", cd="35"), _block(1, cb="309")])
    assert len(st) == 1 and st.iloc[0].cbs == ["308", "309"] and st.iloc[0].cds == ["35", "40"]


def test_null_area_not_in_tags():
    st, *_ = _run(None, blocks=[_block(0, cb=None, cd=None), _block(1)])
    assert st.iloc[0].cbs == ["309"] and st.iloc[0].cds == ["40"]


def test_stretch_sums_equal_blocks():
    b = [_block(i, score=3.0 + i, killed=i % 2) for i in range(6)]
    st, *_ = _run(None, blocks=b)
    s = st.iloc[0]
    assert len(st) == 1 and s.score == sum(3.0 + i for i in range(6)) and s.killed_5y == 3
    assert s.crashes_5y == 12 and s.last_crash_date == "2026-01-06" and s.blocks == 6
    assert s.bbox[0] < s.bbox[2] and s.bbox[1] == s.bbox[3] == 40.65


def test_from_to_street():
    extra = [{"segmentid": "0000090", "street": "FLATBUSH AV", "lboro": "3", "nodeidfrom": "1", "nodeidto": "99",
              "featuretyp": "0", "rb_layer": "B", "geometry": json.dumps(mapping(_line(20)))},
             {"segmentid": "0000091", "street": "UTICA AV", "lboro": "3", "nodeidfrom": "4", "nodeidto": "98",
              "featuretyp": "0", "rb_layer": "B", "geometry": json.dumps(mapping(_line(21)))}]
    st, *_ = _run([0, 1, 2], lion=_lion(extra=extra))
    assert (st.iloc[0].from_street, st.iloc[0].to_street) == ("FLATBUSH AV", "UTICA AV")


def test_street_totals_by_tier():
    b = [_block(0, tier=1, score=10, killed=1), _block(1, tier=1, score=5), _block(4, tier=2, score=7)]
    st, *_ = _run(None, blocks=b, current={IDS[4]: "paint"})
    sr = street_totals(pd.DataFrame(b), st)
    assert len(sr) == 2
    t1 = sr[sr["tier"] == 1].iloc[0]
    assert t1.street_key == "Brooklyn|EMPIREBOULEVARD|1" and t1.blocks == 2 and t1.score == 15
    assert t1.killed_5y == 1 and t1.stretch_ids == ["S0000001"] and t1.cbs == ["309"] and t1["rank"] == 1
    t2 = sr[sr["tier"] == 2].iloc[0]
    assert t2.street_key.endswith("|2") and t2["rank"] == 2 and t2.stretch_ids == ["S0000005"]
