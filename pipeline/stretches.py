"""Combine ranked blocks into stretches (connected runs of one street and tier) and whole-street totals."""
import re
from collections import Counter, defaultdict

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import shapely

from pipeline.areas import assign_blocks
from pipeline.config import BORO_NAMES, GAP_BLOCKS
from pipeline.matching import norm_street

TIER_OF = {"none": 1, "paint": 2, "sharrow": 2}
# rail lines and alleys are not cross streets
_NOT_CROSS = re.compile(r"(\bLINE$|^ALLEY$|\bALLEY$)")
SUMS = ["crashes_5y", "injured_5y", "killed_5y", "crashes_no_lane_5y"]


def _top(spellings):
    """Most common value, ties alphabetical."""
    c = Counter(s for s in spellings if s)
    return min(c, key=lambda k: (-c[k], k)) if c else None


def _sorted_ids(values):
    return sorted({str(v) for v in values if v is not None and not pd.isna(v)})


def _boro(lboro: pd.Series) -> pd.Series:
    num = pd.to_numeric(lboro, errors="coerce").astype("Int64").astype("string")
    return num.map(BORO_NAMES)


def _kept_gap_edges(ranked, gaps, k):
    """ranked/gaps: dicts segmentid -> (u, v). Gap edges lying on a path of <= k consecutive gap edges
    between endpoints of two different ranked edges."""
    at_ranked = defaultdict(set)
    for sid, (u, v) in ranked.items():
        at_ranked[u].add(sid)
        at_ranked[v].add(sid)
    adj = defaultdict(list)
    for sid, (u, v) in gaps.items():
        adj[u].append((sid, v))
        adj[v].append((sid, u))
    kept = set()

    def dfs(start, node, path, seen_nodes):
        if path and node in at_ranked:
            a, b = at_ranked[start], at_ranked[node]
            if not (a == b and len(a) == 1):
                kept.update(path)
            return  # a path ends at the first ranked endpoint it reaches
        if len(path) == k:
            return
        for sid, nxt in adj[node]:
            if sid not in path and nxt not in seen_nodes:
                dfs(start, nxt, path + [sid], seen_nodes | {nxt})

    for t in at_ranked:
        if t in adj:
            dfs(t, t, [], {t})
    return kept


