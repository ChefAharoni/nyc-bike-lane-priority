"""Print the CB 9 (Brooklyn, id 309) walkthrough as Markdown from a data_out folder.

Usage: python3 scripts/cb_walkthrough.py [data_out]
Reads stretches.json and areas.json and formats rows the way the site's ranked list does.
"""
import json
import sys
from pathlib import Path

AREA = "309"
out = Path(sys.argv[1] if len(sys.argv) > 1 else "data_out")
stretches = json.loads((out / "stretches.json").read_text())
areas = json.loads((out / "areas.json").read_text())


def title(s: str) -> str:
    return " ".join(w if w[:1].isdigit() else w.capitalize() for w in s.lower().split(" "))


def tag(cb: str) -> str:
    return f"CB {int(cb[1:])}"


def ends(s: dict) -> str:
    return f"{title(s['from_street']) if s['from_street'] else 'continues'} → {title(s['to_street']) if s['to_street'] else 'continues'}"


def tags(s: dict) -> str:
    cbs = s["cbs"]
    return " / ".join(tag(c) for c in [AREA] + [c for c in cbs if c != AREA])


def others(s: dict) -> str:
    return ", ".join(tag(c) for c in s["cbs"] if c != AREA)


mine = [s for s in stretches if AREA in s["cbs"]]
shared = [s for s in mine if len(s["cbs"]) > 1]
cb = next(a for a in areas["cb"] if a["id"] == AREA)
t = cb["totals"]

print(f"### {cb['name']} totals (areas.json)\n")
for k in ("crashes_5y", "injured_5y", "killed_5y", "ranked_blocks", "tier1_blocks", "tier2_blocks", "stretches", "shared_stretches"):
    print(f"- {k}: {t[k]:,}")
print(f"- lane_at_crash_5y: {t['lane_at_crash_5y']}")
print(f"- check: stretches in stretches.json for this board = {len(mine)}, shared = {len(shared)}\n")

print("### Top 5 stretches\n")
print("| # | Street | From → to | Tier | Blocks | Crashes counted | Score | Board tags |")
print("|---:|---|---|---|---:|---:|---:|---|")
for i, s in enumerate(mine[:5], 1):
    print(f"| {i} | {title(s['street'])} | {ends(s)} | T{s['tier']} | {s['blocks']} | {s['crashes_5y']:,} | {s['score']:.1f} | {tags(s)} |")

print(f"\n### Shared stretches: {len(shared)} in total, first 10 by CB 9 rank\n")
print("| CB 9 rank | Street | From → to | Tier | Blocks | Score | Also in |")
print("|---:|---|---|---|---:|---:|---|")
for s in shared[:10]:
    print(f"| {mine.index(s) + 1} | {title(s['street'])} | {ends(s)} | T{s['tier']} | {s['blocks']} | {s['score']:.1f} | {others(s)} |")
