"""
Regresjonstest for `wenche send-skattemelding` (CLI).

CLI-kommandoen må sende `gjeldende_dokument_id` videre til skd.send(), slik at
konvolutten får `dokumentreferanseTilGjeldendeDokument`. Uten den avviser
Skatteetaten innsendingen med `innkommendeForespoerselManglerReferanseTilGjeldendeSkattemelding`
(issue #84). UI-en og valider-kommandoen gjorde dette allerede; CLI-en hang etter.
"""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from wenche.cli import main

# Minimal gyldig forhåndsutfylt skattemeldingUpersonlig v5 slik at
# hent_partsnummer() finner <partsnummer>.
_FORHANDSUTFYLT = (
    '<skattemelding xmlns="urn:no:skatteetaten:fastsetting:formueinntekt:'
    'skattemelding:upersonlig:ekstern:v5">'
    "<partsnummer>3002792459</partsnummer>"
    "<inntektsaar>2025</inntektsaar></skattemelding>"
).encode("utf-8")

_CONFIG = Path(__file__).resolve().parent.parent / "config.example.yaml"


def test_send_skattemelding_sender_gjeldende_dokument_id(monkeypatch):
    monkeypatch.delenv("WENCHE_ENV", raising=False)
    monkeypatch.delenv("SKD_TEST_PARTSNUMMER", raising=False)

    with patch(
        "wenche.auth.get_skd_skattemelding_tokens",
        return_value={"maskinporten_token": "m", "altinn_token": "a"},
    ), patch("wenche.skd_skattemelding_client.SkdSkattemeldingClient") as Client:
        skd = Client.return_value.__enter__.return_value
        skd.hent_forhåndsutfylt_med_id.return_value = (
            _FORHANDSUTFYLT,
            "SKI:755:970817908",
        )
        skd.send.return_value = "instans-123"

        result = CliRunner().invoke(
            main, ["send-skattemelding", "--config", str(_CONFIG)]
        )

    assert result.exit_code == 0, result.output
    skd.send.assert_called_once()
    assert skd.send.call_args.kwargs["gjeldende_dokument_id"] == "SKI:755:970817908"
