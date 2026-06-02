"""
Feilhåndtering i hostet innsending: Altinn/SKD-feil skal aldri bli en rå 500 til brukeren.

`_utfor` pakker innsendingen og gjør de tre feilklassene domeneklientene melder om til lesbare
HTTP-svar: valideringsfeil → 422, rå httpx-feil (Altinn) og RuntimeError (SKD-klienten) → 502.
"""
import httpx
import pytest
from fastapi import HTTPException

from hosted.api.innsending import _utfor
from wenche.innsending import InnsendingValideringsfeil
from wenche.skd_skattemelding_client import SkattemeldingValideringsfeil


def _hev(exc):
    def fn():
        raise exc
    return fn


def test_altinn_serverfeil_blir_502_ikke_500():
    req = httpx.Request("POST", "https://brg.apps.tt02.altinn.no/brg/x/instances")
    feil = httpx.HTTPStatusError("500", request=req, response=httpx.Response(500, request=req))
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(feil))
    assert ei.value.status_code == 502
    assert "serverfeil" in str(ei.value.detail).lower()


def test_altinn_403_blir_lesbar_502():
    req = httpx.Request("POST", "https://brg.apps.tt02.altinn.no/brg/x/instances")
    feil = httpx.HTTPStatusError("403", request=req, response=httpx.Response(403, request=req))
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(feil))
    assert ei.value.status_code == 502


def test_skd_runtimeerror_blir_502():
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(RuntimeError("Feil ved henting av forhåndsutfylt skattemelding: 403")))
    assert ei.value.status_code == 502


def test_aarsregnskap_valideringsfeil_blir_422():
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(InnsendingValideringsfeil(["Balansen går ikke opp"])))
    assert ei.value.status_code == 422
    assert ei.value.detail == {"feil": ["Balansen går ikke opp"]}


def test_skattemelding_valideringsfeil_blir_422():
    resultat = {"resultat": "validertMedFeil", "aarsak": "tekniskFeil",
                "avvik_ved_validering": [{"avvikstype": "tekniskFeil"}],
                "avvik_etter_beregning": [], "veiledning": []}
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(SkattemeldingValideringsfeil(resultat)))
    assert ei.value.status_code == 422
    assert "validering" in ei.value.detail
