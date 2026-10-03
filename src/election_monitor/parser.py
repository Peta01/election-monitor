from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from .models import ElectionSnapshot, MunicipalityRef, PartyResult, PollingProgress


class ParserError(RuntimeError):
    pass


class ElectionParser:
    def parse(
        self,
        raw_bytes: bytes,
        municipality_code: str,
        source_url: str,
        source_hash: str,
        fetched_at: datetime | None = None,
    ) -> ElectionSnapshot:
        try:
            root = ET.fromstring(raw_bytes)
        except ET.ParseError as exc:
            raise ParserError(f"Invalid election XML: {exc}") from exc

        if _local_name(root.tag) != "VYSLEDKY_OBEC":
            raise ParserError(f"Unexpected XML root element: {_local_name(root.tag)}")

        error = _child(root, "CHYBA")
        if error is not None:
            raise ParserError((error.text or "The election source returned an error.").strip())

        municipality_node = _child(root, "OBEC")
        if municipality_node is None:
            raise ParserError("The election XML does not contain municipality results.")

        code = municipality_code.strip()
        if not code.isascii() or not code.isdigit() or len(code) > 6:
            raise ParserError("Municipality code must contain 1 to 6 digits.")
        source_code = _required_attribute(municipality_node, "KODZASTUP")
        normalized_code = code.zfill(6)
        if source_code.zfill(6) != normalized_code:
            raise ParserError(
                f"Election data is for municipality {source_code}, not {normalized_code}."
            )

        name = _required_attribute(municipality_node, "NAZEVZAST")
        result_node = _child(municipality_node, "VYSLEDEK")
        if result_node is None:
            raise ParserError("The election XML does not contain a result element.")
        turnout_node = _child(result_node, "UCAST")
        if turnout_node is None:
            raise ParserError("The election XML does not contain turnout data.")

        progress = PollingProgress(
            processed_districts=_integer_attribute(turnout_node, "OKRSKY_ZPRAC"),
            total_districts=_integer_attribute(turnout_node, "OKRSKY_CELKEM"),
            turnout_percent=_float_attribute(turnout_node, "UCAST_PROC"),
        )
        electoral_districts = _children(municipality_node, "OBVOD")
        if electoral_districts:
            seat_counts = {
                _required_attribute(district, "CIS_OBVODU"): _integer_attribute(
                    district, "VOLENO_ZASTUP"
                )
                for district in electoral_districts
            }
            result_elements = [
                (
                    _required_attribute(district, "CIS_OBVODU"),
                    _child(district, "VYSLEDEK"),
                )
                for district in electoral_districts
            ]
        else:
            seat_counts = {
                "0": _integer_attribute(municipality_node, "VOLENO_ZASTUP")
            }
            result_elements = [("0", result_node)]

        party_results: list[PartyResult] = []
        valid_votes: dict[str, int] = {}
        for constituency_id, constituency_result in result_elements:
            if constituency_result is None:
                raise ParserError(
                    f"The election XML does not contain results for constituency {constituency_id}."
                )
            constituency_turnout = _child(constituency_result, "UCAST")
            if constituency_turnout is None:
                raise ParserError(
                    f"The election XML does not contain turnout data for constituency "
                    f"{constituency_id}."
                )
            valid_votes[constituency_id] = _integer_attribute(
                constituency_turnout, "PLATNE_HLASY"
            )
            party_results.extend(
                PartyResult(
                    list_id=_optional_attribute(party, "POR_STR_HLAS_LIST")
                    or _required_attribute(party, "VSTRANA"),
                    name=_required_attribute(party, "NAZEV_STRANY"),
                    votes=_integer_attribute(party, "HLASY"),
                    percent=_float_attribute(party, "HLASY_PROC"),
                    candidate_count=_integer_attribute(party, "KANDIDATU_POCET"),
                    constituency_id=constituency_id,
                )
                for party in _children(constituency_result, "VOLEBNI_STRANA")
            )
        return ElectionSnapshot(
            municipality=MunicipalityRef(code=normalized_code, name=name),
            fetched_at=fetched_at or datetime.now(UTC),
            source_url=source_url,
            source_hash=source_hash,
            progress=progress,
            party_results=party_results,
            seats_to_elect=_integer_attribute(municipality_node, "VOLENO_ZASTUP"),
            seat_counts_by_constituency=seat_counts,
            valid_votes_by_constituency=valid_votes,
        )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element if _local_name(child.tag) == name), None)


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local_name(child.tag) == name]


def _required_attribute(element: ET.Element, name: str) -> str:
    value = element.attrib.get(name)
    if value is None:
        raise ParserError(f"Missing required XML attribute: {name}")
    return value


def _optional_attribute(element: ET.Element, name: str) -> str | None:
    return element.attrib.get(name)


def _integer_attribute(element: ET.Element, name: str) -> int:
    value = _required_attribute(element, name)
    try:
        return int(value)
    except ValueError as exc:
        raise ParserError(f"Invalid integer in XML attribute {name}: {value}") from exc


def _float_attribute(element: ET.Element, name: str) -> float:
    value = _required_attribute(element, name)
    try:
        return float(value)
    except ValueError as exc:
        raise ParserError(f"Invalid number in XML attribute {name}: {value}") from exc
