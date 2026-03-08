"""
Tester for BRG XML-generering i wenche/brg_xml.py.
Verifiserer at generert XML er velformet og inneholder korrekte verdier.
"""

import xml.etree.ElementTree as ET

from wenche.brg_xml import generer_hovedskjema, generer_underskjema


NS_HOVED = "http://schema.brreg.no/regnsys/aarsregnskap_vanlig"
NS_UNDER = "http://schema.brreg.no/regnsys/aarsregnskap_vanlig/underskjema"


def _parse(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)


# ---------------------------------------------------------------------------
# Hovedskjema
# ---------------------------------------------------------------------------

def test_hovedskjema_er_gyldig_xml(eksempel_regnskap):
    xml_bytes = generer_hovedskjema(eksempel_regnskap)
    root = _parse(xml_bytes)
    assert root is not None


def test_hovedskjema_namespace(eksempel_regnskap):
    root = _parse(generer_hovedskjema(eksempel_regnskap))
    assert root.tag == f"{{{NS_HOVED}}}melding"


def test_hovedskjema_dataformat_id(eksempel_regnskap):
    root = _parse(generer_hovedskjema(eksempel_regnskap))
    assert root.attrib["dataFormatId"] == "1266"


def test_hovedskjema_orgnummer(eksempel_regnskap):
    root = _parse(generer_hovedskjema(eksempel_regnskap))
    orgnr = root.find(f".//{{{NS_HOVED}}}organisasjonsnummer")
    assert orgnr is not None
    assert orgnr.text == "123456789"


def test_hovedskjema_selskapsnavn(eksempel_regnskap):
    root = _parse(generer_hovedskjema(eksempel_regnskap))
    navn = root.find(f".//{{{NS_HOVED}}}navn")
    assert navn is not None
    assert navn.text == "Test Holding AS"


def test_hovedskjema_regnskapsaar(eksempel_regnskap):
    root = _parse(generer_hovedskjema(eksempel_regnskap))
    aar = root.find(f".//{{{NS_HOVED}}}regnskapsaar")
    assert aar is not None
    assert aar.text == "2025"


def test_hovedskjema_ikke_revidert_som_standard(eksempel_regnskap):
    root = _parse(generer_hovedskjema(eksempel_regnskap))
    ikke_rev = root.find(f".//{{{NS_HOVED}}}aarsregnskapIkkeRevideres")
    assert ikke_rev is not None
    assert ikke_rev.text == "ja"


def test_hovedskjema_signatar_er_daglig_leder(eksempel_regnskap):
    root = _parse(generer_hovedskjema(eksempel_regnskap))
    sign = root.find(f".//{{{NS_HOVED}}}bekreftendeSelskapsrepresentant")
    assert sign is not None
    assert sign.text == "Ola Nordmann"


# ---------------------------------------------------------------------------
# Underskjema
# ---------------------------------------------------------------------------

def test_underskjema_er_gyldig_xml(eksempel_regnskap):
    xml_bytes = generer_underskjema(eksempel_regnskap)
    root = _parse(xml_bytes)
    assert root is not None


def test_underskjema_namespace(eksempel_regnskap):
    root = _parse(generer_underskjema(eksempel_regnskap))
    assert root.tag == f"{{{NS_UNDER}}}melding"


def test_underskjema_dataformat_id(eksempel_regnskap):
    root = _parse(generer_underskjema(eksempel_regnskap))
    assert root.attrib["dataFormatId"] == "758"


def test_underskjema_driftsresultat(eksempel_regnskap):
    root = _parse(generer_underskjema(eksempel_regnskap))
    driftsresultat = root.find(
        f".//{{{NS_UNDER}}}driftsresultat/{{{NS_UNDER}}}aarets"
    )
    assert driftsresultat is not None
    assert int(driftsresultat.text) == -5500


def test_underskjema_sum_eiendeler(eksempel_regnskap):
    root = _parse(generer_underskjema(eksempel_regnskap))
    sum_ei = root.find(f".//{{{NS_UNDER}}}sumEiendeler/{{{NS_UNDER}}}aarets")
    assert sum_ei is not None
    assert int(sum_ei.text) == 101200


def test_underskjema_sum_egenkapital_og_gjeld(eksempel_regnskap):
    root = _parse(generer_underskjema(eksempel_regnskap))
    sum_ekg = root.find(
        f".//{{{NS_UNDER}}}sumEgenkapitalGjeld/{{{NS_UNDER}}}aarets"
    )
    assert sum_ekg is not None
    assert int(sum_ekg.text) == 101200


def test_underskjema_utelater_nullinjer(eksempel_regnskap):
    """Linjer med verdi 0 skal ikke inkluderes i XML (f.eks. salgsinntekter=0)."""
    root = _parse(generer_underskjema(eksempel_regnskap))
    salgsinntekter = root.findall(f".//{{{NS_UNDER}}}salgsinntekt")
    assert len(salgsinntekter) == 0


def test_underskjema_inkluderer_nonzero_linjer(eksempel_regnskap):
    """Linjer med verdi != 0 skal være med (f.eks. aksjer i datterselskap)."""
    root = _parse(generer_underskjema(eksempel_regnskap))
    aksjer = root.findall(f".//{{{NS_UNDER}}}investeringDatterselskap")
    assert len(aksjer) == 1


def test_underskjema_returnerer_bytes(eksempel_regnskap):
    assert isinstance(generer_underskjema(eksempel_regnskap), bytes)


def test_hovedskjema_returnerer_bytes(eksempel_regnskap):
    assert isinstance(generer_hovedskjema(eksempel_regnskap), bytes)
