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


class TestAaretsUnderskudd:
    """
    Tester for de avledede underskuddssumene som SKD krever for å unngå
    «manglerSkattemelding»-avvik i etterBeregning (jf. tilbakemelding 2026-05).
    """

    def test_aarets_underskudd_inkluderer_alle_avledede_summer(self):
        root = _parse(generer_skattemelding_upersonlig(
            12345678, 2024, aarets_underskudd=5000,
        ))
        iou = root.find(f"{{{_NS}}}inntektOgUnderskudd")
        assert iou is not None

        # inntektsfradrag/underskudd = årets underskudd
        ifr = iou.find(f"{{{_NS}}}inntektsfradrag/{{{_NS}}}underskudd/{{{_NS}}}beloepSomHeltall")
        assert ifr is not None and ifr.text == "5000"

        # inntektFoerFradragForEventueltAvgittKonsernbidrag = -underskudd
        ifu = iou.find(
            f"{{{_NS}}}inntektFoerFradragForEventueltAvgittKonsernbidrag/{{{_NS}}}beloepSomHeltall"
        )
        assert ifu is not None and ifu.text == "-5000"

        # samletUnderskudd = årets underskudd. Emitteres UTEN erOverstyrt:
        # feltet er erAvledet, og når påstanden er lik SKDs utkast er
        # overstyring et falskt signal til interessentoppfølgingen (SSV-5187).
        sum_u_el = iou.find(f"{{{_NS}}}samletUnderskudd")
        sum_u = sum_u_el.find(f"{{{_NS}}}beloep/{{{_NS}}}beloepSomHeltall")
        assert sum_u is not None and sum_u.text == "5000"
        assert sum_u_el.find(f"{{{_NS}}}erOverstyrt") is None

    def test_fremfoerbart_er_summen_av_aarets_og_fremfoert(self):
        # Fremført fra tidligere år 1500 + årets underskudd 5000 = 6500
        root = _parse(generer_skattemelding_upersonlig(
            12345678, 2024,
            fremfoert_underskudd=1500,
            aarets_underskudd=5000,
        ))
        utf = root.find(f"{{{_NS}}}inntektOgUnderskudd/{{{_NS}}}underskuddTilFremfoering")
        assert utf is not None

        fra_tidligere = utf.find(
            f"{{{_NS}}}fremfoertUnderskuddFraTidligereAar/{{{_NS}}}beloepSomHeltall"
        )
        assert fra_tidligere is not None and fra_tidligere.text == "1500"

        fremfoerbart_el = utf.find(f"{{{_NS}}}fremfoerbartUnderskuddIInntekt")
        fremfoerbart = fremfoerbart_el.find(
            f"{{{_NS}}}beloep/{{{_NS}}}beloepSomHeltall"
        )
        assert fremfoerbart is not None and fremfoerbart.text == "6500"
        # UTEN erOverstyrt, jf. SSV-5187.
        assert fremfoerbart_el.find(f"{{{_NS}}}erOverstyrt") is None

    def test_aarets_underskudd_uten_fremfoert_genererer_underskuddTilFremfoering(self):
        root = _parse(generer_skattemelding_upersonlig(
            12345678, 2024, aarets_underskudd=4000,
        ))
        utf = root.find(f"{{{_NS}}}inntektOgUnderskudd/{{{_NS}}}underskuddTilFremfoering")
        assert utf is not None
        # Uten fremført fra tidligere år, men med årets underskudd:
        # fremfoerbartUnderskuddIInntekt = 0 + 4000 = 4000
        fremfoerbart = utf.find(
            f"{{{_NS}}}fremfoerbartUnderskuddIInntekt/{{{_NS}}}beloep/{{{_NS}}}beloepSomHeltall"
        )
        assert fremfoerbart is not None and fremfoerbart.text == "4000"
        # fremfoertUnderskuddFraTidligereAar utelates når 0
        assert utf.find(f"{{{_NS}}}fremfoertUnderskuddFraTidligereAar") is None

    def test_uten_underskudd_ingen_avledede_summer(self):
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024))
        assert root.find(f"{{{_NS}}}inntektOgUnderskudd") is None

    def test_output_med_underskudd_er_gyldig_xml(self):
        result = generer_skattemelding_upersonlig(
            12345678, 2024, fremfoert_underskudd=1500, aarets_underskudd=5000,
        )
        fromstring(result.decode("utf-8"))


class TestVerdsettingAvAksje:
    """
    SKD beregner samletVerdiBakAksjeneISelskapet = verdiFoerRabatt - gjeld,
    men forventer at vi echo-er verdien i `verdsettingAvAksje`-blokken for
    å unngå «manglerSkattemelding»-avvik (jf. OFL Holdings 2025-tilbakemelding).

    Feltet emitteres UTEN erOverstyrt-flagget — Skatteetatens PDF-visning
    skjuler verdien fra Formue-seksjonen hvis flagget er satt.
    """

    def test_emit_med_positiv_netto(self):
        root = _parse(generer_skattemelding_upersonlig(
            12345678, 2024,
            formue_verdi_foer_rabatt=72622,
            samlet_gjeld=12682,
        ))
        sva = root.find(
            f"{{{_NS}}}verdsettingAvAksje/{{{_NS}}}samletVerdiBakAksjeneISelskapet"
        )
        assert sva is not None
        assert sva.findtext(f"{{{_NS}}}beloep/{{{_NS}}}beloepSomHeltall") == "59940"
        # Eksplisitt: erOverstyrt skal IKKE være satt
        assert sva.find(f"{{{_NS}}}erOverstyrt") is None

    def test_gulv_paa_null_naar_gjeld_overstiger_formue(self):
        root = _parse(generer_skattemelding_upersonlig(
            12345678, 2024,
            formue_verdi_foer_rabatt=10000,
            samlet_gjeld=15000,
        ))
        verdi = root.find(
            f"{{{_NS}}}verdsettingAvAksje/{{{_NS}}}samletVerdiBakAksjeneISelskapet"
            f"/{{{_NS}}}beloep/{{{_NS}}}beloepSomHeltall"
        )
        assert verdi is not None and verdi.text == "0"

    def test_utelat_naar_formue_ikke_oppgitt(self):
        # Ingen formue-input → ingen verdsettingAvAksje-blokk
        root = _parse(generer_skattemelding_upersonlig(12345678, 2024))
        assert root.find(f"{{{_NS}}}verdsettingAvAksje") is None
