from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "election_monitor.sqlite3"
DEFAULT_POLL_INTERVAL_SECONDS = 60
DEFAULT_SOURCE_URL = "https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm"
