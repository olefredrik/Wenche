"""
Enhetstester for miljø-/konfig-tilstanden (wenche/web/backend/miljo.py) og
versjonssjekken (oppdatering.py) i self-hosted Wenche.

Alle filoperasjoner pekes om til tmp_path slik at testene aldri rører den
ekte ~/.wenche-katalogen.
"""
import os
import stat

import pytest

from wenche.web.backend import miljo, oppdatering


@pytest.fixture
def isolert_miljo(tmp_path, monkeypatch):
    """Pek modul-tilstanden mot tmp og registrer originalverdier for restore."""
    wenche_dir = tmp_path / ".wenche"
    monkeypatch.setattr(miljo, "_WENCHE_DIR", wenche_dir)
    monkeypatch.setattr(miljo, "_BRUKER_ENV_FIL", wenche_dir / ".env")
    monkeypatch.setattr(miljo, "_PRIVAT_NOKKEL_FIL", wenche_dir / "maskinporten_privat.pem")
    monkeypatch.setattr(miljo, "_AKTIV_ENV", miljo._AKTIV_ENV)
    monkeypatch.setenv("WENCHE_ENV", os.getenv("WENCHE_ENV", "prod"))
    return wenche_dir


# ---------------------------------------------------------------------------
# Miljølåsing og config-fil
# ---------------------------------------------------------------------------

def test_sett_env_avviser_ukjent_miljo(isolert_miljo):
    with pytest.raises(ValueError):
        miljo.sett_env("staging")


def test_sett_env_speiler_til_wenche_env(isolert_miljo):
    miljo.sett_env("test")
    assert miljo.aktiv_env() == "test"
    assert miljo.er_test() is True
    assert os.environ["WENCHE_ENV"] == "test"


def test_config_fil_skiller_test_og_prod(isolert_miljo):
    miljo.sett_env("prod")
    assert miljo.config_fil().name == "config.yaml"
    miljo.sett_env("test")
    assert miljo.config_fil().name == "config.dev.yaml"


# ---------------------------------------------------------------------------
# Credential-oppslag per miljø
# ---------------------------------------------------------------------------

def test_miljospesifikk_variabel_vinner(isolert_miljo, monkeypatch):
    monkeypatch.setenv("MIN_VAR", "generisk")
    monkeypatch.setenv("MIN_VAR_TEST", "testverdi")
    assert miljo.les_konfig_for_milj("MIN_VAR", env="test") == "testverdi"
    assert miljo.les_konfig_for_milj("MIN_VAR", env="prod") == "generisk"


def test_eksplisitt_tom_miljovariabel_er_autoritativ(isolert_miljo, monkeypatch):
    # En tom miljøspesifikk variabel skal IKKE falle tilbake til den generiske:
    # brukeren har eksplisitt sagt «ingen verdi i dette miljøet».
    monkeypatch.setenv("MIN_VAR", "generisk")
    monkeypatch.setenv("MIN_VAR_TEST", "")
    assert miljo.les_konfig_for_milj("MIN_VAR", env="test", default="d") == "d"


# ---------------------------------------------------------------------------
# med_test_org: tvinger Tenor-orgnr i testmiljø
# ---------------------------------------------------------------------------

def test_med_test_org_bytter_orgnr_i_test(isolert_miljo, monkeypatch):
    miljo.sett_env("test")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    cfg = {"selskap": {"org_nummer": "922020523", "navn": "Ekte AS"}}
    resultat = miljo.med_test_org(cfg)
    assert resultat["selskap"]["org_nummer"] == "310137715"
    assert resultat["selskap"]["navn"] == "Ekte AS"
    assert cfg["selskap"]["org_nummer"] == "922020523"  # original muteres ikke


def test_med_test_org_noop_i_prod(isolert_miljo, monkeypatch):
    miljo.sett_env("prod")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    cfg = {"selskap": {"org_nummer": "922020523"}}
    assert miljo.med_test_org(cfg) is cfg


def test_med_test_org_noop_uten_testorgnr(isolert_miljo, monkeypatch):
    miljo.sett_env("test")
    monkeypatch.delenv("SKD_TEST_ORG_NUMMER", raising=False)
    cfg = {"selskap": {"org_nummer": "922020523"}}
    assert miljo.med_test_org(cfg) is cfg


# ---------------------------------------------------------------------------
# Systembruker-tilstand på disk (per miljø)
# ---------------------------------------------------------------------------

def test_request_id_rundtur_per_miljo(isolert_miljo):
    miljo.lagre_request_id("req-test", env="test")
    miljo.lagre_request_id("req-prod", env="prod")
    assert miljo.les_request_id(env="test") == "req-test"
    assert miljo.les_request_id(env="prod") == "req-prod"


def test_les_request_id_tom_uten_fil(isolert_miljo):
    assert miljo.les_request_id(env="test") == ""


def test_confirm_url_tom_streng_lagres_ikke(isolert_miljo):
    miljo.lagre_confirm_url("", env="test")
    assert miljo.les_confirm_url(env="test") == ""
    miljo.lagre_confirm_url("https://example.test/confirm", env="test")
    assert miljo.les_confirm_url(env="test") == "https://example.test/confirm"


# ---------------------------------------------------------------------------
# ~/.wenche/.env-håndtering
# ---------------------------------------------------------------------------

def test_sikre_bruker_env_fil_oppretter_med_0600(isolert_miljo, tmp_path, monkeypatch):
    tom_cwd = tmp_path / "tom-katalog"
    tom_cwd.mkdir()
    monkeypatch.chdir(tom_cwd)  # repo-roten har en .env som ellers ville migrert
    migrert = miljo.sikre_bruker_env_fil()
    assert migrert is False
    fil = miljo._BRUKER_ENV_FIL
    assert fil.exists()
    assert stat.S_IMODE(fil.stat().st_mode) == 0o600


def test_sikre_bruker_env_fil_migrerer_cwd_env(isolert_miljo, tmp_path, monkeypatch):
    cwd = tmp_path / "arbeidskatalog"
    cwd.mkdir()
    (cwd / ".env").write_text("ORG_NUMMER=922020523\n", encoding="utf-8")
    monkeypatch.chdir(cwd)
    migrert = miljo.sikre_bruker_env_fil()
    assert migrert is True
    assert "ORG_NUMMER=922020523" in miljo._BRUKER_ENV_FIL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Versjonssjekk (oppdatering.py)
# ---------------------------------------------------------------------------

def test_parse_versjon():
    assert oppdatering.parse_versjon("0.25.0") == (0, 25, 0)
    assert oppdatering.parse_versjon("1.2.3rc1") == (1, 2, 3)


def test_er_nyere_versjon():
    assert oppdatering.er_nyere_versjon("0.26.0", "0.25.9") is True
    assert oppdatering.er_nyere_versjon("0.25.0", "0.25.0") is False
    assert oppdatering.er_nyere_versjon("0.9.0", "0.25.0") is False


def test_fake_ny_versjon_overstyrer(monkeypatch):
    monkeypatch.setenv("WENCHE_FAKE_NY_VERSJON", "99.0.0")
    assert oppdatering.hent_nyeste_pypi_versjon() == "99.0.0"


def test_pypi_nettverksfeil_gir_none(monkeypatch):
    import httpx

    monkeypatch.delenv("WENCHE_FAKE_NY_VERSJON", raising=False)

    def kast(*a, **kw):
        raise httpx.ConnectError("nede")

    monkeypatch.setattr(oppdatering.httpx, "get", kast)
    assert oppdatering.hent_nyeste_pypi_versjon() is None
