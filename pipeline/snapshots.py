"""Dated, gzipped copies of the contract files, so the site can show how the ranking changed."""
import gzip
import json
import shutil
from datetime import date
from pathlib import Path

from pipeline.config import SNAPSHOT_DAILY_DAYS

FILES = ["meta", "areas", "blocks", "stretches", "streets"]


def write_snapshot(out_dir: Path, snapshots_dir: Path, data_date: date) -> None:
    target = Path(snapshots_dir) / data_date.isoformat()
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        data = (Path(out_dir) / f"{name}.json").read_bytes()
        # level 9, mtime 0: the same input always gives the same bytes
        with open(target / f"{name}.json.gz", "wb") as raw, \
                gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=raw, mtime=0) as gz:
            gz.write(data)


def prune(dates: list[date], today: date) -> list[date]:
    """Dates to delete: keep everything under 90 days old; older ones keep only the earliest
    snapshot of each calendar month."""
    old = [d for d in dates if (today - d).days >= SNAPSHOT_DAILY_DAYS]
    earliest: dict[tuple[int, int], date] = {}
    for d in sorted(old):
        earliest.setdefault((d.year, d.month), d)
    keep = set(earliest.values())
    return sorted(d for d in old if d not in keep)


def _dates(snapshots_dir: Path) -> list[date]:
    out = []
    for p in Path(snapshots_dir).iterdir():
        if p.is_dir():
            try:
                out.append(date.fromisoformat(p.name))
            except ValueError:
                pass
    return out


def apply_prune(snapshots_dir: Path, today: date) -> list[date]:
    gone = prune(_dates(snapshots_dir), today)
    for d in gone:
        shutil.rmtree(Path(snapshots_dir) / d.isoformat())
    return gone


def write_index(snapshots_dir: Path) -> dict:
    """Write index.json ({latest, dates} newest first) and return it."""
    dates = sorted((d.isoformat() for d in _dates(snapshots_dir)), reverse=True)
    if not dates:
        raise ValueError(f"no snapshots in {snapshots_dir}")
    index = {"latest": dates[0], "dates": dates}
    (Path(snapshots_dir) / "index.json").write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
    return index
