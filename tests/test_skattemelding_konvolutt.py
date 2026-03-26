"""
Tester for skattemelding_konvolutt.py.

Verifiserer at konvolutten som genereres er strukturelt korrekt:
- Riktig namespace
- base64-kodet innhold
- Obligatoriske felt er til stede
- Valgfrie felt (næringsoppgave, TIN) håndteres korrekt
- Ugyldig input gir ValueError
"""

import base64
from xml.etree.ElementTree import fromstring

import pytest

from wenche.skattemelding_konvolutt import generer_konvolutt

_NS = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:request:v2"
_DUMMY_XML = b"<skattemelding><inntektsaar>2024</inntektsaar></skattemelding>"
_DUMMY_NS_XML = b"<ns:skattemelding><ns:inntektsaar>2024</ns:inntektsaar></ns:skattemelding>"


def _parse(xml_bytes: bytes):
    return fromstring(xml_bytes.decode("utf-8"))


class TestKonvolutt:
    def test_rootelement_navn(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        assert "skattemeldingOgNaeringsspesifikasjonRequest" in root.tag

    def test_namespace_er_satt(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        assert _NS in root.tag

    def test_inntektsaar(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        aar = root.find(f"{{{_NS}}}inntektsaar")
        assert aar is not None
        assert aar.text == "2024"

    def test_ett_dokument_uten_naeringsspesifikasjon(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        dokumenter = root.find(f"{{{_NS}}}dokumenter")
        docs = list(dokumenter)
        assert len(docs) == 1

    def test_dokumenttype_er_skattemeldingUpersonlig(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        dok = root.find(f".//{{{_NS}}}dokument")
        assert dok.find(f"{{{_NS}}}type").text == "skattemeldingUpersonlig"

    def test_encoding_er_utf8(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        dok = root.find(f".//{{{_NS}}}dokument")
        assert dok.find(f"{{{_NS}}}encoding").text == "utf-8"

    def test_content_er_base64_av_original_xml(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        dok = root.find(f".//{{{_NS}}}dokument")
        content_b64 = dok.find(f"{{{_NS}}}content").text
        decoded = base64.b64decode(content_b64)
        assert decoded == _DUMMY_XML

    def test_innsendingsformaal_standard_er_egenfastsetting(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        info = root.find(f"{{{_NS}}}innsendingsinformasjon")
        assert info.find(f"{{{_NS}}}innsendingsformaal").text == "egenfastsetting"

    def test_innsendingstype_standard_er_komplett(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        info = root.find(f"{{{_NS}}}innsendingsinformasjon")
        assert info.find(f"{{{_NS}}}innsendingstype").text == "komplett"

    def test_opprettetAv_er_wenche(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        info = root.find(f"{{{_NS}}}innsendingsinformasjon")
        assert info.find(f"{{{_NS}}}opprettetAv").text == "Wenche"

    def test_tin_settes_naar_orgnr_er_oppgitt(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024, orgnr="922020523"))
        info = root.find(f"{{{_NS}}}innsendingsinformasjon")
        assert info.find(f"{{{_NS}}}tin").text == "922020523"

    def test_tin_mangler_naar_orgnr_ikke_er_oppgitt(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024))
        info = root.find(f"{{{_NS}}}innsendingsinformasjon")
        assert info.find(f"{{{_NS}}}tin") is None

    def test_to_dokumenter_med_naeringsspesifikasjon(self):
        naring_xml = b"<naeringsspesifikasjon/>"
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024, naeringsspesifikasjon_xml=naring_xml))
        dokumenter = root.find(f"{{{_NS}}}dokumenter")
        docs = list(dokumenter)
        assert len(docs) == 2
        typer = [d.find(f"{{{_NS}}}type").text for d in docs]
        assert "skattemeldingUpersonlig" in typer
        assert "naeringsspesifikasjon" in typer

    def test_naeringsspesifikasjon_content_er_base64(self):
        naring_xml = b"<naeringsspesifikasjon><test/></naeringsspesifikasjon>"
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024, naeringsspesifikasjon_xml=naring_xml))
        for dok in root.findall(f".//{{{_NS}}}dokument"):
            if dok.find(f"{{{_NS}}}type").text == "naeringsspesifikasjon":
                decoded = base64.b64decode(dok.find(f"{{{_NS}}}content").text)
                assert decoded == naring_xml

    def test_ugyldig_innsendingsformaal_gir_valueerror(self):
        with pytest.raises(ValueError, match="innsendingsformaal"):
            generer_konvolutt(_DUMMY_XML, 2024, innsendingsformaal="ugyldig")

    def test_ugyldig_innsendingstype_gir_valueerror(self):
        with pytest.raises(ValueError, match="innsendingstype"):
            generer_konvolutt(_DUMMY_XML, 2024, innsendingstype="ugyldig")

    def test_klage_innsendingsformaal(self):
        root = _parse(generer_konvolutt(_DUMMY_XML, 2024, innsendingsformaal="klage"))
        info = root.find(f"{{{_NS}}}innsendingsinformasjon")
        assert info.find(f"{{{_NS}}}innsendingsformaal").text == "klage"

    def test_output_er_gyldig_utf8_xml(self):
        result = generer_konvolutt(_DUMMY_XML, 2024, orgnr="922020523")
        assert isinstance(result, bytes)
        result.decode("utf-8")
        fromstring(result.decode("utf-8"))
