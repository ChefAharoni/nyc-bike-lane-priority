"""Fetch NYC Open Data tables (Socrata), candidate crashes and the LION street file."""

import json
import logging
import os
import re
import shutil
import time
import zipfile
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pyogrio
import requests
from shapely.geometry import mapping

from pipeline.config import BASE_URL, DATASETS

logger = logging.getLogger(__name__)

PAGE_SIZE = 50000
RETRIES = 5
BACKOFF_SECONDS = 1.0
TIMEOUT = 120
BATCH = 200  # collision_ids per request, keeps the URL short

CYCLIST_WHERE = "number_of_cyclist_injured > 0 OR number_of_cyclist_killed > 0"
PERSON_WHERE = "person_type in('Bicyclist','Other Motorized')"
VEHICLE_TERMS = ["BIKE", "BICY", "SCOOT", "MOPED", "CYCLE"]
VEHICLE_WHERE = " OR ".join(f"upper(vehicle_type) like '%{t}%'" for t in VEHICLE_TERMS)

LION_KEEP = [
    "SegmentID", "Street", "FeatureTyp", "SegmentTyp", "RB_Layer", "NonPed", "TrafDir",
    "LBoro", "RBoro", "NodeIDFrom", "NodeIDTo", "StreetWidth_Max", "Number_Travel_Lanes",
    "POSTED_SPEED", "BikeLane", "BIKE_TRAFDIR", "SHAPE_Length",
]

# Patchable in tests so backoff does not actually wait.
sleep = time.sleep


class FetchError(RuntimeError):
    """A fetch failed after retries, or returned incomplete data."""


def _headers() -> dict[str, str]:
    token = os.environ.get("SOCRATA_APP_TOKEN")
    return {"X-App-Token": token} if token else {}


def _get(session, url: str, params: dict | None = None):
    """GET with retries on 429/5xx/timeouts and exponential backoff."""
    last = "no attempts"
    for attempt in range(RETRIES):
        if attempt:
            sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
        try:
            resp = session.get(url, params=params, headers=_headers(), timeout=TIMEOUT)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last = repr(exc)
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            last = f"HTTP {resp.status_code}"
            continue
        resp.raise_for_status()
        return resp
    raise FetchError(f"GET {url} failed after {RETRIES} attempts: {last}")


