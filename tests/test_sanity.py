import copy
import json

from pipeline.sanity import check, load_meta

SRC = ["crashes", "persons", "vehicles", "routes", "council", "community", "lion"]


def meta(crashes=81000, ranked=17000, date_="2026-11-21", cb=59, cd=51):
    return {"data_date": date_,
            "counts": {"bike_crashes": crashes, "ranked_blocks": ranked, **{f"rows_{s}": 10 for s in SRC}},
            "area_ids": {"cb": [str(i) for i in range(cb)], "cd": [str(i) for i in range(cd)]}}


def test_sanity_pass():
    assert check(meta(81500, 17100, "2026-11-22"), meta()) == []


def test_sanity_drop_fails():
    reasons = check(meta(crashes=int(81000 * 0.97)), meta())
    assert len(reasons) == 1 and "bike crashes" in reasons[0]


def test_sanity_rise_fails():
    reasons = check(meta(crashes=int(81000 * 1.06)), meta())
    assert len(reasons) == 1 and "bike crashes" in reasons[0]


def test_sanity_ranked_change_fails():
    reasons = check(meta(ranked=int(17000 * 1.06)), meta())
    assert len(reasons) == 1 and "ranked blocks" in reasons[0]


def test_sanity_date_goes_back_fails():
    reasons = check(meta(date_="2026-11-20"), meta())
    assert len(reasons) == 1 and "data_date" in reasons[0]


def test_sanity_missing_area_fails():
    reasons = check(meta(cb=58), meta())
    assert len(reasons) == 1 and "cb" in reasons[0]


def test_sanity_zero_rows_source_fails():
    m = meta()
    m["counts"]["rows_routes"] = 0
    reasons = check(m, meta())
    assert len(reasons) == 1 and "routes" in reasons[0]


def test_sanity_first_run_bounds():
    assert check(meta(), None) == []
    assert any("bike crashes" in r for r in check(meta(crashes=1000), None))
    assert any("ranked blocks" in r for r in check(meta(ranked=50_000), None))
    assert any("59" in r for r in check(meta(cb=58), None))
    assert any("51" in r for r in check(meta(cd=50), None))


def test_load_meta_reads_area_ids_next_to_meta(tmp_path):
    m = copy.deepcopy(meta())
    del m["area_ids"]
    (tmp_path / "meta.json").write_text(json.dumps(m))
    (tmp_path / "areas.json").write_text(json.dumps({"cb": [{"id": "101"}], "cd": [{"id": "1"}, {"id": "2"}]}))
    assert load_meta(tmp_path / "meta.json")["area_ids"] == {"cb": ["101"], "cd": ["1", "2"]}
    assert load_meta(tmp_path / "nope.json") is None


def test_sanity_previous_without_area_ids_fails():
    prev = meta()
    del prev["area_ids"]
    reasons = check(meta(), prev)
    assert len(reasons) == 1 and "previous areas.json missing" in reasons[0]
