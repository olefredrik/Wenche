"""
Dokument- og frist-endepunktene for self-hosted Wenche (HTTP-nivå, ingen nettverk).

Speiler test_hosted_dokumenter.py: alle fire dokumenttyper genereres som base64-filer rett
fra config i request-body, ugyldig config gir 422. Frist-endepunktet gir statisk info uten
nettverkskall; live-sjekken er av i testmiljø.
"""
import base64

import pytest
from fastapi.testclient import TestClient

from tests.test_selfhosted_innsending import _gyldig_config
from wenche.web.backend import miljo
from wenche.web.backend.app import lag_app
from wenche.web.backend.ruter_frister import _statussjekk_aktiv


@pytest.fixture
def klient(monkeypatch):
    monkeypatch.setattr(miljo, "_AKTIV_ENV", miljo._AKTIV_ENV)
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    with TestClient(lag_app(env="test", serve_spa=False)) as klient:
        yield klient


# ---------------------------------------------------------------------------
# Dokumenter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("type_", ["skattemelding", "aarsregnskap", "aksjonaer", "noter"])
def test_dokumenter_genereres(klient, type_):
    r = klient.post(f"/api/dokumenter/{type_}", json=_gyldig_config())
    assert r.status_code == 200, r.text
    filer = r.json()["filer"]
    assert filer, "forventet minst én fil"
    for f in filer:
        assert f["filnavn"] and f["mime"]
        base64.b64decode(f["base64"])  # gyldig base64


def test_dokumenter_bruker_test_org(klient):
    # I testmiljø skal med_test_org bytte org i genererte dokumenter til Tenor-orgnr.
    r = klient.post("/api/dokumenter/aarsregnskap", json=_gyldig_config(org="922020523"))
    assert r.status_code == 200, r.text
    assert "310137715" in r.json()["filer"][0]["filnavn"]


def test_aarsregnskap_ubalansert_gir_422(klient):
    cfg = _gyldig_config()
    cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = 999
    r = klient.post("/api/dokumenter/aarsregnskap", json=cfg)
    assert r.status_code == 422
    assert "feil" in r.json()["detail"]


def test_aksjonaer_ugyldig_foedselsnummer_gir_422(klient):
    cfg = _gyldig_config()
    cfg["aksjonaerer"][0]["fodselsnummer"] = "12345"
    r = klient.post("/api/dokumenter/aksjonaer", json=cfg)
    assert r.status_code == 422
    assert any("fødselsnummer" in f.lower() for f in r.json()["detail"]["feil"])


# ---------------------------------------------------------------------------
# Frister og helse
# ---------------------------------------------------------------------------

def test_frister_statisk_info(klient):
    data = klient.get("/api/frister").json()
    assert data["env"] == "test"
    assert data["statussjekk_aktiv"] is False  # aldri live-sjekk i testmiljø
    assert {f["key"] for f in data["frister"]} == {"skattemelding", "aarsregnskap", "aksjonaerregister"}
    for f in data["frister"]:
        assert f["neste_frist"]  # ISO-dato satt


def test_frist_sjekk_inaktiv_gir_tomt_svar(klient):
    assert klient.post("/api/frister/sjekk").json() == {"statuser": {}}


def test_statussjekk_aktiv_kun_i_prod_med_ekte_orgnr(monkeypatch):
    monkeypatch.setattr(miljo, "_AKTIV_ENV", "prod")
    monkeypatch.setenv("ORG_NUMMER", "922020523")
    aktiv, orgnr = _statussjekk_aktiv()
    assert (aktiv, orgnr) == (True, "922020523")
    monkeypatch.setenv("ORG_NUMMER", "123456789")  # placeholder fra eksempel-config
    assert _statussjekk_aktiv()[0] is False


def test_health_og_update_check(klient, monkeypatch):
    monkeypatch.setenv("WENCHE_FAKE_NY_VERSJON", "99.0.0")
    assert klient.get("/api/health").json()["status"] == "ok"
    data = klient.get("/api/update-check").json()
    assert data["siste"] == "99.0.0"
    assert data["nyere"] is True
