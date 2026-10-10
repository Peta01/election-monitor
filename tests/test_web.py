from datetime import UTC, datetime

import pytest
import requests
from fastapi.testclient import TestClient

from election_monitor import municipalities, web
from election_monitor.candidates import Candidate
from election_monitor.db import Repository
from election_monitor.models import (
    ElectedRepresentative,
    ElectionSnapshot,
    MunicipalityRef,
    PartyResult,
    PollingProgress,
)
from election_monitor.municipalities import MunicipalityOption
from election_monitor.polling import PollingService


def _option() -> MunicipalityOption:
    return MunicipalityOption(
        "123456", "Testov", "Testov", "7200", "Zlínský kraj", "7204", "Zlín"
    )


def test_home_offers_searchable_official_council_list(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        municipalities,
        "get_municipalities",
        lambda: [_option()],
    )

    response = TestClient(web.app).get("/")

    assert response.status_code == 200
    assert 'lang="cs"' in response.text
    assert "Testov (123456)" in response.text
    assert 'id="region-select"' in response.text
    assert 'id="district-select"' in response.text
    assert 'id="municipality-select"' in response.text
    assert 'id="theme-toggle"' in response.text
    assert 'localStorage.setItem("election-monitor-theme", theme)' in response.text
    assert '[data-theme="dark"]' in response.text
    assert "60 sekund" in response.text


def test_selection_persists_municipality_for_background_tracking(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        municipalities,
        "get_municipalities",
        lambda: [_option()],
    )
    repository = Repository(tmp_path / "elections.sqlite3")
    monkeypatch.setattr(
        web,
        "polling_service",
        PollingService(repository, fetch_snapshot=lambda _code: _snapshot()),
    )

    with TestClient(web.app) as client:
        selected = client.get("/vyber?code=123456", follow_redirects=False)
        invalid = client.get("/vyber?code=654321", follow_redirects=False)

    assert selected.status_code == 303
    assert selected.headers["location"] == "/vysledky/123456"
    assert invalid.headers["location"] == "/"
    tracked = repository.list_tracked_municipalities()
    assert len(tracked) == 1
    assert tracked[0]["code"] == "123456"


def test_results_refresh_and_do_not_duplicate_unchanged_snapshots(
    tmp_path, monkeypatch
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    repository.save_snapshot(_snapshot())
    monkeypatch.setattr(municipalities, "get_municipalities", lambda: [_option()])
    service = PollingService(repository, fetch_snapshot=lambda _code: _snapshot())
    monkeypatch.setattr(web, "polling_service", service)

    with TestClient(web.app) as client:
        first = client.get("/vysledky/123456")
        second = client.get("/vysledky/123456")

    assert first.status_code == second.status_code == 200
    assert 'content="60;url=/vysledky/123456"' in first.text
    assert "Výsledky kandidátních listin" in first.text
    assert "Testovací kandidátka" in first.text
    assert "3 / 3" in first.text

    with repository._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] == 1


def test_results_explain_that_first_poll_is_pending(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        municipalities,
        "get_municipalities",
        lambda: [_option()],
    )
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    repository.update_poll_failure("123456", "404 Not Found")
    monkeypatch.setattr(
        web,
        "polling_service",
        PollingService(repository, fetch_snapshot=_not_published),
    )

    with TestClient(web.app) as client:
        response = client.get("/vysledky/123456")

    assert response.status_code == 200
    assert "ČSÚ zatím neposkytl výsledky" in response.text
    assert "404 Not Found" in response.text
    assert 'content="60;url=/vysledky/123456"' in response.text


