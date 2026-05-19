"""
Tester for miljø-spesifikk env-variabelhåndtering i wenche.auth.
"""

import os
from unittest.mock import patch

import pytest

from wenche.auth import _les_miljo_env


@pytest.fixture(autouse=True)
def rensk_env():
    """Sørg for at testene ikke arver MASKINPORTEN-variabler fra omgivelsen."""
    bevart = {}
    for navn in [
        "MASKINPORTEN_CLIENT_ID",
        "MASKINPORTEN_CLIENT_ID_TEST",
        "MASKINPORTEN_CLIENT_ID_PROD",
        "MASKINPORTEN_KID",
        "MASKINPORTEN_KID_TEST",
        "MASKINPORTEN_KID_PROD",
        "MASKINPORTEN_PRIVAT_NOKKEL",
        "MASKINPORTEN_PRIVAT_NOKKEL_TEST",
        "MASKINPORTEN_PRIVAT_NOKKEL_PROD",
    ]:
        if navn in os.environ:
            bevart[navn] = os.environ.pop(navn)
    yield
    for navn, verdi in bevart.items():
        os.environ[navn] = verdi


class TestLesMiljoEnv:

    def test_milj_spesifikk_prefereres_over_generisk(self):
        os.environ["MASKINPORTEN_CLIENT_ID"] = "generisk"
        os.environ["MASKINPORTEN_CLIENT_ID_PROD"] = "prod-uuid"
        os.environ["MASKINPORTEN_CLIENT_ID_TEST"] = "test-uuid"

        assert _les_miljo_env("MASKINPORTEN_CLIENT_ID", "prod") == "prod-uuid"
        assert _les_miljo_env("MASKINPORTEN_CLIENT_ID", "test") == "test-uuid"

    def test_faller_tilbake_til_generisk_navn(self):
        os.environ["MASKINPORTEN_CLIENT_ID"] = "felles-uuid"
        assert _les_miljo_env("MASKINPORTEN_CLIENT_ID", "prod") == "felles-uuid"
        assert _les_miljo_env("MASKINPORTEN_CLIENT_ID", "test") == "felles-uuid"

    def test_kun_milj_spesifikk_satt_funker(self):
        os.environ["MASKINPORTEN_CLIENT_ID_PROD"] = "kun-prod"

        assert _les_miljo_env("MASKINPORTEN_CLIENT_ID", "prod") == "kun-prod"

        # Test-miljø har verken _TEST eller generisk → skal feile
        with pytest.raises(RuntimeError) as exc:
            _les_miljo_env("MASKINPORTEN_CLIENT_ID", "test", "hjelp")
        assert "MASKINPORTEN_CLIENT_ID_TEST" in str(exc.value)
        assert "fallback" in str(exc.value)

    def test_paakrevd_uten_treff_kaster(self):
        with pytest.raises(RuntimeError) as exc:
            _les_miljo_env("MASKINPORTEN_CLIENT_ID", "prod", "fyll inn klient-ID")
        assert "MASKINPORTEN_CLIENT_ID_PROD" in str(exc.value)
        assert "fyll inn klient-ID" in str(exc.value)

    def test_ikke_paakrevd_returnerer_default(self):
        verdi = _les_miljo_env(
            "MASKINPORTEN_PRIVAT_NOKKEL", "prod",
            paakrevd=False, default="maskinporten_privat.pem",
        )
        assert verdi == "maskinporten_privat.pem"

    def test_ikke_paakrevd_returnerer_milj_verdi_naar_satt(self):
        os.environ["MASKINPORTEN_PRIVAT_NOKKEL_PROD"] = "prod_key.pem"
        verdi = _les_miljo_env(
            "MASKINPORTEN_PRIVAT_NOKKEL", "prod",
            paakrevd=False, default="maskinporten_privat.pem",
        )
        assert verdi == "prod_key.pem"

    def test_env_lower_case_funker_ogs(self):
        """Skal akseptere både 'prod'/'test' og 'PROD'/'TEST'."""
        os.environ["MASKINPORTEN_CLIENT_ID_PROD"] = "prod-uuid"
        assert _les_miljo_env("MASKINPORTEN_CLIENT_ID", "prod") == "prod-uuid"
        assert _les_miljo_env("MASKINPORTEN_CLIENT_ID", "PROD") == "prod-uuid"
