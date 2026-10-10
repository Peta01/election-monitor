from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class MunicipalityRef:
    code: str
    name: str


@dataclass(slots=True)
class PollingProgress:
    processed_districts: int
    total_districts: int
    turnout_percent: float | None = None


@dataclass(slots=True)
class PartyResult:
    list_id: str
    name: str
    votes: int
    percent: float | None = None
    mandates_virtual: int | None = None
    candidate_count: int = 0
    constituency_id: str = "0"


@dataclass(slots=True)
class ElectedRepresentative:
    constituency_id: str
    list_id: str
    party_name: str
    order: int
    name: str
    votes: int
    percent: float | None = None


@dataclass(slots=True)
class ElectionSnapshot:
    municipality: MunicipalityRef
    fetched_at: datetime
    source_url: str
    source_hash: str
    progress: PollingProgress
    party_results: list[PartyResult]
    seats_to_elect: int
    seat_counts_by_constituency: dict[str, int] = field(default_factory=dict)
    valid_votes_by_constituency: dict[str, int] = field(default_factory=dict)
    threshold_percent: int | None = None
    lottery_required: bool = False
    allocation_error: str | None = None
    elected_representatives: list[ElectedRepresentative] = field(default_factory=list)
