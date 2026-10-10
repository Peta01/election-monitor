from __future__ import annotations

import csv
import io
import threading
import time
import zipfile
from dataclasses import dataclass

import requests

from .config import CANDIDATES_CACHE_PATH, CANDIDATES_CACHE_SECONDS
from .municipalities import RegistryError, download_registry_archive


@dataclass(frozen=True, slots=True)
class Candidate:
    constituency_id: str
    list_id: str
    order: int
    name: str
    age: int | None
    occupation: str
    residence: str
    votes: int | None = None


_lock = threading.Lock()
_memory: dict[str, tuple[float, list[Candidate]]] = {}


def get_candidates(code: str) -> list[Candidate]:
    """Vrací platné kandidáty zastupitelstva z registru ČSÚ (kvrk.csv)."""
    code = code.zfill(6)
    with _lock:
        cached = _memory.get(code)
        if cached and time.time() - cached[0] < 60:
            return cached[1]
        content = _read_registry_csv()
        candidates = parse_candidates_csv(content, code)
        _memory[code] = (time.time(), candidates)
        return candidates


def parse_candidates_csv(content: bytes, code: str) -> list[Candidate]:
    try:
        rows = csv.DictReader(io.StringIO(content.decode("cp1250")), delimiter=";")
        parsed = [
            _candidate(row)
            for row in rows
            if (row.get("KODZASTUP") or "").strip().zfill(6) == code
            and (row.get("PLATNOST") or "A").strip() == "A"
        ]
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise RegistryError("Registr kandidátů ČSÚ se nepodařilo přečíst.") from exc

    # Hlasy se zobrazují, až když je zdroj skutečně obsahuje.
    has_votes = any((row[1] or 0) > 0 for row in parsed)
    return sorted(
        (
            _with_votes(candidate, votes if has_votes else None)
            for candidate, votes in parsed
        ),
        key=lambda c: (c.constituency_id, int(c.list_id), c.order),
    )


def _with_votes(candidate: Candidate, votes: int | None) -> Candidate:
    return Candidate(
        candidate.constituency_id,
        candidate.list_id,
        candidate.order,
        candidate.name,
        candidate.age,
        candidate.occupation,
        candidate.residence,
        votes,
    )


def _candidate(row: dict[str, str | None]) -> tuple[Candidate, int]:
    def text(key: str) -> str:
        return (row.get(key) or "").strip()

    name = " ".join(
        part
        for part in (
            text("TITULPRED"),
            text("JMENO"),
            text("PRIJMENI"),
        )
        if part
    )
    if text("TITULZA"):
        name = f"{name}, {text('TITULZA')}"
    age = text("VEK")
    return (
        Candidate(
            constituency_id=text("COBVODU") or "0",
            list_id=text("POR_STR_HL"),
            order=int(text("PORCISLO")),
            name=name,
            age=int(age) if age.isdigit() else None,
            occupation=text("POVOLANI"),
            residence=text("BYDLISTEN"),
        ),
        int(text("POCHLASU") or 0),
    )


def _read_registry_csv() -> bytes:
    path = CANDIDATES_CACHE_PATH
    try:
        fresh = time.time() - path.stat().st_mtime < CANDIDATES_CACHE_SECONDS
    except OSError:
        fresh = False
    if fresh:
        return path.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(download_registry_archive())) as archive:
            name = next(
                item
                for item in archive.namelist()
                if item.lower() in {"csv/kvrk.csv", "kvrk.csv"}
            )
            if archive.getinfo(name).file_size > 60_000_000:
                raise RegistryError("Soubor registru kandidátů překračuje povolenou velikost.")
            content = archive.read(name)
    except (requests.RequestException, zipfile.BadZipFile, StopIteration, RegistryError):
        if path.exists():
            return path.read_bytes()
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return content
