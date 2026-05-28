"""
Tester for aksjonærregister-XML-generering i wenche/aksjonaerregister.py.

Bruker SKDs RF-1086 / RF-1086-U format med grp-/datadef-elementnavn.
"""

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import httpx
import pytest

from wenche.aksjonaerregister import (
    generer_hovedskjema_xml,
    generer_underskjema_xml,
    valider,
    valider_mot_brg,
)
from wenche.models import Aksjonaer, Aksjonaerregisteroppgave, Selskap


@pytest.fixture
def eksempel_selskap():
    return Selskap(
        navn="Test Holding AS",
        org_nummer="123456789",
        daglig_leder="Ola Nordmann",
        styreleder="Ola Nordmann",
        forretningsadresse="Testveien 1, 0001 Oslo",
        stiftelsesaar=2020,
        aksjekapital=30000,
        kontakt_epost="ola@test.no",
    )


@pytest.fixture
def eksempel_aksjonaer():
    return Aksjonaer(
        navn="Ola Nordmann",
        fodselsnummer="20916997389",
        antall_aksjer=100,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=300,
    )


@pytest.fixture
def eksempel_oppgave(eksempel_selskap, eksempel_aksjonaer):
    return Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2024,
        aksjonaerer=[eksempel_aksjonaer],
    )


@pytest.fixture
def oppgave_stiftelsesaar(eksempel_selskap, eksempel_aksjonaer):
    """Oppgave der regnskapsåret er det samme som stiftelsesåret (2020)."""
    return Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2020,
        aksjonaerer=[eksempel_aksjonaer],
    )


def _parse(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)


# ---------------------------------------------------------------------------
# Hovedskjema — XML-struktur
# ---------------------------------------------------------------------------

def test_hovedskjema_er_gyldig_xml(eksempel_oppgave):
    xml_bytes = generer_hovedskjema_xml(eksempel_oppgave)
    root = _parse(xml_bytes)
    assert root is not None


def test_hovedskjema_returnerer_bytes(eksempel_oppgave):
    assert isinstance(generer_hovedskjema_xml(eksempel_oppgave), bytes)


def test_hovedskjema_skjemanummer(eksempel_oppgave):
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    assert root.attrib["skjemanummer"] == "890"
    assert root.attrib["blankettnummer"] == "RF-1086"


def test_hovedskjema_orgnummer(eksempel_oppgave):
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    orgnr = root.find(".//{*}EnhetOrganisasjonsnummer-datadef-18")
    assert orgnr is not None
    assert orgnr.text == "123456789"


def test_hovedskjema_inntektsaar(eksempel_oppgave):
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    aar = root.find(
        ".//GenerellInformasjon-grp-2587/Selskap-grp-2588/Inntektsar-datadef-692"
    )
    assert aar is not None
    assert aar.text == "2024"


def test_hovedskjema_aksjekapital(eksempel_oppgave):
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    ak = root.find(".//{*}Aksjekapital-datadef-87")
    assert ak is not None
    assert int(ak.text) == 30000


def test_hovedskjema_antall_aksjer(eksempel_oppgave):
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    antall = root.find(".//{*}AksjerMvAntall-datadef-29167")
    assert antall is not None
    assert int(antall.text) == 100


def test_hovedskjema_paalydende(eksempel_oppgave):
    """Pålydende per aksje = aksjekapital / antall_aksjer = 30000 / 100 = 300."""
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    paalydende = root.find(".//{*}AksjeMvPalydende-datadef-23945")
    assert paalydende is not None
    # Heltallspålydende skal formateres uten desimalpunktum
    assert paalydende.text == "300"


