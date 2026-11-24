"""Label each matched crash with the bike lane that was on its block on the crash date."""
import pandas as pd

CLASS = {"I": "protected", "II": "paint", "III": "sharrow"}
RANK = {"protected": 3, "paint": 2, "sharrow": 1, "none": 0}


def on_street_routes(routes):
    """On-street bike routes with the date range each one was on the street."""
    r = routes[(routes["onoffst"] == "ON") & routes["facilitycl"].isin(list(CLASS))].copy()
    r["segmentid"] = r["segmentid"].str.strip().str.zfill(7)
    r["facility"] = r["facilitycl"].map(CLASS)
    r["start"] = pd.to_datetime(r["instdate"].str[:10], errors="coerce")
    r["end"] = pd.to_datetime(r["ret_date"].str[:10], errors="coerce")
    # Retired with no retire date: we can't say when it was on the street, so it never counts
    r = r[~((r["status"] == "Retired") & r["end"].isna())]
    r["detail"] = r["ft_facilit"].fillna(r["tf_facilit"])
    return r[["segmentid", "facility", "detail", "start", "end"]]


def facility_on(pairs, routes):
    """pairs: collision_id, segmentid, crash_dt -> best facility in effect that day (else 'none')."""
    j = pairs.merge(routes, on="segmentid", how="left")
    active = (j["start"] <= j["crash_dt"]) & (j["end"].isna() | (j["end"] > j["crash_dt"]))
    j.loc[~active, ["facility", "detail", "start"]] = [None, None, pd.NaT]
    j["facility"] = j["facility"].fillna("none")
    j["rank"] = j["facility"].map(RANK)
    # If two routes overlapped that day (a lane being upgraded), keep the stronger one
    j = j.sort_values("rank", ascending=False).drop_duplicates(["collision_id"])
    out = j.set_index("collision_id")[["facility", "detail", "start"]]
    # Keep dtypes stable even when no pair is given (an empty frame would otherwise turn float)
    return out.astype({"facility": object, "detail": object, "start": "datetime64[ns]"})


def enrich(crashes, match, routes):
    r = on_street_routes(routes)
    c = crashes.merge(match, on="collision_id", how="left")
    c["crash_dt"] = pd.to_datetime(c["crash_date"].str[:10], errors="coerce")
    placed = c[c["segmentid"].notna()]

    main = facility_on(placed[["collision_id", "segmentid", "crash_dt"]], r)
    c["facility_at_crash"] = c["collision_id"].map(main["facility"]).astype(object).fillna("unknown")
    c["facility_detail"] = c["collision_id"].map(main["detail"])
    installed = pd.Series(main["start"].reindex(c["collision_id"]).to_numpy(), index=c.index)  # reindex: map fails on an empty datetime series
    c["lane_installed"] = installed.dt.strftime("%Y-%m-%d")

    # Corner crashes: the other block of the same street must agree, or confidence drops
    t = placed[placed["tie_segmentid"].notna()][["collision_id", "tie_segmentid", "crash_dt"]]
    tie = facility_on(t.rename(columns={"tie_segmentid": "segmentid"}), r)["facility"]
    c["tie_facility"] = c["collision_id"].map(tie)
    differs = c["tie_facility"].notna() & (c["tie_facility"] != c["facility_at_crash"]) & (c["match_confidence"] == "high")
    c.loc[differs, ["match_confidence", "match_reason"]] = ["medium", "corner_blocks_differ"]

    c["protection_class"] = c["facility_at_crash"].map(
        {"protected": "Protected", "paint": "Unprotected", "sharrow": "Unprotected", "none": "None"}).fillna("Unknown")
    c["crash_year"] = c["crash_dt"].dt.year.astype("Int64")

    c = c.drop(columns=["crash_dt"])
    return c.astype(object).where(c.notna(), None)  # real nulls, never NaN
