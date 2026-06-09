"""
Feilhåndtering i hostet innsending: Altinn/SKD-feil skal aldri bli en rå 500 til brukeren.

`_utfor` pakker innsendingen og gjør feilene domeneklientene melder om til lesbare HTTP-svar:
valideringsfeil → 422; HTTP-feil (Altinn), nettverksfeil/tidsavbrudd (httpx.RequestError) og
RuntimeError (SKD-klienten / token-henting) → 502; bevisst reist HTTPException slipper gjennom
uendret; alt annet → kontrollert 500 med melding (aldri en naken stacktrace).
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


def test_nettverksfeil_timeout_blir_502_ikke_500():
    # httpx.RequestError (tidsavbrudd) er søsken av HTTPStatusError, ikke en undertype, og
    # ble tidligere en naken 500. Den ledende forklaringen på skattemelding-500-en.
    req = httpx.Request("POST", "https://skatt.skatteetaten.no/api/skattemelding/v2/valider")
    feil = httpx.ConnectTimeout("timed out", request=req)
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(feil))
    assert ei.value.status_code == 502
    assert "tidsavbrudd" in str(ei.value.detail).lower()


def test_nettverksfeil_uten_request_kaster_ikke_i_handteringen():
    # httpx' .request kaster RuntimeError hvis den ikke er satt — håndteringen må ikke selv
    # kaste når den logger URL-en.
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(httpx.ConnectError("ingen request satt")))
    assert ei.value.status_code == 502


def test_uventet_feiltype_blir_kontrollert_500():
    # Siste skanse: en uventet feiltype skal bli en ren 500 med melding, ikke en stacktrace.
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(ValueError("noe uventet")))
    assert ei.value.status_code == 500
    assert "uventet" in str(ei.value.detail).lower()


def test_bevisst_httpexception_slipper_gjennom_uendret():
    # F.eks. _sjekk_org sin 409 skal ikke pakkes om til 502/500.
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(HTTPException(status_code=409, detail="org matcher ikke")))
    assert ei.value.status_code == 409
    assert ei.value.detail == "org matcher ikke"


def test_upstream_feilkropp_lekker_ikke_til_klient():
    """Rå feilkropp fra Altinn/SKD skal logges server-side, aldri sendes til nettleseren."""
    req = httpx.Request("POST", "https://skatt.skatteetaten.no/api/skattemelding/v2")
    svar = httpx.Response(400, text="intern-altinn-detalj-xyz stacktrace", request=req)
    feil = httpx.HTTPStatusError("400", request=req, response=svar)
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(feil))
    assert ei.value.status_code == 502
    assert "intern-altinn-detalj-xyz" not in str(ei.value.detail)
    assert "400" in str(ei.value.detail)  # statuskoden er fortsatt synlig for brukeren
