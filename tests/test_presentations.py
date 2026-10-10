from datetime import UTC, datetime

from election_monitor.candidates import Candidate
from election_monitor.models import (
    ElectedRepresentative,
    ElectionSnapshot,
    MunicipalityRef,
    PartyResult,
    PollingProgress,
)
from election_monitor.presentations import (
    _elected_representatives,
    generate_election_presentation,
)


def test_election_presentation_is_an_a4_pdf_with_escaped_result_text(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "election_monitor.presentations.get_candidates",
        lambda _code: [
            Candidate("0", "1", 1, "Jan Novák", None, "", "", 25),
            Candidate("0", "1", 2, "Eva Svobodová", None, "", "", 10),
        ],
    )
    snapshot = ElectionSnapshot(
        municipality=MunicipalityRef("123456", "Český Testov & Město"),
        fetched_at=datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
        source_url="https://example.test/?a=1&b=2",
        source_hash="snapshot",
        progress=PollingProgress(3, 3, 50.0),
        party_results=[
            PartyResult(
                "1", "Strana & její kandidáti", 123, 50.0, 2, candidate_count=2
            )
        ],
        seats_to_elect=3,
    )
    output_path = tmp_path / "123456.pdf"

    generate_election_presentation(snapshot, output_path)

    content = output_path.read_bytes()
    assert content.startswith(b"%PDF-")
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in content


def test_elected_representatives_follow_candidate_votes_and_allocated_mandates() -> None:
    snapshot = ElectionSnapshot(
        municipality=MunicipalityRef("123456", "Testov"),
        fetched_at=datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
        source_url="https://example.test",
        source_hash="snapshot",
        progress=PollingProgress(1, 1),
        party_results=[PartyResult("1", "Strana", 100, mandates_virtual=2, candidate_count=3)],
        seats_to_elect=2,
    )
    candidates = [
        Candidate("0", "1", 1, "První", None, "", "", 5),
        Candidate("0", "1", 2, "Druhý", None, "", "", 50),
        Candidate("0", "1", 3, "Třetí", None, "", "", 45),
    ]

    elected = _elected_representatives(snapshot, candidates)

    assert [seat.candidate.name for seat in elected] == ["Druhý", "Třetí"]


def test_presentation_uses_official_elected_representative_votes(
    tmp_path, monkeypatch
) -> None:
    snapshot = ElectionSnapshot(
        municipality=MunicipalityRef("123456", "Testov"),
        fetched_at=datetime(2026, 10, 10, 12, 0, tzinfo=UTC),
        source_url="https://example.test/results.xml",
        source_hash="snapshot",
        progress=PollingProgress(1, 1),
        party_results=[PartyResult("1", "Strana", 100, mandates_virtual=1)],
        seats_to_elect=1,
        elected_representatives=[
            ElectedRepresentative("0", "1", "Strana", 2, "Zvolený kandidát", 42, 42.0)
        ],
    )
    monkeypatch.setattr(
        "election_monitor.presentations.get_candidates",
        lambda _code: (_ for _ in ()).throw(AssertionError("not needed for official data")),
    )

    output_path = tmp_path / "123456.pdf"
    generate_election_presentation(snapshot, output_path)

    assert output_path.read_bytes().startswith(b"%PDF-")
