"""
Vakten mot fremmede nettsteder i den lokale serveren (wenche/web/backend/vakt.py).

Serveren lytter på 127.0.0.1 uten innlogging. Testene sender kall slik en fremmed side ville
gjort det fra nettleseren (fremmed Origin, cross-site-flagg, fremmed Host) og slik SPA-en gjør
det (loopback-origin pluss klientheader), og sjekker at bare det siste slipper gjennom.
"""
import pytest
from fastapi.testclient import TestClient

from wenche.web.backend.app import lag_app
from wenche.web.backend.vakt import KLIENT_HEADER, avvisningsgrunn, er_lokal_origin

_EGEN = {KLIENT_HEADER: "1"}


@pytest.fixture
def klient():
    with TestClient(lag_app(env="test", serve_spa=False), base_url="http://127.0.0.1") as k:
        yield k


def test_lokal_origin_godtas_uansett_port_og_skjema():
    assert er_lokal_origin("http://127.0.0.1:8080")
    assert er_lokal_origin("http://localhost:5174")
    assert er_lokal_origin("http://[::1]:8080")
    assert not er_lokal_origin("https://evil.example")
    assert not er_lokal_origin("null")
    assert not er_lokal_origin("http://127.0.0.1.evil.example")


def test_get_uten_headere_slipper_gjennom(klient):
    assert klient.get("/api/health").status_code == 200


def test_post_med_fremmed_origin_avvises(klient):
    r = klient.post("/api/frister/sjekk", headers={"Origin": "https://evil.example", **_EGEN})
    assert r.status_code == 403
    assert "annet nettsted" in r.json()["detail"]


def test_post_med_origin_null_avvises(klient):
    """Skjema fra en sandkasse-iframe eller file:// sender Origin: null."""
    r = klient.post("/api/frister/sjekk", headers={"Origin": "null", **_EGEN})
    assert r.status_code == 403


def test_cross_site_flagg_avvises_selv_uten_origin(klient):
    r = klient.get("/api/health", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_post_uten_klientheader_avvises(klient):
    r = klient.post("/api/frister/sjekk", headers={"Origin": "http://localhost:5174"})
    assert r.status_code == 403
    assert KLIENT_HEADER in r.json()["detail"]


def test_post_fra_spa_slipper_gjennom(klient):
    r = klient.post(
        "/api/frister/sjekk",
        headers={"Origin": "http://localhost:5174", "Sec-Fetch-Site": "same-origin", **_EGEN},
    )
    assert r.status_code == 200


def test_vakten_gjelder_bare_api(klient):
    """Statiske filer og rot-ruten er ikke dekket; der finnes ingen sideeffekter."""
    assert klient.post("/ikke-api", headers={"Origin": "https://evil.example"}).status_code != 403


def test_fremmed_host_avvises():
    """DNS-rebinding: angriperens domene peker på 127.0.0.1, så Host er ikke loopback."""
    with TestClient(lag_app(env="test", serve_spa=False), base_url="http://evil.example") as k:
        assert k.get("/api/health").status_code == 400


def test_avvisningsgrunn_er_ren_funksjon():
    assert avvisningsgrunn("GET", {}) is None
    assert avvisningsgrunn("POST", {}) is not None
    assert avvisningsgrunn("POST", {KLIENT_HEADER: "1"}) is None
    assert avvisningsgrunn("GET", {"origin": "https://evil.example"}) is not None
