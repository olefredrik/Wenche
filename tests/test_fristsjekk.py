"""
Tester for fristsjekk-modulen (wenche/fristsjekk.py).
Verifiserer statussjekk mot Skatteetatens og Brønnøysundregistrenes API-er.

Alle HTTP-kall er mocket — testene gjør ingen ekte nettverkskall.
"""

import os
from datetime import date
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree as ET

import httpx
import pytest

from wenche.fristsjekk import (
    FristStatus,
    neste_frist,
    regnskapsaar_for_frist,
    sjekk_skattemelding,
    sjekk_aarsregnskap,
    sjekk_aksjonaerregister,
)


def _freeze_today(d: date):
    """`date`-subklasse med today() frosset til gitt dato."""
    klass = type("FrozenDate", (date,), {})
    klass.today = classmethod(lambda cls: d)
    return klass


# ---------------------------------------------------------------------------
# Hjelpefunksjoner for test-XML
# ---------------------------------------------------------------------------

_NS = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:forespoersel:response:v2"


def _wrapper_xml(doc_type: str) -> str:
    """Bygg en minimal wrapper-XML med gitt <type>-verdi."""
    return (
        f'<skattemeldingOgNaeringsspesifikasjonforespoerselResponse xmlns="{_NS}">'
        f"<dokumenter><skattemeldingdokument>"
        f"<id>SKI:756:1</id><encoding>utf-8</encoding>"
        f"<content>dW1teQ==</content>"
        f"<type>{doc_type}</type>"
        f"</skattemeldingdokument></dokumenter>"
        f"</skattemeldingOgNaeringsspesifikasjonforespoerselResponse>"
    )


