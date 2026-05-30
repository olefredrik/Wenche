"""
Tester for miljø- og utløpsvalidering av Altinn-token-cachen i wenche.auth.

Regresjonsdekning for issue #103: et cachet token (utløpt eller fra feil
miljø) ble tidligere returnert ukritisk av get_altinn_token() og ga 401
ved innsending i produksjon.
"""

import base64
import json
import time

import pytest

from wenche import auth

PROD_ISS = "https://platform.altinn.no/authentication/api/v1/openid/"
TEST_ISS = "https://platform.tt02.altinn.no/authentication/api/v1/openid/"


def _fake_token(exp: int, iss: str) -> str:
    """Bygger et JWT-lignende token (usignert) med gitt exp og iss."""
    def seg(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")

    return f"{seg({'alg': 'RS256'})}.{seg({'exp': exp, 'iss': iss})}.signatur"


class _LoginSpy:
    """Erstatter auth.login og teller kall; returnerer et ferskt token."""

    def __init__(self):
        self.kall = 0

    def __call__(self, *args, **kwargs):
        self.kall += 1
        return {"altinn_token": "FERSKT", "maskinporten_token": "m"}


class TestEnvFraIss:
    def test_tt02_gir_test(self):
        assert auth._env_fra_iss(TEST_ISS) == "test"

    def test_prod_gir_prod(self):
        assert auth._env_fra_iss(PROD_ISS) == "prod"

    def test_tom_gir_prod(self):
        assert auth._env_fra_iss("") == "prod"


class TestTokenFile:
    def test_prod_bruker_token_json(self):
        assert auth._token_file("prod").name == "token.json"

    def test_test_bruker_token_dev_json(self):
        assert auth._token_file("test").name == "token.dev.json"


class TestAltinnTokenGyldig:
    def test_ferskt_og_riktig_miljo_er_gyldig(self):
        tok = _fake_token(int(time.time()) + 3600, PROD_ISS)
        assert auth._altinn_token_gyldig(tok, "prod") is True

    def test_utlopt_er_ugyldig(self):
        tok = _fake_token(int(time.time()) - 10, PROD_ISS)
        assert auth._altinn_token_gyldig(tok, "prod") is False

    def test_naer_utlop_innenfor_margin_er_ugyldig(self):
        tok = _fake_token(int(time.time()) + 30, PROD_ISS)
        assert auth._altinn_token_gyldig(tok, "prod", margin_sek=60) is False

    def test_feil_miljo_er_ugyldig(self):
        # tt02-token, men vi spør om prod (kjernen i #103)
        tok = _fake_token(int(time.time()) + 3600, TEST_ISS)
        assert auth._altinn_token_gyldig(tok, "prod") is False

    def test_uleselig_token_er_ugyldig(self):
        assert auth._altinn_token_gyldig("ikke-et-jwt", "prod") is False
        assert auth._altinn_token_gyldig("", "prod") is False


class TestGetAltinnToken:
    @pytest.fixture
    def spy(self, monkeypatch, tmp_path):
        """Isolerer cache til tmp og erstatter login med en spion."""
        spy = _LoginSpy()
        monkeypatch.setattr(auth, "login", spy)
        monkeypatch.setattr(
            auth, "_token_file", lambda env=None: tmp_path / "token.json"
        )
        monkeypatch.setenv("WENCHE_ENV", "prod")
        return spy

    def _skriv_cache(self, tmp_path, tok):
        (tmp_path / "token.json").write_text(
            json.dumps({"altinn_token": tok, "maskinporten_token": "m"})
        )

    def test_gjenbruker_gyldig_cache_uten_login(self, spy, tmp_path):
        self._skriv_cache(tmp_path, _fake_token(int(time.time()) + 3600, PROD_ISS))
        assert auth.get_altinn_token() != "FERSKT"
        assert spy.kall == 0

    def test_re_login_ved_utlopt_token(self, spy, tmp_path):
        self._skriv_cache(tmp_path, _fake_token(int(time.time()) - 10, PROD_ISS))
        assert auth.get_altinn_token() == "FERSKT"
        assert spy.kall == 1

    def test_re_login_ved_feil_miljo(self, spy, tmp_path):
        # Regresjon #103: tt02-token i prod-cachen skal forkastes, ikke 401.
        self._skriv_cache(tmp_path, _fake_token(int(time.time()) + 3600, TEST_ISS))
        assert auth.get_altinn_token() == "FERSKT"
        assert spy.kall == 1

    def test_re_login_naar_cache_mangler(self, spy):
        assert auth.get_altinn_token() == "FERSKT"
        assert spy.kall == 1

    def test_re_login_ved_korrupt_cache(self, spy, tmp_path):
        (tmp_path / "token.json").write_text("{ ikke gyldig json")
        assert auth.get_altinn_token() == "FERSKT"
        assert spy.kall == 1
