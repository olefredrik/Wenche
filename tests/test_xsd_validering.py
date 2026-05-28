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
from wenche.models import SkattemeldingKonfig
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skattemelding_konvolutt import generer_konvolutt
from wenche.skattemelding_xml import (
    beregn_verdi_bak_aksjene,
    generer_skattemelding_fra_konfig,
    generer_skattemelding_upersonlig,
)

etree = pytest.importorskip("lxml.etree")

_XSD_DIR = Path(wenche.__file__).parent / "xsd"
_SM_NS = "{urn:no:skatteetaten:fastsetting:formueinntekt:skattemelding:upersonlig:ekstern:v5}"
_NS_NS = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"

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

    def test_id_er_lik_kode(self, regnskap_med_utbytte):
        # Skatteetaten krever at <id> på hver resultat-/balanseforekomst er lik
        # kodeverdien (resultatOgBalanseregnskapstype), ikke en tilfeldig UUID.
        # Ellers: avvik idAvvikerFraKrav (validertMedFeil → "Ugyldig innsending").
        xml = generer_naeringsspesifikasjon(regnskap_med_utbytte, _PARTSNUMMER)
        root = etree.fromstring(xml)
        ns = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"
        forekomster = 0
        for el in root.iter():
            id_el = el.find(f"{ns}id")
            type_el = el.find(f"{ns}type/{ns}resultatOgBalanseregnskapstype")
            if id_el is not None and type_el is not None:
                forekomster += 1
                assert id_el.text == type_el.text, (
                    f"id ({id_el.text!r}) != kode ({type_el.text!r}) i <{el.tag.replace(ns, '')}>"
                )
        assert forekomster > 0, "Fant ingen forekomster å sjekke"


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


class TestOpplysningOgVerdsettingXsd:
    def test_opplysning_og_formue_validerer(self):
        xml = generer_skattemelding_upersonlig(
            partsnummer=_PARTSNUMMER,
            inntektsaar=2025,
            fremfoert_underskudd=0,
            boersnotert=False,
            harytelse=True,
            formue_verdi_foer_rabatt=72622,
            samlet_gjeld=12682,
        )
        _valider(xml, "skattemeldingUpersonlig_v5_ekstern.xsd")
        root = etree.fromstring(xml)
        opl = root.find(f"{_SM_NS}opplysningOmSkattesubjekt")
        assert opl.findtext(f"{_SM_NS}erBoersnotert") == "false"
        assert opl.find(
            f"{_SM_NS}harYtelseMellomAksjonaerEllerNaerstaaendeOgSelskapEllerSelskapetsDatterselskap"
        ).text == "true"
        # Formue-seksjonen settes overstyrt; Skatteetaten utleder verdi bak aksjene
        # = 72622 - 12682 = 59940.
        fog = root.find(f"{_SM_NS}formueOgGjeld")
        vfr = fog.find(f"{_SM_NS}samletVerdiFoerEventuellVerdsettingsrabatt")
        assert vfr.findtext(f"{_SM_NS}beloep/{_SM_NS}beloepSomHeltall") == "72622"
        assert vfr.find(f"{_SM_NS}erOverstyrt/{_SM_NS}boolsk").text == "true"
        assert fog.find(
            f"{_SM_NS}samletGjeld/{_SM_NS}beloep/{_SM_NS}beloepSomHeltall"
        ).text == "12682"
        # formueOgGjeld skal komme før opplysningOmSkattesubjekt (XSD-sekvens)
        barn = [c.tag.replace(_SM_NS, "") for c in root]
        assert barn.index("formueOgGjeld") < barn.index("opplysningOmSkattesubjekt")
        # verdsettingAvAksje/samletVerdiBakAksjeneISelskapet skal emittes
        # eksplisitt (72622 - 12682 = 59940) for å unngå «manglerSkattemelding»-
        # avvik i SKDs etterBeregning. Plassering: etter opplysningOmSkattesubjekt.
        # UTEN erOverstyrt-flagget — Skatteetatens PDF-visning skjuler verdien
        # fra Formue-seksjonen hvis flagget er satt.
        vav = root.find(f"{_SM_NS}verdsettingAvAksje")
        assert vav is not None
        verdi_bak = vav.find(f"{_SM_NS}samletVerdiBakAksjeneISelskapet")
        assert verdi_bak is not None
        assert verdi_bak.findtext(f"{_SM_NS}beloep/{_SM_NS}beloepSomHeltall") == "59940"
        assert verdi_bak.find(f"{_SM_NS}erOverstyrt") is None
        assert barn.index("opplysningOmSkattesubjekt") < barn.index("verdsettingAvAksje")

    def test_beregn_verdi_bak_aksjene(self, eksempel_regnskap):
        # eksempel_regnskap: aksjer 100000 (bok, erstattes), bank 1200,
        # langsiktig gjeld 105500. formuesverdi 80000 → 80000+1200-105500 < 0 → gulv 0.
        konfig = SkattemeldingKonfig(formuesverdi_aksjer=80000)
        assert beregn_verdi_bak_aksjene(eksempel_regnskap, konfig) == 0
        # Positiv netto:
        konfig2 = SkattemeldingKonfig(formuesverdi_aksjer=200000)
        # 200000 + 1200 - 105500 = 95700
        assert beregn_verdi_bak_aksjene(eksempel_regnskap, konfig2) == 95700
        # Uten formuesverdi og uten override → None
        assert beregn_verdi_bak_aksjene(eksempel_regnskap, SkattemeldingKonfig()) is None
        # Eksplisitt overstyring vinner
        konfig3 = SkattemeldingKonfig(samlet_verdi_bak_aksjene=12345)
        assert beregn_verdi_bak_aksjene(eksempel_regnskap, konfig3) == 12345


