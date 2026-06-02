"""
SAF-T-import-endepunktet for hostet Wenche (HTTP-nivå).

- Uten invite er importen stengt (401).
- Med invite parses en opplastet SAF-T og config-dict returneres for forhåndsfylling.
- foregaaende=true returnerer kun fjorårets sammenligningstall.
- Ugyldig XML gir 422, for stor fil gir 413.
"""
import importlib

import pytest
from fastapi.testclient import TestClient

from hosted.api.auth import lag_invite_token
from tests.test_saft import KONTOER, _saft_xml

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


def _inviter(klient, org="314273818"):
    klient.post("/api/auth/invite", json={"token": lag_invite_token(org)})


def test_saft_stengt_uten_invite(klient):
    r = klient.post("/api/saft/import", content=_saft_xml(KONTOER))
    assert r.status_code == 401


def test_saft_import_med_invite(klient):
    _inviter(klient)
    r = klient.post("/api/saft/import", content=_saft_xml(KONTOER))
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg["selskap"]["navn"] == "Testholding AS"
    assert cfg["resultatregnskap"]["driftsinntekter"]["salgsinntekter"] == 100000
    assert cfg["balanse"]["egenkapital_og_gjeld"]["langsiktig_gjeld"]["laan_fra_aksjonaer"] == 200000


def test_saft_foregaaende_returnerer_kun_sammenligningstall(klient):
    _inviter(klient)
    r = klient.post("/api/saft/import?foregaaende=true", content=_saft_xml(KONTOER))
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data.keys()) == {"regnskapsaar", "foregaaende_aar"}
    assert "resultatregnskap" in data["foregaaende_aar"]
    assert "balanse" in data["foregaaende_aar"]


def test_saft_ugyldig_xml_gir_422(klient):
    _inviter(klient)
    r = klient.post("/api/saft/import", content=b"ikke xml")
    assert r.status_code == 422


def test_saft_for_stor_fil_gir_413(klient):
    _inviter(klient)
    r = klient.post("/api/saft/import", content=b"x" * 1_000_001)
    assert r.status_code == 413
