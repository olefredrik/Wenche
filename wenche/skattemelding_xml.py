"""
Generator for skattemeldingUpersonlig XML (RF-1028 / v5).

Produserer XML som pakkes inn i konvolutten og sendes til Skatteetaten
via Altinn3. Krever partsnummer fra Skatteetatens forhåndsutfylt-API.

Namespace: urn:no:skatteetaten:fastsetting:formueinntekt:skattemelding:upersonlig:ekstern:v5
XSD: skattemeldingUpersonlig_v5_ekstern.xsd

Felter merket erAvledet="true" i XSD-en beregnes også av Skatteetaten, men
en tilbakemelding fra prod-innsending 2026-05 viste at SKD forventer at vi
echo-er våre egne beregnede summer (samletUnderskudd, inntektsfradrag/
underskudd, inntektFoerFradragForEventueltAvgittKonsernbidrag,
fremfoerbartUnderskuddIInntekt) for kryssvalidering. Manglende summer
flagges som «manglerSkattemelding» i avvikEtterBeregning selv om
resultatAvValidering blir «validertOK».
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from wenche.models import Aarsregnskap, SkattemeldingKonfig

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "skattemelding:upersonlig:ekstern:v5"
)


def _overstyrt_heltall(parent: Element, tag: str, verdi: int) -> None:
    """Bygger et StortBeloepSomHeltallMedOverstyring-element med erOverstyrt=true."""
    el = SubElement(parent, tag)
    beloep = SubElement(el, "beloep")
    SubElement(beloep, "beloepSomHeltall").text = str(int(round(verdi)))
    erov = SubElement(el, "erOverstyrt")
    SubElement(erov, "boolsk").text = "true"


def _heltall_med_innkapsling(parent: Element, tag: str, verdi: int) -> None:
    """Bygger et BeloepSomHeltallMedInnkapsling-element (uten erOverstyrt)."""
    el = SubElement(parent, tag)
    SubElement(el, "beloepSomHeltall").text = str(int(round(verdi)))


def generer_skattemelding_upersonlig(
    partsnummer: int,
    inntektsaar: int,
    fremfoert_underskudd: int = 0,
    aarets_underskudd: int = 0,
    boersnotert: bool | None = None,
    harytelse: bool | None = None,
    formue_verdi_foer_rabatt: int | None = None,
    samlet_gjeld: int | None = None,
) -> bytes:
    """
    Genererer skattemeldingUpersonlig XML for innsending til Skatteetaten.

    Args:
        partsnummer:          Skatteetatens interne partsnummer for selskapet.
                              Hentes fra forhåndsutfylt-API (GET /api/skattemelding/v2/{år}/{orgnr})
                              eller Tenor testdatasøk for testmiljø.
        inntektsaar:          Inntektsår (f.eks. 2024).
        fremfoert_underskudd: Fremført underskudd fra tidligere år (kroner, heltall).
                              Korresponderer med konfig.underskudd_til_fremfoering.
                              0 = elementet inkluderes ikke i XML.
        aarets_underskudd:    Årets underskudd (positiv kroner-heltall, magnitude).
                              Fra |min(0, aarsresultat)| når aarsresultat < 0.
                              0 = underskuddsbaserte felter utelates. Når > 0
                              emitteres samletUnderskudd, inntektsfradrag/underskudd,
                              inntektFoerFradragForEventueltAvgittKonsernbidrag,
                              og fremfoerbartUnderskuddIInntekt = aarets +
                              fremfoert. Med disse blir SKDs etterBeregning ren
                              (ingen «manglerSkattemelding»-avvik).
        boersnotert:          Om selskapet er børsnotert. None = utelat opplysningen.
        harytelse:            Om det er ytelser mellom aksjonær/nærstående og selskapet
                              (f.eks. lån fra aksjonær). None = utelat opplysningen.
        formue_verdi_foer_rabatt: Samlet formuesverdi av eiendelene før
                              verdsettingsrabatt (heltall). Settes overstyrt i
                              formueOgGjeld. None = utelat Formue-seksjonen.
        samlet_gjeld:         Sum gjeld (heltall), settes overstyrt i formueOgGjeld.
                              Skatteetaten utleder verdi bak aksjene =
                              formue_verdi_foer_rabatt - samlet_gjeld (gulv 0).

    Returns:
        XML-bytes klar for innpakking i konvolutt via generer_konvolutt().
    """
    root = Element("skattemelding", xmlns=_NS)

    SubElement(root, "partsnummer").text = str(partsnummer)
    SubElement(root, "inntektsaar").text = str(inntektsaar)

    if fremfoert_underskudd > 0 or aarets_underskudd > 0:
        iou = SubElement(root, "inntektOgUnderskudd")
        utf = SubElement(iou, "underskuddTilFremfoering")
        if fremfoert_underskudd > 0:
            fremfoert = SubElement(utf, "fremfoertUnderskuddFraTidligereAar")
            SubElement(fremfoert, "beloepSomHeltall").text = str(
                int(round(fremfoert_underskudd))
            )
        if aarets_underskudd > 0:
            # fremfoerbartUnderskuddIInntekt = årets + fremført fra tidligere år.
            # Står sist i UnderskuddTilFremfoering-sekvensen.
            _overstyrt_heltall(
                utf,
                "fremfoerbartUnderskuddIInntekt",
                aarets_underskudd + fremfoert_underskudd,
            )
        if aarets_underskudd > 0:
            # XSD-sekvens i InntektOgUnderskudd:
            #   underskuddTilFremfoering -> inntekt -> inntektsfradrag
            #   -> inntektFoerFradragForEventueltAvgittKonsernbidrag
            #   -> samletInntekt -> samletUnderskudd
            ifr = SubElement(iou, "inntektsfradrag")
            _heltall_med_innkapsling(ifr, "underskudd", aarets_underskudd)
            _heltall_med_innkapsling(
                iou,
                "inntektFoerFradragForEventueltAvgittKonsernbidrag",
                -aarets_underskudd,
            )
            _overstyrt_heltall(iou, "samletUnderskudd", aarets_underskudd)

    # formueOgGjeld: formuesgrunnlaget bak aksjene. Skatteetaten utleder
    # samletVerdiBakAksjeneISelskapet = samletVerdiFoerVerdsettingsrabatt -
    # samletGjeld (jf. VerdsettingAvAksje.kt). Feltene er erAvledet, så de settes
    # overstyrt slik at Formue-seksjonen vises og verdien utledes korrekt.
    # XSD-pos: etter inntektOgUnderskudd, før opplysningOmSkattesubjekt.
    if formue_verdi_foer_rabatt is not None:
        fog = SubElement(root, "formueOgGjeld")
        _overstyrt_heltall(
            fog, "samletVerdiFoerEventuellVerdsettingsrabatt", formue_verdi_foer_rabatt
        )
        _overstyrt_heltall(fog, "samletGjeld", samlet_gjeld or 0)

    # opplysningOmSkattesubjekt. Rekkefølgen erBoersnotert -> harYtelse er bundet
    # av XSD-sekvensen.
    if boersnotert is not None or harytelse is not None:
        opl = SubElement(root, "opplysningOmSkattesubjekt")
        if boersnotert is not None:
            SubElement(opl, "erBoersnotert").text = "true" if boersnotert else "false"
        if harytelse is not None:
            SubElement(
                opl,
                "harYtelseMellomAksjonaerEllerNaerstaaendeOgSelskapEllerSelskapetsDatterselskap",
            ).text = "true" if harytelse else "false"

    return tostring(root, encoding="unicode").encode("utf-8")


def beregn_formue_inputs(
    regnskap: Aarsregnskap, konfig: SkattemeldingKonfig
) -> tuple[int | None, int | None]:
    """
    Beregner (samletVerdiFoerVerdsettingsrabatt, samletGjeld) for formueOgGjeld.

    Skatteetaten utleder verdi bak aksjene = verdiFoerRabatt - gjeld (gulv 0),
    grunnlaget for eiernes formuesskatt. Formuesverdi av aksjene (aksjeoppgaven
    RF-1088S) erstatter bokført verdi; bank og fordringer regnes til pålydende.

    Returnerer (None, None) hvis verken formuesverdi_aksjer eller en eksplisitt
    overstyring (samlet_verdi_bak_aksjene) er satt.
    """
    b = regnskap.balanse
    samlet_gjeld = int(
        round(
            b.egenkapital_og_gjeld.langsiktig_gjeld.sum
            + b.egenkapital_og_gjeld.kortsiktig_gjeld.sum
        )
    )
    if konfig.samlet_verdi_bak_aksjene is not None:
        netto = max(0, int(round(konfig.samlet_verdi_bak_aksjene)))
        return netto + samlet_gjeld, samlet_gjeld
    if not konfig.formuesverdi_aksjer:
        return None, None
    verdi_foer_rabatt = int(
        round(
            konfig.formuesverdi_aksjer
            + b.eiendeler.omloepmidler.bankinnskudd
            + b.eiendeler.omloepmidler.kortsiktige_fordringer
            + b.eiendeler.anleggsmidler.langsiktige_fordringer
        )
    )
    return verdi_foer_rabatt, samlet_gjeld


def beregn_verdi_bak_aksjene(
    regnskap: Aarsregnskap, konfig: SkattemeldingKonfig
) -> int | None:
    """Netto verdi bak aksjene = verdiFoerRabatt - gjeld (gulv 0). For visning/kontroll."""
    foer, gjeld = beregn_formue_inputs(regnskap, konfig)
    if foer is None:
        return None
    return max(0, foer - (gjeld or 0))


def generer_skattemelding_fra_konfig(
    regnskap: Aarsregnskap, konfig: SkattemeldingKonfig, partsnummer: int
) -> bytes:
    """
    Bygger skattemeldingUpersonlig-XML fra regnskap + konfig.

    Utleder opplysningOmSkattesubjekt (børsnotert, ytelse mellom aksjonær og
    selskap) og verdi bak aksjene, slik at alle kallsteder (CLI, UI) deler samme
    logikk. harytelse utledes fra om det finnes lån fra aksjonær.
    """
    laan_fra_aksjonaer = regnskap.balanse.egenkapital_og_gjeld.langsiktig_gjeld.laan_fra_aksjonaer
    harytelse = bool(laan_fra_aksjonaer and laan_fra_aksjonaer > 0)
    verdi_foer_rabatt, samlet_gjeld = beregn_formue_inputs(regnskap, konfig)
    # Årets underskudd som positiv kroner-magnitude. For et overskuddsår
    # (eller nullresultat) blir det 0 og underskuddsbaserte felter utelates.
    aarets_underskudd = max(0, int(round(-regnskap.resultatregnskap.aarsresultat)))
    return generer_skattemelding_upersonlig(
        partsnummer=partsnummer,
        inntektsaar=regnskap.regnskapsaar,
        fremfoert_underskudd=int(konfig.underskudd_til_fremfoering),
        aarets_underskudd=aarets_underskudd,
        boersnotert=konfig.boersnotert,
        harytelse=harytelse,
        formue_verdi_foer_rabatt=verdi_foer_rabatt,
        samlet_gjeld=samlet_gjeld,
    )


def hent_partsnummer(skattemelding_xml: bytes) -> int:
    """
    Henter partsnummer fra en skattemeldingUpersonlig XML.

    Partsnummer er Skatteetatens interne ID for selskapet og hentes
    fra forhåndsutfylt skattemelding (GET /api/skattemelding/v2/{år}/{orgnr}).

    Raises:
        ValueError: hvis partsnummer ikke finnes i XML-en.
    """
    root = fromstring(skattemelding_xml.decode("utf-8"))
    element = root.find(f"{{{_NS}}}partsnummer")
    if element is None or not element.text:
        raise ValueError(
            "Fant ikke <partsnummer> i skattemelding-XML-en. "
            "Kontroller at XML-en er en gyldig skattemeldingUpersonlig v5."
        )
    return int(element.text)
