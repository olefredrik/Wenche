"""
Dokument-endepunktene for hostet Wenche (HTTP-nivå).

- Uten invite er dokumentgenerering stengt.
- Med invite genereres alle fire dokumenttyper (skattemelding, årsregnskap, aksjonær, noter)
  som base64-filer, rett fra config-en i request-body (ingen nettverk, ingenting lagres).
- Ugyldig årsregnskap (balansen går ikke opp) gir 422 uten å generere.
"""
import base64
import importlib

import pytest
from fastapi.testclient import TestClient

from hosted.api.auth import lag_invite_token

_INVITE_SECRET = "test-invite-secret"


@pytest.fixture
def klient(monkeypatch):
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("HOSTED_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HOSTED_INVITE_SECRET", _INVITE_SECRET)
    from hosted.api import config

    config.settings.cache_clear()
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as klient:
        yield klient
    config.settings.cache_clear()


def _gyldig_config(org="314273818"):
    """Komplett, balansert årsregnskap-config (eiendeler = EK = 30000), med noter."""
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
        "noter": {"antall_ansatte": 0, "laan_til_naerstaaende": []},
    }


def _inviter(klient, org="314273818"):
    klient.post("/api/auth/invite", json={"token": lag_invite_token(org)})


def test_dokumenter_stengt_uten_invite(klient):
    r = klient.post("/api/dokumenter/noter", json=_gyldig_config())
    assert r.status_code == 401


@pytest.mark.parametrize("type_", ["skattemelding", "aarsregnskap", "aksjonaer", "noter"])
def test_dokumenter_genereres_med_invite(klient, type_):
    _inviter(klient)
    r = klient.post(f"/api/dokumenter/{type_}", json=_gyldig_config())
    assert r.status_code == 200, r.text
    filer = r.json()["filer"]
    assert filer, "forventet minst én fil"
    for f in filer:
        assert f["filnavn"] and f["mime"]
        base64.b64decode(f["base64"])  # gyldig base64


def test_aarsregnskap_uten_balanse_gir_422(klient):
    _inviter(klient)
    cfg = _gyldig_config()
    cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = 999  # balansen går ikke opp
    r = klient.post("/api/dokumenter/aarsregnskap", json=cfg)
    assert r.status_code == 422
    assert "feil" in r.json()["detail"]


@pytest.mark.parametrize("verdi", ["", None])
def test_skattemelding_tomt_stiftelsesaar_gir_422_ikke_500(klient, verdi):
    # Regresjon: en tom stiftelsesår/aksjekapital (typisk etter SAF-T-import, issue #130) ble
    # før en naken int('')/float('')-500. Nå er det et rettbart avvik med lesbar melding.
    _inviter(klient)
    cfg = _gyldig_config()
    cfg["selskap"]["stiftelsesaar"] = verdi
    r = klient.post("/api/dokumenter/skattemelding", json=cfg)
    assert r.status_code == 422, r.text
    feil = r.json()["detail"]["feil"]
    assert any("Stiftelsesår" in f for f in feil)
