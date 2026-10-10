import threading
from datetime import UTC, datetime

import requests

from election_monitor.candidates import Candidate
from election_monitor.db import Repository
from election_monitor.models import (
    ElectionSnapshot,
    MunicipalityRef,
    PollingProgress,
)
from election_monitor.municipalities import MunicipalityOption
from election_monitor.polling import PollingService
from election_monitor.presentations import PRESENTATION_FORMAT_VERSION


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


def test_completed_municipality_presentation_is_generated_once_and_independently(
    tmp_path,
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option("111111", "Částečná obec"))
    repository.add_tracked_municipality(_option("222222", "Hotová obec"))
    repository.add_tracked_municipality(_option("333333", "Bez údaje"))
    generated: list[str] = []
    presentations_dir = tmp_path / "presentations"

    def fetch(code: str) -> ElectionSnapshot:
        snapshot = _snapshot(code)
        snapshot.municipality.name = "Částečná obec" if code == "111111" else "Hotová obec"
        if code == "111111":
            snapshot.progress = PollingProgress(1, 2)
        elif code == "222222":
            snapshot.progress = PollingProgress(2, 2)
        else:
            snapshot.progress = PollingProgress(0, 0)
        return snapshot

    def generate(snapshot: ElectionSnapshot, output_path) -> None:
        generated.append(snapshot.municipality.code)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF-test")

    PollingService(
        repository,
        fetch_snapshot=fetch,
        presentation_generator=generate,
        candidate_loader=lambda _code: [],
        presentations_dir=presentations_dir,
    ).poll_once()

    assert generated == ["222222"]
    assert repository.get_presentation("111111") is None
    assert repository.get_presentation("222222") is not None
    assert repository.get_presentation("333333") is None

    repository = Repository(tmp_path / "elections.sqlite3")
    PollingService(
        repository,
        fetch_snapshot=fetch,
        presentation_generator=generate,
        candidate_loader=lambda _code: [],
        presentations_dir=presentations_dir,
    ).poll_once()

    assert generated == ["222222"]


def test_completed_old_presentation_is_regenerated_to_current_format(tmp_path) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option("222222", "Hotová obec"))
    snapshot = _snapshot("222222")
    snapshot.progress = PollingProgress(2, 2)
    snapshot_id = repository.save_snapshot(snapshot)
    old_pdf = tmp_path / "presentations" / "222222.pdf"
    old_pdf.parent.mkdir(parents=True)
    old_pdf.write_bytes(b"%PDF-old")
    repository.save_presentation("222222", snapshot_id, old_pdf, format_version=1)
    generated: list[str] = []

    def generate(result: ElectionSnapshot, output_path) -> None:
        generated.append(result.municipality.code)
        output_path.write_bytes(b"%PDF-new")

    PollingService(
        repository,
        fetch_snapshot=lambda _code: snapshot,
        presentation_generator=generate,
        candidate_loader=lambda _code: [],
        presentations_dir=old_pdf.parent,
    ).poll_once()

    presentation = repository.get_presentation("222222")
    assert generated == ["222222"]
    assert presentation["format_version"] == PRESENTATION_FORMAT_VERSION
    assert old_pdf.read_bytes() == b"%PDF-new"


def test_presentation_is_regenerated_when_candidate_votes_become_available(
    tmp_path,
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option("222222", "Hotová obec"))
    snapshot = _snapshot("222222")
    snapshot.progress = PollingProgress(2, 2)
    snapshot_id = repository.save_snapshot(snapshot)
    pdf = tmp_path / "presentations" / "222222.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-without-votes")
    repository.save_presentation(
        "222222",
        snapshot_id,
        pdf,
        PRESENTATION_FORMAT_VERSION,
        candidate_votes_available=False,
    )
    generated: list[str] = []

    def generate(result: ElectionSnapshot, output_path) -> None:
        generated.append(result.municipality.code)
        output_path.write_bytes(b"%PDF-with-votes")

    PollingService(
        repository,
        fetch_snapshot=lambda _code: snapshot,
        presentation_generator=generate,
        candidate_loader=lambda _code: [
            Candidate("0", "1", 1, "Kandidát", None, "", "", 42)
        ],
        presentations_dir=pdf.parent,
    ).poll_once()

    presentation = repository.get_presentation("222222")
    assert generated == ["222222"]
    assert presentation["candidate_votes_available"] == 1
    assert pdf.read_bytes() == b"%PDF-with-votes"


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