def test_hovedskjema_paalydende_desimal():
    """
    Selskaper med fri pålydende (lovlig siden 2013) kan ha brøkdeler av en
    krone som pålydende. For 30 000 kr aksjekapital fordelt på 300 000 aksjer
    er pålydende 0,10. Skjemaet må representere dette eksakt, ikke trunkere
    til 0 som integer-divisjon ville gjort. RF-1086 tillater opptil 6
    desimaler (bekreftet i SSV-5278), og vi stripper etterstilte nuller for
    kompakt representasjon.
    """
    selskap = Selskap(
        navn="Fragmentert Holding AS",
        org_nummer="987654321",
        daglig_leder="Kari Nordmann",
        styreleder="Kari Nordmann",
        forretningsadresse="Testveien 2, 0001 Oslo",
        stiftelsesaar=2020,
        aksjekapital=30000,
        kontakt_epost="kari@test.no",
    )
    aksjonaer = Aksjonaer(
        navn="Kari Nordmann",
        fodselsnummer="20916997389",
        antall_aksjer=300000,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=0.10,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=selskap,
        regnskapsaar=2024,
        aksjonaerer=[aksjonaer],
    )
    root = _parse(generer_hovedskjema_xml(oppgave))
    paalydende = root.find(".//{*}AksjeMvPalydende-datadef-23945")
    assert paalydende is not None
    assert paalydende.text == "0.1"
    # Fjorår-pålydende skal også reflektere desimalverdien (ikke stiftelsesår)
    fjor = root.find(".//{*}AksjeMvPalydendeFjoraret-datadef-23944")
    assert fjor is not None
    assert fjor.text == "0.1"


def test_hovedskjema_kontakt_epost(eksempel_oppgave):
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    epost = root.find(".//{*}KontaktpersonSkjemaEPost-datadef-30533")
    assert epost is not None
    assert epost.text == "ola@test.no"


# ---------------------------------------------------------------------------
# Underskjema — XML-struktur
# ---------------------------------------------------------------------------

def test_underskjema_er_gyldig_xml(eksempel_oppgave):
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    xml_bytes = generer_underskjema_xml(aksjonaer, eksempel_oppgave)
    root = _parse(xml_bytes)
    assert root is not None


def test_underskjema_returnerer_bytes(eksempel_oppgave):
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    assert isinstance(generer_underskjema_xml(aksjonaer, eksempel_oppgave), bytes)


def test_underskjema_skjemanummer(eksempel_oppgave):
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, eksempel_oppgave))
    assert root.attrib["skjemanummer"] == "923"
    assert root.attrib["blankettnummer"] == "RF-1086-U"


def test_underskjema_fodselsnummer(eksempel_oppgave):
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, eksempel_oppgave))
    fnr = root.find(".//{*}AksjonarFodselsnummer-datadef-1156")
    assert fnr is not None
    assert fnr.text == "20916997389"


def test_underskjema_antall_aksjer(eksempel_oppgave):
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, eksempel_oppgave))
    antall = root.find(".//{*}AksjonarAksjerAntall-datadef-17741")
    assert antall is not None
    assert int(antall.text) == 100


def test_underskjema_anskaffelsesverdi(oppgave_stiftelsesaar):
    """Anskaffelsesverdi = innbetalt_kapital_per_aksje * antall_aksjer = 300 * 100 = 30000.
    Transaksjonsfelter skal kun være med i stiftelsesåret."""
    aksjonaer = oppgave_stiftelsesaar.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, oppgave_stiftelsesaar))
    verdi = root.find(".//{*}AksjeAnskaffelsesverdi-datadef-17636")
    assert verdi is not None
    assert int(verdi.text) == 30000


def test_underskjema_ingen_transaksjon_etter_stiftelsesaar(eksempel_oppgave):
    """For inntektsår etter stiftelsesåret skal ingen transaksjon rapporteres (MTRA_004)."""
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, eksempel_oppgave))
    assert root.find(".//{*}AksjeAnskaffelsesverdi-datadef-17636") is None
    assert root.find(".//{*}AksjerErvervsdato-datadef-17746") is None


def test_underskjema_fjoraret_lik_antall_aksjer_etter_stiftelsesaar(eksempel_oppgave):
    """For inntektsår etter stiftelsesåret skal AksjerAntallFjoraret == antall_aksjer."""
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, eksempel_oppgave))
    fjoraret = root.find(".//{*}AksjerAntallFjoraret-datadef-29168")
    assert fjoraret is not None
    assert int(fjoraret.text) == aksjonaer.antall_aksjer


