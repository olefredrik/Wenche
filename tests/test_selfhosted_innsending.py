"""
Innsendings-endepunktene for self-hosted Wenche (HTTP-nivå, ingen nettverk).

Speiler test_hosted_innsending_feil.py for den self-hostede backenden: dry-run gir
strukturert ok/feil, valideringsfeil ved ekte innsending blir 422, og alle feiltyper fra
domeneklientene (HTTP-feil, nettverksfeil, RuntimeError) blir lesbare 502-svar, aldri en
naken 500. Auth mockes; ingenting treffer nett eller disk.
"""
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from wenche.web.backend import miljo
from wenche.web.backend.app import lag_app
from wenche.web.backend.ruter_innsending import _utfor


def _gyldig_config(org="310137715"):
    """Komplett, balansert årsregnskap-config (eiendeler = EK = 30000)."""
    return {
        "selskap": {"navn": "Test AS", "org_nummer": org, "daglig_leder": "D L",
                    "styreleder": "D L", "forretningsadresse": "Vei 1, 0001 OSLO",
                    "stiftelsesaar": 2018, "aksjekapital": 30000, "kontakt_epost": "a@b.no"},
        "regnskapsaar": 2024,
        "resultatregnskap": {
            "driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
            "driftskostnader": {"loennskostnader": 0, "avskrivninger": 0, "andre_driftskostnader": 0},
            "finansposter": {"utbytte_fra_datterselskap": 0, "andre_finansinntekter": 0,
                             "rentekostnader": 0, "andre_finanskostnader": 0}},
        "balanse": {
            "eiendeler": {"anleggsmidler": {"aksjer_i_datterselskap": 0, "andre_aksjer": 0, "langsiktige_fordringer": 0},
                          "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000}},
            "egenkapital_og_gjeld": {
                "egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 0},
                "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
                "kortsiktig_gjeld": {"leverandoergjeld": 0, "skyldige_offentlige_avgifter": 0,
                                     "annen_kortsiktig_gjeld": 0}}},
        "skattemelding": {"anvend_fritaksmetoden": False, "boersnotert": False,
                          "underskudd_til_fremfoering": 0, "formuesverdi_aksjer": 0},
        "aksjonaerer": [{"navn": "X", "fodselsnummer": "24847799354", "antall_aksjer": 300,
                         "aksjeklasse": "ordinære", "utbytte_utbetalt": 0,
                         "innbetalt_kapital_per_aksje": 100}],
    }


@pytest.fixture
def klient(monkeypatch):
    # Registrer original-verdien for restore, lag_app muterer den via sett_env.
    monkeypatch.setattr(miljo, "_AKTIV_ENV", miljo._AKTIV_ENV)
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    with TestClient(lag_app(env="test", serve_spa=False)) as klient:
        yield klient


# ---------------------------------------------------------------------------
# Dry-run: lokal validering, strukturert ok/feil
# ---------------------------------------------------------------------------

def test_dryrun_aarsregnskap_ok(klient):
    r = klient.post("/api/innsending/aarsregnskap?dry_run=true", json=_gyldig_config())
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_dryrun_aksjonaer_viser_valideringsfeil(klient):
    # Regresjon: valider_aksjonaer returnerte tidligere alltid ok=True uten å validere.
    cfg = _gyldig_config()
    del cfg["selskap"]["kontakt_epost"]
    cfg["aksjonaerer"][0]["fodselsnummer"] = "12345"
    r = klient.post("/api/innsending/aksjonaer?dry_run=true", json=cfg)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is False
    assert any("kontakt_epost" in f for f in data["feil"])


def test_dryrun_skattemelding_ok(klient):
    r = klient.post("/api/innsending/skattemelding?dry_run=true", json=_gyldig_config())
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


# ---------------------------------------------------------------------------
# Ekte innsending: valideringsfeil blir 422 før noe sendes
# ---------------------------------------------------------------------------

def test_aksjonaer_valideringsfeil_blir_422_ikke_systemexit(klient, monkeypatch):
    import wenche.auth as auth_mod

    monkeypatch.setattr(auth_mod, "get_skd_aksjonaer_token", lambda: "fake-token")
    cfg = _gyldig_config()
    del cfg["selskap"]["kontakt_epost"]
    r = klient.post("/api/innsending/aksjonaer", json=cfg)
    assert r.status_code == 422, r.text
    assert any("kontakt_epost" in f for f in r.json()["detail"]["feil"])


def test_aarsregnskap_valideringsfeil_blir_422(klient, monkeypatch):
    import wenche.auth as auth_mod

    monkeypatch.setattr(auth_mod, "get_altinn_token", lambda: "fake-token")
    cfg = _gyldig_config()
    cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = 999  # balansen går ikke opp
    r = klient.post("/api/innsending/aarsregnskap", json=cfg)
    assert r.status_code == 422, r.text
    assert "feil" in r.json()["detail"]


# ---------------------------------------------------------------------------
# _utfor: alle feiltyper fra domeneklientene blir lesbare 502, aldri naken 500
# ---------------------------------------------------------------------------

def _hev(e):
    def fn():
        raise e
    return fn


def test_altinn_403_blir_lesbar_502():
    req = httpx.Request("POST", "https://brg.apps.tt02.altinn.no/brg/x/instances")
    feil = httpx.HTTPStatusError("403", request=req, response=httpx.Response(403, request=req))
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(feil))
    assert ei.value.status_code == 502
    assert "403" in str(ei.value.detail)


def test_nettverksfeil_timeout_blir_502_ikke_500():
    # Samme hull som hostet tettet i PR #131: httpx.RequestError er søsken av
    # HTTPStatusError og ble en naken 500 i self-hosted.
    req = httpx.Request("POST", "https://skatt.skatteetaten.no/api/skattemelding/v2/valider")
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(httpx.ConnectTimeout("timed out", request=req)))
    assert ei.value.status_code == 502
    assert "tidsavbrudd" in str(ei.value.detail).lower()


def test_runtimeerror_blir_502():
    with pytest.raises(HTTPException) as ei:
        _utfor(_hev(RuntimeError("Feil ved henting av forhåndsutfylt skattemelding: 403")))
    assert ei.value.status_code == 502
