"""
Innsendings-endepunktene for self-hosted Wenche (HTTP-nivå, ingen nettverk).

Dry-run gir strukturert ok/feil, valideringsfeil ved ekte innsending blir 422, token-hentingen
ligger inne i feilfellen, og 403 i testmiljø får Tenor-hintet. Selve feilfellen (`kjoer`) er
delt med hostet og dekkes i test_web_felles_innsending.py. Auth mockes; ingenting treffer nett
eller disk.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from wenche.web.backend import miljo, ruter_innsending
from wenche.web.backend.app import lag_app
from wenche.web.felles.innsending import kjoer


def _gyldig_config(org="310137715"):
    """Komplett, balansert årsregnskap-config (eiendeler = EK = 30000)."""
    return {
        "selskap": {
            "navn": "Test AS",
            "org_nummer": org,
            "daglig_leder": "D L",
            "styreleder": "D L",
            "forretningsadresse": "Vei 1, 0001 OSLO",
            "stiftelsesaar": 2018,
            "aksjekapital": 30000,
            "kontakt_epost": "a@b.no",
        },
        "regnskapsaar": 2024,
        "resultatregnskap": {
            "driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
            "driftskostnader": {
                "loennskostnader": 0,
                "avskrivninger": 0,
                "andre_driftskostnader": 0,
            },
            "finansposter": {
                "utbytte_fra_datterselskap": 0,
                "andre_finansinntekter": 0,
                "rentekostnader": 0,
                "andre_finanskostnader": 0,
            },
        },
        "balanse": {
            "eiendeler": {
                "anleggsmidler": {
                    "aksjer_i_datterselskap": 0,
                    "andre_aksjer": 0,
                    "langsiktige_fordringer": 0,
                },
                "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000},
            },
            "egenkapital_og_gjeld": {
                "egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 0},
                "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
                "kortsiktig_gjeld": {
                    "leverandoergjeld": 0,
                    "skyldige_offentlige_avgifter": 0,
                    "annen_kortsiktig_gjeld": 0,
                },
            },
        },
        "skattemelding": {
            "anvend_fritaksmetoden": False,
            "boersnotert": False,
            "underskudd_til_fremfoering": 0,
            "formuesverdi_aksjer": 0,
        },
        "aksjonaerer": [
            {
                "navn": "X",
                "fodselsnummer": "24847799354",
                "antall_aksjer": 300,
                "aksjeklasse": "ordinære",
                "utbytte_utbetalt": 0,
                "innbetalt_kapital_per_aksje": 100,
            }
        ],
    }


@pytest.fixture
def klient(monkeypatch):
    # Registrer original-verdien for restore, lag_app muterer den via sett_env.
    monkeypatch.setattr(miljo, "_AKTIV_ENV", miljo._AKTIV_ENV)
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    with TestClient(
        lag_app(env="test", serve_spa=False),
        # Vakten i vakt.py krever loopback-Host og klientheaderen på endringskall.
        base_url="http://127.0.0.1",
        headers={"X-Wenche-Klient": "1"},
    ) as klient:
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


def _hev(e):
    def fn():
        raise e

    return fn


# ---------------------------------------------------------------------------
# Strukturerte feil (wenche.feil) og token-henting inne i feilfellen
# ---------------------------------------------------------------------------


def test_tokenfeil_blir_lesbar_502_ikke_500(klient, monkeypatch):
    """Token-hentingen ligger inne i feilfellen: et avslag fra Maskinporten skal ikke bli 500."""
    import wenche.auth as auth_mod
    from wenche.feil import AuthFeil

    def avslag():
        raise AuthFeil(status=400, kode="invalid_scope", beskrivelse="scope mangler")

    monkeypatch.setattr(auth_mod, "get_altinn_token", avslag)
    r = klient.post("/api/innsending/aarsregnskap", json=_gyldig_config())
    assert r.status_code == 502, r.text
    assert "invalid_scope" in r.json()["detail"]


def test_403_i_testmiljo_gir_tenor_hint(klient):
    from wenche.feil import MyndighetsFeil

    feil = MyndighetsFeil("altinn", "oppretting av innsending i Altinn", status=403)
    with pytest.raises(HTTPException) as ei:
        kjoer(_hev(feil), hint_403=ruter_innsending.hint_403())
    assert ei.value.status_code == 502
    assert "Tenor" in str(ei.value.detail)


def test_403_i_prod_gir_ikke_tenor_hint(monkeypatch):
    monkeypatch.setattr(miljo, "_AKTIV_ENV", "prod")
    assert ruter_innsending.hint_403() is None
