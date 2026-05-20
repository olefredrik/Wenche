"""Tester for parsing av Skatteetatens tilbakemelding etter skattemelding-innsending."""

from unittest.mock import MagicMock

import pytest

from wenche.skd_skattemelding_client import _verifiser_tilbakemelding

NS = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:response:v2"


def _mock_altinn_med_tilbakemelding(xml: bytes | None):
    altinn = MagicMock()
    altinn.hent_data_element_bytes.return_value = xml
    return altinn


def test_godkjent_tilbakemelding_raises_ikke(capsys):
    xml = (
        f'<skattemeldingOgNaeringsspesifikasjonResponse xmlns="{NS}">'
        '<resultatAvValidering>validertUtenFeil</resultatAvValidering>'
        '</skattemeldingOgNaeringsspesifikasjonResponse>'
    ).encode()
    altinn = _mock_altinn_med_tilbakemelding(xml)
    _verifiser_tilbakemelding(altinn, {"id": "test/abc"})
    out = capsys.readouterr().out
    assert "godkjent" in out.lower()


def test_avvist_med_aarsak_raises_runtimeerror():
    # Eksempel fra OFL Holding 2026-05-20 avvisning.
    xml = (
        f'<skattemeldingOgNaeringsspesifikasjonResponse xmlns="{NS}">'
        '<resultatAvValidering>validertMedFeil</resultatAvValidering>'
        '<aarsakTilValidertMedFeil>innkommendeForespoerselManglerSporTilUtfoerende</aarsakTilValidertMedFeil>'
        '</skattemeldingOgNaeringsspesifikasjonResponse>'
    ).encode()
    altinn = _mock_altinn_med_tilbakemelding(xml)
    with pytest.raises(RuntimeError) as exc:
        _verifiser_tilbakemelding(altinn, {"id": "test/abc"})
    assert "avviste" in str(exc.value).lower()
    assert "innkommendeForespoerselManglerSporTilUtfoerende" in str(exc.value)
    assert "validertMedFeil" in str(exc.value)


def test_avvist_uten_aarsak_raises_likevel():
    xml = (
        f'<skattemeldingOgNaeringsspesifikasjonResponse xmlns="{NS}">'
        '<resultatAvValidering>validertMedFeil</resultatAvValidering>'
        '</skattemeldingOgNaeringsspesifikasjonResponse>'
    ).encode()
    altinn = _mock_altinn_med_tilbakemelding(xml)
    with pytest.raises(RuntimeError) as exc:
        _verifiser_tilbakemelding(altinn, {"id": "test/abc"})
    assert "validertMedFeil" in str(exc.value)


def test_manglende_tilbakemelding_gir_advarsel_uten_exception(capsys):
    altinn = _mock_altinn_med_tilbakemelding(None)
    _verifiser_tilbakemelding(altinn, {"id": "test/abc"})
    out = capsys.readouterr().out
    assert "advarsel" in out.lower()


def test_ugyldig_xml_raiser_runtimeerror():
    altinn = _mock_altinn_med_tilbakemelding(b"dette er ikke xml")
    with pytest.raises(RuntimeError) as exc:
        _verifiser_tilbakemelding(altinn, {"id": "test/abc"})
    assert "parse" in str(exc.value).lower()


def test_manglende_resultatfelt_gir_advarsel(capsys):
    xml = (
        f'<skattemeldingOgNaeringsspesifikasjonResponse xmlns="{NS}">'
        '<dokumenter/>'
        '</skattemeldingOgNaeringsspesifikasjonResponse>'
    ).encode()
    altinn = _mock_altinn_med_tilbakemelding(xml)
    _verifiser_tilbakemelding(altinn, {"id": "test/abc"})
    out = capsys.readouterr().out
    assert "advarsel" in out.lower()
