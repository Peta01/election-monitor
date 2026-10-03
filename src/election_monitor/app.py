from __future__ import annotations

from .config import DEFAULT_SOURCE_URL, DB_PATH
from .db import Repository
from .downloader import Downloader
from .parser import ElectionParser


def main() -> None:
    downloader = Downloader()
    payload = downloader.fetch(DEFAULT_SOURCE_URL)

    parser = ElectionParser()
    snapshot = parser.parse(
        payload.content,
        municipality_code="000000",
        source_url=payload.url,
        source_hash=payload.content_hash,
    )

    repo = Repository(DB_PATH)
    repo.save_snapshot(snapshot)
    print("Snapshot stored")


if __name__ == "__main__":
    main()
