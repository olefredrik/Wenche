"""
Tester for miljø-spesifikk env-variabelhåndtering i wenche.auth.
"""

import os
from unittest.mock import patch

import pytest

from wenche.auth import (
    _altinn_exchange_url,
    _les_miljo_env,
    _maskinporten_aud,
    _maskinporten_token_url,
)


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


class TestRuntimeEnvUrls:
    """URL-ene må reflektere gjeldende WENCHE_ENV, ikke cachet verdi ved import."""

    def test_token_url_bytter_med_env(self):
        with patch.dict(os.environ, {"WENCHE_ENV": "test"}):
            assert _maskinporten_token_url() == "https://test.maskinporten.no/token"
        with patch.dict(os.environ, {"WENCHE_ENV": "prod"}):
            assert _maskinporten_token_url() == "https://maskinporten.no/token"

    def test_audience_bytter_med_env(self):
        with patch.dict(os.environ, {"WENCHE_ENV": "test"}):
            assert _maskinporten_aud() == "https://test.maskinporten.no/"
        with patch.dict(os.environ, {"WENCHE_ENV": "prod"}):
            assert _maskinporten_aud() == "https://maskinporten.no/"

    def test_altinn_exchange_url_bytter_med_env(self):
        with patch.dict(os.environ, {"WENCHE_ENV": "test"}):
            assert "tt02" in _altinn_exchange_url()
        with patch.dict(os.environ, {"WENCHE_ENV": "prod"}):
            assert "tt02" not in _altinn_exchange_url()
            assert "platform.altinn.no" in _altinn_exchange_url()

    def test_default_er_prod_naar_env_ikke_satt(self):
        # Fjern WENCHE_ENV midlertidig
        opprinnelig = os.environ.pop("WENCHE_ENV", None)
        try:
            assert _maskinporten_token_url() == "https://maskinporten.no/token"
            assert _maskinporten_aud() == "https://maskinporten.no/"
        finally:
            if opprinnelig is not None:
                os.environ["WENCHE_ENV"] = opprinnelig


class TestLesCliCredentials:
    """Felles credential-lasting for self-hosted innloggingsfunksjonene."""

    def test_leser_miljospesifikke_credentials_og_nokkel(self, tmp_path, monkeypatch):
        from wenche.auth import _les_cli_credentials

        nokkel = tmp_path / "nokkel.pem"
        nokkel.write_bytes(b"-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----\n")
        monkeypatch.setenv("MASKINPORTEN_CLIENT_ID_TEST", "klient-test")
        monkeypatch.setenv("MASKINPORTEN_KID_TEST", "kid-test")
        monkeypatch.setenv("MASKINPORTEN_PRIVAT_NOKKEL", str(nokkel))
        creds = _les_cli_credentials("test")
        assert creds.client_id == "klient-test"
        assert creds.kid == "kid-test"
        assert creds.private_key_pem == nokkel.read_bytes()

    def test_manglende_client_id_kaster_med_hjelpetekst(self, monkeypatch):
        import pytest

        from wenche.auth import _les_cli_credentials

        monkeypatch.delenv("MASKINPORTEN_CLIENT_ID", raising=False)
        monkeypatch.delenv("MASKINPORTEN_CLIENT_ID_TEST", raising=False)
        with pytest.raises(RuntimeError, match="MASKINPORTEN_CLIENT_ID"):
            _les_cli_credentials("test")


class TestLesSystembrukerOrg:
    def test_test_miljo_bruker_tenor_org(self, monkeypatch):
        from wenche.auth import _les_systembruker_org

        monkeypatch.setenv("ORG_NUMMER", "922020523")
        monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
        assert _les_systembruker_org("test") == "310137715"
        assert _les_systembruker_org("prod") == "922020523"

    def test_test_miljo_uten_tenor_faller_tilbake_til_eget(self, monkeypatch):
        from wenche.auth import _les_systembruker_org

        monkeypatch.setenv("ORG_NUMMER", "922020523")
        monkeypatch.delenv("SKD_TEST_ORG_NUMMER", raising=False)
        assert _les_systembruker_org("test") == "922020523"
