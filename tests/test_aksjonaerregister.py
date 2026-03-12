"""
Tester for aksjonærregister-XML-generering i wenche/aksjonaerregister.py.
"""

import xml.etree.ElementTree as ET

import pytest

from wenche.aksjonaerregister import generer_xml, valider
from wenche.models import Aksjonaer, Aksjonaerregisteroppgave, Selskap


NS = "urn:ske:fastsetting:formueinntekt:aksjerekopp:v2"


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
        regnskapsaar=2025,
        aksjonaerer=[eksempel_aksjonaer],
    )


def _parse(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)


# ---------------------------------------------------------------------------
# XML-struktur
# ---------------------------------------------------------------------------

def test_generer_xml_er_gyldig_xml(eksempel_oppgave):
    xml_bytes = generer_xml(eksempel_oppgave)
    root = _parse(xml_bytes)
    assert root is not None


def test_generer_xml_returnerer_bytes(eksempel_oppgave):
    assert isinstance(generer_xml(eksempel_oppgave), bytes)


def test_generer_xml_namespace(eksempel_oppgave):
    root = _parse(generer_xml(eksempel_oppgave))
    assert root.tag == f"{{{NS}}}Skjema"


def test_generer_xml_skjemanummer(eksempel_oppgave):
    root = _parse(generer_xml(eksempel_oppgave))
    assert root.attrib["skjemanummer"] == "RF-1086"


def test_generer_xml_orgnummer(eksempel_oppgave):
    root = _parse(generer_xml(eksempel_oppgave))
    orgnr = root.find(f".//{{{NS}}}Organisasjonsnummer")
    assert orgnr is not None
    assert orgnr.text == "123456789"


def test_generer_xml_inntektsaar(eksempel_oppgave):
    root = _parse(generer_xml(eksempel_oppgave))
    aar = root.find(f"{{{NS}}}Inntektsaar")
    assert aar is not None
    assert aar.text == "2025"


def test_generer_xml_antall_aksjer(eksempel_oppgave):
    root = _parse(generer_xml(eksempel_oppgave))
    antall = root.find(f".//{{{NS}}}AntallAksjer")
    assert antall is not None
    assert int(antall.text) == 100


def test_generer_xml_aksjonaer_fnr(eksempel_oppgave):
    root = _parse(generer_xml(eksempel_oppgave))
    fnr = root.find(f".//{{{NS}}}Fodselsnummer")
    assert fnr is not None
    assert fnr.text == "01010112345"


def test_generer_xml_utelater_utbytte_ved_null(eksempel_oppgave):
    """Utbytte-element skal ikke inkluderes hvis utbytte_utbetalt == 0."""
    root = _parse(generer_xml(eksempel_oppgave))
    utbytte = root.findall(f".//{{{NS}}}Utbytte")
    assert len(utbytte) == 0


def test_generer_xml_inkluderer_utbytte_ved_nonzero(eksempel_selskap):
    aksjonaer = Aksjonaer(
        navn="Kari Nordmann",
        fodselsnummer="02020212345",
        antall_aksjer=50,
        aksjeklasse="A",
        utbytte_utbetalt=25000,
        innbetalt_kapital_per_aksje=300,
    )
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2025,
        aksjonaerer=[aksjonaer],
    )
    root = _parse(generer_xml(oppgave))
    utbytte = root.findall(f".//{{{NS}}}Utbytte")
    assert len(utbytte) == 1
    belop = utbytte[0].find(f"{{{NS}}}UtbytteBelop")
    assert int(belop.text) == 25000


# ---------------------------------------------------------------------------
# Validering
# ---------------------------------------------------------------------------

def test_valider_ok(eksempel_oppgave):
    assert valider(eksempel_oppgave) == []


def test_valider_ingen_aksjonaerer(eksempel_selskap):
    oppgave = Aksjonaerregisteroppgave(
        selskap=eksempel_selskap,
        regnskapsaar=2025,
        aksjonaerer=[],
    )
    feil = valider(oppgave)
    assert any("aksjonær" in f.lower() for f in feil)


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
        regnskapsaar=2025,
        aksjonaerer=[aksjonaer],
    )
    feil = valider(oppgave)
    assert any("fødselsnummer" in f.lower() for f in feil)
