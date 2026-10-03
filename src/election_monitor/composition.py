from __future__ import annotations

from dataclasses import dataclass

from .candidates import Candidate
from .models import ElectionSnapshot, PartyResult


@dataclass(frozen=True, slots=True)
class Seat:
    constituency_id: str
    party_name: str
    candidate: Candidate


def candidates_for_party(party: PartyResult, candidates: list[Candidate]) -> list[Candidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.list_id == party.list_id
        and (party.constituency_id == "0" or candidate.constituency_id == party.constituency_id)
    ]


def rank_candidates(party: PartyResult, party_candidates: list[Candidate]) -> list[Candidate]:
    """Pořadí podle § 45 odst. 3 a 4; odst. 4 jen pokud jsou známy hlasy kandidátů."""
    ballot_order = sorted(party_candidates, key=lambda candidate: candidate.order)
    if party.candidate_count < 1 or any(candidate.votes is None for candidate in ballot_order):
        return ballot_order
    average = party.votes // party.candidate_count
    promoted = sorted(
        (
            candidate
            for candidate in ballot_order
            if (candidate.votes or 0) * 10 >= average * 11
        ),
        key=lambda candidate: (-(candidate.votes or 0), candidate.order),
    )
    rest = [candidate for candidate in ballot_order if candidate not in promoted]
    return promoted + rest


def council_composition(
    snapshot: ElectionSnapshot, candidates: list[Candidate]
) -> list[Seat]:
    seats: list[Seat] = []
    for party in snapshot.party_results:
        mandates = party.mandates_virtual or 0
        if mandates < 1:
            continue
        ranked = rank_candidates(party, candidates_for_party(party, candidates))
        seats.extend(
            Seat(party.constituency_id, party.name, candidate) for candidate in ranked[:mandates]
        )
    return seats
