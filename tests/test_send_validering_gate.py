"""
Forhåndsvalidering-porten i SkdSkattemeldingClient.send().

send() kjører valider-tjenesten først og avbryter uten å laste opp hvis
resultatet ikke er validertOK. Porten skal kun blokkere på validertMedFeil,
ikke på de ikke-blokkerende avvik-etter-beregning/merknader som finnes på
enhver gyldig innsending.
"""

from unittest.mock import MagicMock, patch

import pytest

from wenche.skd_skattemelding_client import (
    SkattemeldingValideringsfeil,
    SkdSkattemeldingClient,
)

_SM = b"<skattemelding/>"  # innhold irrelevant; valider() mockes


def _klient() -> SkdSkattemeldingClient:
    return SkdSkattemeldingClient("dummy-token", env="test")


def test_send_blokkerer_ved_validertMedFeil():
    skd = _klient()
    skd.valider = MagicMock(
        return_value={
            "resultat": "validertMedFeil",
            "aarsak": "idAvvikerFraKrav",
            "avvik_ved_validering": [
                {"avvikstype": "idAvvikerFraKrav", "oevrigInformasjon": "feil id"}
            ],
            "avvik_etter_beregning": [],
            "veiledning": [],
        }
    )
    with patch("wenche.skd_skattemelding_client.AltinnClient") as Altinn:
        with pytest.raises(SkattemeldingValideringsfeil) as ei:
            skd.send(2025, "123456789", _SM, altinn_token="a")
        Altinn.assert_not_called()  # ingenting lastet opp
    assert ei.value.resultat["resultat"] == "validertMedFeil"
    assert "Ingenting er sendt inn" in str(ei.value)


def test_send_fortsetter_ved_validertOK_med_ikke_blokkerende_avvik():
    skd = _klient()
    # validertOK, men med avvik-etter-beregning og merknader (som på enhver
    # gyldig innsending). Disse skal IKKE stoppe innsendingen.
    skd.valider = MagicMock(
        return_value={
            "resultat": "validertOK",
            "aarsak": None,
            "avvik_ved_validering": [],
            "avvik_etter_beregning": [{"avvikstype": "manglerNaeringsopplysninger"}],
            "veiledning": [{"veiledningstype": "N_MANGLER_VERDI_BAK_AKSJENE"}],
        }
    )
    with patch("wenche.skd_skattemelding_client.AltinnClient") as Altinn:
        inst = Altinn.return_value.__enter__.return_value
        inst.opprett_instans.return_value = {"id": "i1"}
        inst.fullfoor_instans.return_value = "https://altinn/inbox"
        url = skd.send(2025, "123456789", _SM, altinn_token="a")
    assert url == "https://altinn/inbox"
    skd.valider.assert_called_once()


def test_send_hopper_over_validering_naar_avslaatt():
    skd = _klient()
    skd.valider = MagicMock()
    with patch("wenche.skd_skattemelding_client.AltinnClient") as Altinn:
        inst = Altinn.return_value.__enter__.return_value
        inst.opprett_instans.return_value = {"id": "i1"}
        inst.fullfoor_instans.return_value = "https://altinn/inbox"
        skd.send(2025, "123456789", _SM, altinn_token="a", valider_foerst=False)
    skd.valider.assert_not_called()
