from __future__ import annotations

from .models import ElectionSnapshot, MunicipalityRef, PartyResult, PollingProgress


class ParserError(RuntimeError):
    pass


class ElectionParser:
    def parse(self, raw_bytes: bytes, municipality_code: str, source_url: str, source_hash: str) -> ElectionSnapshot:
        # TODO: detect ZIP/CSV/XML and parse real election data.
        # This is only a scaffold until we inspect the actual source format.
        municipality = MunicipalityRef(code=municipality_code, name=f"Municipality {municipality_code}")
        progress = PollingProgress(processed_districts=0, total_districts=0, turnout_percent=None)
        party_results: list[PartyResult] = []
        return ElectionSnapshot(
            municipality=municipality,
            fetched_at=None,  # replaced by caller or parser implementation later
            source_url=source_url,
            source_hash=source_hash,
            progress=progress,
            party_results=party_results,
        )
