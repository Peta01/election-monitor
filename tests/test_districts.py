import hashlib
from datetime import UTC, datetime

import requests

from election_monitor import app
from election_monitor.downloader import DownloadedPayload


def _xml(votes_1: int, votes_2: int) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<VYSLEDKY_OBEC xmlns="http://www.volby.cz/kv/">
<OBEC KODZASTUP="544779" NAZEVZAST="Lisov" VOLENO_ZASTUP="21">
<VYSLEDEK><UCAST OKRSKY_CELKEM="4" OKRSKY_ZPRAC="0" UCAST_PROC="0.00" PLATNE_HLASY="0"/></VYSLEDEK>
<OBVOD CIS_OBVODU="1" VOLENO_ZASTUP="15"><VYSLEDEK>
<UCAST OKRSKY_CELKEM="4" OKRSKY_ZPRAC="0" UCAST_PROC="0.00" PLATNE_HLASY="{votes_1}"/>
<VOLEBNI_STRANA VSTRANA="1" NAZEV_STRANY="A" HLASY="{votes_1}" HLASY_PROC="0" KANDIDATU_POCET="15"/>
</VYSLEDEK></OBVOD>
<OBVOD CIS_OBVODU="2" VOLENO_ZASTUP="6"><VYSLEDEK>
<UCAST OKRSKY_CELKEM="4" OKRSKY_ZPRAC="0" UCAST_PROC="0.00" PLATNE_HLASY="{votes_2}"/>
<VOLEBNI_STRANA VSTRANA="1" NAZEV_STRANY="A" HLASY="{votes_2}" HLASY_PROC="0" KANDIDATU_POCET="6"/>
</VYSLEDEK></OBVOD>
</OBEC></VYSLEDKY_OBEC>""".encode()


def test_district_files_are_merged_by_file_number(monkeypatch) -> None:
    files = {"_1": _xml(0, 99), "_2": _xml(99, 0)}

    def fetch(self, url: str) -> DownloadedPayload:
        suffix = url.rsplit("544779", 1)[1].removesuffix(".xml")
        if suffix not in files:
            response = requests.Response()
            response.status_code = 404
            raise requests.HTTPError("404", response=response)
        content = files[suffix]
        return DownloadedPayload(
            url, content, datetime.now(UTC), hashlib.sha256(content).hexdigest()
        )

    monkeypatch.setattr(app.Downloader, "fetch", fetch)

    snapshot = app.fetch_current_snapshot("544779")

    votes = {party.constituency_id: party.votes for party in snapshot.party_results}
    assert votes == {"1": 0, "2": 0}
    assert snapshot.valid_votes_by_constituency == {"1": 0, "2": 0}