def build_stretches(blocks: pd.DataFrame, lion: pd.DataFrame, current: pd.Series,
                    gap_blocks: int = GAP_BLOCKS, areas: gpd.GeoDataFrame | None = None):
    """Returns (stretches, segment_to_stretch, gap_blocks_df).

    stretches: contract Stretch columns. segment_to_stretch: segmentid -> stretch_id for ranked and gap members.
    gap_blocks_df: the bridged gap blocks (segmentid, street, borough, current_facility, cb, cd, geometry,
    mid_lat, mid_lon, area_by_nearest, stretch_id). `areas` (from load_areas) assigns their cb/cd; blocks
    already in `blocks` keep theirs."""
    empty_cols = ["stretch_id", "street", "borough", "tier", "rank", "from_street", "to_street", "blocks",
                  "segmentids", "gap_segmentids", "score", *SUMS, "last_crash_date", "cbs", "cds", "bbox"]
    gap_cols = ["segmentid", "street", "borough", "current_facility", "cb", "cd", "geometry", "mid_lat",
                "mid_lon", "area_by_nearest", "stretch_id"]
    rb = blocks[blocks["priority_rank"].notna()].copy()
    if rb.empty:
        return (pd.DataFrame(columns=empty_cols), pd.Series(dtype=object, name="stretch_id"),
                pd.DataFrame(columns=gap_cols))
    rb["tier"] = pd.to_numeric(rb["tier"]).astype(int)
    rb["nname"] = rb["street"].map(norm_street)
    rb["score"] = pd.to_numeric(rb["score"]).astype(float)
    for c in SUMS:
        rb[c] = pd.to_numeric(rb[c]).fillna(0).astype(int)
    rb = rb.set_index("segmentid", drop=False)

    # LION snap layer, one row per segment
    snap = lion[(lion["featuretyp"] == "0") & lion["rb_layer"].isin(["B", "R"])]
    snap = snap.drop_duplicates("segmentid").set_index("segmentid", drop=False)
    nodes = {sid: (a, b) for sid, a, b in zip(snap["segmentid"], snap["nodeidfrom"], snap["nodeidto"])}
    snap_borough = _boro(snap["lboro"])
    snap_name = snap["street"].map(norm_street)
    snap_tier = snap["segmentid"].map(current).astype(object).fillna("none").map(TIER_OF)  # protected -> NaN
    ranked_ids = set(rb["segmentid"])
    cand = pd.DataFrame({"borough": snap_borough, "nname": snap_name, "tier": snap_tier})
    cand = cand[cand["tier"].notna() & cand["nname"].notna() & cand["borough"].notna()
                & ~cand.index.isin(ranked_ids)]
    cand["tier"] = cand["tier"].astype(int)
    gap_by_key = {k: list(g.index) for k, g in cand.groupby(["borough", "nname", "tier"])}

    members = []  # (ranked ids, gap ids, graph)
    for key, grp in rb.groupby(["borough", "nname", "tier"]):
        ranked = {sid: nodes[sid] for sid in grp["segmentid"] if sid in nodes}
        if len(ranked) < len(grp):  # ranked block absent from the snap layer: still its own stretch
            raise ValueError(f"ranked blocks not in LION: {sorted(set(grp['segmentid']) - set(ranked))[:5]}")
        gaps = {sid: nodes[sid] for sid in gap_by_key.get(key, [])}
        kept = _kept_gap_edges(ranked, gaps, gap_blocks) if gaps and gap_blocks > 0 else set()
        g = nx.Graph()
        owner = {}
        for sid, (u, v) in ranked.items():
            g.add_edge(u, v)
            owner[sid] = (u, v)
        for sid in kept:
            u, v = gaps[sid]
            g.add_edge(u, v)
            owner[sid] = (u, v)
        comp_of = {}
        for i, comp in enumerate(nx.connected_components(g)):
            for n in comp:
                comp_of[n] = i
        by_comp = defaultdict(lambda: ([], [], []))
        for sid, (u, v) in owner.items():
            r, gp, edges = by_comp[comp_of[u]]
            (r if sid in ranked else gp).append(sid)
            edges.append((u, v))
        for r, gp, edges in by_comp.values():
            members.append((sorted(r), sorted(gp), edges))

    # Gap block rows
    all_gap = sorted({s for _, gp, _ in members for s in gp})
    gdf = _gap_frame(snap.loc[all_gap], current, blocks, areas, snap_borough)

    # Nodes -> street spellings, for from/to streets
    need = {n for _, _, edges in members for e in edges for n in e}
    at_node = defaultdict(Counter)
    for col in ("nodeidfrom", "nodeidto"):
        sub = snap[snap[col].isin(need) & snap["street"].notna()]
        for n, s in zip(sub[col], sub["street"]):
            if str(s).strip().lower() not in ("", "nan", "none") and not _NOT_CROSS.search(str(s).upper()):
                at_node[n][s] += 1
    coords = _node_coords(snap, need)

    geom_by_sid = {**{sid: g for sid, g in zip(rb["segmentid"], rb["geometry"])},
                   **{sid: g for sid, g in zip(gdf["segmentid"], gdf["geometry"])}}
    gap_cb = gdf.set_index("segmentid")["cb"] if len(gdf) else pd.Series(dtype=object)
    gap_cd = gdf.set_index("segmentid")["cd"] if len(gdf) else pd.Series(dtype=object)
    rows = []
    for r, gp, edges in members:
        sub = rb.loc[r]
        sid0 = "S" + min(r)
        all_ids = r + gp
        bounds = shapely.total_bounds(np.array([geom_by_sid[s] for s in all_ids], dtype=object))
        nname = sub["nname"].iloc[0]
        frm, to = _ends(edges, coords, at_node, nname)
        dates = [d for d in sub["last_crash_date"] if d is not None and not pd.isna(d)]
        rows.append({
            "stretch_id": sid0, "street": _top(sub["street"]), "borough": sub["borough"].iloc[0],
            "tier": int(sub["tier"].iloc[0]), "from_street": frm, "to_street": to,
            "blocks": len(all_ids), "segmentids": r, "gap_segmentids": gp,
            "score": float(sub["score"].sum()), **{c: int(sub[c].sum()) for c in SUMS},
            "last_crash_date": max(dates) if dates else None,
            "cbs": _sorted_ids(list(sub["cb"]) + [gap_cb.get(s) for s in gp]),
            "cds": _sorted_ids(list(sub["cd"]) + [gap_cd.get(s) for s in gp]),
            "bbox": [round(float(x), 6) for x in bounds],
        })
    st = pd.DataFrame(rows)
    for c in ("from_street", "to_street", "last_crash_date"):
        st[c] = st[c].astype(object).where(st[c].notna(), None)  # real nulls, never NaN
    st = st.sort_values(["tier", "score", "killed_5y", "crashes_5y", "stretch_id"],
                        ascending=[True, False, False, False, True]).reset_index(drop=True)
    st.insert(4, "rank", np.arange(1, len(st) + 1))

    seg_map = {}
    for sid0, r, gp in zip(st["stretch_id"], st["segmentids"], st["gap_segmentids"]):
        for s in r + gp:
            seg_map[s] = sid0
    seg_to = pd.Series(seg_map, dtype=object, name="stretch_id")
    gdf["stretch_id"] = gdf["segmentid"].map(seg_map)
    return st[empty_cols], seg_to, gdf[gap_cols]


def _node_coords(snap, need):
    out = {}
    geoms = shapely.from_geojson(snap["geometry"].values) if len(snap) else []
    for a, b, g in zip(snap["nodeidfrom"], snap["nodeidto"], geoms):
        if g is None or g.is_empty:
            continue
        xy = shapely.get_coordinates(g)  # works for Multi* too
        if a in need and a not in out:
            out[a] = tuple(xy[0])
        if b in need and b not in out:
            out[b] = tuple(xy[-1])
    return out