class TestEgenkapitalavstemmingOgYtelseXsd:
    def _regnskap_med_foregaaende(self, eksempel_regnskap):
        # Sett inngående EK lik aksjekapital (30000) slik at endring blir
        # negativ (årets underskudd) for eksempel_regnskap (EK-sum < 30000).
        from wenche.models import Balanse, EgenkapitalOgGjeld, Egenkapital
        eksempel_regnskap.foregaaende_aar_balanse = Balanse(
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000),
            )
        )
        return eksempel_regnskap

    def test_egenkapitalavstemming_og_ytelse_validerer(self, eksempel_regnskap):
        r = self._regnskap_med_foregaaende(eksempel_regnskap)
        xml = generer_naeringsspesifikasjon(r, _PARTSNUMMER)
        _valider(xml, "naeringsspesifikasjon_v6_ekstern.xsd")
        root = etree.fromstring(xml)

        ekavst = root.find(f"{_NS_NS}egenkapitalavstemming")
        assert ekavst is not None
        # inngående EK = 30000
        assert ekavst.findtext(
            f"{_NS_NS}inngaaendeEgenkapital/{_NS_NS}beloep/{_NS_NS}beloep"
        ) == "30000.00"
        endring = ekavst.find(f"{_NS_NS}egenkapitalendring")
        kode = endring.findtext(f"{_NS_NS}egenkapitalendringstype/{_NS_NS}egenkapitalendringstype")
        # EK-sum i eksempel_regnskap (30000 - 34300 = -4300) < 30000 → underskudd
        assert kode == "aaretsUnderskudd"
        assert endring.findtext(f"{_NS_NS}id") == kode  # id == kode
        # Beløp føres som positiv magnitude
        beloep = float(endring.findtext(f"{_NS_NS}beloep/{_NS_NS}beloep/{_NS_NS}beloep"))
        assert beloep > 0

        # Ytelse: lån fra aksjonær (105500) spesifisert under andreForhold
        laan = root.find(
            f"{_NS_NS}andreForhold/{_NS_NS}ytelseFraAksjonaerDeltakerEllerNaerstaaende/{_NS_NS}laan"
        )
        assert laan is not None
        assert laan.findtext(f"{_NS_NS}laanesaldoVedUtgangAvInntektsaar") == "105500"
