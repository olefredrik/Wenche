"""
Per-org invite-flyt for hostet Wenche (HTTP-nivå, Altinn mocket).

Beviser herdingen fra sikkerhetsgjennomgangen:
- Uten invite er alt stengt.
- Invite-lenken bærer ETT orgnr; org blir autoritativt fra tokenet, ikke brukerinput
  (en angriper kan ikke overstyre org via request-body).
- AlreadyApproved binder kun til org-en i tokenet.
- Ugyldige og gamle (streng-)tokens avvises.
- Serveren fail-closer i prod hvis hemmelighetene ikke er overstyrt.

Altinn-kallene (wenche.systembruker) mockes, så testen treffer ikke nett eller tt02.
"""
import importlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer

import hosted.api.systembruker as sb
from hosted.api.auth import lag_invite_token

_INVITE_SECRET = "test-invite-secret"


@pytest.fixture
def klient(monkeypatch):
    """TestClient med test-miljø og egne (ikke-default) hemmeligheter; isolert per test."""
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


def test_uten_invite_er_stengt(klient):
    assert klient.get("/api/auth/me").json() == {"invited": False}
    assert klient.post("/api/systembruker/request").status_code == 401


def test_ugyldig_og_gammelt_token_avvises(klient):
    # Søppel uten gyldig signatur.
    assert klient.post("/api/auth/invite", json={"token": "soppel"}).json()["invited"] is False
    # Gammelt streng-token (delt-secret-modellen) skal ikke lenger godtas.
    gammelt = URLSafeSerializer(_INVITE_SECRET, salt="invite").dumps("wenche-invite")
    assert klient.post("/api/auth/invite", json={"token": gammelt}).json()["invited"] is False


def test_per_org_invite_already_approved(klient, monkeypatch):
    _stub_vendor(monkeypatch)
    monkeypatch.setattr(
        sb.wsb, "hent_systembrukere", lambda tok, vendor: [{"reporteeOrgNo": "314273818"}]
    )

    token = lag_invite_token("314273818")
    assert klient.post("/api/auth/invite", json={"token": token}).json() == {
        "invited": True,
        "invite_org": "314273818",
    }

    me = klient.get("/api/auth/me").json()
    assert me["invited"] is True
    assert me["invite_org"] == "314273818"
    assert me["kunde_org"] is None

    res = klient.post("/api/systembruker/request").json()
    assert res["status"] == "AlreadyApproved"
    assert res["kunde_org"] == "314273818"
    assert klient.get("/api/auth/me").json()["kunde_org"] == "314273818"


def test_request_bruker_token_org_ikke_body(klient, monkeypatch):
    """Sikkerhetsegenskapen: org kommer fra tokenet, ikke fra request-body."""
    _stub_vendor(monkeypatch)
    monkeypatch.setattr(sb.wsb, "hent_systembrukere", lambda tok, vendor: [])
    monkeypatch.setattr(sb.wsb, "registrer_system", lambda tok, vendor, cid: {})
    fanget = {}

    def fake_opprett(tok, vendor, org):
        fanget["org"] = org
        return {"id": "req-1", "status": "New", "confirmUrl": "https://altinn/confirm"}

    monkeypatch.setattr(sb.wsb, "opprett_forespørsel", fake_opprett)

    klient.post("/api/auth/invite", json={"token": lag_invite_token("314273818")})
    # Angriper forsøker å overstyre org via body:
    res = klient.post("/api/systembruker/request", json={"org": "999999999"})
    assert res.status_code == 200
    assert res.json()["confirm_url"] == "https://altinn/confirm"
    assert fanget["org"] == "314273818"  # token-org, ikke body-org


def test_prod_uten_secrets_nekter_oppstart(monkeypatch):
    monkeypatch.setenv("WENCHE_ENV", "prod")
    monkeypatch.delenv("HOSTED_SESSION_SECRET", raising=False)
    monkeypatch.delenv("HOSTED_INVITE_SECRET", raising=False)
    from hosted.api.config import Settings

    with pytest.raises(RuntimeError, match="prod uten egne hemmeligheter"):
        Settings()