def test_home_lists_tracked_municipalities_and_can_stop_tracking(
    tmp_path, monkeypatch
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    repository.save_snapshot(_snapshot())
    monkeypatch.setattr(municipalities, "get_municipalities", lambda: [_option()])
    monkeypatch.setattr(
        web,
        "polling_service",
        PollingService(repository, fetch_snapshot=lambda _code: _snapshot()),
    )

    with TestClient(web.app) as client:
        response = client.get("/")
        removed = client.post("/sledovani/123456/odebrat", follow_redirects=False)

    assert "Sledované obce (1)" in response.text
    assert "Přestat sledovat" in response.text
    assert 'href="/vysledky/123456"' in response.text
    assert "Okrsky: 3 / 3" in response.text
    assert removed.status_code == 303
    assert repository.list_tracked_municipalities() == []


def _snapshot() -> ElectionSnapshot:
    return ElectionSnapshot(
        municipality=MunicipalityRef("123456", "Testov"),
        fetched_at=datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
        source_url="https://example.test/results.xml",
        source_hash="same-results",
        progress=PollingProgress(3, 3, 50.0),
        party_results=[
            PartyResult(
                "1",
                "Testovací kandidátka",
                100,
                percent=100,
                mandates_virtual=3,
                candidate_count=3,
            )
        ],
        seats_to_elect=3,
        seat_counts_by_constituency={"0": 3},
        valid_votes_by_constituency={"0": 100},
    )


def _not_published(_code: str) -> ElectionSnapshot:
    raise requests.HTTPError("404 Not Found")


@pytest.fixture(autouse=True)
def offline_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        web,
        "get_candidates",
        lambda _code: [
            Candidate("0", "1", order, f"Kandidát {order}", 40, "učitel", "Testov")
            for order in (1, 2, 3)
        ],
    )


def test_results_list_candidates_and_link_to_development(tmp_path, monkeypatch) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    repository.save_snapshot(_snapshot())
    monkeypatch.setattr(web, "polling_service", PollingService(repository))

    response = TestClient(web.app).get("/vysledky/123456")

    assert "Kandidát 2" in response.text
    assert 'href="/vysledky/123456/vyvoj"' in response.text


def test_results_show_official_votes_for_elected_candidates(tmp_path, monkeypatch) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    snapshot = _snapshot()
    snapshot.elected_representatives = [
        ElectedRepresentative("0", "1", "Testovací kandidátka", 2, "Kandidát 2", 1234, 12.5)
    ]
    repository.save_snapshot(snapshot)
    monkeypatch.setattr(web, "polling_service", PollingService(repository))

    response = TestClient(web.app).get("/vysledky/123456")

    assert response.status_code == 200
    assert "1\u00a0234" in response.text
    assert "Hlasy zvolených zastupitelů jsou převzaty z oficiálního XML ČSÚ" in response.text
    assert "u ostatních kandidátů nejsou v tomto zdroji uvedeny" in response.text


def test_results_show_official_elected_votes_when_candidate_registry_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    snapshot = _snapshot()
    snapshot.elected_representatives = [
        ElectedRepresentative("0", "1", "Testovací kandidátka", 2, "Kandidát 2", 1234)
    ]
    repository.save_snapshot(snapshot)
    monkeypatch.setattr(
        web,
        "get_candidates",
        lambda _code: (_ for _ in ()).throw(requests.ConnectionError("offline")),
    )
    monkeypatch.setattr(web, "polling_service", PollingService(repository))

    response = TestClient(web.app).get("/vysledky/123456")

    assert response.status_code == 200
    assert "Kandidáty se nepodařilo načíst: offline" in response.text
    assert "Kandidát 2" in response.text
    assert "1\u00a0234" in response.text


def test_completed_results_link_to_saved_a4_pdf(tmp_path, monkeypatch) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    repository.save_snapshot(_snapshot())
    pdf_path = tmp_path / "presentations" / "123456.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-test")
    latest = repository.get_latest_snapshot("123456")
    snapshot_id = repository.save_snapshot(latest)
    repository.save_presentation("123456", snapshot_id, pdf_path)
    monkeypatch.setattr(web, "polling_service", PollingService(repository))

    with TestClient(web.app) as client:
        page = client.get("/vysledky/123456")
        download = client.get("/prezentace/123456")

    assert 'href="/prezentace/123456"' in page.text
    assert "Stáhnout prezentaci A4 (PDF)" in page.text
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content == b"%PDF-test"


