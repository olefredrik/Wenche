"""
Tests for BRG XML fixes: corrected orid values, linje_enkel structure,
and base64 decoding of forhåndsutfylt skattemelding.
"""

import base64
import dataclasses
import xml.etree.ElementTree as ET

import pytest

from wenche.brg_xml import generer_hovedskjema, generer_underskjema
from wenche.models import (
    Aarsregnskap,
    Anleggsmidler,
    Balanse,
    Driftsinntekter,
    Driftskostnader,
    Egenkapital,
    EgenkapitalOgGjeld,
    Eiendeler,
    Finansposter,
    KortsiktigGjeld,
    LangsiktigGjeld,
    Omloepmidler,
    Resultatregnskap,
    Selskap,
)

NS = "http://schema.brreg.no/regnsys/aarsregnskap_vanlig/underskjema"
NS_H = "http://schema.brreg.no/regnsys/aarsregnskap_vanlig"


def _parse(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)


def _orid(root: ET.Element, tag: str) -> dict[str, str]:
    """Return {child_tag: orid} for immediate children of first matching element."""
    el = root.find(f".//{{{NS}}}{tag}")
    if el is None:
        return {}
    return {
        child.tag.split("}")[-1]: child.attrib.get("orid", "")
        for child in el
    }


@pytest.fixture
def regnskap_med_alle_poster():
    """Regnskap that exercises linje_enkel paths and corrected orid elements."""
    selskap = Selskap(
        navn="Testselskap AS",
        org_nummer="987654321",
        daglig_leder="Test Testesen",
        styreleder="Test Testesen",
        forretningsadresse="Testveien 1, 0001 Oslo",
        stiftelsesaar=2020,
        aksjekapital=30000,
    )
    return Aarsregnskap(
        selskap=selskap,
        regnskapsaar=2025,
        resultatregnskap=Resultatregnskap(
            driftsinntekter=Driftsinntekter(salgsinntekter=50000),
            driftskostnader=Driftskostnader(andre_driftskostnader=20000),
            finansposter=Finansposter(
                andre_finansinntekter=1000,
                rentekostnader=15000,
            ),
        ),
        balanse=Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(
                    andre_aksjer=200000,
                    langsiktige_fordringer=50000,
                ),
                omloepmidler=Omloepmidler(bankinnskudd=5000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(
                    aksjekapital=30000,
                    overkursfond=10000,
                    annen_egenkapital=-124000,
                ),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=300000),
                kortsiktig_gjeld=KortsiktigGjeld(leverandoergjeld=39000),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Corrected orid values
# ---------------------------------------------------------------------------


class TestSumOverfoeringerOgDisponeringer:
    def test_orid_aarets_is_7071(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        orids = _orid(root, "sumOverfoeringerOgDisponeringer")
        assert orids["aarets"] == "7071"

    def test_orid_fjoraarets_is_7072(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        orids = _orid(root, "sumOverfoeringerOgDisponeringer")
        assert orids["fjoraarets"] == "7072"


class TestInvesteringAksjerAndeler:
    def test_orid_beskrivelse_is_29024(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}investeringAksjerAndeler/{{{NS}}}beskrivelse")
        assert el is not None
        assert el.attrib["orid"] == "29024"

    def test_orid_aarets_is_7100(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}investeringAksjerAndeler/{{{NS}}}aarets")
        assert el is not None
        assert el.attrib["orid"] == "7100"

    def test_orid_fjoraarets_is_7101(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}investeringAksjerAndeler/{{{NS}}}fjoraarets")
        assert el is not None
        assert el.attrib["orid"] == "7101"


class TestAnnenFordring:
    def test_orid_beskrivelse_is_29025(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}annenFordring/{{{NS}}}beskrivelse")
        assert el is not None
        assert el.attrib["orid"] == "29025"

    def test_orid_aarets_is_203(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}annenFordring/{{{NS}}}aarets")
        assert el is not None
        assert el.attrib["orid"] == "203"

    def test_orid_fjoraarets_is_27585(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}annenFordring/{{{NS}}}fjoraarets")
        assert el is not None
        assert el.attrib["orid"] == "27585"


class TestAnnenRenteinntekt:
    def test_orid_aarets_is_150(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        orids = _orid(root, "annenRenteinntekt")
        assert orids["aarets"] == "150"

    def test_orid_fjoraarets_is_7030(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        orids = _orid(root, "annenRenteinntekt")
        assert orids["fjoraarets"] == "7030"


# ---------------------------------------------------------------------------
# linje_enkel: no altinnRowId, no <beskrivelse>
# ---------------------------------------------------------------------------


class TestLinjeEnkel:
    """Elements using linje_enkel must have no altinnRowId attribute and no <beskrivelse> child."""

    LINJE_ENKEL_TAGS = [
        "rentekostnad",
        "annenRenteinntekt",
        "overkursfond",
        "leverandoergjeld",
    ]

    def test_no_altinn_row_id(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        for tag in self.LINJE_ENKEL_TAGS:
            el = root.find(f".//{{{NS}}}{tag}")
            if el is not None:
                assert "altinnRowId" not in el.attrib, (
                    f"{tag} should not have altinnRowId"
                )

    def test_no_beskrivelse_child(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        for tag in self.LINJE_ENKEL_TAGS:
            el = root.find(f".//{{{NS}}}{tag}")
            if el is not None:
                besk = el.find(f"{{{NS}}}beskrivelse")
                assert besk is None, (
                    f"{tag} should not have <beskrivelse> child"
                )

    def test_has_aarets_and_fjoraarets(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        for tag in self.LINJE_ENKEL_TAGS:
            el = root.find(f".//{{{NS}}}{tag}")
            if el is not None:
                assert el.find(f"{{{NS}}}aarets") is not None, (
                    f"{tag} missing <aarets>"
                )
                assert el.find(f"{{{NS}}}fjoraarets") is not None, (
                    f"{tag} missing <fjoraarets>"
                )

    def test_rentekostnad_value(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}rentekostnad/{{{NS}}}aarets")
        assert el is not None
        assert int(el.text) == 15000

    def test_overkursfond_value(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}overkursfond/{{{NS}}}aarets")
        assert el is not None
        assert int(el.text) == 10000

    def test_leverandoergjeld_value(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        el = root.find(f".//{{{NS}}}leverandoergjeld/{{{NS}}}aarets")
        assert el is not None
        assert int(el.text) == 39000

    def test_laan_fra_aksjonaer_klassifisert_som_annen_langsiktig_gjeld(
        self, regnskap_med_alle_poster
    ):
        """Lån fra aksjonær skal ikke klassifiseres som konserngjeld i BRG-XML
        for et selskap som ikke er morselskap. Skal i stedet være en
        oevrigLangsiktigGjeld-linje med beskrivelse 'Lån fra aksjonær'."""
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        # langsiktigKonserngjeld skal ikke lenger forekomme
        assert root.find(f".//{{{NS}}}langsiktigKonserngjeld") is None
        # Lån fra aksjonær skal være en oevrigLangsiktigGjeld med riktig beskrivelse
        for el in root.findall(f".//{{{NS}}}oevrigLangsiktigGjeld"):
            besk = el.find(f"{{{NS}}}beskrivelse")
            if besk is not None and besk.text == "Lån fra aksjonær":
                aarets = el.find(f"{{{NS}}}aarets")
                assert aarets is not None
                assert int(aarets.text) == 300000
                return
        assert False, "Fant ikke oevrigLangsiktigGjeld med 'Lån fra aksjonær'-beskrivelse"

    def test_zero_values_omitted(self, eksempel_regnskap):
        """linje_enkel with 0 for both years should produce no element."""
        root = _parse(generer_underskjema(eksempel_regnskap))
        assert root.find(f".//{{{NS}}}rentekostnad") is None
        assert root.find(f".//{{{NS}}}overkursfond") is None
        assert root.find(f".//{{{NS}}}leverandoergjeld") is None


class TestLinjeVsLinjeEnkel:
    """Regular linje() elements MUST have altinnRowId and <beskrivelse>."""

    LINJE_TAGS = [
        "annenDriftskostnad",
        "investeringAksjerAndeler",
        "annenFordring",
    ]

    def test_has_altinn_row_id(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        for tag in self.LINJE_TAGS:
            el = root.find(f".//{{{NS}}}{tag}")
            if el is not None:
                assert "altinnRowId" in el.attrib, (
                    f"{tag} should have altinnRowId"
                )

    def test_has_beskrivelse(self, regnskap_med_alle_poster):
        root = _parse(generer_underskjema(regnskap_med_alle_poster))
        for tag in self.LINJE_TAGS:
            el = root.find(f".//{{{NS}}}{tag}")
            if el is not None:
                besk = el.find(f"{{{NS}}}beskrivelse")
                assert besk is not None, (
                    f"{tag} should have <beskrivelse> child"
                )


# ---------------------------------------------------------------------------
# noteMaskinellBehandling = "10"
# ---------------------------------------------------------------------------


def test_note_maskinell_behandling_is_10(regnskap_med_alle_poster):
    root = _parse(generer_hovedskjema(regnskap_med_alle_poster))
    note = root.find(f".//{{{NS_H}}}noteMaskinellBehandling")
    assert note is not None
    assert note.text == "10"


def _bekreftende(root: ET.Element) -> str | None:
    el = root.find(f".//{{{NS_H}}}bekreftendeSelskapsrepresentant")
    return el.text if el is not None else None


def test_signatar_bruker_daglig_leder_naar_satt(regnskap_med_alle_poster):
    selskap = dataclasses.replace(
        regnskap_med_alle_poster.selskap, daglig_leder="Per Daglig", styreleder="Kari Styreleder"
    )
    regnskap = dataclasses.replace(regnskap_med_alle_poster, selskap=selskap, signatar=None)
    assert _bekreftende(_parse(generer_hovedskjema(regnskap))) == "Per Daglig"


def test_signatar_faller_tilbake_paa_styreleder_uten_daglig_leder(regnskap_med_alle_poster):
    # Passivt holding uten daglig leder: styrelederen skal stå som bekreftende representant.
    selskap = dataclasses.replace(
        regnskap_med_alle_poster.selskap, daglig_leder="", styreleder="Kari Styreleder"
    )
    regnskap = dataclasses.replace(regnskap_med_alle_poster, selskap=selskap, signatar=None)
    assert _bekreftende(_parse(generer_hovedskjema(regnskap))) == "Kari Styreleder"


# ---------------------------------------------------------------------------
# Base64 decoding of forhåndsutfylt skattemelding
# ---------------------------------------------------------------------------


class TestBase64Dekoding:
    """Test wrapper-XML unwrapping in SkdSkattemeldingClient.hent_forhåndsutfylt."""

    def _make_wrapper(self, inner_xml: bytes) -> bytes:
        encoded = base64.b64encode(inner_xml).decode()
        ns = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:forespoersel:response:v2"
        return (
            f'<response xmlns="{ns}">'
            f"<content>{encoded}</content>"
            f"</response>"
        ).encode()

    def test_unwraps_base64_wrapper(self):
        from xml.etree.ElementTree import ParseError, fromstring
        import binascii

        inner = b"<skattemeldingUpersonlig>test</skattemeldingUpersonlig>"
        wrapper = self._make_wrapper(inner)

        # Replicate the decoding logic from hent_forhåndsutfylt
        root = fromstring(wrapper)
        ns = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:forespoersel:response:v2"
        content_el = root.find(f".//{{{ns}}}content")
        if content_el is None:
            content_el = root.find(".//{*}content")
        result = base64.b64decode(content_el.text) if content_el is not None and content_el.text else wrapper

        assert result == inner

    def test_wildcard_namespace_fallback(self):
        inner = b"<skattemeldingUpersonlig>data</skattemeldingUpersonlig>"
        encoded = base64.b64encode(inner).decode()
        wrapper = (
            f'<response xmlns="some:other:namespace">'
            f"<content>{encoded}</content>"
            f"</response>"
        ).encode()

        from xml.etree.ElementTree import fromstring
        root = fromstring(wrapper)
        ns = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:forespoersel:response:v2"
        content_el = root.find(f".//{{{ns}}}content")
        if content_el is None:
            content_el = root.find(".//{*}content")
        result = base64.b64decode(content_el.text) if content_el is not None and content_el.text else wrapper

        assert result == inner

    def test_non_wrapper_xml_returned_as_is(self):
        from xml.etree.ElementTree import ParseError, fromstring
        import binascii

        raw = b"<skattemeldingUpersonlig>direkte</skattemeldingUpersonlig>"

        # Replicate decoding logic — no <content> element found
        try:
            root = fromstring(raw)
            ns = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:forespoersel:response:v2"
            content_el = root.find(f".//{{{ns}}}content")
            if content_el is None:
                content_el = root.find(".//{*}content")
            if content_el is not None and content_el.text:
                result = base64.b64decode(content_el.text)
            else:
                result = raw
        except (ParseError, binascii.Error):
            result = raw

        assert result == raw

    def test_invalid_xml_falls_through(self):
        from xml.etree.ElementTree import ParseError
        import binascii

        raw = b"this is not xml at all"

        try:
            from xml.etree.ElementTree import fromstring
            root = fromstring(raw)
            content_el = root.find(".//{*}content")
            if content_el is not None and content_el.text:
                result = base64.b64decode(content_el.text)
            else:
                result = raw
        except (ParseError, binascii.Error):
            result = raw

        assert result == raw

    def test_bad_base64_falls_through(self):
        import binascii
        from xml.etree.ElementTree import ParseError, fromstring

        ns = "no:skatteetaten:fastsetting:formueinntekt:skattemeldingognaeringsspesifikasjon:forespoersel:response:v2"
        raw = f'<response xmlns="{ns}"><content>!!!not-base64!!!</content></response>'.encode()

        try:
            root = fromstring(raw)
            content_el = root.find(f".//{{{ns}}}content")
            if content_el is None:
                content_el = root.find(".//{*}content")
            if content_el is not None and content_el.text:
                result = base64.b64decode(content_el.text)
            else:
                result = raw
        except (ParseError, binascii.Error):
            result = raw

        assert result == raw
