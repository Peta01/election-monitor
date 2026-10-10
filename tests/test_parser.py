import sqlite3
from datetime import UTC, datetime

import pytest

from election_monitor.config import source_url_for
from election_monitor.db import Repository
from election_monitor.parser import ElectionParser, ParserError

XML = b"""<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/"
    DATUM_CAS_GENEROVANI="2026-10-10T12:30:00">
  <OBEC KODZASTUP="123456" NAZEVZAST="Testov" VOLENO_ZASTUP="3">
    <VYSLEDEK>
      <UCAST OKRSKY_CELKEM="4" OKRSKY_ZPRAC="3" UCAST_PROC="42.50"
          PLATNE_HLASY="1250"/>
      <VOLEBNI_STRANA VSTRANA="12" NAZEV_STRANY="Testovac&#237; strana"
          HLASY="1250" HLASY_PROC="100.00" KANDIDATU_POCET="3">
        <ZASTUPITEL PORADOVE_CISLO="2" JMENO="Eva" PRIJMENI="Nov&#225;kov&#225;"
            TITULPRED="Ing." TITULZA="Ph.D." HLASY="456" HLASY_PROC="36.48"/>
      </VOLEBNI_STRANA>
    </VYSLEDEK>
  </OBEC>
</VYSLEDKY_OBEC>
"""


def test_parse_council_results() -> None:
    fetched_at = datetime(2026, 10, 10, 12, 31, tzinfo=UTC)

    snapshot = ElectionParser().parse(
        XML,
        municipality_code="123456",
        source_url="https://example.test/results.xml",
        source_hash="abc123",
        fetched_at=fetched_at,
    )

    assert snapshot.municipality.code == "123456"
    assert snapshot.municipality.name == "Testov"
    assert snapshot.fetched_at == fetched_at
    assert snapshot.progress.processed_districts == 3
    assert snapshot.progress.total_districts == 4
    assert snapshot.progress.turnout_percent == 42.5
    assert snapshot.seats_to_elect == 3
    assert snapshot.valid_votes_by_constituency == {"0": 1250}
    assert len(snapshot.party_results) == 1
    assert snapshot.party_results[0].list_id == "12"
    assert snapshot.party_results[0].name == "Testovací strana"
    assert snapshot.party_results[0].votes == 1250
    assert snapshot.party_results[0].percent == 100
    assert snapshot.party_results[0].candidate_count == 3
    assert len(snapshot.elected_representatives) == 1
    representative = snapshot.elected_representatives[0]
    assert (representative.list_id, representative.party_name) == (
        "12",
        "Testovací strana",
    )
    assert representative.order == 2
    assert representative.name == "Ing. Eva Nováková, Ph.D."
    assert representative.votes == 456
    assert representative.percent == 36.48


def test_parse_electoral_districts_separately() -> None:
    xml = b"""<VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/">
      <OBEC KODZASTUP="123456" NAZEVZAST="Testov" VOLENO_ZASTUP="4">
        <VYSLEDEK><UCAST OKRSKY_CELKEM="2" OKRSKY_ZPRAC="2"
          UCAST_PROC="40" PLATNE_HLASY="200"/></VYSLEDEK>
        <OBVOD CIS_OBVODU="1" VOLENO_ZASTUP="2">
          <VYSLEDEK>
            <UCAST OKRSKY_CELKEM="1" OKRSKY_ZPRAC="1" UCAST_PROC="40"
              PLATNE_HLASY="100"/>
            <VOLEBNI_STRANA VSTRANA="1" NAZEV_STRANY="A" HLASY="60"
              HLASY_PROC="60" KANDIDATU_POCET="2"/>
            <VOLEBNI_STRANA VSTRANA="2" NAZEV_STRANY="B" HLASY="40"
              HLASY_PROC="40" KANDIDATU_POCET="2"/>
          </VYSLEDEK>
        </OBVOD>
        <OBVOD CIS_OBVODU="2" VOLENO_ZASTUP="2">
          <VYSLEDEK>
            <UCAST OKRSKY_CELKEM="1" OKRSKY_ZPRAC="1" UCAST_PROC="40"
              PLATNE_HLASY="100"/>
            <VOLEBNI_STRANA VSTRANA="1" NAZEV_STRANY="A" HLASY="70"
              HLASY_PROC="70" KANDIDATU_POCET="2"/>
            <VOLEBNI_STRANA VSTRANA="2" NAZEV_STRANY="B" HLASY="30"
              HLASY_PROC="30" KANDIDATU_POCET="2"/>
          </VYSLEDEK>
        </OBVOD>
      </OBEC>
    </VYSLEDKY_OBEC>"""

    snapshot = ElectionParser().parse(
        xml,
        municipality_code="123456",
        source_url="https://example.test/results.xml",
        source_hash="abc123",
    )

    assert snapshot.seat_counts_by_constituency == {"1": 2, "2": 2}
    assert snapshot.valid_votes_by_constituency == {"1": 100, "2": 100}
    assert [result.constituency_id for result in snapshot.party_results] == [
        "1",
        "1",
        "2",
        "2",
    ]


