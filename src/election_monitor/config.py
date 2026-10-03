from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "election_monitor.sqlite3"
DEFAULT_POLL_INTERVAL_SECONDS = 60
COUNCIL_REGISTRY_CACHE_PATH = DATA_DIR / "councils.json"
CANDIDATES_CACHE_PATH = DATA_DIR / "kvrk.csv"
COUNCIL_REGISTRY_CACHE_SECONDS = 24 * 60 * 60
COUNCIL_REGISTRY_PAGE_URL = "https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm"
COUNCIL_GEOGRAPHY_URL = "https://volby.gov.cz/opendata/kv2026/KV_nuts.htm"
ELECTION_DATE = "20261009"
SOURCE_URL_TEMPLATE = (
    "https://volby.gov.cz/appdata/kv2026/"
    f"{ELECTION_DATE}/odata/zastup/vysledky_obec_{{municipality_code}}{{suffix}}.xml"
)


def source_url_for(municipality_code: str, suffix: str = "") -> str:
    code = municipality_code.strip()
    if not code.isascii() or not code.isdigit() or len(code) > 6:
        raise ValueError("Municipality code must contain 1 to 6 digits.")
    return SOURCE_URL_TEMPLATE.format(municipality_code=code.zfill(6), suffix=suffix)
