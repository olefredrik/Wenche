"""
XSD-validering av generert XML mot Skatteetatens bundlede skjemaer.

Skatteetatens valideringstjeneste avviser konvolutter der de indre
dokumentene ikke er i henhold til XSD (feilkode SMEVB-005, jf. SSV-5187).
XSD-sekvenser er rekkefølge-bundet, så feil rekkefølge på elementene gjør
XML-en ugyldig selv om alle feltene er til stede. Disse testene fanger den
klassen av feil i CI, uten å trenge API-tilgang.

Krever lxml (dev-avhengighet). Hopper over hvis lxml ikke er installert.
"""

from pathlib import Path

import pytest

import wenche
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skattemelding_konvolutt import generer_konvolutt
from wenche.skattemelding_xml import generer_skattemelding_upersonlig

etree = pytest.importorskip("lxml.etree")

_XSD_DIR = Path(wenche.__file__).parent / "xsd"

_PARTSNUMMER = 123456789


def _valider(xml_bytes: bytes, xsd_navn: str) -> None:
    """Validerer xml_bytes mot XSD-en og feiler med XSD-avvikene som melding."""
    schema = etree.XMLSchema(etree.parse(str(_XSD_DIR / xsd_navn)))
    doc = etree.fromstring(xml_bytes)
    if not schema.validate(doc):
        avvik = "\n".join(
            f"  linje {e.line}: {e.message}" for e in schema.error_log
        )
        pytest.fail(f"XML er ugyldig mot {xsd_navn}:\n{avvik}")


class TestSkattemeldingUpersonligXsd:
    def test_validerer_mot_v5(self):
        xml = generer_skattemelding_upersonlig(
            partsnummer=_PARTSNUMMER, inntektsaar=2025, fremfoert_underskudd=0
        )
        _valider(xml, "skattemeldingUpersonlig_v5_ekstern.xsd")

    def test_validerer_med_fremfoert_underskudd(self):
        xml = generer_skattemelding_upersonlig(
            partsnummer=_PARTSNUMMER, inntektsaar=2025, fremfoert_underskudd=50000
        )
        _valider(xml, "skattemeldingUpersonlig_v5_ekstern.xsd")


class TestNaeringsspesifikasjonXsd:
    def test_validerer_negativ_egenkapital(self, eksempel_regnskap):
        # eksempel_regnskap har annen_egenkapital=-34300 (konto 2080) og
        # langsiktig gjeld. Dette er caset som tidligere ga SMEVB-005 fordi
        # egenkapital ble lagt før langsiktigGjeld/kortsiktigGjeld.
        xml = generer_naeringsspesifikasjon(eksempel_regnskap, _PARTSNUMMER)
        _valider(xml, "naeringsspesifikasjon_v6_ekstern.xsd")

    def test_validerer_positiv_egenkapital(self, regnskap_med_utbytte):
        xml = generer_naeringsspesifikasjon(regnskap_med_utbytte, _PARTSNUMMER)
        _valider(xml, "naeringsspesifikasjon_v6_ekstern.xsd")

    def test_gjeldOgEgenkapital_rekkefolge(self, eksempel_regnskap):
        # Eksplisitt vakt mot regresjon av rekkefølge-bugen: XSD-sekvensen
        # GjeldOgEgenkapital krever langsiktigGjeld -> kortsiktigGjeld ->
        # egenkapital.
        xml = generer_naeringsspesifikasjon(eksempel_regnskap, _PARTSNUMMER)
        root = etree.fromstring(xml)
        ns = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"
        gek = root.find(f".//{ns}gjeldOgEgenkapital")
        assert gek is not None
        barn = [c.tag.replace(ns, "") for c in gek]
        rekkefolge = {
            navn: i for i, navn in enumerate(
                ["langsiktigGjeld", "kortsiktigGjeld", "egenkapital"]
            ) if navn in barn
        }
        posisjoner = [barn.index(navn) for navn in rekkefolge]
        assert posisjoner == sorted(posisjoner), (
            f"Feil rekkefølge i gjeldOgEgenkapital: {barn}"
        )


class TestKonvoluttXsd:
    def _konvolutt(self, eksempel_regnskap, gjeldende_dokument_id=None):
        sm = generer_skattemelding_upersonlig(
            partsnummer=_PARTSNUMMER, inntektsaar=2025, fremfoert_underskudd=0
        )
        ns = generer_naeringsspesifikasjon(eksempel_regnskap, _PARTSNUMMER)
        return generer_konvolutt(
            skattemelding_xml=sm,
            inntektsaar=2025,
            orgnr=eksempel_regnskap.selskap.org_nummer,
            naeringsspesifikasjon_xml=ns,
            gjeldende_dokument_id=gjeldende_dokument_id,
        )

    def test_konvolutt_validerer(self, eksempel_regnskap):
        konvolutt = self._konvolutt(eksempel_regnskap)
        _valider(konvolutt, "skattemeldingognaeringsspesifikasjonrequest_v2.xsd")

    def test_konvolutt_med_dokumentreferanse_validerer(self, eksempel_regnskap):
        konvolutt = self._konvolutt(eksempel_regnskap, gjeldende_dokument_id="abc-123")
        _valider(konvolutt, "skattemeldingognaeringsspesifikasjonrequest_v2.xsd")
