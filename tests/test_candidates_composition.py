import io
import zipfile
from datetime import UTC, datetime

from election_monitor import candidates
from election_monitor.candidates import Candidate, parse_candidates_csv
from election_monitor.composition import council_composition, rank_candidates
from election_monitor.models import (
    ElectionSnapshot,
    MunicipalityRef,
    PartyResult,
    PollingProgress,
)

HEADER = (
    "KODZASTUP;COBVODU;POR_STR_HL;PORCISLO;JMENO;PRIJMENI;TITULPRED;TITULZA;"
    "VEK;POVOLANI;BYDLISTEN;PLATNOST;POCHLASU\n"
)


def _csv(votes: int) -> bytes:
    rows = (
        f'123456;1;2;1;"Jan";"Novák";"Ing.";"";40;"učitel";"Testov";"A";{votes}\n'
        '123456;1;2;2;"Eva";"Svobodová";"";"DiS.";30;"lékařka";"Testov";"N";0\n'
        '999999;1;1;1;"Cizí";"Kandidát";"";"";50;"";"Jinde";"A";0\n'
    )
    return (HEADER + rows).encode("cp1250")


def _party() -> PartyResult:
    return PartyResult("1", "A", 100, mandates_virtual=2, candidate_count=4)


def _candidates(votes: list[int | None]) -> list[Candidate]:
    return [
        Candidate("0", "1", order, f"K{order}", None, "", "", value)
        for order, value in enumerate(votes, start=1)
    ]


def test_candidates_are_filtered_and_votes_hidden_until_available() -> None:
    hidden = parse_candidates_csv(_csv(0), "123456")
    shown = parse_candidates_csv(_csv(25), "123456")

    assert [candidate.name for candidate in hidden] == ["Ing. Jan Novák"]
    assert hidden[0].votes is None
    assert shown[0].votes == 25


def test_ballot_order_is_used_without_candidate_votes() -> None:
    ranked = rank_candidates(_party(), _candidates([None] * 4))

    assert [candidate.order for candidate in ranked] == [1, 2, 3, 4]


def test_candidates_with_ten_percent_above_average_move_first() -> None:
    # Průměr je 25, hranice 27,5: postupují kandidáti 3 (40 hlasů) a 4 (30 hlasů).
    ranked = rank_candidates(_party(), _candidates([10, 20, 40, 30]))

    assert [candidate.order for candidate in ranked] == [3, 4, 1, 2]


def test_candidate_registry_refreshes_after_short_cache_expiry(
    tmp_path, monkeypatch
) -> None:
    cache_path = tmp_path / "kvrk.csv"
    cache_path.write_bytes(b"old candidate data")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("csv/kvrk.csv", b"fresh candidate data")
    monkeypatch.setattr(candidates, "CANDIDATES_CACHE_PATH", cache_path)
    monkeypatch.setattr(candidates, "CANDIDATES_CACHE_SECONDS", 0)
    monkeypatch.setattr(
        candidates, "download_registry_archive", lambda: archive.getvalue()
    )

    assert candidates._read_registry_csv() == b"fresh candidate data"
    assert cache_path.read_bytes() == b"fresh candidate data"


def test_council_composition_takes_mandates_in_order() -> None:
    snapshot = ElectionSnapshot(
        MunicipalityRef("123456", "Testov"),
        datetime.now(UTC),
        "https://example.test",
        "hash",
        PollingProgress(1, 1),
        [_party()],
        2,
    )

    seats = council_composition(snapshot, _candidates([None] * 4))

    assert [seat.candidate.order for seat in seats] == [1, 2]
