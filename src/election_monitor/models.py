from dataclasses import dataclass
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


@dataclass(slots=True)
class ElectionSnapshot:
    municipality: MunicipalityRef
    fetched_at: datetime
    source_url: str
    source_hash: str
    progress: PollingProgress
    party_results: list[PartyResult]