def _mock_response(status_code: int = 200, text: str = "", json_data=None) -> MagicMock:
    """Lag et mock httpx.Response-objekt."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.text = text
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


# ---------------------------------------------------------------------------
# Skattemelding
# ---------------------------------------------------------------------------

@pytest.fixture
def prod_env():
    """Kjør test med WENCHE_ENV=prod slik at sjekk_skattemelding går full flyt."""
    with patch.dict(os.environ, {"WENCHE_ENV": "prod"}):
        yield


class TestSjekkSkattemelding:

    @patch("wenche.fristsjekk.httpx.get")
    @patch("wenche.fristsjekk.get_skd_skattemelding_maskinporten_token", create=True)
    def test_fastsatt_gir_innfridd(self, mock_token, mock_get, prod_env):
        """Respons med skattemeldingUpersonligFastsatt → innfridd=True."""
        # Importer igjen etter patching
        import wenche.fristsjekk as mod
        mock_token_fn = MagicMock(return_value="test-token")
        with patch.object(mod, "sjekk_skattemelding", wraps=mod.sjekk_skattemelding):
            with patch("wenche.auth.get_skd_skattemelding_maskinporten_token", mock_token_fn):
                mock_get.return_value = _mock_response(
                    text=_wrapper_xml("skattemeldingUpersonligFastsatt"),
                )
                result = mod.sjekk_skattemelding("931808869", 2025)

        assert result.innfridd is True
        assert "sendt inn og godkjent" in result.brukertekst
        assert "931808869" in result.lenke

    @patch("wenche.fristsjekk.httpx.get")
    def test_utkast_gir_ikke_innfridd(self, mock_get, prod_env):
        """Respons med skattemeldingUpersonligUtkast → innfridd=False."""
        with patch("wenche.auth.get_skd_skattemelding_maskinporten_token", return_value="t"):
            mock_get.return_value = _mock_response(
                text=_wrapper_xml("skattemeldingUpersonligUtkast"),
            )
            result = sjekk_skattemelding("931808869", 2025)

        assert result.innfridd is False
        assert "ikke innsendt" in result.brukertekst

    @patch("wenche.fristsjekk.httpx.get")
    def test_http_feil_gir_beskrivelse(self, mock_get, prod_env):
        """HTTP 500 fra Skatteetaten → innfridd=False med feilmelding."""
        with patch("wenche.auth.get_skd_skattemelding_maskinporten_token", return_value="t"):
            mock_get.return_value = _mock_response(status_code=500)
            result = sjekk_skattemelding("931808869", 2025)

        assert result.innfridd is False
        assert "HTTP 500" in result.beskrivelse

    @patch("wenche.fristsjekk.httpx.get")
    def test_ugyldig_xml_gir_beskrivelse(self, mock_get, prod_env):
        """Ugyldig XML fra Skatteetaten → innfridd=False med feilmelding."""
        with patch("wenche.auth.get_skd_skattemelding_maskinporten_token", return_value="t"):
            mock_get.return_value = _mock_response(text="dette er ikke xml")
            result = sjekk_skattemelding("931808869", 2025)

        assert result.innfridd is False
        assert "Ugyldig svar" in result.beskrivelse

    def test_manglende_maskinporten_gir_beskrivelse(self, prod_env):
        """RuntimeError fra auth → innfridd=False med 'ikke konfigurert'."""
        with patch(
            "wenche.auth.get_skd_skattemelding_maskinporten_token",
            side_effect=RuntimeError("MASKINPORTEN_CLIENT_ID mangler"),
        ):
            result = sjekk_skattemelding("931808869", 2025)

        assert result.innfridd is False
        assert "Maskinporten" in result.beskrivelse

    @patch("wenche.fristsjekk.httpx.get")
    def test_nettverksfeil_gir_beskrivelse(self, mock_get, prod_env):
        """Timeout/nettverksfeil → innfridd=False med feilmelding."""
        with patch("wenche.auth.get_skd_skattemelding_maskinporten_token", return_value="t"):
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            result = sjekk_skattemelding("931808869", 2025)

        assert result.innfridd is False
        assert "kontakte Skatteetaten" in result.beskrivelse

    def test_testmiljo_hopper_over_sjekken(self):
        """I testmiljø skal vi vise informativ melding, ikke ringe API-et."""
        with patch.dict(os.environ, {"WENCHE_ENV": "test"}):
            result = sjekk_skattemelding("922020523", 2025)

        assert result.innfridd is False
        assert "test" in result.beskrivelse.lower() or "test" in result.brukertekst.lower()
        assert "prod" in result.brukertekst.lower()


# ---------------------------------------------------------------------------
# Årsregnskap
# ---------------------------------------------------------------------------

class TestSjekkAarsregnskap:

    @patch("wenche.fristsjekk.httpx.get")
    def test_regnskap_funnet_gir_innfridd(self, mock_get):
        """Regnskap for riktig år i BRG-respons → innfridd=True."""
        mock_get.return_value = _mock_response(json_data=[
            {
                "regnskapsperiode": {"fraDato": "2025-01-01", "tilDato": "2025-12-31"},
                "mottaksdag": "2026-04-15",
            },
        ])
        result = sjekk_aarsregnskap("931808869", 2025)

        assert result.innfridd is True
        assert "mottatt" in result.brukertekst.lower()
        assert "2025" in result.brukertekst
        assert result.tidspunkt == "2026-04-15"

    @patch("wenche.fristsjekk.httpx.get")
    def test_annet_aar_gir_ikke_innfridd(self, mock_get):
        """Kun regnskap for 2024 i respons, spør etter 2025 → innfridd=False."""
        mock_get.return_value = _mock_response(json_data=[
            {
                "regnskapsperiode": {"fraDato": "2024-01-01", "tilDato": "2024-12-31"},
            },
        ])
        result = sjekk_aarsregnskap("931808869", 2025)

        assert result.innfridd is False
        assert "ikke mottatt" in result.brukertekst.lower()

    @patch("wenche.fristsjekk.httpx.get")
    def test_tom_liste_gir_ikke_innfridd(self, mock_get):
        """Tom liste fra BRG → innfridd=False."""
        mock_get.return_value = _mock_response(json_data=[])
        result = sjekk_aarsregnskap("931808869", 2025)

        assert result.innfridd is False

    @patch("wenche.fristsjekk.httpx.get")
    def test_http_feil_gir_beskrivelse(self, mock_get):
        """HTTP-feil fra BRG → innfridd=False med feilmelding."""
        mock_get.return_value = _mock_response(status_code=404)
        result = sjekk_aarsregnskap("931808869", 2025)

        assert result.innfridd is False
        assert "kontakte" in result.beskrivelse.lower()

    @patch("wenche.fristsjekk.httpx.get")
    def test_nettverksfeil_gir_beskrivelse(self, mock_get):
        """Nettverksfeil mot BRG → innfridd=False med feilmelding."""
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        result = sjekk_aarsregnskap("931808869", 2025)

        assert result.innfridd is False
        assert "kontakte" in result.beskrivelse.lower()

    @patch("wenche.fristsjekk.httpx.get")
    def test_ugyldig_json_gir_beskrivelse(self, mock_get):
        """Ugyldig JSON fra BRG → innfridd=False med feilmelding."""
        resp = _mock_response()
        resp.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = resp
        result = sjekk_aarsregnskap("931808869", 2025)

        assert result.innfridd is False
        assert "Uventet svar" in result.beskrivelse


# ---------------------------------------------------------------------------
# Aksjonærregister
# ---------------------------------------------------------------------------

class TestSjekkAksjonaerregister:

    def test_returnerer_alltid_ikke_innfridd(self):
        """Ingen offentlig API — skal alltid returnere innfridd=False."""
        result = sjekk_aksjonaerregister("931808869", 2025)

        assert result.innfridd is False
        assert result.beskrivelse != ""


# ---------------------------------------------------------------------------
# FristStatus dataklasse
# ---------------------------------------------------------------------------

class TestFristStatus:

    def test_standardverdier(self):
        """FristStatus() med standardverdier skal være ikke-innfridd."""
        status = FristStatus()
        assert status.innfridd is False
        assert status.tidspunkt is None
        assert status.lenke is None

    def test_innfridd_med_lenke(self):
        """FristStatus med alle felt utfylt."""
        status = FristStatus(
            innfridd=True,
            brukertekst="Levert",
            lenke="https://example.com",
            tidspunkt="2026-03-30",
        )
        assert status.innfridd is True
        assert status.lenke == "https://example.com"


# ---------------------------------------------------------------------------
# Frist-dato og regnskapsår-utregning
# ---------------------------------------------------------------------------

class TestRegnskapsaarForFrist:

    def test_skattemelding_frist_31_mai_etter_idag(self):
        """18. mai 2026: neste 31. mai er 2026 → regnskapsår 2025."""
        with patch("wenche.fristsjekk.date", _freeze_today(date(2026, 5, 18))):
            assert regnskapsaar_for_frist(5, 31) == 2025

    def test_aarsregnskap_frist_31_juli(self):
        """18. mai 2026: neste 31. juli er 2026 → regnskapsår 2025."""
        with patch("wenche.fristsjekk.date", _freeze_today(date(2026, 5, 18))):
            assert regnskapsaar_for_frist(7, 31) == 2025

    def test_aksjonaerregister_frist_31_januar_etter_passert(self):
        """18. mai 2026: 31. jan 2026 er passert, neste er 2027 → regnskapsår 2026."""
        with patch("wenche.fristsjekk.date", _freeze_today(date(2026, 5, 18))):
            assert regnskapsaar_for_frist(1, 31) == 2026

    def test_frist_idag_telles_som_aktiv(self):
        """Dagens dato er fristen → frist.year - 1 = forrige år."""
        with patch("wenche.fristsjekk.date", _freeze_today(date(2026, 5, 31))):
            assert regnskapsaar_for_frist(5, 31) == 2025

    def test_dagen_etter_frist_ruller_til_neste_aar(self):
        """1. juni 2026: 31. mai er passert, neste er 2027 → regnskapsår 2026."""
        with patch("wenche.fristsjekk.date", _freeze_today(date(2026, 6, 1))):
            assert regnskapsaar_for_frist(5, 31) == 2026


class TestNesteFrist:

    def test_frist_i_fremtiden_samme_aar(self):
        with patch("wenche.fristsjekk.date", _freeze_today(date(2026, 5, 18))):
            assert neste_frist(7, 31) == date(2026, 7, 31)

    def test_frist_passert_ruller_til_neste_aar(self):
        with patch("wenche.fristsjekk.date", _freeze_today(date(2026, 5, 18))):
            assert neste_frist(1, 31) == date(2027, 1, 31)