def test_underskjema_fjoraret_null_i_stiftelsesaar(oppgave_stiftelsesaar):
    """I stiftelsesåret skal AksjerAntallFjoraret være 0 (ingen beholdning foregående år)."""
    aksjonaer = oppgave_stiftelsesaar.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, oppgave_stiftelsesaar))
    fjoraret = root.find(".//{*}AksjerAntallFjoraret-datadef-29168")
    assert fjoraret is not None
    assert int(fjoraret.text) == 0


def test_underskjema_orgnummer(eksempel_oppgave):
    aksjonaer = eksempel_oppgave.aksjonaerer[0]
    root = _parse(generer_underskjema_xml(aksjonaer, eksempel_oppgave))
    orgnr = root.find(
        ".//SelskapsOgAksjonaropplysninger-grp-3987"
        "/Selskapsidentifikasjon-grp-3986"
        "/EnhetOrganisasjonsnummer-datadef-18"
    )
    assert orgnr is not None
    assert orgnr.text == "123456789"


# ---------------------------------------------------------------------------
# Validering
# ---------------------------------------------------------------------------

def test_valider_ok(eksempel_oppgave):
    assert valider(eksempel_oppgave) == []


def test_valider_ingen_aksjonaerer(eksempel_selskap):
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2024,
        aksjonaerer=[],
    )
    feil = valider(oppgave)
    assert any("aksjonær" in f.lower() for f in feil)


def test_valider_mangler_epost(eksempel_aksjonaer):
    selskap_uten_epost = Selskap(
        navn="Test AS",
        org_nummer="123456789",
        daglig_leder="Ola",
        styreleder="Ola",
        forretningsadresse="Testveien 1",
        stiftelsesaar=2020,
        aksjekapital=30000,
        kontakt_epost="",
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=selskap_uten_epost,
        regnskapsaar=2024,
        aksjonaerer=[eksempel_aksjonaer],
    )
    feil = valider(oppgave)
    assert any("epost" in f.lower() or "e-post" in f.lower() for f in feil)


def test_valider_stiftelsesaar_etter_regnskapsaar(eksempel_selskap, eksempel_aksjonaer):
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2019,
        aksjonaerer=[eksempel_aksjonaer],
    )
    feil = valider(oppgave)
    assert any("stiftelsesaar" in f.lower() for f in feil)


