"""Per-area totals (community boards, council districts), citywide and unassigned.

Crash fields count bike crashes with coordinates in the 5-year window (any match confidence) by the
crash's own location. Block fields count ranked blocks by the block midpoint's area. Stretch fields
count stretches whose `cbs` / `cds` include the area."""
from collections import Counter
from datetime import date

import pandas as pd

LANES = ["none", "paint", "sharrow", "protected", "unknown"]
KINDS = {"cb": "cbs", "cd": "cds"}


def empty_totals() -> dict:
    return {"crashes_5y": 0, "injured_5y": 0, "killed_5y": 0, "lane_at_crash_5y": {k: 0 for k in LANES},
            "ranked_blocks": 0, "tier1_blocks": 0, "tier2_blocks": 0, "stretches": 0, "shared_stretches": 0}


def window_crashes(crashes: pd.DataFrame, window_start: date) -> pd.DataFrame:
    """Crashes with coordinates on or after window_start, with numeric rider counts and a clean lane."""
    lat = pd.to_numeric(crashes["latitude"], errors="coerce")
    lon = pd.to_numeric(crashes["longitude"], errors="coerce")
    keep = lat.notna() & lon.notna() & (crashes["crash_date"].str[:10] >= window_start.isoformat())
    c = crashes[keep].copy()
    c["riders_injured"] = pd.to_numeric(c["riders_injured"]).fillna(0).astype(int)
    c["riders_killed"] = pd.to_numeric(c["riders_killed"]).fillna(0).astype(int)
    lane = c["facility_at_crash"].astype(object)
    c["lane"] = lane.where(lane.isin(LANES), "unknown")
    return c


def _crash_fields(c: pd.DataFrame) -> dict:
    lanes = c["lane"].value_counts()
    return {"crashes_5y": len(c), "injured_5y": int(c["riders_injured"].sum()),
            "killed_5y": int(c["riders_killed"].sum()),
            "lane_at_crash_5y": {k: int(lanes.get(k, 0)) for k in LANES}}


def _ranked(blocks: pd.DataFrame) -> pd.DataFrame:
    b = blocks[blocks["priority_rank"].notna()].copy()
    b["tier"] = pd.to_numeric(b["tier"]).astype(int)
    return b


def _block_fields(b: pd.DataFrame) -> dict:
    return {"ranked_blocks": len(b), "tier1_blocks": int((b["tier"] == 1).sum()),
            "tier2_blocks": int((b["tier"] == 2).sum())}


def _stretch_fields(counts: int, shared: int) -> dict:
    return {"stretches": counts, "shared_stretches": shared}


def area_totals(crashes_with_areas: pd.DataFrame, blocks: pd.DataFrame, stretches: pd.DataFrame,
                window_start: date) -> dict[str, dict[str, dict]]:
    """{"cb": {id: AreaTotals}, "cd": {...}} for every id that has a crash, block or stretch."""
    c = window_crashes(crashes_with_areas, window_start)
    b = _ranked(blocks)
    out: dict[str, dict[str, dict]] = {}
    for kind, col in KINDS.items():
        per: dict[str, dict] = {}
        cg = {k: g for k, g in c[c[kind].notna()].groupby(kind)}
        bg = {k: g for k, g in b[b[kind].notna()].groupby(kind)}
        touch, shared = Counter(), Counter()
        for ids in stretches[col] if len(stretches) else []:
            for i in set(ids):
                touch[i] += 1
                if len(set(ids)) >= 2:
                    shared[i] += 1
        for aid in sorted(set(cg) | set(bg) | set(touch)):
            t = empty_totals()
            if aid in cg:
                t.update(_crash_fields(cg[aid]))
            if aid in bg:
                t.update(_block_fields(bg[aid]))
            t.update(_stretch_fields(touch[aid], shared[aid]))
            per[str(aid)] = t
        out[kind] = per
    return out


def citywide(crashes_with_areas: pd.DataFrame, blocks: pd.DataFrame, stretches: pd.DataFrame,
             window_start: date) -> dict:
    """Everything; shared_stretches = stretches touching more than one community board."""
    t = empty_totals()
    t.update(_crash_fields(window_crashes(crashes_with_areas, window_start)))
    t.update(_block_fields(_ranked(blocks)))
    shared = sum(1 for ids in stretches["cbs"] if len(set(ids)) > 1) if len(stretches) else 0
    t.update(_stretch_fields(len(stretches), shared))
    return t


def unassigned(crashes_with_areas: pd.DataFrame, blocks: pd.DataFrame, window_start: date,
               kind: str = "cb") -> dict:
    """Crashes and ranked blocks with no area of `kind`. Stretches are never unassigned (0)."""
    c = window_crashes(crashes_with_areas, window_start)
    b = _ranked(blocks)
    t = empty_totals()
    t.update(_crash_fields(c[c[kind].isna()]))
    t.update(_block_fields(b[b[kind].isna()]))
    return t
