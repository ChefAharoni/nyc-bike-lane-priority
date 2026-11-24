import gzip
import json
from datetime import date

from pipeline.snapshots import prune, write_index, write_snapshot

TODAY = date(2026, 11, 24)


def d(s):
    return date.fromisoformat(s)


def test_prune():
    dates = [d(x) for x in ("2026-08-01", "2026-08-02", "2026-08-26", "2026-08-27", "2026-11-23")]
    assert sorted(prune(dates, TODAY)) == [d("2026-08-02"), d("2026-08-26")]


def test_prune_keeps_earliest_when_first_missing():
    dates = [d(x) for x in ("2026-07-03", "2026-07-04", "2026-07-30", "2026-11-01")]
    assert sorted(prune(dates, TODAY)) == [d("2026-07-04"), d("2026-07-30")]


def test_prune_keeps_everything_within_90_days():
    dates = [d(x) for x in ("2026-08-27", "2026-08-28", "2026-09-01", "2026-09-02")]
    assert prune(dates, TODAY) == []  # all under 90 days old


def test_index_newest_first(tmp_path):
    for x in ("2026-11-01", "2026-11-23", "2026-09-30"):
        (tmp_path / x).mkdir()
    (tmp_path / "notes").mkdir()
    idx = write_index(tmp_path)
    assert idx == {"latest": "2026-11-23", "dates": ["2026-11-23", "2026-11-01", "2026-09-30"]}
    assert json.loads((tmp_path / "index.json").read_text()) == idx


def test_write_snapshot_copies_files(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    for n in ("meta", "areas", "blocks", "stretches", "streets"):
        (out / f"{n}.json").write_text(json.dumps({"n": n}))
    write_snapshot(out, tmp_path / "snaps", d("2026-11-21"))
    f = tmp_path / "snaps/2026-11-21/blocks.json.gz"
    assert json.loads(gzip.decompress(f.read_bytes())) == {"n": "blocks"}
    write_snapshot(out, tmp_path / "snaps2", d("2026-11-21"))
    assert f.read_bytes() == (tmp_path / "snaps2/2026-11-21/blocks.json.gz").read_bytes()  # deterministic
    assert len(list((tmp_path / "snaps/2026-11-21").iterdir())) == 5
