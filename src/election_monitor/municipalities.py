from __future__ import annotations

import csv
import io
import json
import re
import threading
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

from .config import (
    COUNCIL_GEOGRAPHY_URL,
    COUNCIL_REGISTRY_CACHE_PATH,
    COUNCIL_REGISTRY_CACHE_SECONDS,
    COUNCIL_REGISTRY_PAGE_URL,
)


class RegistryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MunicipalityOption:
    code: str
    council_name: str
    municipality_name: str
    region_code: str = ""
    region_name: str = ""
    district_code: str = ""
    district_name: str = ""

    @property
    def label(self) -> str:
        if self.council_name.casefold() == self.municipality_name.casefold():
            return self.municipality_name
        return f"{self.council_name} — {self.municipality_name}"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


class _GeographyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


_registry_lock = threading.Lock()
_registry_cache: tuple[float, list[MunicipalityOption]] | None = None
_registry_filename = re.compile(r"KV2026reg\d+_csv\.zip$", re.IGNORECASE)
_cache_ttl = COUNCIL_REGISTRY_CACHE_SECONDS
_cache_version = 2
_region_nuts_to_code = {
    "CZ01": "1100",
    "CZ02": "2100",
    "CZ031": "3100",
    "CZ032": "3200",
    "CZ041": "4100",
    "CZ042": "4200",
    "CZ051": "5100",
    "CZ052": "5200",
    "CZ053": "5300",
    "CZ063": "6100",
    "CZ064": "6200",
    "CZ071": "7100",
    "CZ072": "7200",
    "CZ080": "8100",
}


def get_municipalities() -> list[MunicipalityOption]:
    global _registry_cache
    now = datetime.now(UTC).timestamp()
    with _registry_lock:
        if _registry_cache and now - _registry_cache[0] < _cache_ttl:
            return _registry_cache[1].copy()

        cached = _read_cache()
        if cached and now - cached[0] < _cache_ttl:
            _registry_cache = cached
            return cached[1].copy()

        try:
            options = _download_registry()
        except (requests.RequestException, RegistryError):
            if cached:
                _registry_cache = cached
                return cached[1].copy()
            raise

        _write_cache(now, options)
        _registry_cache = (now, options)
        return options.copy()


def parse_geography_html(content: bytes) -> tuple[dict[str, str], dict[str, str]]:
    try:
        parser = _GeographyParser()
        parser.feed(content.decode("cp1250"))
    except UnicodeDecodeError as exc:
        raise RegistryError("Číselník krajů a okresů ČSÚ se nepodařilo přečíst.") from exc

    labels = {
        row[1]: row[2]
        for row in parser.rows
        if len(row) >= 3 and re.fullmatch(r"CZ[0-9A-Z]+", row[1])
    }
    region_names = {
        region_code: labels[nuts_code]
        for nuts_code, region_code in _region_nuts_to_code.items()
        if nuts_code in labels
    }
    district_names: dict[str, str] = {}
    for nuts_code, name in labels.items():
        region_nuts = next(
            (
                code
                for code in sorted(_region_nuts_to_code, key=len, reverse=True)
                if nuts_code.startswith(code) and len(nuts_code) == 6
            ),
            None,
        )
        if region_nuts is None:
            continue
        suffix = nuts_code[len(region_nuts) :]
        district_number = (
            int(suffix)
            if suffix.isdigit()
            else ord(suffix[-1]) - ord("A") + 10
        )
        district_code = f"{_region_nuts_to_code[region_nuts][:2]}{district_number:02d}"
        district_names[district_code] = name
    if len(region_names) != len(_region_nuts_to_code) or not district_names:
        raise RegistryError("Číselník krajů a okresů ČSÚ nemá očekávaný formát.")
    return region_names, district_names


