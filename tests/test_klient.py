"""Klientbasen (wenche/klient.py): miljø, Bearer-token, og ett kall som blir MyndighetsFeil."""

import httpx
import pytest

from wenche import miljoer
from wenche.feil import MyndighetsFeil
from wenche.klient import HttpKlient


class _Klient(HttpKlient):
    tjeneste = "altinn"


def _med_transport(klient: HttpKlient, handler) -> HttpKlient:
    """Bytt httpx-klienten med en som svarer fra `handler`, men behold headerne."""
    gammel = klient._http
    klient._http = httpx.Client(transport=httpx.MockTransport(handler), headers=gammel.headers)
    gammel.close()
    return klient


def test_token_og_miljo():
    sett = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sett["auth"] = request.headers["Authorization"]
        sett["accept"] = request.headers["Accept"]
        return httpx.Response(200, json={"ok": True})

    with _med_transport(_Klient("hemmelig", env="test"), handler) as k:
        assert k.miljo is miljoer.TEST
        assert k._kall("GET", "https://x/y", "et steg").json() == {"ok": True}
    assert sett == {"auth": "Bearer hemmelig", "accept": "application/json"}


def test_feilstatus_blir_myndighetsfeil_med_steg_og_kode():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": "AUTH-00004"}, request=request)

    with (
        _med_transport(_Klient("t", env="prod"), handler) as k,
        pytest.raises(MyndighetsFeil) as ei,
    ):
        k._kall("POST", "https://x/y", "oppretting av innsending i Altinn")
    e = ei.value
    assert (e.tjeneste, e.steg, e.status, e.kode) == (
        "altinn",
        "oppretting av innsending i Altinn",
        400,
        "AUTH-00004",
    )


def test_nettverksfeil_blir_myndighetsfeil():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nede", request=request)

    with (
        _med_transport(_Klient("t", env="prod"), handler) as k,
        pytest.raises(MyndighetsFeil) as ei,
    ):
        k._kall("GET", "https://x/y", "henting av status")
    assert "tidsavbrudd" in str(ei.value) and ei.value.steg == "henting av status"


def test_kontekst_lukker_klienten():
    k = _Klient("t", env="test")
    with k:
        pass
    assert k._http.is_closed
