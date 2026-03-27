"""
Tester for skattemelding_xml.py.

Verifiserer at skattemeldingUpersonlig-XML er strukturelt korrekt:
- Riktig namespace
- Obligatoriske felt (partsnummer, inntektsaar)
- Fremført underskudd håndteres korrekt (inkludert / utelatt)
- Output er gyldig UTF-8 XML
"""

from xml.etree.ElementTree import fromstring

import pytest

from wenche.skattemelding_xml import generer_skattemelding_upersonlig

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "skattemelding:upersonlig:ekstern:v5"
)


def _parse(xml_bytes: bytes):
    return fromstring(xml_bytes.decode("utf-8"))


class TestSkattemeldingXml:
    def test_rootelement_navn(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024))
        assert "skattemelding" in root.tag

    def test_namespace_er_satt(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024))
        assert _NS in root.tag

    def test_partsnummer(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024))
        assert root.find(f"{{{_NS}}}partsnummer").text == "12345678"

    def test_inntektsaar(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024))
        assert root.find(f"{{{_NS}}}inntektsaar").text == "2024"

    def test_fremfoert_underskudd_inkluderes(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024, fremfoert_underskudd=50000))
        beloep = root.find(
            f".//{{{_NS}}}fremfoertUnderskuddFraTidligereAar/{{{_NS}}}beloepSomHeltall"
        )
        assert beloep is not None
        assert beloep.text == "50000"

    def test_fremfoert_underskudd_rundes_til_heltall(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024, fremfoert_underskudd=50000.7))
        beloep = root.find(
            f".//{{{_NS}}}fremfoertUnderskuddFraTidligereAar/{{{_NS}}}beloepSomHeltall"
        )
        assert beloep.text == "50001"

    def test_uten_underskudd_ingen_inntektogunderskudd(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024))
        assert root.find(f"{{{_NS}}}inntektOgUnderskudd") is None

    def test_underskudd_null_inkluderes_ikke(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024, fremfoert_underskudd=0))
        assert root.find(f"{{{_NS}}}inntektOgUnderskudd") is None

    def test_underskudd_struktur_er_korrekt(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024, fremfoert_underskudd=10000))
        iou = root.find(f"{{{_NS}}}inntektOgUnderskudd")
        assert iou is not None
        utf = iou.find(f"{{{_NS}}}underskuddTilFremfoering")
        assert utf is not None
        fremfoert = utf.find(f"{{{_NS}}}fremfoertUnderskuddFraTidligereAar")
        assert fremfoert is not None

    def test_output_er_gyldig_utf8_xml(self):
        result = generer_skattemelding_upersonlig(12345678, 2024, fremfoert_underskudd=10000)
        assert isinstance(result, bytes)
        result.decode("utf-8")
        fromstring(result.decode("utf-8"))

    def test_output_uten_underskudd_er_gyldig_xml(self):
        result = generer_skattemelding_upersonlig(99887766, 2023)
        assert isinstance(result, bytes)
        fromstring(result.decode("utf-8"))
