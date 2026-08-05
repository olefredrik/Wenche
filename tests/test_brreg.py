"""
Enhetsregister-oppslag for forhåndsfylling (wenche.brreg).

Parsingen dekkes direkte; fetch-funksjonene mockes på httpx-nivå og må være fail-soft: ukjent
org, manglende felt og transient nettverksfeil skal aldri kaste, bare gi tomme verdier (0/"").
"""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from wenche import brreg

_ROLLER = {
    "rollegrupper": [
        {
            "type": {"kode": "DAGL"},
            "roller": [
                {"type": {"kode": "DAGL"}, "person": {"navn": {"fornavn": "Kari", "etternavn": "Nordmann"}}},
            ],
        },
        {
            "type": {"kode": "STYR"},
            "roller": [
                {"type": {"kode": "LEDE"}, "person": {"navn": {"fornavn": "Ola", "mellomnavn": "F", "etternavn": "Lie"}}},
                {"type": {"kode": "MEDL"}, "person": {"navn": {"fornavn": "Per", "etternavn": "Hansen"}}},
            ],
        },
    ]
}


def test_parse_roller_plukker_daglig_leder_og_styreleder():
    r = brreg.parse_roller(_ROLLER)
    assert r["daglig_leder"] == "Kari Nordmann"
    assert r["styreleder"] == "Ola F Lie"  # styreleder er rolletype LEDE i STYR-gruppen, ikke MEDL
    assert r["alle"] == ["Kari Nordmann", "Ola F Lie", "Per Hansen"]


def test_parse_roller_hopper_over_fratraadt_og_doed():
    data = {
        "rollegrupper": [
            {"type": {"kode": "DAGL"}, "roller": [
                {"type": {"kode": "DAGL"}, "fratraadt": True,
                 "person": {"navn": {"fornavn": "Gammel", "etternavn": "Leder"}}},
            ]},
            {"type": {"kode": "STYR"}, "roller": [
                {"type": {"kode": "LEDE"},
                 "person": {"erDoed": True, "navn": {"fornavn": "Avdod", "etternavn": "Leder"}}},
            ]},
        ]
    }
    r = brreg.parse_roller(data)
    assert r["daglig_leder"] == ""
    assert r["styreleder"] == ""
    assert r["alle"] == []


def test_parse_roller_tomt_svar():
    assert brreg.parse_roller({}) == {"daglig_leder": "", "styreleder": "", "alle": []}


def test_parse_stiftelsesaar():
    assert brreg.parse_stiftelsesaar({"stiftelsesdato": "2018-06-15"}) == 2018
    assert brreg.parse_stiftelsesaar({"stiftelsesdato": ""}) == 0
    assert brreg.parse_stiftelsesaar({}) == 0
    assert brreg.parse_stiftelsesaar({"stiftelsesdato": "xx"}) == 0


def test_parse_enhet_navn_adresse_og_stiftelsesaar():
    data = {
        "navn": "OFL HOLDING AS",
        "stiftelsesdato": "2018-12-11",
        "forretningsadresse": {
            "adresse": ["c/o Ole Fredrik Lie", "Kong Carls gate 29"],
            "postnummer": "4010",
            "poststed": "STAVANGER",
        },
    }
    e = brreg.parse_enhet(data)
    assert e["navn"] == "OFL HOLDING AS"
    assert e["forretningsadresse"] == "c/o Ole Fredrik Lie, Kong Carls gate 29, 4010 STAVANGER"
    assert e["stiftelsesaar"] == 2018


def test_parse_enhet_tomt_svar():
    assert brreg.parse_enhet({}) == {
        "navn": "",
        "forretningsadresse": "",
        "stiftelsesaar": 0,
        "stiftelsesdato": "",
    }


def _resp(status_code: int = 200, json_data: dict | None = None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    return resp


@patch("wenche.brreg.httpx.get")
def test_hent_roller_ok(mock_get):
    mock_get.return_value = _resp(json_data=_ROLLER)
    r = brreg.hent_roller("999999999")
    assert r["daglig_leder"] == "Kari Nordmann"
    assert r["styreleder"] == "Ola F Lie"


@patch("wenche.brreg.httpx.get")
def test_hent_roller_404_failsoft(mock_get):
    mock_get.return_value = _resp(status_code=404)
    assert brreg.hent_roller("999999999") == {"daglig_leder": "", "styreleder": "", "alle": []}


@patch("wenche.brreg.httpx.get")
def test_hent_roller_nettverksfeil_failsoft(mock_get):
    mock_get.side_effect = httpx.ConnectError("nede")
    assert brreg.hent_roller("999999999")["alle"] == []


@patch("wenche.brreg.httpx.get")
def test_hent_enhet_ok(mock_get):
    mock_get.return_value = _resp(json_data={"navn": "TEST AS", "stiftelsesdato": "2020-01-02"})
    e = brreg.hent_enhet("999999999")
    assert e["navn"] == "TEST AS"
    assert e["stiftelsesaar"] == 2020


@patch("wenche.brreg.httpx.get")
def test_hent_enhet_5xx_failsoft(mock_get):
    mock_get.return_value = _resp(status_code=503)
    assert brreg.hent_enhet("999999999") == {
        "navn": "",
        "forretningsadresse": "",
        "stiftelsesaar": 0,
        "stiftelsesdato": "",
    }


def test_parse_stiftelsesdato_beholder_dag_og_maaned():
    # Regresjon: oppslaget kastet før bort dag og måned, så RF-1086 oppgav 1. januar og et
    # forlenget første regnskapsår startet på feil dato.
    assert brreg.parse_stiftelsesdato({"stiftelsesdato": "2025-11-20"}) == "2025-11-20"


@pytest.mark.parametrize("verdi", [None, "", "  ", "2025-13-01", "tullball", "2025"])
def test_parse_stiftelsesdato_ugyldig_gir_tom(verdi):
    assert brreg.parse_stiftelsesdato({"stiftelsesdato": verdi}) == ""


def test_parse_enhet_tar_med_stiftelsesdato():
    e = brreg.parse_enhet({"navn": "TEST AS", "stiftelsesdato": "2025-11-20"})
    assert e["stiftelsesdato"] == "2025-11-20"
    assert e["stiftelsesaar"] == 2025
