import threading
from datetime import UTC, datetime

import requests

from election_monitor.db import Repository
from election_monitor.models import (
    ElectionSnapshot,
    MunicipalityRef,
    PollingProgress,
)
from election_monitor.municipalities import MunicipalityOption
from election_monitor.polling import PollingService


def test_polling_service_keeps_successful_snapshots_and_surfaces_failures(
    tmp_path,
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option("123456", "Úspěšná obec"))
    repository.add_tracked_municipality(_option("654321", "Obec bez dat"))

    def fetch(code: str) -> ElectionSnapshot:
        if code == "654321":
            raise requests.HTTPError("404 Not Found")
        return _snapshot(code)

    service = PollingService(repository, fetch_snapshot=fetch)
    service.poll_once()

    tracked = {item["code"]: item for item in repository.list_tracked_municipalities()}
    assert tracked["123456"]["last_error"] is None
    assert tracked["123456"]["last_success_at"] is not None
    assert tracked["654321"]["last_error"] == "404 Not Found"
    assert repository.get_latest_snapshot("123456").municipality.name == "Úspěšná obec"
    assert repository.get_latest_snapshot("654321") is None


def test_unpublished_results_404_is_not_reported_as_error(tmp_path) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option("544779", "Lisov"))

    def fetch(code: str) -> ElectionSnapshot:
        response = requests.Response()
        response.status_code = 404
        raise requests.HTTPError("404 Not Found", response=response)

    PollingService(repository, fetch_snapshot=fetch).poll_once()

    tracked = repository.list_tracked_municipalities()[0]
    assert tracked["last_error"] is None
    assert tracked["last_attempt_at"] is not None


def test_snapshot_is_saved_only_when_processed_districts_change(tmp_path) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option("123456", "Obec"))

    def save(processed: int, source_hash: str) -> int:
        snapshot = _snapshot("123456")
        snapshot.progress = PollingProgress(processed, 2)
        snapshot.source_hash = source_hash
        return repository.save_snapshot(snapshot)

    first = save(0, "a")
    assert save(0, "b") == first
    second = save(1, "c")
    assert second != first
    assert save(1, "d") == second


def test_tracking_survives_repository_recreation(tmp_path) -> None:
    database = tmp_path / "elections.sqlite3"
    Repository(database).add_tracked_municipality(_option("123456", "Testov"))

    restarted_repository = Repository(database)

    assert [
        item["code"] for item in restarted_repository.list_tracked_municipalities()
    ] == ["123456"]


def test_polling_service_runs_immediately_and_repeats_until_stopped(tmp_path) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option("123456", "Testov"))
    poll_completed = threading.Event()
    calls = 0

    def fetch(_code: str) -> ElectionSnapshot:
        nonlocal calls
        calls += 1
        poll_completed.set()
        return _snapshot("123456")

    service = PollingService(
        repository,
        fetch_snapshot=fetch,
        interval_seconds=0.05,
    )
    service.start()
    try:
        assert poll_completed.wait(timeout=1)
        poll_completed.clear()
        assert poll_completed.wait(timeout=1)
    finally:
        service.stop()

    assert calls >= 2


def _option(code: str, name: str) -> MunicipalityOption:
    return MunicipalityOption(code, name, name, "7200", "Zlínský kraj", "7204", "Zlín")


def _snapshot(code: str) -> ElectionSnapshot:
    return ElectionSnapshot(
        municipality=MunicipalityRef(code, "Úspěšná obec"),
        fetched_at=datetime.now(UTC),
        source_url="https://example.test/results.xml",
        source_hash="snapshot-hash",
        progress=PollingProgress(0, 2),
        party_results=[],
        seats_to_elect=5,
    )
