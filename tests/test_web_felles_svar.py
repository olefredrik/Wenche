"""
Svar-modellene (wenche/web/felles/svar.py) er kontrakten mot SPA-ene: de ligger i OpenAPI-
skjemaet, og felt som er None utelates så JSON-en er uendret for kall som ikke bruker dem.
"""

from fastapi.testclient import TestClient

from tests.test_selfhosted_innsending import _gyldig_config
from wenche.web.backend.app import lag_app


def _skjema() -> dict:
    return lag_app(env="test", serve_spa=False).openapi()


def test_delte_svarmodeller_ligger_i_openapi():
    komponenter = _skjema()["components"]["schemas"]
    for navn in ("Fil", "FilerSvar", "SkatteberegningSvar", "ValideringSvar", "InnsendingSvar"):
        assert navn in komponenter, navn


def test_innsending_svarer_med_validering_eller_innsending():
    svar = _skjema()["paths"]["/api/innsending/aarsregnskap"]["post"]["responses"]["200"]
    skjema = svar["content"]["application/json"]["schema"]
    refs = {alt["$ref"].rsplit("/", 1)[-1] for alt in skjema["anyOf"]}
    assert refs == {"ValideringSvar", "InnsendingSvar"}


def test_tomme_felt_utelates_fra_dry_run_svaret(monkeypatch):
    from wenche.web.backend import miljo

    monkeypatch.setattr(miljo, "_AKTIV_ENV", miljo._AKTIV_ENV)
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    with TestClient(
        lag_app(env="test", serve_spa=False),
        base_url="http://127.0.0.1",
        headers={"X-Wenche-Klient": "1"},
    ) as k:
        r = k.post(
            "/api/innsending/aarsregnskap", params={"dry_run": "true"}, json=_gyldig_config()
        )
    assert r.status_code == 200, r.text
    # Ingen antall_aksjonaerer/regnskapsaar for årsregnskapet, og ingen innsendingsfelt.
    assert set(r.json()) == {"dry_run", "ok", "feil", "advarsler"}
