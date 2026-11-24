"""Bike crash definition: which hurt people count as riders, and per-crash rider counts."""
import pandas as pd


def normalize_vehicle(label) -> str:
    """Map free-text vehicle_type to bicycle / e-bike / e-scooter / excluded / unknown."""
    if label is None or pd.isna(label):
        return "unknown"
    t = str(label).strip().upper()
    if any(k in t for k in ("MOPED", "MOTOR", "DIRT", "MINIBIKE")):
        return "excluded"
    if t.startswith("E-S") or "SCOOT" in t:
        return "e-scooter"
    if t.startswith("E-B") or t.startswith("EBIK"):
        return "e-bike"
    if any(k in t for k in ("BIKE", "BICY", "PEDICAB")):
        return "bicycle"
    return "unknown"


def _none_for_missing(df: pd.DataFrame, skip=()) -> pd.DataFrame:
    for c in df.columns:
        if c not in skip:
            df[c] = df[c].astype(object).where(df[c].notna(), None)
    return df


def build_bike_persons(persons: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    hurt = persons[persons["person_injury"].isin(["Injured", "Killed"])]
    hurt = hurt[hurt["person_type"].isin(["Bicyclist", "Other Motorized"])]
    # Person.vehicle_id points at Vehicles.unique_id (not Vehicles.vehicle_id)
    veh = (vehicles[["collision_id", "unique_id", "vehicle_type"]]
           .drop_duplicates(["collision_id", "unique_id"])
           .rename(columns={"unique_id": "vehicle_id"}))
    df = hurt.merge(veh, on=["collision_id", "vehicle_id"], how="left")
    df["vehicle_class"] = df["vehicle_type"].map(normalize_vehicle)

    bicyclist = df["person_type"] == "Bicyclist"
    ebike_or_scooter = df["vehicle_class"].isin(["e-bike", "e-scooter"])
    # Every Bicyclist counts; Other Motorized only on an e-bike or e-scooter
    df = df[bicyclist | ebike_or_scooter].copy()
    df["bike_type"] = df["vehicle_class"].where(ebike_or_scooter, "bicycle")

    keep = ["collision_id", "person_id", "vehicle_id", "crash_date", "person_type", "person_injury",
            "vehicle_type", "bike_type", "person_age", "person_sex", "bodily_injury", "safety_equipment"]
    out = df[[c for c in keep if c in df.columns]].reset_index(drop=True)
    return _none_for_missing(out)


def build_bike_crashes(bike_persons: pd.DataFrame, crashes: pd.DataFrame) -> pd.DataFrame:
    agg = bike_persons.groupby("collision_id").agg(
        riders_injured=("person_injury", lambda s: int((s == "Injured").sum())),
        riders_killed=("person_injury", lambda s: int((s == "Killed").sum())),
        bicycle_riders=("bike_type", lambda s: int((s == "bicycle").sum())),
        ebike_riders=("bike_type", lambda s: int((s == "e-bike").sum())),
        escooter_riders=("bike_type", lambda s: int((s == "e-scooter").sum())),
        bike_types=("bike_type", lambda s: "+".join(sorted(set(s)))),
    ).reset_index()
    cols = ["collision_id", "crash_date", "crash_time", "borough", "zip_code", "latitude", "longitude",
            "on_street_name", "cross_street_name", "off_street_name",
            "contributing_factor_vehicle_1", "contributing_factor_vehicle_2", "inclusion_reason"]
    c = crashes[[x for x in cols if x in crashes.columns]].drop_duplicates("collision_id")
    out = c.merge(agg, on="collision_id", how="inner")
    counts = ["riders_injured", "riders_killed", "bicycle_riders", "ebike_riders", "escooter_riders"]
    return _none_for_missing(out, skip=counts)
