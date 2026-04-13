"""
Tester for aksjonærregister-XML-generering i wenche/aksjonaerregister.py.

Bruker SKDs RF-1086 / RF-1086-U format med grp-/datadef-elementnavn.
"""

import xml.etree.ElementTree as ET

import pytest

from wenche.aksjonaerregister import (
    generer_hovedskjema_xml,
    generer_underskjema_xml,
    valider,
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
        fodselsnummer="01010112345",
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
    """Pålydende per aksje = aksjekapital // antall_aksjer = 30000 // 100 = 300."""
    root = _parse(generer_hovedskjema_xml(eksempel_oppgave))
    paalydende = root.find(".//{*}AksjeMvPalydende-datadef-23945")
    assert paalydende is not None
    assert int(paalydende.text) == 300


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
    assert fnr.text == "01010112345"


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
