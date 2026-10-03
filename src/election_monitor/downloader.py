from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests


@dataclass(slots=True)
class DownloadedPayload:
    url: str
    content: bytes
    fetched_at: datetime
    content_hash: str


class Downloader:
    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, url: str) -> DownloadedPayload:
        response = requests.get(
            url,
            timeout=self.timeout_seconds,
            headers={"User-Agent": "election-monitor/0.1"},
        )
        response.raise_for_status()
        content = response.content
        return DownloadedPayload(
            url=url,
            content=content,
            fetched_at=datetime.now(timezone.utc),
            content_hash=hashlib.sha256(content).hexdigest(),
        )


def save_raw(payload: DownloadedPayload, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload.content)
