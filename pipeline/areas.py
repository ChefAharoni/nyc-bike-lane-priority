"""Assign blocks and crashes to Community Boards (cb) and City Council Districts (cd)."""
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pipeline.config import BORO_NAMES, JIA_CODES

NYC_LAT = (40.45, 40.95)
NYC_LON = (-74.3, -73.65)


def _norm_cd(v) -> str:
    return str(int(float(str(v).strip())))


def load_areas(council: pd.DataFrame, community: pd.DataFrame) -> gpd.GeoDataFrame:
    """One row per area, EPSG:2263: kind (cb/cd), id, name, borough, is_jia, geometry."""
    rows, geoms = [], []
    for _, r in community.iterrows():
        code = str(r["boro_cd"]).strip()
        code = str(int(float(code)))
        boro = BORO_NAMES[code[0]]
        jia = code in JIA_CODES
        name = f"{boro} park/airport area {code}" if jia else f"{boro} CB {int(code[1:])}"
        rows.append({"kind": "cb", "id": code, "name": name, "borough": boro, "is_jia": jia})
        geoms.append(shapely.from_geojson(r["the_geom"]))
    for _, r in council.iterrows():
        cid = _norm_cd(r["coundist"])
        rows.append({"kind": "cd", "id": cid, "name": f"Council District {cid}", "borough": None,
                     "is_jia": False})
        geoms.append(shapely.from_geojson(r["the_geom"]))
    areas = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326").to_crs(epsg=2263)
    areas["borough"] = areas["borough"].astype(object).where(areas["borough"].notna(), None)
    return areas


def _assign_kind(pts: np.ndarray, valid: np.ndarray, sub: gpd.GeoDataFrame, jia_to_nearest: bool,
                 max_ft: float):
    """Return (ids object array, by_nearest bool array) aligned to pts."""
    n = len(pts)
    out = np.full(n, None, dtype=object)
    by_nearest = np.zeros(n, dtype=bool)
    sub = sub.sort_values("id", kind="stable")
    ids = sub["id"].to_numpy()
    jia = sub["is_jia"].to_numpy()
    geoms = sub.geometry.to_numpy()
    real_pos = np.flatnonzero(~jia)
    real_geoms = geoms[real_pos]
    vidx = np.flatnonzero(valid)
    if len(vidx) == 0 or len(geoms) == 0:
        return out, by_nearest
    tree = shapely.STRtree(geoms)
    p_i, a_i = tree.query(pts[vidx], predicate="intersects")
    # first real area (id order) and whether any JIA contains the point
    first_real = np.full(n, -1)
    in_jia = np.zeros(n, dtype=bool)
    for pi, ai in sorted(zip(vidx[p_i], a_i), key=lambda t: (t[0], t[1])):
        if jia[ai]:
            in_jia[pi] = True
        elif first_real[pi] < 0:
            first_real[pi] = ai
    hit = first_real >= 0
    out[hit] = ids[first_real[hit]]

    todo = valid & ~hit
    if jia_to_nearest:
        j = np.flatnonzero(todo & in_jia)
        if len(j) and len(real_geoms):
            rt = shapely.STRtree(real_geoms)
            near = rt.nearest(pts[j])
            out[j] = ids[real_pos[near]]
            by_nearest[j] = True
        todo = todo & ~in_jia
    t = np.flatnonzero(todo)
    cand = real_geoms if jia_to_nearest else geoms
    cand_ids = ids[real_pos] if jia_to_nearest else ids
    if len(t) and len(cand):
        ct = shapely.STRtree(cand)
        near = ct.nearest(pts[t])
        dist = shapely.distance(pts[t], cand[near])
        ok = dist <= max_ft
        out[t[ok]] = cand_ids[near[ok]]
    return out, by_nearest


def assign_points(points: gpd.GeoSeries, areas: gpd.GeoDataFrame, max_ft: float = 500) -> pd.DataFrame:
    """cb, cd (str or None) and area_by_nearest, index aligned to points (EPSG:2263)."""
    pts = points.to_numpy()
    valid = (~points.isna() & ~points.is_empty).to_numpy()
    cb, by_nearest = _assign_kind(pts, valid, areas[areas["kind"] == "cb"], True, max_ft)
    cd, _ = _assign_kind(pts, valid, areas[areas["kind"] == "cd"], False, max_ft)
    return pd.DataFrame({"cb": pd.Series(cb, index=points.index, dtype=object),
                         "cd": pd.Series(cd, index=points.index, dtype=object),
                         "area_by_nearest": by_nearest}, index=points.index)


def _points(lon, lat, valid) -> gpd.GeoSeries:
    pts = gpd.GeoSeries(gpd.points_from_xy(lon.where(valid), lat.where(valid)), index=lon.index,
                        crs="EPSG:4326").to_crs(epsg=2263)
    return pts.where(valid)


def assign_blocks(blocks: pd.DataFrame, areas: gpd.GeoDataFrame) -> pd.DataFrame:
    lon = pd.to_numeric(blocks["mid_lon"], errors="coerce")
    lat = pd.to_numeric(blocks["mid_lat"], errors="coerce")
    valid = lon.notna() & lat.notna()
    res = assign_points(_points(lon, lat, valid), areas)
    return pd.concat([blocks.drop(columns=[c for c in res.columns if c in blocks.columns]), res], axis=1)


def assign_crashes(enriched: pd.DataFrame, areas: gpd.GeoDataFrame) -> pd.DataFrame:
    lat = pd.to_numeric(enriched["latitude"], errors="coerce")
    lon = pd.to_numeric(enriched["longitude"], errors="coerce")
    valid = lat.between(*NYC_LAT) & lon.between(*NYC_LON)
    res = assign_points(_points(lon, lat, valid), areas)[["cb", "cd"]]
    return pd.concat([enriched.drop(columns=[c for c in res.columns if c in enriched.columns]), res], axis=1)
