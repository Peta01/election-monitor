from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Callable

import requests

from .app import fetch_current_snapshot
from .config import DB_PATH, DEFAULT_POLL_INTERVAL_SECONDS
from .db import Repository
from .municipalities import MunicipalityOption
from .parser import ParserError

LOGGER = logging.getLogger(__name__)


class PollingService:
    def __init__(
        self,
        repository: Repository | None = None,
        fetch_snapshot: Callable = fetch_current_snapshot,
        interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> None:
        self.repository = repository or Repository(DB_PATH)
        self.fetch_snapshot = fetch_snapshot
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="election-result-poller",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def track(self, option: MunicipalityOption) -> None:
        self.repository.add_tracked_municipality(option)
        self._wake.set()

    def poll_once(self) -> None:
        for municipality in self.repository.list_tracked_municipalities():
            if self._stop.is_set():
                return
            code = municipality["code"]
            try:
                self.repository.update_poll_attempt(code)
                snapshot = self.fetch_snapshot(code)
            except requests.HTTPError as exc:
                # 404 znamená, že ČSÚ výsledky pro obec ještě nezveřejnil.
                if exc.response is not None and exc.response.status_code == 404:
                    LOGGER.info("Results for %s are not published yet", code)
                    continue
                LOGGER.warning("Polling results for %s failed: %s", code, exc)
                self._save_failure(code, exc)
                continue
            except (requests.RequestException, ParserError, ValueError) as exc:
                LOGGER.warning("Polling results for %s failed: %s", code, exc)
                self._save_failure(code, exc)
                continue

            try:
                self.repository.save_snapshot(snapshot)
                self.repository.update_poll_success(code)
            except (OSError, sqlite3.Error):
                LOGGER.exception("Database operation failed while polling %s", code)

    def _save_failure(self, code: str, exc: Exception) -> None:
        try:
            self.repository.update_poll_failure(code, str(exc))
        except (OSError, sqlite3.Error):
            LOGGER.exception("Could not save polling error for %s", code)

    def _run(self) -> None:
        self._wake.set()
        while not self._stop.is_set():
            self._wake.wait(timeout=self.interval_seconds)
            self._wake.clear()
            if not self._stop.is_set():
                self.poll_once()
