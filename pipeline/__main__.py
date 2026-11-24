"""CLI: uv run python -m pipeline --out data_out --raw raw --snapshots data_out/snapshots"""
import argparse
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline.contract import load_sources, write_contract
from pipeline.run import run
from pipeline.sanity import check, load_meta
from pipeline.snapshots import apply_prune, write_index, write_snapshot
from pipeline.tiles import build_tiles
from pipeline.totals import window_crashes

EXIT_SANITY = 3


def main(argv=None, today: date | None = None) -> int:
    """today (the run date, UTC) is injectable for tests."""
    p = argparse.ArgumentParser(prog="pipeline", description="Rank NYC street blocks for protected bike lanes.")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--raw", type=Path, default=None, help="dev cache of fetched sources (parquet)")
    p.add_argument("--lion-cache", type=Path, default=Path(".cache/lion"), help="LION download cache")
    p.add_argument("--as-of", type=date.fromisoformat, default=None, help="ignore crashes after YYYY-MM-DD")
    p.add_argument("--no-tiles", action="store_true", help="skip the vector tiles (needs tippecanoe)")
    p.add_argument("--previous-meta", type=Path, default=None,
                   help="meta.json of the last deployed run, for the sanity gate (missing file = first run)")
    p.add_argument("--snapshots", type=Path, default=None, help="write a dated snapshot here and prune old ones")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    today = today or datetime.now(timezone.utc).date()

    res = run(a.out, a.raw, a.lion_cache, a.as_of)
    write_contract(res, a.out, sources=load_sources(a.raw))

    print("Top blocks:")
    for _, r in res.blocks.head(5).iterrows():
        print(f"  #{r['priority_rank']} {r['segmentid']} {r['street']} score={r['score']} tier={r['tier']}")
    print(f"data_date={res.data_date} window_start={res.window_start} recent_start={res.recent_start}")
    for k, v in res.counts.items():
        print(f"{k}: {v:,}")

    previous = load_meta(a.previous_meta) if a.previous_meta is not None else None
    reasons = check(load_meta(a.out / "meta.json"), previous)
    if reasons:
        print("Sanity check failed:", file=sys.stderr)
        for r in reasons:
            print(r, file=sys.stderr)
        return EXIT_SANITY

    if not a.no_tiles:
        build_tiles(res.segments, res.routes, window_crashes(res.enriched, res.window_start), a.out)
    if a.snapshots is not None:
        write_snapshot(a.out, a.snapshots, res.data_date)
        apply_prune(a.snapshots, today)
        write_index(a.snapshots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
