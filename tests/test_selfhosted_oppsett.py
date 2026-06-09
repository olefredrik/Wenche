"""
Oppsett-endepunktene for self-hosted Wenche (HTTP-nivå, Altinn/Maskinporten mocket).

Dekker den mest kritiske utestede stien i self-hosted-backenden: lagring av
Maskinporten-credentials og privat nøkkel (skriver til ~/.wenche, her pekt om til tmp),
tilkoblingstesten med oversatte feilmeldinger, og systembruker-onboardingen
(registrer → opprett forespørsel → status → oppdater rettigheter).
"""
import stat

import pytest
from fastapi.testclient import TestClient

from wenche.web.backend import miljo
from wenche.web.backend.app import lag_app
from wenche.web.backend.ruter_oppsett import _tolk_feilmelding

_PEM = "-----BEGIN PRIVATE KEY-----\nMIIEv...\n-----END PRIVATE KEY-----\n"


@pytest.fixture
def klient(tmp_path, monkeypatch):
    """TestClient i testmiljø med ~/.wenche pekt om til tmp og rene credential-env-vars."""
    wenche_dir = tmp_path / ".wenche"
    monkeypatch.setattr(miljo, "_WENCHE_DIR", wenche_dir)
    monkeypatch.setattr(miljo, "_BRUKER_ENV_FIL", wenche_dir / ".env")
    monkeypatch.setattr(miljo, "_PRIVAT_NOKKEL_FIL", wenche_dir / "maskinporten_privat.pem")
    monkeypatch.setattr(miljo, "_AKTIV_ENV", miljo._AKTIV_ENV)
    monkeypatch.setenv("WENCHE_ENV", "test")
    # Tøm credentials fra repoets .env (lastes ved import) og registrer restore for
    # variablene endepunktene setter, slik at ingenting lekker mellom tester.
    for var in (
        "MASKINPORTEN_CLIENT_ID", "MASKINPORTEN_CLIENT_ID_TEST",
        "MASKINPORTEN_KID", "MASKINPORTEN_KID_TEST",
        "ORG_NUMMER", "SKD_TEST_ORG_NUMMER",
    ):
        monkeypatch.delenv(var, raising=False)
    # Pek nøkkelstien bort fra repoets ekte PEM-fil.
    monkeypatch.setenv("MASKINPORTEN_PRIVAT_NOKKEL", str(wenche_dir / "maskinporten_privat.pem"))
    with TestClient(lag_app(env="test", serve_spa=False)) as klient:
        yield klient


# ---------------------------------------------------------------------------
# Status og lagring av credentials/nøkkel
# ---------------------------------------------------------------------------

def test_status_uten_oppsett_viser_mangler(klient):
    data = klient.get("/api/oppsett/status").json()
    assert data["env"] == "test"
    assert data["credentials"]["komplett"] is False
    assert set(data["credentials"]["mangler"]) == {"Klient-ID", "Nøkkel-ID", "Orgnr"}
    assert data["nokkel"]["ok"] is False
    assert data["systembruker"]["har_forespoersel"] is False


def test_lagre_credentials_skriver_miljosuffiks(klient):
    r = klient.put("/api/oppsett/credentials", json={
        "client_id": "klient-123", "kid": "kid-456", "orgnr": "310137715",
    })
    assert r.status_code == 200 and r.json()["ok"] is True
    innhold = miljo._BRUKER_ENV_FIL.read_text(encoding="utf-8")
    assert "MASKINPORTEN_CLIENT_ID_TEST" in innhold and "klient-123" in innhold
    assert "MASKINPORTEN_KID_TEST" in innhold and "kid-456" in innhold
    # I testmiljø lagres orgnr som SKD_TEST_ORG_NUMMER, aldri som ORG_NUMMER.
    assert "SKD_TEST_ORG_NUMMER" in innhold and "310137715" in innhold

    status = klient.get("/api/oppsett/status").json()
    assert status["credentials"]["komplett"] is True


def test_lagre_nokkel_avviser_ikke_pem(klient):
    r = klient.post("/api/oppsett/nokkel", json={"pem": "dette er ikke en nøkkel"})
    assert r.status_code == 422


def test_lagre_nokkel_skriver_0600_og_peker_env(klient):
    r = klient.post("/api/oppsett/nokkel", json={"pem": _PEM})
    assert r.status_code == 200, r.text
    fil = miljo._PRIVAT_NOKKEL_FIL
    assert fil.read_text(encoding="utf-8") == _PEM
    assert stat.S_IMODE(fil.stat().st_mode) == 0o600
    status = klient.get("/api/oppsett/status").json()
    assert status["nokkel"]["ok"] is True


# ---------------------------------------------------------------------------
# Tilkoblingstest med oversatte feilmeldinger
# ---------------------------------------------------------------------------

def test_tilkobling_feil_gir_lesbar_melding(klient, monkeypatch):
    import wenche.auth as auth_mod

    raa = (
        'Maskinporten svarte 401:\n'
        '{"error": "invalid_grant", "error_description": "Client authentication failed"}'
    )
    monkeypatch.setattr(auth_mod, "login", lambda **kw: (_ for _ in ()).throw(RuntimeError(raa)))
    data = klient.post("/api/oppsett/test-tilkobling").json()
    assert data["auth_ok"] is False
    assert "ikke registrert" in data["melding"]
    assert "sjolvbetjening.test.samarbeid.digdir.no" in data["melding"]


def test_tilkobling_ok_uten_forespoersel(klient, monkeypatch):
    import wenche.auth as auth_mod

    monkeypatch.setattr(auth_mod, "login", lambda **kw: {"altinn_token": "tok"})
    data = klient.post("/api/oppsett/test-tilkobling").json()
    assert data["auth_ok"] is True
    assert data["systembruker"]["status"] == "ikke_opprettet"