def test_valider_ugyldig_fnr(eksempel_selskap):
    aksjonaer = Aksjonaer(
        navn="Feil Person",
        fodselsnummer="1234",
        antall_aksjer=10,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=300,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2024,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert any("fødselsnummer" in f.lower() for f in feil)


def test_valider_fnr_riktig_lengde_men_feil_kontrollsifre(eksempel_selskap):
    # 11 siffer, men kontrollsifrene stemmer ikke (modulus-11).
    aksjonaer = Aksjonaer(
        navn="Typo Person",
        fodselsnummer="20916997380",  # siste siffer endret fra 9 til 0
        antall_aksjer=10,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=300,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2024,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert any("kontrollsifre" in f.lower() for f in feil)


def test_valider_stiftelse_i_inntektsaar_krever_innbetalt_kapital(eksempel_selskap):
    # Selskapet er stiftet i inntektsåret men aksjonær har 0 i innbetalt kapital.
    aksjonaer = Aksjonaer(
        navn="Stifter Nordmann",
        fodselsnummer="20916997389",
        antall_aksjer=100,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=0,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,  # stiftelsesaar=2020
        regnskapsaar=2020,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert any("innbetalt_kapital_per_aksje" in f for f in feil)


def test_valider_sum_innbetalt_matcher_aksjekapital_ved_nyemisjon(eksempel_selskap):
    # Selskap stiftet i regnskapsåret med aksjekapital 30000, men aksjonæren bidrar
    # bare 30 * 100 = 3000. Det skal trigge MAKH_053-sjekken.
    aksjonaer = Aksjonaer(
        navn="Underdekkende Nordmann",
        fodselsnummer="20916997389",
        antall_aksjer=100,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=30,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,  # aksjekapital=30000, stiftelsesaar=2020
        regnskapsaar=2020,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert any("Sum innbetalt kapital" in f for f in feil)


def test_valider_sum_innbetalt_lik_aksjekapital_ok(eksempel_selskap):
    # 100 aksjer * 300 = 30000, matcher selskapets aksjekapital.
    aksjonaer = Aksjonaer(
        navn="Korrekt Nordmann",
        fodselsnummer="20916997389",
        antall_aksjer=100,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=300,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2020,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert not any("Sum innbetalt kapital" in f for f in feil)


def test_valider_sum_innbetalt_ikke_sjekket_etter_stiftelsesaar(eksempel_selskap):
    # Mismatch er OK når selskapet ikke ble stiftet i inntektsåret —
    # da brukes ikke feltet i stiftelsestransaksjonen.
    aksjonaer = Aksjonaer(
        navn="Etablert Nordmann",
        fodselsnummer="20916997389",
        antall_aksjer=100,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=30,  # Mismatch, men ikke stiftelsesår
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,  # stiftelsesaar=2020
        regnskapsaar=2024,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert not any("Sum innbetalt kapital" in f for f in feil)


def test_valider_innbetalt_kapital_null_ok_etter_stiftelsesaar(eksempel_selskap):
    # Innbetalt kapital = 0 er OK når selskapet ikke ble stiftet i inntektsåret.
    aksjonaer = Aksjonaer(
        navn="Etablert Nordmann",
        fodselsnummer="20916997389",
        antall_aksjer=100,
        aksjeklasse="A",
        utbytte_utbetalt=0,
        innbetalt_kapital_per_aksje=0,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,  # stiftelsesaar=2020
        regnskapsaar=2024,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert not any("innbetalt_kapital_per_aksje" in f for f in feil)


# ---------------------------------------------------------------------------
# valider_mot_brg
# ---------------------------------------------------------------------------

def _brg_mock(status_code: int = 200, json_data: dict | None = None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    return resp


@patch("wenche.aksjonaerregister.httpx.get")
def test_valider_mot_brg_samsvar_gir_ingen_advarsel(mock_get, eksempel_oppgave):
    mock_get.return_value = _brg_mock(json_data={"stiftelsesdato": "2020-06-15"})
    assert valider_mot_brg(eksempel_oppgave) == []


@patch("wenche.aksjonaerregister.httpx.get")
def test_valider_mot_brg_mismatch_gir_advarsel(mock_get, eksempel_oppgave):
    # BRG har 2018, config har 2020 → mismatch.
    mock_get.return_value = _brg_mock(json_data={"stiftelsesdato": "2018-12-11"})
    advarsler = valider_mot_brg(eksempel_oppgave)
    assert len(advarsler) == 1
    assert "MAKS_025" in advarsler[0]
    assert "2018" in advarsler[0]
    assert "2020" in advarsler[0]


@patch("wenche.aksjonaerregister.httpx.get")
def test_valider_mot_brg_404_gir_advarsel_om_ukjent_orgnr(mock_get, eksempel_oppgave):
    mock_get.return_value = _brg_mock(status_code=404)
    advarsler = valider_mot_brg(eksempel_oppgave)
    assert len(advarsler) == 1
    assert "ikke funnet" in advarsler[0].lower()


@patch("wenche.aksjonaerregister.httpx.get")
def test_valider_mot_brg_nettverksfeil_returnerer_tom_liste(mock_get, eksempel_oppgave):
    # Transient feil skal ikke blokkere innsending.
    mock_get.side_effect = httpx.ConnectError("Connection refused")
    assert valider_mot_brg(eksempel_oppgave) == []


@patch("wenche.aksjonaerregister.httpx.get")
def test_valider_mot_brg_5xx_returnerer_tom_liste(mock_get, eksempel_oppgave):
    mock_get.return_value = _brg_mock(status_code=503)
    assert valider_mot_brg(eksempel_oppgave) == []


@patch("wenche.aksjonaerregister.httpx.get")
def test_valider_mot_brg_uten_stiftelsesdato_i_svar(mock_get, eksempel_oppgave):
    # BRG-svar uten stiftelsesdato (uvanlig, men håndteres trygt).
    mock_get.return_value = _brg_mock(json_data={"navn": "TEST AS"})
    assert valider_mot_brg(eksempel_oppgave) == []
