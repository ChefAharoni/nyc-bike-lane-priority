import shutil

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString

from pipeline.tiles import build_tiles

pytestmark = pytest.mark.skipif(shutil.which("tippecanoe") is None, reason="tippecanoe not installed")


def test_tiles_written(tmp_path):
    segs = gpd.GeoDataFrame(
        {"segmentid": ["0000001", "0000002"]},
        geometry=[LineString([(990000, 200000), (990200, 200000)]),
                  LineString([(990200, 200000), (990400, 200100)])], crs="EPSG:2263")
    routes = pd.DataFrame({
        "the_geom": ['{"type":"MultiLineString","coordinates":[[[-73.98,40.73],[-73.97,40.74]]]}'] * 3,
        "status": ["Current", "Current", "Retired"], "onoffst": ["ON", "OFF", "ON"],
        "facilitycl": ["I", "II", "III"]})
    crashes = pd.DataFrame({
        "collision_id": ["a", "b"], "crash_date": ["2026-10-01T00:00:00.000"] * 2,
        "latitude": ["40.73", "40.731"], "longitude": ["-73.98", "-73.981"],
        "lane": ["none", "unknown"], "riders_injured": [1, 0], "riders_killed": [0, 1],
        "matched_street": ["MAIN ST", None], "segmentid": ["0000001", None]})
    build_tiles(segs, routes, crashes, tmp_path)
    for n in ("blocks", "bike_lanes", "crashes"):
        assert (tmp_path / f"{n}.pmtiles").stat().st_size > 0
    assert (tmp_path / "blocks.pmtiles").read_bytes()[:7] == b"PMTiles"
    assert not list(tmp_path.glob("*.geojson*"))
