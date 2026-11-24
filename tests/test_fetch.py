import json

import geopandas as gpd
import pandas as pd
import pytest
import requests
from shapely.geometry import LineString

from pipeline import fetch
from pipeline.fetch import FetchError, candidate_crashes, fetch_socrata, read_lion


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fetch, "sleep", lambda s: None)


class Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    """Answers the count pre-check with `total`, then data pages from `pages`."""

    def __init__(self, pages, total=None, script=None):
        self.pages, self.script = list(pages), list(script or [])
        self.total = total if total is not None else sum(len(p) for p in pages)
        self.data_calls = 0
        self.calls = 0

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls += 1
        if self.script:
            r = self.script.pop(0)
            if r is not None:
                return r
        if params.get("$select") == "count(*)":
            return Resp(200, [{"count": str(self.total)}])
        self.data_calls += 1
        return Resp(200, self.pages.pop(0))


def rows(n):
    return [{"a": str(i)} for i in range(n)]


def test_pages_until_short_page():
    s = FakeSession([rows(50000), rows(50000), rows(3)])
    df = fetch_socrata("x", session=s)
    assert len(df) == 100003
    assert s.data_calls == 3  # data pages only; the count pre-check is an extra request


def test_retries_then_succeeds():
    s = FakeSession([rows(2)], script=[Resp(503), Resp(503)])
    df = fetch_socrata("x", session=s)
    assert len(df) == 2
    assert s.calls == 4  # 2 failures + count + 1 data page


def test_gives_up_after_repeated_failures():
    s = FakeSession([], script=[Resp(500)] * 5)
    with pytest.raises(FetchError):
        fetch_socrata("x", session=s)


def test_empty_middle_page_raises():
    s = FakeSession([rows(50000), []], total=120000)
    with pytest.raises(FetchError):
        fetch_socrata("x", session=s)


def test_nested_values_become_json():
    s = FakeSession([[{"g": {"type": "Point"}, "n": 5, "z": None}]])
    df = fetch_socrata("x", session=s)
    assert df.loc[0, "g"] == '{"type": "Point"}'
    assert df.loc[0, "n"] == "5"
    assert df.loc[0, "z"] is None


def test_candidate_crashes_tops_up_from_persons():
    a, b, c = "a" * 32, "b" * 32, "c" * 32
    calls = []

    def fake_fetch(dataset_id, where=None, **kw):
        calls.append(where)
        if where.startswith("number_of_cyclist"):
            return pd.DataFrame({"collision_id": [a, b], "location": ["x", "y"]})
        assert f"'{c}'" in where and "bad id" not in where and f"'{a}'" not in where
        return pd.DataFrame({"collision_id": [c], "location": ["z"]})

    persons = pd.DataFrame({
        "collision_id": [a, c, "bad id", "d" * 32],
        "person_injury": ["Injured", "Injured", "Injured", "Unspecified"],
    })
    out = candidate_crashes(persons, fetch=fake_fetch)
    assert list(out["collision_id"]) == [a, b, c]
    assert list(out["inclusion_reason"]) == ["cyclist_count", "cyclist_count", "person_table"]
    assert "location" not in out.columns


def test_read_lion_shape(tmp_path):
    cols = {k: [1, 2] for k in fetch.LION_KEEP if k not in ("Street", "SegmentID", "geometry")}
    gdf = gpd.GeoDataFrame(
        {**cols, "SegmentID": ["123", " 0000456"], "Street": ["MAIN ST", "OAK AVE"],
         "LBoro": [2.0, 2.0]},
        geometry=[LineString([(990000, 200000), (990100, 200100)]),
                  LineString([(991000, 201000), (991100, 201100)])],
        crs="EPSG:2263",
    )
    path = tmp_path / "lion.gpkg"
    gdf.to_file(path, layer="lion", driver="GPKG")

    df = read_lion(path)
    assert set(df.columns) == {c.lower() for c in fetch.LION_KEEP} | {"geometry"}
    assert list(df["segmentid"]) == ["0000123", "0000456"]
    assert list(df["lboro"]) == ["2", "2"]
    assert all(str(t) == "string" for t in df.dtypes)
    geom = json.loads(df.loc[0, "geometry"])
    assert geom["type"] == "LineString"
    assert -74.1 < geom["coordinates"][0][0] < -73.7


