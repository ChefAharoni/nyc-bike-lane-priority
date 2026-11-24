import pandas as pd
import pytest

from pipeline.bike_crashes import (
    build_bike_crashes,
    build_bike_persons,
    normalize_vehicle,
)


@pytest.mark.parametrize(
    "label,expected",
    [
        ("E-Bike", "e-bike"),
        ("E-Bik", "e-bike"),
        ("E-Scooter (standing)", "e-scooter"),
        ("Standing Scooter", "e-scooter"),
        ("Moped", "excluded"),
        ("Motorbike", "excluded"),
        ("BICYCLE", "bicycle"),
        ("Pedicab", "bicycle"),
        (None, "unknown"),
        (float("nan"), "unknown"),
        (pd.NA, "unknown"),
    ],
)
def test_normalize_vehicle(label, expected):
    assert normalize_vehicle(label) == expected


def _person(cid, pid, vid, ptype="Bicyclist", injury="Injured"):
    return {"collision_id": cid, "person_id": pid, "vehicle_id": vid,
            "person_type": ptype, "person_injury": injury}


def _vehicle(cid, uid, vid, vtype):
    return {"collision_id": cid, "unique_id": uid, "vehicle_id": vid, "vehicle_type": vtype}


def test_person_joins_vehicle_on_unique_id():
    persons = pd.DataFrame([_person("1", "p1", "u1", ptype="Other Motorized")], dtype=object)
    # vehicle_id column deliberately differs from unique_id: only unique_id may match
    vehicles = pd.DataFrame([_vehicle("1", "u1", "other", "E-Bike")], dtype=object)
    out = build_bike_persons(persons, vehicles)
    assert out["bike_type"].tolist() == ["e-bike"]

    vehicles = pd.DataFrame([_vehicle("1", "zzz", "u1", "E-Bike")], dtype=object)
    assert build_bike_persons(persons, vehicles).empty


def test_other_motorized_moped_dropped_bicyclist_kept():
    persons = pd.DataFrame([
        _person("1", "p1", "u1", ptype="Bicyclist"),
        _person("2", "p2", "u2", ptype="Other Motorized"),
    ], dtype=object)
    vehicles = pd.DataFrame([
        _vehicle("1", "u1", "v1", "Moped"),
        _vehicle("2", "u2", "v2", "Moped"),
    ], dtype=object)
    out = build_bike_persons(persons, vehicles)
    assert out["person_id"].tolist() == ["p1"]
    assert out["bike_type"].tolist() == ["bicycle"]


def test_unspecified_injury_dropped():
    persons = pd.DataFrame([
        _person("1", "p1", "u1", injury="Unspecified"),
        _person("1", "p2", "u1", injury=None),
    ], dtype=object)
    vehicles = pd.DataFrame([_vehicle("1", "u1", "v1", "Bike")], dtype=object)
    assert build_bike_persons(persons, vehicles).empty


def test_crash_counts():
    persons = pd.DataFrame([
        _person("1", "p1", "u1", ptype="Other Motorized", injury="Injured"),
        _person("1", "p2", "u2", ptype="Bicyclist", injury="Killed"),
    ], dtype=object)
    vehicles = pd.DataFrame([
        _vehicle("1", "u1", "v1", "E-Bike"),
        _vehicle("1", "u2", "v2", "Bike"),
    ], dtype=object)
    crashes = pd.DataFrame([
        {"collision_id": "1", "crash_date": "2024-01-01", "borough": "BROOKLYN", "latitude": None},
        {"collision_id": "2", "crash_date": "2024-01-02", "borough": "QUEENS"},
    ], dtype=object)
    bp = build_bike_persons(persons, vehicles)
    out = build_bike_crashes(bp, crashes)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["riders_injured"] == 1
    assert row["riders_killed"] == 1
    assert row["bicycle_riders"] == 1
    assert row["ebike_riders"] == 1
    assert row["escooter_riders"] == 0
    assert row["bike_types"] == "bicycle+e-bike"
    # a missing value stays None (never NaN) and counts stay ints
    assert row["latitude"] is None
    assert out["riders_injured"].dtype.kind == "i"
    assert row["crash_date"] == "2024-01-01"
