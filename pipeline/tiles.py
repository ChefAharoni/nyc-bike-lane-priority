"""Vector tiles (PMTiles) for the map, built with tippecanoe from line-delimited GeoJSON."""
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd

from pipeline.lane_status import CLASS

logger = logging.getLogger(__name__)

COMMON = ["-zg", "--drop-densest-as-needed", "--extend-zooms-if-still-dropping", "--force", "-q"]


def _blocks_lines(segs: gpd.GeoDataFrame):
    segs = segs.to_crs(epsg=4326) if segs.crs is not None and segs.crs.to_epsg() != 4326 else segs
    for sid, geom in zip(segs["segmentid"], segs.geometry):
        if geom is not None and not geom.is_empty:
            yield {"type": "Feature", "properties": {"segmentid": str(sid)}, "geometry": geom.__geo_interface__}


def _lane_lines(routes: pd.DataFrame):
    r = routes[(routes["status"] == "Current") & routes["facilitycl"].isin(list(CLASS))
               & routes["onoffst"].isin(["ON", "OFF"]) & routes["the_geom"].notna()]
    for geom, cls, onoff in zip(r["the_geom"], r["facilitycl"], r["onoffst"]):
        yield {"type": "Feature", "properties": {"facility": CLASS[cls], "onoff": onoff},
               "geometry": json.loads(geom)}


def _crash_points(crashes: pd.DataFrame):
    lat = pd.to_numeric(crashes["latitude"], errors="coerce")
    lon = pd.to_numeric(crashes["longitude"], errors="coerce")
    inj = pd.to_numeric(crashes["riders_injured"]).fillna(0).astype(int)
    kil = pd.to_numeric(crashes["riders_killed"]).fillna(0).astype(int)
    for i in range(len(crashes)):
        if pd.isna(lat.iloc[i]) or pd.isna(lon.iloc[i]):
            continue
        row = crashes.iloc[i]
        yield {"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(lon.iloc[i]), float(lat.iloc[i])]},
               "properties": {
                   "collision_id": str(row["collision_id"]), "date": str(row["crash_date"])[:10],
                   "lane": str(row["lane"]), "injured": int(inj.iloc[i]), "killed": int(kil.iloc[i]),
                   "street": "" if pd.isna(row["matched_street"]) else str(row["matched_street"]),
                   "segmentid": "" if pd.isna(row["segmentid"]) else str(row["segmentid"])}}


def _tippecanoe(features, layer: str, out: Path, tmp: Path, extra: list[str]) -> None:
    src = tmp / f"{layer}.geojsonl"
    with open(src, "w", encoding="utf-8") as f:
        for feat in features:
            f.write(json.dumps(feat, separators=(",", ":")) + "\n")
    cmd = ["tippecanoe", *COMMON, *extra, "-l", layer, "-o", str(out), str(src)]
    logger.info("tippecanoe: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


# blocks.pmtiles uses -d14 (full detail 14 bits per tile). At the default 12 bits a block shorter than
# about 2 m at z12 collapses to a point and vanishes; one ranked block (0354377) was lost that way.
def build_tiles(lion_segments: gpd.GeoDataFrame, routes: pd.DataFrame, crashes_5y: pd.DataFrame,
                out_dir: Path) -> None:
    """Write blocks.pmtiles, bike_lanes.pmtiles and crashes.pmtiles to out_dir.
    crashes_5y needs collision_id, crash_date, latitude, longitude, lane, riders_injured, riders_killed,
    matched_street, segmentid. Raises if tippecanoe is missing."""
    if shutil.which("tippecanoe") is None:
        raise RuntimeError("tippecanoe not found on PATH; install it or run with --no-tiles")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        _tippecanoe(_blocks_lines(lion_segments), "blocks", out_dir / "blocks.pmtiles", tmp, ["-Z10", "-d14"])
        _tippecanoe(_lane_lines(routes), "lanes", out_dir / "bike_lanes.pmtiles", tmp, ["-Z10"])
        _tippecanoe(_crash_points(crashes_5y), "crashes", out_dir / "crashes.pmtiles", tmp, ["-Z10", "-r1"])