def test_short_total_raises():
    s = FakeSession([rows(2)], total=5)
    with pytest.raises(FetchError):
        fetch_socrata("x", session=s)


def _patch_fetch(monkeypatch):
    calls = []

    def no_network(*a, **kw):
        raise AssertionError("real network attempted")

    monkeypatch.setattr(requests.Session, "get", no_network)
    monkeypatch.setattr(requests, "get", no_network)

    def fake(dataset_id, where=None, select=None, session=None):
        calls.append(dataset_id)
        return pd.DataFrame({"collision_id": ["a" * 32, "b" * 32], "v": ["x", None],
                             "person_injury": ["Injured", None]})

    monkeypatch.setattr(fetch, "fetch_socrata", fake)
    return calls


def test_fetch_sources_writes_and_reads_cache_with_none(tmp_path, monkeypatch):
    calls = _patch_fetch(monkeypatch)
    first = fetch.fetch_sources(tmp_path)
    assert set(first) == set(fetch.SOURCES)
    assert all((tmp_path / f"{n}.parquet").exists() for n in fetch.SOURCES)
    assert fetch.DATASETS["crashes"] in calls  # crashes path went through the fake too
    n_calls = len(calls)

    second = fetch.fetch_sources(tmp_path)
    assert len(calls) == n_calls  # cache hit, no network
    assert second["vehicles"].loc[1, "v"] is None
    assert second["vehicles"].loc[0, "v"] == "x"


class ZipSession:
    def __init__(self, zip_bytes=b"", blob="blob1"):
        self.zip_bytes, self.downloads, self.blob = zip_bytes, 0, blob

    def get(self, url, params=None, headers=None, timeout=None, stream=False):
        if url.endswith(".json"):
            return Resp(200, {"blobId": self.blob, "rowsUpdatedAt": 123})
        self.downloads += 1
        assert f"/files/{self.blob}?download=true" in url
        r = Resp(200)
        r.iter_content = lambda n: [self.zip_bytes]
        return r


def _zip_with_gdb(tmp_path):
    import zipfile
    z = tmp_path / "src.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("lion/lion.gdb/a00000001.gdbtable", "x")
    return z.read_bytes()


def test_download_lion_extracts_then_hits_cache(tmp_path):
    s = ZipSession(_zip_with_gdb(tmp_path))
    cache = tmp_path / "cache"
    gdb = fetch.download_lion(cache, session=s)
    assert gdb.name == "lion.gdb" and gdb.parent.parent == cache / "blob1"
    again = fetch.download_lion(cache, session=s)
    assert again == gdb and s.downloads == 1


def test_download_lion_cleans_up_after_bad_zip(tmp_path):
    s = ZipSession(b"not a zip")
    cache = tmp_path / "cache"
    with pytest.raises(Exception):
        fetch.download_lion(cache, session=s)
    assert not (cache / "blob1").exists()


def test_download_lion_keys_cache_on_blob_id(tmp_path):
    """rowsUpdatedAt is stale for LION; a new blobId means the file was replaced."""
    s = ZipSession(_zip_with_gdb(tmp_path))
    cache = tmp_path / "cache"
    first = fetch.download_lion(cache, session=s)
    s.blob = "blob2"
    second = fetch.download_lion(cache, session=s)
    assert s.downloads == 2 and second != first and second.parent.parent == cache / "blob2"
    s.blob = "blob1"
    assert fetch.download_lion(cache, session=s) == first and s.downloads == 2
