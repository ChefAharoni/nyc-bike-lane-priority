import json
from datetime import date

import pytest

import pipeline.__main__ as cli
from pipeline.contract import write_contract
from pipeline.run import run
from test_run import raw_and_lion  # noqa: F401  (pytest fixture)

SOURCES = {k: "2026-11-01T00:00:00+00:00" for k in
           ("crashes", "persons", "vehicles", "routes", "council", "community", "lion")}


def test_cli_sanity_failure_exits_3_and_writes_no_snapshot(tmp_path, raw_and_lion, capsys, monkeypatch):  # noqa: F811
    raw, lion_path = raw_and_lion
    as_of = date(2026, 11, 15)
    # "previous deployed run": the same data, but with more bike crashes than the new run has
    prev = tmp_path / "prev"
    write_contract(run(prev, raw, tmp_path / "lc", as_of, lion_path=lion_path), prev, sources=SOURCES)
    meta = json.loads((prev / "meta.json").read_text())
    meta["counts"]["bike_crashes"] = int(meta["counts"]["bike_crashes"] / 0.97) + 1
    (prev / "meta.json").write_text(json.dumps(meta))

    monkeypatch.setattr(cli, "run", lambda out, raw_dir, cache, as_of_: run(
        out, raw_dir, cache, as_of_, lion_path=lion_path))
    monkeypatch.setattr(cli, "load_sources", lambda raw_dir: SOURCES)
    snaps = tmp_path / "snaps"
    code = cli.main(["--out", str(tmp_path / "out"), "--raw", str(raw), "--as-of", as_of.isoformat(),
                     "--no-tiles", "--snapshots", str(snaps), "--previous-meta", str(prev / "meta.json")],
                    today=date(2026, 11, 24))
    assert code == 3
    err = capsys.readouterr().err
    assert "Sanity check failed" in err and "bike crashes" in err
    assert not snaps.exists()
