"""
Forhåndsfyll-endepunktet /api/selskap (hostet).

Krever invite (som alt annet), nøkler på den signerte øktbindingen (ikke brukerinput), og
returnerer styringsdata fra Enhetsregisteret som SAF-T ikke bærer. Brreg-oppslaget mockes.
"""
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


def test_selskap_krever_invite(klient):
    assert klient.get("/api/selskap").status_code == 401


def test_selskap_forhandsfyller_fra_brreg(klient, monkeypatch):
    from wenche import brreg

    monkeypatch.setattr(
        brreg, "hent_roller",
        lambda org, **k: {"daglig_leder": "Kari Nordmann", "styreleder": "Ola Lie", "alle": []},
    )
    monkeypatch.setattr(brreg, "hent_stiftelsesaar", lambda org, **k: 2018)

    token = lag_invite_token("314273818")
    assert klient.post("/api/auth/invite", json={"token": token}).json()["invited"] is True

    data = klient.get("/api/selskap").json()
    # Org kommer fra den signerte invite-bindingen, ikke fra brukerinput.
    assert data["org_nummer"] == "314273818"
    assert data["daglig_leder"] == "Kari Nordmann"
    assert data["styreleder"] == "Ola Lie"
    assert data["stiftelsesaar"] == 2018