def test_tilkobling_ok_med_godkjent_systembruker(klient, monkeypatch):
    import wenche.auth as auth_mod
    import wenche.systembruker as sb_mod

    monkeypatch.setattr(auth_mod, "login", lambda **kw: {"altinn_token": "tok"})
    monkeypatch.setattr(auth_mod, "login_admin", lambda: "admin-tok")
    monkeypatch.setattr(sb_mod, "hent_forespørsel_status", lambda token, rid: {"status": "Accepted"})
    miljo.lagre_request_id("req-1")
    data = klient.post("/api/oppsett/test-tilkobling").json()
    assert data["auth_ok"] is True
    assert data["systembruker"]["status"] == "godkjent"


# ---------------------------------------------------------------------------
# Systembruker-onboarding
# ---------------------------------------------------------------------------

def test_registrer_system_uten_orgnr_gir_409(klient):
    assert klient.post("/api/oppsett/registrer-system").status_code == 409


def test_opprett_systembruker_persisterer_forespoersel(klient, monkeypatch):
    import wenche.auth as auth_mod
    import wenche.systembruker as sb_mod

    monkeypatch.setenv("ORG_NUMMER", "922020523")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    monkeypatch.setattr(auth_mod, "login_admin", lambda: "admin-tok")
    monkeypatch.setattr(sb_mod, "registrer_system", lambda token, org, cid: {"oppdatert": False})
    opprettet = {}

    def fake_opprett(token, vendor, party):
        opprettet["vendor"], opprettet["party"] = vendor, party
        return {"id": "req-42", "confirmUrl": "https://altinn.test/confirm/42", "status": "New"}

    monkeypatch.setattr(sb_mod, "opprett_forespørsel", fake_opprett)
    data = klient.post("/api/oppsett/systembruker").json()
    assert data["request_id"] == "req-42"
    assert data["confirm_url"] == "https://altinn.test/confirm/42"
    # Vendor er alltid eget orgnr; rapportøren er Tenor-orgnr i testmiljø.
    assert opprettet == {"vendor": "922020523", "party": "310137715"}
    assert miljo.les_request_id() == "req-42"
    assert miljo.les_confirm_url() == "https://altinn.test/confirm/42"


def test_systembruker_status_uten_forespoersel(klient):
    data = klient.post("/api/oppsett/systembruker/status").json()
    assert data["status"] == "ikke_opprettet"


@pytest.mark.parametrize("altinn_status,forventet", [
    ("Accepted", "godkjent"), ("New", "venter"), ("Rejected", "avvist"), ("Borte", "ukjent"),
])
def test_systembruker_status_tolkes(klient, monkeypatch, altinn_status, forventet):
    import wenche.auth as auth_mod
    import wenche.systembruker as sb_mod

    monkeypatch.setattr(auth_mod, "login_admin", lambda: "admin-tok")
    monkeypatch.setattr(sb_mod, "hent_forespørsel_status", lambda token, rid: {"status": altinn_status})
    miljo.lagre_request_id("req-1")
    assert klient.post("/api/oppsett/systembruker/status").json()["status"] == forventet


def test_oppdater_systembruker_uten_brukere_gir_409(klient, monkeypatch):
    import wenche.auth as auth_mod
    import wenche.systembruker as sb_mod

    monkeypatch.setenv("ORG_NUMMER", "922020523")
    monkeypatch.setattr(auth_mod, "login_admin", lambda: "admin-tok")
    monkeypatch.setattr(sb_mod, "hent_systembrukere", lambda token, org: [])
    assert klient.post("/api/oppsett/systembruker/oppdater").status_code == 409


def test_oppdater_systembruker_velger_riktig_rapportoer(klient, monkeypatch):
    import wenche.auth as auth_mod
    import wenche.systembruker as sb_mod

    monkeypatch.setenv("ORG_NUMMER", "922020523")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    monkeypatch.setattr(auth_mod, "login_admin", lambda: "admin-tok")
    monkeypatch.setattr(sb_mod, "hent_systembrukere", lambda token, org: [
        {"id": "sb-feil", "reporteeOrgNo": "999999999"},
        {"id": "sb-riktig", "reporteeOrgNo": "310137715"},
    ])
    brukt = {}

    def fake_endring(token, systembruker_id, retter):
        brukt["id"] = systembruker_id
        return {"confirmUrl": "https://altinn.test/confirm/endring", "status": "New"}

    monkeypatch.setattr(sb_mod, "opprett_endringsforespørsel", fake_endring)
    data = klient.post("/api/oppsett/systembruker/oppdater").json()
    assert brukt["id"] == "sb-riktig"
    assert data["confirm_url"] == "https://altinn.test/confirm/endring"


# ---------------------------------------------------------------------------
# Feilmeldingsoversettelsen (enhetsnivå)
# ---------------------------------------------------------------------------

def test_tolk_feilmelding_invalid_scope(monkeypatch):
    monkeypatch.setattr(miljo, "_AKTIV_ENV", "test")
    raa = 'Maskinporten svarte 400:\n{"error": "invalid_scope", "error_description": "x"}'
    melding = _tolk_feilmelding(raa)
    assert "scopes" in melding


def test_tolk_feilmelding_http_uten_json(monkeypatch):
    monkeypatch.setattr(miljo, "_AKTIV_ENV", "test")
    melding = _tolk_feilmelding("Maskinporten svarte 503:\nService Unavailable")
    assert "HTTP 503" in melding


def test_tolk_feilmelding_ukjent_tekst_gir_foerste_linje():
    assert _tolk_feilmelding("Noe annet gikk galt\ndetaljer") == "Noe annet gikk galt"
