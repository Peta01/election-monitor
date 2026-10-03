from datetime import UTC, datetime

import pytest

from election_monitor.allocation import AllocationError, allocate_mandates
from election_monitor.models import (
    ElectionSnapshot,
    MunicipalityRef,
    PartyResult,
    PollingProgress,
)


def snapshot(
    seats: int,
    parties: list[PartyResult],
    valid_votes: int | None = None,
) -> ElectionSnapshot:
    return ElectionSnapshot(
        municipality=MunicipalityRef("123456", "Testov"),
        fetched_at=datetime.now(UTC),
        source_url="https://example.test/results.xml",
        source_hash="abc123",
        progress=PollingProgress(1, 1),
        party_results=parties,
        seats_to_elect=seats,
        seat_counts_by_constituency={"0": seats},
        valid_votes_by_constituency={
            "0": valid_votes
            if valid_votes is not None
            else sum(party.votes for party in parties)
        },
    )


def party(list_id: str, votes: int, candidates: int = 10) -> PartyResult:
    return PartyResult(
        list_id=list_id,
        name=list_id,
        votes=votes,
        candidate_count=candidates,
    )


def test_allocates_seats_using_dhondt() -> None:
    result = allocate_mandates(
        snapshot(
            7,
            [party("A", 1000), party("B", 600), party("C", 400)],
        )
    )

    assert result.mandates_by_constituency == {"0": {"A": 4, "B": 2, "C": 1}}
    assert result.threshold_percent == 5


def test_reduces_threshold_until_at_least_two_lists_qualify() -> None:
    result = allocate_mandates(snapshot(5, [party("A", 960), party("B", 40)]))

    assert result.threshold_percent == 4
    assert result.mandates_by_constituency == {"0": {"A": 5, "B": 0}}


def test_threshold_adjusts_for_number_of_candidates() -> None:
    result = allocate_mandates(
        snapshot(5, [party("A", 990, candidates=5), party("B", 10, candidates=1)])
    )

    assert result.threshold_percent == 5
    assert result.mandates_by_constituency["0"]["B"] == 0


def test_single_list_is_not_subject_to_threshold() -> None:
    result = allocate_mandates(snapshot(3, [party("A", 100, candidates=3)]))

    assert result.threshold_percent is None
    assert result.mandates_by_constituency == {"0": {"A": 3}}
    assert result.lottery_required is False


def test_reports_lottery_when_cutoff_tie_cannot_be_resolved_by_votes() -> None:
    result = allocate_mandates(
        snapshot(3, [party("A", 100), party("B", 50), party("C", 50)])
    )

    assert result.mandates_by_constituency == {"0": {"A": 2, "B": 1, "C": 0}}
    assert result.lottery_required is True


def test_allocates_each_electoral_district_separately() -> None:
    election = snapshot(4, [])
    election.seat_counts_by_constituency = {"1": 2, "2": 2}
    election.valid_votes_by_constituency = {"1": 100, "2": 100}
    election.party_results = [
        PartyResult("A", "A", 60, candidate_count=2, constituency_id="1"),
        PartyResult("B", "B", 40, candidate_count=2, constituency_id="1"),
        PartyResult("A", "A", 60, candidate_count=2, constituency_id="2"),
        PartyResult("B", "B", 40, candidate_count=2, constituency_id="2"),
    ]

    result = allocate_mandates(election)

    assert result.mandates_by_constituency == {
        "1": {"A": 1, "B": 1},
        "2": {"A": 1, "B": 1},
    }


def test_rejects_votes_above_reported_valid_vote_total() -> None:
    with pytest.raises(AllocationError, match="do not match valid votes"):
        allocate_mandates(snapshot(3, [party("A", 101)], valid_votes=100))