def _to_text(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return json.dumps(v) if isinstance(v, (dict, list)) else str(v)


def fetch_socrata(
    dataset_id: str,
    where: str | None = None,
    select: str | None = None,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Page through a Socrata dataset. Nested values (geometry) become JSON strings."""
    session = session or requests.Session()
    url = f"{BASE_URL}/resource/{dataset_id}.json"

    count_params = {"$select": "count(*)"}
    if where:
        count_params["$where"] = where
    total = int(_get(session, url, count_params).json()[0]["count"])

    rows: list[dict] = []
    offset = 0
    while True:
        params = {"$limit": PAGE_SIZE, "$offset": offset, "$order": ":id"}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        page = _get(session, url, params).json()
        if not page and offset < total:
            raise FetchError(f"{dataset_id}: empty page at offset {offset}, expected {total} rows")
        rows.extend(page)
        logger.info("%s: fetched %d rows", dataset_id, len(rows))
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    if len(rows) < total:
        raise FetchError(f"{dataset_id}: fetched {len(rows)} rows, expected at least {total}")

    df = pd.DataFrame(rows)
    for col in df.columns:
        df[col] = df[col].map(_to_text).astype(object)
    return df


def candidate_crashes(persons: pd.DataFrame, fetch: Callable = fetch_socrata) -> pd.DataFrame:
    """Crashes NYPD flagged with a cyclist hurt, plus crashes where the person table
    shows a hurt bike/e-bike/scooter rider but the crash row has no cyclist count."""
    flagged = fetch(DATASETS["crashes"], CYCLIST_WHERE)
    flagged["inclusion_reason"] = "cyclist_count"

    hurt = persons[persons["person_injury"].isin(["Injured", "Killed"])]
    # collision_id is a 32-char hex hash; keep only well-formed ids so quoting is safe
    ids = {i for i in hurt["collision_id"].dropna() if re.fullmatch(r"[0-9a-f]{32}", i)}
    already = set(flagged["collision_id"]) if "collision_id" in flagged else set()
    missing = sorted(ids - already)
    logger.info("Fetching %d crashes missing from the cyclist filter", len(missing))

    extra = []
    for i in range(0, len(missing), BATCH):
        quoted = ",".join(f"'{c}'" for c in missing[i:i + BATCH])
        df = fetch(DATASETS["crashes"], f"collision_id in({quoted})")
        df["inclusion_reason"] = "person_table"
        extra.append(df)

    crashes = pd.concat([flagged] + extra, ignore_index=True)
    crashes = crashes.drop_duplicates("collision_id").drop(columns=["location"], errors="ignore")
    return crashes.astype(object).where(crashes.notna(), None)  # real nulls, never "NaN"


SOURCES = ["crashes", "persons", "vehicles", "routes", "council", "community"]


def fetch_sources(raw_dir: Path | None) -> dict[str, pd.DataFrame]:
    """Fetch all Socrata sources. With raw_dir, reuse parquet from a previous run
    (dev cache) or write it after fetching."""
    if raw_dir is not None:
        raw_dir = Path(raw_dir)
        files = {name: raw_dir / f"{name}.parquet" for name in SOURCES}
        if all(p.exists() for p in files.values()):
            logger.info("reading cached sources from %s", raw_dir)
            out = {}
            for name, p in files.items():
                df = pd.read_parquet(p)
                out[name] = df.astype(object).where(df.notna(), None)  # real nulls, never NaN
            return out

    persons = fetch_socrata(DATASETS["persons"], PERSON_WHERE)
    frames = {
        "crashes": candidate_crashes(persons, fetch=fetch_socrata),
        "persons": persons,
        "vehicles": fetch_socrata(DATASETS["vehicles"], VEHICLE_WHERE),
        "routes": fetch_socrata(DATASETS["routes"]),
        "council": fetch_socrata(DATASETS["council"]),
        "community": fetch_socrata(DATASETS["community"]),
    }
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        for name, df in frames.items():
            df.to_parquet(raw_dir / f"{name}.parquet", index=False)
    return frames


def download_lion(cache_dir: Path, session: requests.Session | None = None) -> Path:
    """Download and unzip the LION file geodatabase; returns the .gdb path."""
    session = session or requests.Session()
    dataset = DATASETS["lion"]
    meta = _get(session, f"{BASE_URL}/api/views/{dataset}.json").json()
    # rowsUpdatedAt is stale for this dataset; blobId changes when the file is replaced
    blob_id = meta["blobId"]
    target = Path(cache_dir) / blob_id

    if not target.exists():
        target.mkdir(parents=True)
        zip_path = target / "lion.zip"
        try:
            resp = session.get(
                f"{BASE_URL}/api/views/{dataset}/files/{blob_id}?download=true",
                headers=_headers(), timeout=TIMEOUT, stream=True,
            )
            resp.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(1 << 20):
                    f.write(chunk)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(target)
            zip_path.unlink()
        except Exception:
            # leave no half-extracted dir that would be mistaken for a cache hit
            shutil.rmtree(target, ignore_errors=True)
            raise

    found = sorted(target.rglob("*.gdb"))
    if not found:
        raise FetchError(f"no .gdb found in {target}")
    return found[0]


def read_lion(gdb: Path, layer: str = "lion") -> pd.DataFrame:
    """LION as a string-typed frame: lowercase columns, WGS84 GeoJSON text in `geometry`."""
    gdf = pyogrio.read_dataframe(gdb, layer=layer, columns=LION_KEEP).to_crs(epsg=4326)

    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["SegmentID"] = df["SegmentID"].astype(str).str.strip().str.zfill(7)
    df["geometry"] = gdf.geometry.map(lambda g: json.dumps(mapping(g)) if g is not None else None)
    for c in df.columns:  # whole-number floats (e.g. borough 2.0) -> integers
        if pd.api.types.is_float_dtype(df[c]) and (df[c].dropna() % 1 == 0).all():
            df[c] = df[c].astype("Int64")
    df.columns = [c.lower() for c in df.columns]
    return df.astype("string")