@pytest.mark.parametrize(
    ("data", "municipality_code", "message"),
    [
        (b"<not-results/>", "123456", "Unexpected XML root"),
        (
            b"<VYSLEDKY_OBEC><CHYBA>Data nejsou dostupn&#225;</CHYBA></VYSLEDKY_OBEC>",
            "123456",
            "Data nejsou dostupná",
        ),
        (XML, "654321", "not 654321"),
        (b"<VYSLEDKY_OBEC>", "123456", "Invalid election XML"),
    ],
)
def test_rejects_invalid_or_unavailable_results(
    data: bytes, municipality_code: str, message: str
) -> None:
    with pytest.raises(ParserError, match=message):
        ElectionParser().parse(
            data,
            municipality_code=municipality_code,
            source_url="https://example.test/results.xml",
            source_hash="abc123",
        )


def test_save_parsed_snapshot_to_sqlite(tmp_path) -> None:
    snapshot = ElectionParser().parse(
        XML,
        municipality_code="123456",
        source_url="https://example.test/results.xml",
        source_hash="abc123",
    )
    snapshot.threshold_percent = 5
    snapshot.lottery_required = True
    repo = Repository(tmp_path / "election.sqlite3")

    snapshot_id = repo.save_snapshot(snapshot)

    with sqlite3.connect(repo.db_path) as connection:
        stored_snapshot = connection.execute(
            "SELECT processed_districts, total_districts, seats_to_elect, "
            "threshold_percent, lottery_required "
            "FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        stored_party = connection.execute(
            "SELECT list_id, name, votes, candidate_count, constituency_id "
            "FROM party_results WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()

    assert stored_snapshot == (3, 4, 3, 5, 1)
    assert stored_party == ("12", "Testovací strana", 1250, 3, "0")
    assert repo.get_latest_snapshot("123456").elected_representatives == (
        snapshot.elected_representatives
    )


def test_new_candidate_votes_are_saved_even_when_precinct_count_is_unchanged(
    tmp_path,
) -> None:
    snapshot = ElectionParser().parse(
        XML,
        municipality_code="123456",
        source_url="https://example.test/results.xml",
        source_hash="before-final-results",
    )
    snapshot.progress.processed_districts = 4
    snapshot.progress.total_districts = 4
    snapshot.elected_representatives.clear()
    repository = Repository(tmp_path / "election.sqlite3")
    first_id = repository.save_snapshot(snapshot)

    snapshot.elected_representatives.append(
        ElectionParser()
        .parse(
            XML,
            municipality_code="123456",
            source_url="https://example.test/results.xml",
            source_hash="final",
        )
        .elected_representatives[0]
    )
    snapshot.source_hash = "final-results-with-candidate-votes"
    final_id = repository.save_snapshot(snapshot)

    assert final_id != first_id
    assert repository.get_latest_snapshot("123456").elected_representatives[0].votes == 456


def test_migrates_existing_database_schema(tmp_path) -> None:
    database = tmp_path / "existing.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE municipalities (id INTEGER PRIMARY KEY, code TEXT, name TEXT);
            CREATE TABLE snapshots (
                id INTEGER PRIMARY KEY, municipality_id INTEGER, fetched_at TEXT,
                source_url TEXT, source_hash TEXT, processed_districts INTEGER,
                total_districts INTEGER, turnout_percent REAL
            );
            CREATE TABLE party_results (
                id INTEGER PRIMARY KEY, snapshot_id INTEGER, list_id TEXT, name TEXT,
                votes INTEGER, percent REAL, mandates_virtual INTEGER
            );
            """
        )

    Repository(database)

    with sqlite3.connect(database) as connection:
        snapshot_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(snapshots)")
        }
        party_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(party_results)")
        }
    assert "seats_to_elect" in snapshot_columns
    assert {"threshold_percent", "lottery_required"} <= snapshot_columns
    assert {"candidate_count", "constituency_id"} <= party_columns


def test_source_url_uses_padded_council_code() -> None:
    assert source_url_for("123") == (
        "https://volby.gov.cz/appdata/kv2026/20261009/odata/zastup/"
        "vysledky_obec_000123.xml"
    )


@pytest.mark.parametrize("code", ["", "1234567", "12A", "１２３"])
def test_source_url_rejects_invalid_council_code(code: str) -> None:
    with pytest.raises(ValueError, match="1 to 6 digits"):
        source_url_for(code)
