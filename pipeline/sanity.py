"""Gate that stops a bad nightly pull from being deployed."""
import json
from pathlib import Path

SOURCES = ["crashes", "persons", "vehicles", "routes", "council", "community", "lion"]
DROP_MAX, RISE_MAX, RANKED_MAX = 0.02, 0.05, 0.05
CRASH_BOUNDS = (60_000, 200_000)
RANKED_BOUNDS = (10_000, 40_000)
FIRST_RUN_AREAS = {"cb": 59, "cd": 51}


def load_meta(path: Path) -> dict | None:
    """meta.json plus `area_ids` read from the areas.json next to it. None if meta.json is absent."""
    path = Path(path)
    if not path.exists():
        return None
    meta = json.loads(path.read_text(encoding="utf-8"))
    areas = path.parent / "areas.json"
    if "area_ids" not in meta and areas.exists():
        a = json.loads(areas.read_text(encoding="utf-8"))
        meta["area_ids"] = {k: [x["id"] for x in a[k]] for k in ("cb", "cd")}
    return meta


def check(meta: dict, previous: dict | None) -> list[str]:
    """Reasons the new data must not ship; empty means pass."""
    reasons = []
    counts = meta["counts"]
    for s in SOURCES:
        if counts.get(f"rows_{s}", 0) == 0:
            reasons.append(f"source dataset {s} returned 0 rows")
    crashes, ranked = counts["bike_crashes"], counts["ranked_blocks"]
    ids = meta.get("area_ids", {})

    if previous is None:
        if not CRASH_BOUNDS[0] <= crashes <= CRASH_BOUNDS[1]:
            reasons.append(f"bike crashes {crashes:,} outside {CRASH_BOUNDS[0]:,} to {CRASH_BOUNDS[1]:,}")
        if not RANKED_BOUNDS[0] <= ranked <= RANKED_BOUNDS[1]:
            reasons.append(f"ranked blocks {ranked:,} outside {RANKED_BOUNDS[0]:,} to {RANKED_BOUNDS[1]:,}")
        for kind, n in FIRST_RUN_AREAS.items():
            if len(ids.get(kind, [])) != n:
                reasons.append(f"expected {n} {kind} areas, found {len(ids.get(kind, []))}")
        return reasons

    pc = previous["counts"]
    change = crashes / pc["bike_crashes"] - 1
    if change < -DROP_MAX or change > RISE_MAX:
        reasons.append(f"bike crashes changed {change:+.1%} ({pc['bike_crashes']:,} to {crashes:,}); "
                       f"allowed -{DROP_MAX:.0%} to +{RISE_MAX:.0%}")
    rchange = ranked / pc["ranked_blocks"] - 1
    if abs(rchange) > RANKED_MAX:
        reasons.append(f"ranked blocks changed {rchange:+.1%} ({pc['ranked_blocks']:,} to {ranked:,}); "
                       f"allowed +/-{RANKED_MAX:.0%}")
    if meta["data_date"] < previous["data_date"]:
        reasons.append(f"data_date {meta['data_date']} is earlier than previous {previous['data_date']}")
    if "area_ids" not in previous:
        reasons.append("previous areas.json missing; cannot check areas")
    for kind, before in previous.get("area_ids", {}).items():
        gone = sorted(set(before) - set(ids.get(kind, [])))
        if gone:
            reasons.append(f"{kind} areas missing: {', '.join(gone)}")
    return reasons
