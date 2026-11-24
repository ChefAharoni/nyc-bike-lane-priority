from pipeline import config


def test_constants():
    assert config.DATASETS["community"] == "5crt-au7u"
    assert config.JIA_CODES == {
        "164", "226", "227", "228", "355", "356",
        "480", "481", "482", "483", "484", "595",
    }
    assert config.SNAP_FT == 100