def test_results_show_simulated_candidate_votes_separately_from_live_results(
    tmp_path, monkeypatch
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    simulated = _snapshot()
    simulated.source_url = "SIMULATION://123456/district/3"
    simulated.progress = PollingProgress(2, 3, 40.0)
    repository.save_snapshot(simulated)
    repository.save_snapshot(_snapshot())
    monkeypatch.setattr(web, "polling_service", PollingService(repository))

    response = TestClient(web.app).get("/vysledky/123456")

    assert response.status_code == 200
    assert "Hlasy kandidátů – testovací simulace" in response.text
    assert "Syntetický stav: 2 / 3 okrsků" in response.text
    assert "Tato čísla nejsou skutečné výsledky ČSÚ." in response.text
    assert ">34</td>" in response.text
    assert ">38</td>" in response.text
    assert ">28</td>" in response.text


def test_simulated_candidate_votes_are_displayed_as_synthetic(monkeypatch) -> None:
    snapshot = _snapshot()
    snapshot.source_url = "SIMULATION://123456/district/1"
    candidates = [
        Candidate("0", "90", order, f"Kandidát {order}", 40, "učitel", "Testov")
        for order in (1, 2, 3)
    ]
    monkeypatch.setattr(web, "_load_candidates", lambda _code: (candidates, None))

    html = web._candidates_html(snapshot, has_districts=False)

    assert "v simulaci uměle rozděleny" in html
    assert "skutečné ani odhadované výsledky" in html
    assert ">34</td>" in html
    assert ">38</td>" in html
    assert ">28</td>" in html
    assert "Kandidát 1" in html
    assert ">—</td>" not in html


def test_development_page_shows_candidate_votes_for_simulation(
    tmp_path, monkeypatch
) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    snapshot = _snapshot()
    snapshot.source_url = "SIMULATION://123456/district/3"
    repository.save_snapshot(snapshot)
    monkeypatch.setattr(web, "polling_service", PollingService(repository))

    response = TestClient(web.app).get("/vysledky/123456/vyvoj")

    assert response.status_code == 200
    assert "Hlasy jednotlivých kandidátů" in response.text
    assert "v simulaci uměle rozděleny" in response.text
    assert ">34</td>" in response.text
    assert ">38</td>" in response.text
    assert ">28</td>" in response.text


def test_development_page_shows_charts_and_named_composition(tmp_path, monkeypatch) -> None:
    repository = Repository(tmp_path / "elections.sqlite3")
    repository.add_tracked_municipality(_option())
    early = _snapshot()
    early.progress = PollingProgress(1, 3, 40.0)
    early.party_results[0].mandates_virtual = 2
    repository.save_snapshot(early)
    repository.save_snapshot(_snapshot())
    monkeypatch.setattr(web, "polling_service", PollingService(repository))

    client = TestClient(web.app)
    latest = client.get("/vysledky/123456/vyvoj")
    early_page = client.get("/vysledky/123456/vyvoj?okrsky=1")

    assert latest.status_code == 200
    assert latest.text.count("<svg") == 2
    assert "Kandidát 3" in latest.text
    assert "Změny složení v čase" in latest.text
    assert "<th>Zastupitel</th>" in latest.text
    assert "Nový zastupitel" in latest.text
    assert "<td>3 / 3</td><td>Nový zastupitel</td><td>Kandidát 3" in latest.text
    assert 'url=/vysledky/123456/vyvoj?okrsky=1"' in early_page.text
    early_table = early_page.text.split("<tbody>")[1]
    assert "Kandidát 2" in early_table
    assert "Kandidát 3" not in early_table