def parse_registry_csv(
    content: bytes,
    region_names: dict[str, str] | None = None,
    district_names: dict[str, str] | None = None,
) -> list[MunicipalityOption]:
    region_names = region_names or {}
    district_names = district_names or {}
    try:
        text = content.decode("cp1250")
        rows = csv.DictReader(io.StringIO(text), delimiter=";")
        options_by_code: dict[str, MunicipalityOption] = {}
        for row in rows:
            code = (row.get("KODZASTUP") or "").strip()
            state = (row.get("STAV_OBCE") or "").strip()
            council_name = (row.get("NAZEVZAST") or "").strip()
            municipality_name = (row.get("NAZEVOBCE") or "").strip()
            region_code = (row.get("KRAJ") or "").strip().zfill(4)
            district_code = (row.get("OKRES") or "").strip().zfill(4)
            if (
                state != "0"
                or not code.isascii()
                or not code.isdigit()
                or not council_name
                or not municipality_name
            ):
                continue
            options_by_code.setdefault(
                code.zfill(6),
                MunicipalityOption(
                    code=code.zfill(6),
                    council_name=council_name,
                    municipality_name=municipality_name,
                    region_code=region_code,
                    region_name=region_names.get(region_code, region_code),
                    district_code=district_code,
                    district_name=district_names.get(district_code, district_code),
                ),
            )
    except (UnicodeDecodeError, csv.Error) as exc:
        raise RegistryError("Číselník obcí ČSÚ se nepodařilo přečíst.") from exc

    if not options_by_code:
        raise RegistryError("Číselník ČSÚ neobsahuje žádná platná zastupitelstva.")
    return sorted(
        options_by_code.values(),
        key=lambda option: (
            option.municipality_name.casefold(),
            option.council_name.casefold(),
            option.code,
        ),
    )


def download_registry_archive() -> bytes:
    page = requests.get(
        COUNCIL_REGISTRY_PAGE_URL,
        timeout=30,
        headers={"User-Agent": "election-monitor/0.1"},
    )
    page.raise_for_status()
    links = _LinkParser()
    links.feed(page.text)
    registry_url = next(
        (
            urljoin(COUNCIL_REGISTRY_PAGE_URL, link)
            for link in links.links
            if _registry_filename.search(link.rsplit("/", 1)[-1])
        ),
        None,
    )
    if registry_url is None:
        raise RegistryError("Na stránce ČSÚ se nepodařilo najít aktuální registr obcí.")

    response = requests.get(
        registry_url,
        timeout=60,
        headers={"User-Agent": "election-monitor/0.1"},
    )
    response.raise_for_status()
    if len(response.content) > 25_000_000:
        raise RegistryError("Stažený číselník ČSÚ překračuje povolenou velikost.")
    return response.content


def _download_registry() -> list[MunicipalityOption]:
    archive_content = download_registry_archive()
    geography_response = requests.get(
        COUNCIL_GEOGRAPHY_URL,
        timeout=30,
        headers={"User-Agent": "election-monitor/0.1"},
    )
    geography_response.raise_for_status()
    region_names, district_names = parse_geography_html(geography_response.content)
    try:
        with zipfile.ZipFile(io.BytesIO(archive_content)) as archive:
            csv_name = next(
                name
                for name in archive.namelist()
                if name.lower().endswith("/kvrzcoco.csv")
                or name.lower() == "kvrzcoco.csv"
            )
            if archive.getinfo(csv_name).file_size > 10_000_000:
                raise RegistryError("Soubor registru obcí překračuje povolenou velikost.")
            return parse_registry_csv(
                archive.read(csv_name),
                region_names=region_names,
                district_names=district_names,
            )
    except (zipfile.BadZipFile, KeyError, StopIteration) as exc:
        raise RegistryError("Archiv registru obcí ČSÚ nemá očekávaný formát.") from exc


def _read_cache() -> tuple[float, list[MunicipalityOption]] | None:
    try:
        data = json.loads(COUNCIL_REGISTRY_CACHE_PATH.read_text(encoding="utf-8"))
        if data.get("version") != _cache_version:
            return None
        timestamp = float(data["fetched_at"])
        options = [MunicipalityOption(**item) for item in data["municipalities"]]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not options:
        return None
    return timestamp, options


def _write_cache(timestamp: float, options: list[MunicipalityOption]) -> None:
    path: Path = COUNCIL_REGISTRY_CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "version": _cache_version,
                "fetched_at": timestamp,
                "municipalities": [asdict(option) for option in options],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(path)
