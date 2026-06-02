"""
Demo-flagget for hostet Wenche.

HOSTED_DEMO_MODE styrer kun et informasjons-flagg i /api/auth/me (banner i SPA-en), ikke
funksjonalitet. Settes på demo-appen (mot tt02), aldri i prod.
"""
import importlib

import pytest
from fastapi.testclient import TestClient

from hosted.api.auth import lag_invite_token


def _klient(monkeypatch, demo: bool):
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("HOSTED_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HOSTED_INVITE_SECRET", "test-invite-secret")
    if demo:
        monkeypatch.setenv("HOSTED_DEMO_MODE", "1")
    else:
        monkeypatch.delenv("HOSTED_DEMO_MODE", raising=False)
    from hosted.api import config

    config.settings.cache_clear()
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    klient = TestClient(main_mod.app)
    klient.post("/api/auth/invite", json={"token": lag_invite_token("314273818")})
    return klient, config


@pytest.mark.parametrize("demo", [True, False])
def test_demo_flagg_i_me(monkeypatch, demo):
    klient, config = _klient(monkeypatch, demo)
    try:
        assert klient.get("/api/auth/me").json()["demo"] is demo
    finally:
        config.settings.cache_clear()
