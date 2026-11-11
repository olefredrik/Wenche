"""
Kroppsgrensen (wenche/web/felles/kropp.py): for store request-kropper avvises med 413 før
appen leser noe, både når Content-Length sier det og når kroppen kommer chunked uten lengde.
Begge appene har middlewaren ytterst; her sjekkes den isolert og gjennom hver app.
"""

import importlib

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from wenche.web.backend.app import lag_app
from wenche.web.felles.kropp import Kroppsgrense, melding


def _app(**kw) -> FastAPI:
    app = FastAPI()

    @app.post("/ekko")
    async def ekko(request: Request) -> dict:
        return {"lengde": len(await request.body())}

    @app.get("/hei")
    def hei() -> dict:
        return {"ok": True}

    app.add_middleware(Kroppsgrense, **kw)
    return app


def test_content_length_over_grensen_gir_413_uten_aa_lese():
    with TestClient(_app(maks_bytes=10)) as k:
        r = k.post("/ekko", content=b"x" * 11)
    assert r.status_code == 413
    assert r.json() == {"detail": melding(10)}


def test_under_grensen_slipper_gjennom_uendret():
    with TestClient(_app(maks_bytes=10)) as k:
        assert k.post("/ekko", content=b"x" * 10).json() == {"lengde": 10}
        assert k.get("/hei").json() == {"ok": True}


def test_chunked_kropp_uten_lengde_avvises_naar_den_passerer_grensen():
    def biter():
        yield b"x" * 6
        yield b"x" * 6

    with TestClient(_app(maks_bytes=10)) as k:
        r = k.post("/ekko", content=biter())
    assert r.status_code == 413


def test_chunked_kropp_under_grensen_spilles_av_for_appen():
    def biter():
        yield b"ab"
        yield b"cd"

    with TestClient(_app(maks_bytes=10)) as k:
        assert k.post("/ekko", content=biter()).json() == {"lengde": 4}


def test_egen_grense_per_sti():
    with TestClient(_app(maks_bytes=10, per_sti={"/ekko": 3})) as k:
        assert k.post("/ekko", content=b"abcd").status_code == 413
        assert k.post("/ekko", content=b"abc").status_code == 200


def test_melding_oppgir_grensen_i_megabyte():
    assert melding(2_000_000) == "Forespørselen er for stor (maks 2 MB)."
    assert melding(1_000_000) == "Forespørselen er for stor (maks 1 MB)."


# --- gjennom appene -----------------------------------------------------------------------


def test_selfhosted_avviser_stor_config_for_parsing():
    with TestClient(
        lag_app(env="test", serve_spa=False),
        base_url="http://127.0.0.1",
        headers={"X-Wenche-Klient": "1"},
    ) as k:
        r = k.post("/api/innsending/aarsregnskap", content=b"{" * 2_000_001)
    assert r.status_code == 413
    assert "for stor" in r.json()["detail"]


@pytest.fixture
def hostet_klient(monkeypatch):
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("HOSTED_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HOSTED_INVITE_SECRET", "test-invite-secret")
    from hosted.api import config

    config.settings.cache_clear()
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as klient:
        yield klient
    config.settings.cache_clear()


def test_hostet_avviser_stor_config_ogsaa_uten_invite(hostet_klient):
    # Poenget med grensen: kroppen parses før vakten kjører, så den må stoppes uavhengig av
    # om økten er invitert.
    r = hostet_klient.post("/api/innsending/aarsregnskap", content=b"{" * 2_000_001)
    assert r.status_code == 413
