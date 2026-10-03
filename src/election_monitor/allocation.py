from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .models import ElectionSnapshot, PartyResult


class AllocationError(ValueError):
    pass


@dataclass(slots=True)
class AllocationResult:
    mandates_by_constituency: dict[str, dict[str, int]]
    threshold_percent: int | None
    lottery_required: bool


@dataclass(frozen=True, slots=True)
class _Quotient:
    value: Fraction
    votes: int
    list_id: str


def allocate_mandates(snapshot: ElectionSnapshot) -> AllocationResult:
    seat_counts = snapshot.seat_counts_by_constituency or {"0": snapshot.seats_to_elect}
    parties_by_constituency: dict[str, list[PartyResult]] = {
        constituency_id: [] for constituency_id in seat_counts
    }
    for party in snapshot.party_results:
        if party.constituency_id not in parties_by_constituency:
            raise AllocationError(
                f"No seat count is available for constituency {party.constituency_id}."
            )
        parties_by_constituency[party.constituency_id].append(party)

    for constituency_id, parties in parties_by_constituency.items():
        if not parties:
            raise AllocationError(
                f"No party-list results are available for constituency {constituency_id}."
            )
        _validate_constituency(
            constituency_id,
            parties,
            seat_counts[constituency_id],
            snapshot.valid_votes_by_constituency.get(
                constituency_id, sum(party.votes for party in parties)
            ),
        )

    if all(len(parties) == 1 for parties in parties_by_constituency.values()):
        mandates: dict[str, dict[str, int]] = {}
        lottery_required = False
        for constituency_id, parties in parties_by_constituency.items():
            mandates[constituency_id], constituency_lottery = _allocate_constituency(
                parties, seat_counts[constituency_id]
            )
            lottery_required = lottery_required or constituency_lottery
        return AllocationResult(mandates, None, lottery_required)

    for threshold in range(5, -1, -1):
        mandates: dict[str, dict[str, int]] = {}
        lottery_required = False
        allocated_mandates = 0
        insufficient_eligible_lists = False

        for constituency_id, parties in parties_by_constituency.items():
            valid_votes = snapshot.valid_votes_by_constituency.get(
                constituency_id, sum(party.votes for party in parties)
            )
            seats = seat_counts[constituency_id]
            eligible = _eligible_parties(parties, valid_votes, seats, threshold)
            if len(parties) > 1 and len(eligible) < 2:
                insufficient_eligible_lists = True
                break
            constituency_mandates, constituency_lottery = _allocate_constituency(
                eligible, seats
            )
            mandates[constituency_id] = {party.list_id: 0 for party in parties}
            mandates[constituency_id].update(constituency_mandates)
            allocated_mandates += sum(constituency_mandates.values())
            lottery_required = lottery_required or constituency_lottery
        else:
            total_seats = sum(seat_counts.values())
            enough_mandates = (
                allocated_mandates >= total_seats // 2 + 1 or allocated_mandates > 5
            )
            if not insufficient_eligible_lists and enough_mandates:
                applied_threshold = (
                    threshold
                    if any(len(parties) > 1 for parties in parties_by_constituency.values())
                    else None
                )
                return AllocationResult(mandates, applied_threshold, lottery_required)

    raise AllocationError(
        "The available party results cannot satisfy the statutory mandate allocation conditions."
    )


def _validate_constituency(
    constituency_id: str,
    parties: list[PartyResult],
    seats: int,
    valid_votes: int,
) -> None:
    if seats < 1:
        raise AllocationError(f"Constituency {constituency_id} must have at least one seat.")
    if valid_votes < 0:
        raise AllocationError(f"Constituency {constituency_id} has a negative valid-vote count.")
    list_ids: set[str] = set()
    for party in parties:
        if party.list_id in list_ids:
            raise AllocationError(
                f"Duplicate list identifier {party.list_id} in constituency {constituency_id}."
            )
        list_ids.add(party.list_id)
        if party.votes < 0 or party.candidate_count < 1:
            raise AllocationError(
                f"List {party.list_id} in constituency {constituency_id} has invalid votes "
                "or candidate count."
            )
    if sum(party.votes for party in parties) != valid_votes:
        raise AllocationError(
            f"Party-list votes do not match valid votes in constituency {constituency_id}."
        )


def _eligible_parties(
    parties: list[PartyResult], valid_votes: int, seats: int, threshold_percent: int
) -> list[PartyResult]:
    if len(parties) == 1:
        return parties.copy()
    return [
        party
        for party in parties
        if party.votes * 100 * seats
        >= threshold_percent * valid_votes * min(party.candidate_count, seats)
    ]


def _allocate_constituency(
    parties: list[PartyResult], seats: int
) -> tuple[dict[str, int], bool]:
    quotients = [
        _Quotient(Fraction(party.votes, divisor), party.votes, party.list_id)
        for party in parties
        for divisor in range(1, min(party.candidate_count, seats) + 1)
    ]
    quotients.sort(key=lambda quotient: (-quotient.value, -quotient.votes, quotient.list_id))
    winners = quotients[:seats]
    mandates = {party.list_id: 0 for party in parties}
    for quotient in winners:
        mandates[quotient.list_id] += 1

    lottery_required = False
    if len(quotients) > seats and winners:
        cutoff = winners[-1]
        lottery_required = any(
            quotient.value == cutoff.value
            and quotient.votes == cutoff.votes
            and quotient.list_id != cutoff.list_id
            for quotient in quotients[seats:]
        )
    return mandates, lottery_required
