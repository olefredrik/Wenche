"""
Enhetsregister-oppslag for forhåndsfylling (wenche.brreg).

Parsingen dekkes direkte; fetch-funksjonene mockes på httpx-nivå og må være fail-soft: ukjent
org, manglende felt og transient nettverksfeil skal aldri kaste, bare gi tomme verdier (0/"").
"""
from unittest.mock import MagicMock, patch

import httpx

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
def test_hent_stiftelsesaar_ok(mock_get):
    mock_get.return_value = _resp(json_data={"stiftelsesdato": "2020-01-02"})
    assert brreg.hent_stiftelsesaar("999999999") == 2020


@patch("wenche.brreg.httpx.get")
def test_hent_stiftelsesaar_5xx_failsoft(mock_get):
    mock_get.return_value = _resp(status_code=503)
    assert brreg.hent_stiftelsesaar("999999999") == 0
