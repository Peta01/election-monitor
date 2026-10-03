import json

import pytest
import requests

from election_monitor import municipalities
from election_monitor.municipalities import MunicipalityOption, RegistryError


def test_parse_official_registry_csv_and_filter_inactive_records() -> None:
    csv_data = (
        "KRAJ;OKRES;KODZASTUP;NAZEVZAST;NAZEVOBCE;STAV_OBCE\r\n"
        '7200;7204;500011;"Želechovice nad Dřevnicí";"Želechovice nad Dřevnicí";0\r\n'
        '7100;7105;500020;"Petrov nad Desnou";"Petrov nad Desnou";0\r\n'
        '7200;7204;500030;"Neaktivní obec";"Neaktivní obec";1\r\n'
        '7200;7204;500011;"Želechovice nad Dřevnicí";"Želechovice nad Dřevnicí";0\r\n'
    ).encode("cp1250")

    options = municipalities.parse_registry_csv(
        csv_data,
        region_names={"7200": "Zlínský kraj", "7100": "Olomoucký kraj"},
        district_names={"7204": "Zlín", "7105": "Šumperk"},
    )

    assert options == [
        MunicipalityOption(
            "500020",
            "Petrov nad Desnou",
            "Petrov nad Desnou",
            "7100",
            "Olomoucký kraj",
            "7105",
            "Šumperk",
        ),
        MunicipalityOption(
            "500011",
            "Želechovice nad Dřevnicí",
            "Želechovice nad Dřevnicí",
            "7200",
            "Zlínský kraj",
            "7204",
            "Zlín",
        ),
    ]


def test_parse_official_nuts_html_into_registry_region_and_district_codes() -> None:
    rows = [
        ("CZ01", "Praha"),
        ("CZ02", "Středočeský kraj"),
        ("CZ031", "Jihočeský kraj"),
        ("CZ032", "Plzeňský kraj"),
        ("CZ041", "Karlovarský kraj"),
        ("CZ042", "Ústecký kraj"),
        ("CZ051", "Liberecký kraj"),
        ("CZ052", "Královéhradecký kraj"),
        ("CZ053", "Pardubický kraj"),
        ("CZ063", "Kraj Vysočina"),
        ("CZ064", "Jihomoravský kraj"),
        ("CZ071", "Olomoucký kraj"),
        ("CZ072", "Zlínský kraj"),
        ("CZ080", "Moravskoslezský kraj"),
        ("CZ0209", "Praha-východ"),
        ("CZ020A", "Praha-západ"),
        ("CZ0642", "Brno-město"),
    ]
    html = "<table>" + "".join(
        f"<tr><td></td><td>{code}</td><td>{name}</td></tr>" for code, name in rows
    ) + "</table>"

    region_names, district_names = municipalities.parse_geography_html(
        html.encode("cp1250")
    )

    assert region_names["7200"] == "Zlínský kraj"
    assert region_names["6200"] == "Jihomoravský kraj"
    assert district_names["2109"] == "Praha-východ"
    assert district_names["2110"] == "Praha-západ"
    assert district_names["6202"] == "Brno-město"


def test_get_municipalities_uses_stale_cache_if_source_is_down(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "councils.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 2,
                "fetched_at": 1,
                "municipalities": [
                    {
                        "code": "500011",
                        "council_name": "Testov",
                        "municipality_name": "Testov",
                        "region_code": "7200",
                        "region_name": "Zlínský kraj",
                        "district_code": "7204",
                        "district_name": "Zlín",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(municipalities, "COUNCIL_REGISTRY_CACHE_PATH", cache_path)
    monkeypatch.setattr(municipalities, "_registry_cache", None)
    monkeypatch.setattr(
        municipalities,
        "_download_registry",
        lambda: (_ for _ in ()).throw(requests.ConnectionError("offline")),
    )

    assert municipalities.get_municipalities() == [
        MunicipalityOption(
            "500011", "Testov", "Testov", "7200", "Zlínský kraj", "7204", "Zlín"
        )
    ]


def test_invalid_registry_is_reported() -> None:
    with pytest.raises(RegistryError, match="neobsahuje"):
        municipalities.parse_registry_csv(
            b"KRAJ;OKRES;KODZASTUP;NAZEVZAST;NAZEVOBCE;STAV_OBCE\r\n"
        )
