from __future__ import annotations

import hashlib
import threading
import webbrowser

import requests
import uvicorn

from .allocation import AllocationError, allocate_mandates
from .config import source_url_for
from .downloader import Downloader
from .models import ElectionSnapshot
from .parser import ElectionParser


def _parse(payload, municipality_code: str) -> ElectionSnapshot:
    return ElectionParser().parse(
        payload.content,
        municipality_code=municipality_code,
        source_url=payload.url,
        source_hash=payload.content_hash,
        fetched_at=payload.fetched_at,
    )


def _fetch_district_snapshot(
    downloader: Downloader, municipality_code: str, first_error: requests.HTTPError
) -> ElectionSnapshot:
    # Obce s více obvody mají soubory _1, _2, ...; z _N se bere obvod N.
    try:
        payload = downloader.fetch(source_url_for(municipality_code, suffix="_1"))
    except requests.HTTPError:
        raise first_error from None
    snapshot = _parse(payload, municipality_code)
    hashes = [payload.content_hash]
    for district_id in sorted(snapshot.seat_counts_by_constituency, key=int):
        if district_id == "1":
            continue
        district_payload = downloader.fetch(
            source_url_for(municipality_code, suffix=f"_{district_id}")
        )
        hashes.append(district_payload.content_hash)
        district = _parse(district_payload, municipality_code)
        snapshot.party_results = [
            party for party in snapshot.party_results if party.constituency_id != district_id
        ] + [
            party for party in district.party_results if party.constituency_id == district_id
        ]
        snapshot.valid_votes_by_constituency[district_id] = (
            district.valid_votes_by_constituency.get(district_id, 0)
        )
    snapshot.party_results.sort(key=lambda party: int(party.constituency_id))
    snapshot.source_hash = hashlib.sha256("".join(hashes).encode()).hexdigest()
    return snapshot


def fetch_current_snapshot(municipality_code: str) -> ElectionSnapshot:
    downloader = Downloader()
    try:
        snapshot = _parse(
            downloader.fetch(source_url_for(municipality_code)), municipality_code
        )
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        snapshot = _fetch_district_snapshot(downloader, municipality_code, exc)
    if snapshot.party_results and all(
        snapshot.valid_votes_by_constituency.get(constituency_id, 0) > 0
        for constituency_id in snapshot.seat_counts_by_constituency
    ):
        try:
            allocation = allocate_mandates(snapshot)
        except AllocationError as exc:
            snapshot.allocation_error = str(exc)
        else:
            snapshot.threshold_percent = allocation.threshold_percent
            snapshot.lottery_required = allocation.lottery_required
            for party in snapshot.party_results:
                party.mandates_virtual = allocation.mandates_by_constituency[
                    party.constituency_id
                ][party.list_id]
    return snapshot


def main() -> None:
    url = "http://127.0.0.1:8000"
    threading.Timer(1, webbrowser.open, args=(url,)).start()
    uvicorn.run("election_monitor.web:app", host="127.0.0.1", port=8000)
