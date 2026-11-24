"""Snap each bike crash to a LION street block."""
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pipeline.config import SNAP_FT, TIE_FT

ABBREV = {
    "AVE": "AVENUE", "AV": "AVENUE", "ST": "STREET", "STR": "STREET", "BLVD": "BOULEVARD",
    "RD": "ROAD", "PL": "PLACE", "DR": "DRIVE", "PKWY": "PARKWAY", "PKY": "PARKWAY",
    "EXPY": "EXPRESSWAY", "EXWY": "EXPRESSWAY", "HWY": "HIGHWAY", "CT": "COURT", "LN": "LANE",
    "TER": "TERRACE", "TPKE": "TURNPIKE", "BR": "BRIDGE", "BRG": "BRIDGE", "SQ": "SQUARE",
    "E": "EAST", "W": "WEST", "N": "NORTH", "S": "SOUTH", "CONC": "CONCOURSE", "EXT": "EXTENSION",
    "FT": "FORT", "FDR": "FRANKLIN D ROOSEVELT", "FIRST": "1", "SECOND": "2", "THIRD": "3", "FOURTH": "4",
    "FIFTH": "5", "SIXTH": "6", "SEVENTH": "7", "EIGHTH": "8", "NINTH": "9", "TENTH": "10",
}

OUT_COLS = ["collision_id", "segmentid", "matched_street", "tie_segmentid", "match_distance_ft",
            "match_confidence", "match_reason", "name_source", "candidates"]


def norm_street(name, address=False):
    """Uppercase, drop punctuation, expand abbreviations, '1ST' -> '1'.
    address=True strips a leading house number ('34-09  83 STREET' -> '83 STREET')."""
    if name is None or pd.isna(name):
        return None
    t = re.sub(r"[^A-Z0-9 \-]", " ", str(name).upper())
    if address:
        t = re.sub(r"^\s*\d+[A-Z]?(-\d+[A-Z]?)?\s+", "", t)
    out = []
    for i, w in enumerate(t.replace("-", " - ").split()):
        w = re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", w)
        if w == "ST" and i == 0:
            w = "SAINT"  # 'ST NICHOLAS AVE'
        out.append(ABBREV.get(w, w))
    # Spaces dropped so 'DE KALB' = 'DEKALB', 'MC DONALD' = 'MCDONALD'
    t = "".join(out).replace("-", "")
    return t or None


def load_segments(lion):
    """Streets as drawn roadbed-by-roadbed, which is how bike routes are attached to LION."""
    s = lion[(lion["featuretyp"] == "0") & lion["rb_layer"].isin(["B", "R"])].copy()
    s["name"] = s["street"].map(norm_street)
    names = s.groupby("segmentid")["name"].agg(lambda x: sorted(set(x.dropna())))
    # reset_index matters: geometry below is a positional array, the other columns align by label
    s = s.drop_duplicates("segmentid").reset_index(drop=True)
    return gpd.GeoDataFrame(
        {"segmentid": s["segmentid"], "street": s["street"], "nonped": s["nonped"].str.strip(),
         "names": s["segmentid"].map(names)},
        geometry=shapely.from_geojson(s["geometry"].values), crs="EPSG:4326",
    ).to_crs(epsg=2263)


def match(crashes, segs):
    c = crashes[["collision_id", "latitude", "longitude", "on_street_name", "off_street_name"]].copy()
    lat = pd.to_numeric(c["latitude"], errors="coerce")
    lon = pd.to_numeric(c["longitude"], errors="coerce")
    has_xy = lat.between(40.45, 40.95) & lon.between(-74.3, -73.65)
    c["crash_name"] = c["on_street_name"].map(norm_street)
    from_addr = c["crash_name"].isna()
    c.loc[from_addr, "crash_name"] = c.loc[from_addr, "off_street_name"].map(lambda v: norm_street(v, address=True))

    pts = gpd.GeoSeries(gpd.points_from_xy(lon[has_xy], lat[has_xy]), index=c.index[has_xy],
                        crs="EPSG:4326").to_crs(epsg=2263)
    pi, si = segs.sindex.query(pts.values, predicate="dwithin", distance=SNAP_FT)
    cand = pd.DataFrame({"row": pts.index[pi], "seg": si})
    cand["dist"] = shapely.distance(pts.values[pi], segs.geometry.values[si])
    cand["crash_name"] = c.loc[cand["row"], "crash_name"].values
    cand["name_match"] = [n is not None and n in names
                          for n, names in zip(cand["crash_name"], segs["names"].values[si])]
    cand["highway"] = segs["nonped"].values[si] == "V"

    rows = []
    for row, g in cand.groupby("row", sort=False):
        g = g.sort_values(["dist", "seg"])
        named = g[g["name_match"]]
        tie_seg = None
        if len(named):
            best = named.iloc[0]
            # Crash on the corner where two blocks of the same street meet: keep the other block
            # so the lane-status step can check both blocks agree
            if len(named) > 1 and named["dist"].iloc[1] - best["dist"] <= TIE_FT:
                tie_seg = int(named["seg"].iloc[1])
            nearest_other = g[~g["name_match"]]["dist"].min()
            if nearest_other < best["dist"] - TIE_FT:  # a differently-named street is clearly closer
                conf, reason = "medium", "name_farther"
            else:
                conf, reason = "high", "name_and_distance"
        else:
            # No name match: nearest street, but highways only win if nothing else is in range
            pool = g[~g["highway"]] if (~g["highway"]).any() else g
            best, conf, reason = pool.iloc[0], "low", "nearest_only"
        rows.append((row, int(best["seg"]), tie_seg, float(best["dist"]), conf, reason, len(g)))
    m = pd.DataFrame(rows, columns=["row", "seg", "tie_seg", "match_distance_ft", "match_confidence",
                                    "match_reason", "candidates"]).set_index("row")

    out = c[["collision_id"]].join(m)
    out["segmentid"] = segs["segmentid"].values[out["seg"].fillna(0).astype(int)]
    out["matched_street"] = segs["street"].values[out["seg"].fillna(0).astype(int)]
    out["tie_segmentid"] = [segs["segmentid"].values[int(t)] if pd.notna(t) else None for t in out["tie_seg"]]
    none = out["seg"].isna()
    out.loc[none, ["segmentid", "matched_street"]] = None
    out.loc[none & ~has_xy, ["match_confidence", "match_reason"]] = ["unmatched", "no_coordinates"]
    out.loc[none & has_xy, ["match_confidence", "match_reason"]] = ["unmatched", "no_street_within_30m"]
    out["name_source"] = np.where(c["on_street_name"].notna(), "on_street",
                                  np.where(c["crash_name"].notna(), "address", "none"))
    out["candidates"] = out["candidates"].fillna(0).astype(int)
    out = out.drop(columns=["seg", "tie_seg"]).reset_index(drop=True)[OUT_COLS]
    for col in OUT_COLS:
        if col != "candidates":
            out[col] = out[col].astype(object).where(out[col].notna(), None)
    return out
