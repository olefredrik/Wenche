"""
Miljøtabellen (wenche/miljoer.py): én kilde for base-URL-er og app-ID-er, WENCHE_ENV valideres,
og .env-filene lastes av inngangene uten å overstyre det som alt er satt i prosessen.
"""

import os

import pytest

from wenche import miljoer, systembruker
from wenche.altinn_client import APPS, AltinnClient
from wenche.feil import KonfigFeil
from wenche.miljoer import last_env_filer
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import SkdSkattemeldingClient


def test_gjeldende_navn_er_prod_uten_variabel(monkeypatch):
    monkeypatch.delenv("WENCHE_ENV", raising=False)
    assert miljoer.gjeldende_navn() == "prod"
    assert miljoer.miljo() is miljoer.PROD
    monkeypatch.setenv("WENCHE_ENV", "test")
    assert miljoer.miljo() is miljoer.TEST


def test_ukjent_miljo_er_konfigfeil_ikke_stille_prod(monkeypatch):
    monkeypatch.setenv("WENCHE_ENV", "staging")
    with pytest.raises(KonfigFeil, match="Ugyldig WENCHE_ENV"):
        miljoer.gjeldende_navn()
    with pytest.raises(KonfigFeil):
        miljoer.miljo("staging")
    with pytest.raises(ValueError):  # eldre kallsteder fanget ValueError fra klientene
        AltinnClient("token", env="staging")


def test_url_ene_per_miljo():
    assert miljoer.TEST.maskinporten_tokenendepunkt == "https://test.maskinporten.no/token"
    assert miljoer.PROD.maskinporten_aud == "https://maskinporten.no/"
    assert miljoer.TEST.altinn_veksling_url.startswith("https://platform.tt02.altinn.no/")
    assert miljoer.PROD.skd_aksjonaer_api == "https://api.skatteetaten.no/api/aksjonaerregister/v1"
    assert (
        miljoer.TEST.altinn_app_url("brg", "aarsregnskap-vanlig-202406")
        == "https://brg.apps.tt02.altinn.no/brg/aarsregnskap-vanlig-202406"
    )
    assert miljoer.TEST.er_test and not miljoer.PROD.er_test


def test_klientene_og_systembruker_bruker_samme_tabell(monkeypatch):
    with AltinnClient("t", env="test") as altinn:
        assert altinn.miljo is miljoer.TEST
        assert altinn._app_base("skattemelding").endswith("/skd/formueinntekt-skattemelding-v2")
    with SkdAksjonaerClient("t", env="prod") as skd:
        assert skd._base == miljoer.PROD.skd_aksjonaer_api
    with SkdSkattemeldingClient("t", env="test") as sm:
        assert sm._base == miljoer.TEST.skd_api
    monkeypatch.setenv("WENCHE_ENV", "test")
    assert systembruker._base() == miljoer.TEST.altinn_platform
    # Rettighetene utledes av app-tabellen, så app-ID-ene finnes ett sted.
    verdier = [r["resource"][0]["value"] for r in systembruker._RIGHTS]
    assert "app_brg_aarsregnskap-vanlig-202406" in verdier
    assert "app_skd_formueinntekt-skattemelding-v2" in verdier
    assert APPS["aarsregnskap"] == {"org": "brg", "app": "aarsregnskap-vanlig-202406"}


def test_last_env_filer_leser_hjem_foerst_og_overstyrer_ikke(tmp_path, monkeypatch):
    hjem = tmp_path / "hjem" / ".wenche"
    hjem.mkdir(parents=True)
    (hjem / ".env").write_text("WENCHE_TEST_A=hjem\nWENCHE_TEST_B=hjem\n", encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / ".env").write_text("WENCHE_TEST_B=cwd\nWENCHE_TEST_C=cwd\n", encoding="utf-8")
    for navn in ("WENCHE_TEST_A", "WENCHE_TEST_B", "WENCHE_TEST_C"):
        monkeypatch.delenv(navn, raising=False)
    monkeypatch.setenv("WENCHE_TEST_A", "prosess")  # satt før lasting: skal vinne
    monkeypatch.setattr(miljoer, "BRUKER_ENV_FIL", hjem / ".env")
    monkeypatch.chdir(cwd)

    last_env_filer()  # den ekte, ikke no-op-en fra conftest

    assert os.environ["WENCHE_TEST_A"] == "prosess"
    assert os.environ["WENCHE_TEST_B"] == "hjem"  # ~/.wenche/.env lastes først og vinner
    assert os.environ["WENCHE_TEST_C"] == "cwd"
    for navn in ("WENCHE_TEST_A", "WENCHE_TEST_B", "WENCHE_TEST_C"):
        monkeypatch.delenv(navn, raising=False)


def test_import_av_auth_laster_ikke_env(tmp_path, monkeypatch):
    """Biblioteket skal ikke mutere miljøet ved import; det er inngangenes jobb."""
    import importlib

    import wenche.auth as auth_mod

    monkeypatch.delenv("WENCHE_TEST_IMPORT", raising=False)
    monkeypatch.setattr(miljoer, "BRUKER_ENV_FIL", tmp_path / ".env")
    (tmp_path / ".env").write_text("WENCHE_TEST_IMPORT=1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    importlib.reload(auth_mod)
    assert "WENCHE_TEST_IMPORT" not in os.environ
