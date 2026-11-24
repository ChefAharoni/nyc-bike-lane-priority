"""Score and rank street blocks by cyclist harm."""

from datetime import date

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from pipeline.config import BORO_NAMES, KILLED_WEIGHT, OLDER_WEIGHT, RECENT_WEIGHT

CLASS = {"I": "protected", "II": "paint", "III": "sharrow"}


def scoring_windows(data_date: date) -> tuple[date, date]:
    """Window start (5 years back) and recent start (2 years back), both on the 1st of the month."""
    return date(data_date.year - 5, data_date.month, 1), date(data_date.year - 2, data_date.month, 1)


def current_facility(routes: pd.DataFrame) -> pd.Series:
    """Today's lane class per padded segmentid: protected / paint / sharrow."""
    r = routes[(routes["onoffst"] == "ON") & (routes["status"] == "Current") & routes["facilitycl"].isin(list(CLASS))]
    r = r.assign(segmentid=r["segmentid"].str.strip().str.zfill(7), facility=r["facilitycl"].map(CLASS))
    return r.drop_duplicates("segmentid").set_index("segmentid")["facility"]


def score_blocks(crashes: pd.DataFrame, lion: pd.DataFrame, routes: pd.DataFrame,
                 window_start: date, recent_start: date) -> pd.DataFrame:
    c = crashes[crashes["segmentid"].notna()].copy()
    c["riders_injured"] = pd.to_numeric(c["riders_injured"]).fillna(0)
    c["riders_killed"] = pd.to_numeric(c["riders_killed"]).fillna(0)
    day = c["crash_date"].str[:10]

    # Scored = reliable match, inside the window, and the rider had no physical protection that day
    scored = c[c["match_confidence"].isin(["high", "medium"]) & (day >= window_start.isoformat())
               & c["protection_class"].isin(["None", "Unprotected"])].copy()
    weight = np.where(scored["crash_date"].str[:10] >= recent_start.isoformat(), RECENT_WEIGHT, OLDER_WEIGHT)
    scored["harm"] = (scored["riders_killed"] * KILLED_WEIGHT + scored["riders_injured"]) * weight
    agg = scored.groupby("segmentid").agg(
        score=("harm", "sum"),
        crashes_5y=("collision_id", "count"),
        injured_5y=("riders_injured", "sum"),
        killed_5y=("riders_killed", "sum"),
        crashes_no_lane_5y=("protection_class", lambda s: int((s == "None").sum())),
        last_crash_date=("crash_date", lambda s: s.max()[:10]),
    )
    total = c.groupby("segmentid").agg(crashes_all_years=("collision_id", "count"))

    # One row per LION block that has any placed bike crash
    lg = lion[lion["segmentid"].isin(total.index) & (lion["featuretyp"] == "0")]
    lg = lg.drop_duplicates("segmentid").reset_index(drop=True)
    g = gpd.GeoDataFrame(
        {"segmentid": lg["segmentid"], "street": lg["street"],
         # lboro may be "3", "3.0" or an int: normalize before the lookup
         "borough": pd.to_numeric(lg["lboro"], errors="coerce").astype("Int64").astype("string").map(BORO_NAMES),
         "posted_speed": pd.to_numeric(lg["posted_speed"], errors="coerce").astype("Int64"),
         "travel_lanes": pd.to_numeric(lg["number_travel_lanes"], errors="coerce").astype("Int64")},
        geometry=shapely.from_geojson(lg["geometry"].values), crs="EPSG:4326",
    )
    g = g.join(total, on="segmentid").join(agg, on="segmentid")
    g["score"] = g["score"].fillna(0).astype(float)
    for col in ["crashes_all_years", "crashes_5y", "injured_5y", "killed_5y", "crashes_no_lane_5y"]:
        g[col] = g[col].fillna(0).astype(int)
    g["current_facility"] = g["segmentid"].map(current_facility(routes)).astype(object).fillna("none")
    g["tier"] = g["current_facility"].map({"none": 1, "paint": 2, "sharrow": 2}).astype("Int64")

    mid = g.to_crs(epsg=2263).geometry.interpolate(0.5, normalized=True)
    mid_ll = gpd.GeoSeries(mid, crs="EPSG:2263").to_crs(epsg=4326)
    g["mid_lat"], g["mid_lon"] = mid_ll.y.round(6), mid_ll.x.round(6)

    # Rank: every Tier 1 (no lane) block above every Tier 2 (paint/sharrow) block
    rankable = g["tier"].notna() & (g["score"] > 0)
    order = g[rankable].sort_values(["tier", "score", "killed_5y", "crashes_5y", "segmentid"],
                                    ascending=[True, False, False, False, True])
    g["priority_rank"] = pd.Series(np.arange(1, len(order) + 1), index=order.index).astype("Int64")
    g["rank_in_tier"] = order.groupby("tier").cumcount().add(1).astype("Int64")

    cols = ["segmentid", "street", "borough", "posted_speed", "travel_lanes", "crashes_all_years", "score",
            "crashes_5y", "injured_5y", "killed_5y", "crashes_no_lane_5y", "last_crash_date",
            "current_facility", "tier", "priority_rank", "rank_in_tier", "mid_lat", "mid_lon", "geometry"]
    out = pd.DataFrame(g[cols]).sort_values("priority_rank", na_position="last").reset_index(drop=True)
    return out.astype(object).where(out.notna(), None)  # real nulls, never NaN
