"""
SAF-T-import-endepunktet for self-hosted Wenche (HTTP-nivå).

Ingen invite/auth lokalt: ruten parser opplastet SAF-T og returnerer config for forhåndsfylling.
Verifiserer foregaaende-grenen og størrelsesgrensen; selve mappingen dekkes av test_saft.py.
"""
import pytest
from fastapi.testclient import TestClient

from tests.test_saft import KONTOER, _saft_xml
from wenche.web.backend.app import lag_app


@pytest.fixture
def klient():
    with TestClient(lag_app(env="test", serve_spa=False)) as klient:
        yield klient


def test_import_returnerer_full_config(klient):
    r = klient.post("/api/saft/import", content=_saft_xml(KONTOER))
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg["selskap"]["org_nummer"] == "310137715"
    assert cfg["skattemelding"]["underskudd_til_fremfoering"] == 40000


def test_foregaaende_kun_sammenligningstall(klient):
    r = klient.post("/api/saft/import?foregaaende=true", content=_saft_xml(KONTOER))
    assert r.status_code == 200, r.text
    assert set(r.json().keys()) == {"regnskapsaar", "foregaaende_aar"}


def test_tom_body_gir_400(klient):
    r = klient.post("/api/saft/import", content=b"")
    assert r.status_code == 400


def test_for_stor_fil_gir_413(klient):
    r = klient.post("/api/saft/import", content=b"x" * 1_000_001)
    assert r.status_code == 413
