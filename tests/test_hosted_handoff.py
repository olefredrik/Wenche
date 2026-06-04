"""
«Fortsett på en annen enhet»-flyten (handoff) for hostet Wenche.

Beviser egenskapene:
- Bare en alt koblet økt (bundet kunde_org) kan lage en overføringslenke.
- En fersk enhet (eget app-objekt, ingen cookie) løser inn lenken og arver bindingen,
  uten ny BankID og uten å treffe Altinn, så cross-device-fortsettelse virker.
- Ugyldige og utløpte tokens avvises.
- Lenken er forankret i sesjonens kunde_org, ikke i brukerinput.

Altinn-kallene (wenche.systembruker) mockes; testen treffer verken nett eller tt02.
"""
import importlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import hosted.api.systembruker as sb
from hosted.api.auth import lag_invite_token


@pytest.fixture
def klient(monkeypatch):
    """TestClient med test-miljø og egne (ikke-default) hemmeligheter; isolert per test."""
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("HOSTED_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HOSTED_INVITE_SECRET", "test-invite-secret")
    monkeypatch.setenv("HOSTED_PUBLIC_URL", "https://app.example.cloud")
    from hosted.api import config

    config.settings.cache_clear()
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as klient:
        yield klient
    config.settings.cache_clear()


def _koble(klient, monkeypatch, org="314273818"):
    """Bind kunde_org på klienten via invite + AlreadyApproved (som en fullført device 1)."""
    creds = SimpleNamespace(client_id="fake-client-id")
    monkeypatch.setattr(sb, "krev_vendor", lambda: (creds, "999999999"))
    monkeypatch.setattr(sb, "admin_token", lambda creds: "fake-token")
    monkeypatch.setattr(sb.wsb, "hent_systembrukere", lambda tok, vendor: [{"reporteeOrgNo": org}])
    klient.post("/api/auth/invite", json={"token": lag_invite_token(org)})
    klient.post("/api/systembruker/request")
    assert klient.get("/api/auth/me").json()["kunde_org"] == org


def test_create_krever_kobling(klient):
    """Uten bundet kunde_org finnes det ingenting å overføre → 409."""
    r = klient.post("/api/auth/handoff/create")
    assert r.status_code == 409


def test_handoff_til_ny_enhet_arver_binding(klient, monkeypatch):
    """
    Device 1 kobler selskapet og lager en overføringslenke; en fersk enhet (eget app-objekt,
    ingen cookie) løser den inn og er straks koblet, uten ny BankID og uten Altinn-kall.
    """
    _koble(klient, monkeypatch, org="314273818")

    r = klient.post("/api/auth/handoff/create").json()
    assert r["lenke"].startswith("https://app.example.cloud/?handoff=")
    assert r["gyldig_sekunder"] == 300
    token = r["lenke"].split("handoff=", 1)[1]

    # Fersk enhet: nytt app-objekt, ingen delt cookie. Ingen vendor-stub her med vilje, så
    # testen viser at innløsningen ikke rører Altinn.
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as enhet2:
        assert enhet2.get("/api/auth/me").json()["invited"] is False
        svar = enhet2.post("/api/auth/handoff/use", json={"token": token}).json()
        assert svar == {"invited": True, "invite_org": "314273818", "kunde_org": "314273818"}
        me = enhet2.get("/api/auth/me").json()
        assert me["invited"] is True and me["kunde_org"] == "314273818"


def test_ugyldig_token_avvises(klient):
    r = klient.post("/api/auth/handoff/use", json={"token": "soppel"}).json()
    assert r["invited"] is False and "Ugyldig" in r["feil"]


def test_utloept_token_avvises(klient, monkeypatch):
    """Et token eldre enn maks-alderen skal nektes (ferskvare)."""
    _koble(klient, monkeypatch, org="314273818")
    token = klient.post("/api/auth/handoff/create").json()["lenke"].split("handoff=", 1)[1]

    import hosted.api.auth as auth_mod

    # Krymp gyldigheten til null: et alt utstedt token er da utløpt ved innløsing.
    monkeypatch.setattr(auth_mod, "_HANDOFF_MAKS_ALDER", -1)
    r = klient.post("/api/auth/handoff/use", json={"token": token}).json()
    assert r["invited"] is False and "utløpt" in r["feil"].lower()


def test_handoff_token_signeres_med_egen_salt(klient, monkeypatch):
    """Et invite-token (annen salt/secret) skal ikke kunne brukes som overføringslenke."""
    _koble(klient, monkeypatch, org="314273818")
    r = klient.post("/api/auth/handoff/use", json={"token": lag_invite_token("314273818")}).json()
    assert r["invited"] is False
