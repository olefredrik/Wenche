"""
Systembruker-statusflyten for hostet Wenche (HTTP-nivå, Altinn mocket).

test_hosted_invite.py dekker request-endepunktet (AlreadyApproved, org fra token,
selvbetjeningssperre); her dekkes resten av onboardingen: ny kunde får confirm_url,
status 'New' binder ingenting, status 'Accepted' binder kunde-org til sesjonen, og
status uten aktiv forespørsel er en lesbar 400.

Altinn-kallene (wenche.systembruker) mockes, så testene treffer ikke nett eller tt02.
"""
import importlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import hosted.api.systembruker as sb
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


def _stub_vendor(monkeypatch):
    creds = SimpleNamespace(client_id="fake-client-id")
    monkeypatch.setattr(sb, "krev_vendor", lambda: (creds, "999999999"))
    monkeypatch.setattr(sb, "admin_token", lambda creds: "fake-token")


def _inviter(klient, org="314273818"):
    r = klient.post("/api/auth/invite", json={"token": lag_invite_token(org)})
    assert r.json()["invited"] is True


def test_status_uten_forespoersel_gir_400(klient, monkeypatch):
    _inviter(klient)
    _stub_vendor(monkeypatch)
    r = klient.post("/api/systembruker/status")
    assert r.status_code == 400


def test_ny_kunde_faar_confirm_url_og_bindes_ved_accepted(klient, monkeypatch):
    """Full onboarding: request → confirm_url → New (ubundet) → Accepted (kunde_org bindes)."""
    org = "314273818"
    _inviter(klient, org)
    _stub_vendor(monkeypatch)
    monkeypatch.setattr(sb.wsb, "hent_systembrukere", lambda token, vendor: [])
    monkeypatch.setattr(sb.wsb, "registrer_system", lambda token, vendor, cid: {})
    monkeypatch.setattr(sb.wsb, "opprett_forespørsel", lambda token, vendor, party: {
        "id": "req-77", "status": "New", "confirmUrl": "https://altinn.test/confirm/77",
    })

    r = klient.post("/api/systembruker/request")
    assert r.status_code == 200, r.text
    assert r.json()["confirm_url"] == "https://altinn.test/confirm/77"

    # Venter på BankID-godkjenning: ingen binding ennå.
    monkeypatch.setattr(sb.wsb, "hent_forespørsel_status", lambda token, rid: {"status": "New"})
    data = klient.post("/api/systembruker/status").json()
    assert data["godkjent"] is False
    assert data["kunde_org"] is None

    # Godkjent i Altinn: kunde-org bindes til sesjonen fra pending_org.
    monkeypatch.setattr(sb.wsb, "hent_forespørsel_status", lambda token, rid: {"status": "Accepted"})
    data = klient.post("/api/systembruker/status").json()
    assert data["godkjent"] is True
    assert data["kunde_org"] == org


def test_avvist_forespoersel_binder_ikke(klient, monkeypatch):
    _inviter(klient)
    _stub_vendor(monkeypatch)
    monkeypatch.setattr(sb.wsb, "hent_systembrukere", lambda token, vendor: [])
    monkeypatch.setattr(sb.wsb, "registrer_system", lambda token, vendor, cid: {})
    monkeypatch.setattr(sb.wsb, "opprett_forespørsel", lambda token, vendor, party: {
        "id": "req-78", "status": "New", "confirmUrl": "https://altinn.test/confirm/78",
    })
    klient.post("/api/systembruker/request")
    monkeypatch.setattr(sb.wsb, "hent_forespørsel_status", lambda token, rid: {"status": "Rejected"})
    data = klient.post("/api/systembruker/status").json()
    assert data["godkjent"] is False
    assert data["kunde_org"] is None
