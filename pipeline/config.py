"""Constants shared across the pipeline."""

BASE_URL = "https://data.cityofnewyork.us"

DATASETS: dict[str, str] = {
    "crashes": "h9gi-nx95",
    "persons": "f55k-p6yu",
    "vehicles": "bm4k-52h4",
    "routes": "mzxg-pwib",
    "lion": "2v4z-66xt",
    "council": "872g-cjhh",
    "community": "5crt-au7u",
}

SNAP_FT = 100
TIE_FT = 3
KILLED_WEIGHT = 10
RECENT_WEIGHT = 1.0
OLDER_WEIGHT = 0.5

# Joint interest areas (parks, airports) in the community district layer.
JIA_CODES: frozenset[str] = frozenset(
    {"164", "226", "227", "228", "355", "356", "480", "481", "482", "483", "484", "595"}
)

BORO_NAMES = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}

GAP_BLOCKS = 2
SNAPSHOT_DAILY_DAYS = 90