def _ends(edges, coords, at_node, nname):
    g = nx.Graph(edges)
    ends = [n for n in g.nodes if g.degree(n) == 1]
    if len(ends) < 2:
        return None, None
    ends = [n for n in ends if n in coords]
    if len(ends) < 2:
        return None, None
    pair = max(((a, b) for i, a in enumerate(ends) for b in ends[i + 1:]),
               key=lambda p: (np.hypot(coords[p[0]][0] - coords[p[1]][0], coords[p[0]][1] - coords[p[1]][1]),
                              str(p)))
    dx = abs(coords[pair[0]][0] - coords[pair[1]][0])
    dy = abs(coords[pair[0]][1] - coords[pair[1]][1])
    axis = 0 if dx >= dy else 1
    a, b = sorted(pair, key=lambda n: (coords[n][axis], str(n)))

    def other(n):
        return _top(s for s in at_node[n] for _ in range(at_node[n][s]) if norm_street(s) != nname)
    return other(a), other(b)


def _gap_frame(gsnap, current, blocks, areas, boro):
    cols = ["segmentid", "street", "borough", "current_facility", "cb", "cd", "geometry", "mid_lat",
            "mid_lon", "area_by_nearest"]
    if gsnap.empty:
        return pd.DataFrame(columns=cols)
    geom = gpd.GeoSeries(shapely.from_geojson(gsnap["geometry"].values), index=gsnap.index, crs="EPSG:4326")
    mid = gpd.GeoSeries(geom.to_crs(epsg=2263).interpolate(0.5, normalized=True), crs="EPSG:2263").to_crs(epsg=4326)
    df = pd.DataFrame({"segmentid": gsnap["segmentid"].to_numpy(), "street": gsnap["street"].to_numpy(),
                       "borough": boro.loc[gsnap.index].astype(object).to_numpy(),
                       "current_facility": gsnap["segmentid"].map(current).astype(object).fillna("none").to_numpy(),
                       "geometry": geom.to_numpy(), "mid_lat": mid.y.round(6).to_numpy(),
                       "mid_lon": mid.x.round(6).to_numpy()})
    known = blocks.drop_duplicates("segmentid").set_index("segmentid") if "cb" in blocks.columns else None
    if areas is not None:
        df = assign_blocks(df, areas)
        if known is not None:  # same midpoint rule, so identical to the blocks frame; keep that frame's value
            for c in ("cb", "cd"):
                inb = df["segmentid"].map(known[c]) if c in known else None
                if inb is not None:
                    df[c] = df[c].where(~df["segmentid"].isin(known.index), inb)
    else:
        df["cb"] = df["segmentid"].map(known["cb"]) if known is not None else None
        df["cd"] = df["segmentid"].map(known["cd"]) if known is not None else None
        df["area_by_nearest"] = False
    for c in ("cb", "cd"):
        df[c] = df[c].astype(object).where(df[c].notna(), None)
    return df[cols].reset_index(drop=True)


def street_totals(blocks: pd.DataFrame, stretches: pd.DataFrame) -> pd.DataFrame:
    cols = ["street_key", "street", "borough", "tier", "rank", "score", "blocks", *SUMS[:3], "stretch_ids",
            "cbs", "cds"]
    rb = blocks[blocks["priority_rank"].notna()].copy()
    if rb.empty:
        return pd.DataFrame(columns=cols)
    rb["tier"] = pd.to_numeric(rb["tier"]).astype(int)
    rb["score"] = pd.to_numeric(rb["score"]).astype(float)
    for c in SUMS[:3]:
        rb[c] = pd.to_numeric(rb[c]).fillna(0).astype(int)
    rb["street_key"] = rb["borough"] + "|" + rb["street"].map(norm_street) + "|" + rb["tier"].astype(str)
    st = stretches.assign(street_key=stretches["borough"] + "|" + stretches["street"].map(norm_street)
                          + "|" + stretches["tier"].astype(str))
    by_st = {k: g for k, g in st.groupby("street_key")}
    rows = []
    for key, g in rb.groupby("street_key"):
        s = by_st.get(key)
        rows.append({
            "street_key": key, "street": _top(g["street"]), "borough": g["borough"].iloc[0],
            "tier": int(g["tier"].iloc[0]), "score": float(g["score"].sum()), "blocks": len(g),
            **{c: int(g[c].sum()) for c in SUMS[:3]},
            "stretch_ids": sorted(s["stretch_id"]) if s is not None else [],
            "cbs": sorted({a for l in s["cbs"] for a in l}) if s is not None else [],
            "cds": sorted({a for l in s["cds"] for a in l}) if s is not None else [],
        })
    out = pd.DataFrame(rows).sort_values(["tier", "score", "killed_5y", "crashes_5y", "street_key"],
                                         ascending=[True, False, False, False, True]).reset_index(drop=True)
    out.insert(4, "rank", np.arange(1, len(out) + 1))
    return out[cols]
