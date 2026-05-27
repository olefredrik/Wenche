"""
Generator for skattemeldingUpersonlig XML (RF-1028 / v5).

Produserer XML som pakkes inn i konvolutten og sendes til Skatteetaten
via Altinn3. Krever partsnummer fra Skatteetatens forhåndsutfylt-API.

Namespace: urn:no:skatteetaten:fastsetting:formueinntekt:skattemelding:upersonlig:ekstern:v5
XSD: skattemeldingUpersonlig_v5_ekstern.xsd

Felter merket erAvledet="true" i XSD-en beregnes av Skatteetaten fra
næringsoppgaven — disse settes ikke av Wenche.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from wenche.models import Aarsregnskap, SkattemeldingKonfig

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "skattemelding:upersonlig:ekstern:v5"
)


def generer_skattemelding_upersonlig(
    partsnummer: int,
    inntektsaar: int,
    fremfoert_underskudd: int = 0,
    boersnotert: bool | None = None,
    harytelse: bool | None = None,
    samlet_verdi_bak_aksjene: int | None = None,
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
        boersnotert:          Om selskapet er børsnotert. None = utelat opplysningen.
        harytelse:            Om det er ytelser mellom aksjonær/nærstående og selskapet
                              (f.eks. lån fra aksjonær). None = utelat opplysningen.
        samlet_verdi_bak_aksjene: Netto formuesverdi bak selskapets egne aksjer (heltall).
                              None = utelat. Settes som overstyrt verdi.

    Returns:
        XML-bytes klar for innpakking i konvolutt via generer_konvolutt().
    """
    root = Element("skattemelding", xmlns=_NS)

    SubElement(root, "partsnummer").text = str(partsnummer)
    SubElement(root, "inntektsaar").text = str(inntektsaar)

    if fremfoert_underskudd > 0:
        iou = SubElement(root, "inntektOgUnderskudd")
        utf = SubElement(iou, "underskuddTilFremfoering")
        fremfoert = SubElement(utf, "fremfoertUnderskuddFraTidligereAar")
        SubElement(fremfoert, "beloepSomHeltall").text = str(round(fremfoert_underskudd))

    # opplysningOmSkattesubjekt (XSD-pos etter inntektOgUnderskudd). Rekkefølgen
    # erBoersnotert -> harYtelse er bundet av XSD-sekvensen.
    if boersnotert is not None or harytelse is not None:
        opl = SubElement(root, "opplysningOmSkattesubjekt")
        if boersnotert is not None:
            SubElement(opl, "erBoersnotert").text = "true" if boersnotert else "false"
        if harytelse is not None:
            SubElement(
                opl,
                "harYtelseMellomAksjonaerEllerNaerstaaendeOgSelskapEllerSelskapetsDatterselskap",
            ).text = "true" if harytelse else "false"

    # verdsettingAvAksje: netto formuesverdi bak aksjene. Feltet er erAvledet i
    # XSD-en, så verdien settes som overstyrt (erOverstyrt=true).
    if samlet_verdi_bak_aksjene is not None:
        vaa = SubElement(root, "verdsettingAvAksje")
        svb = SubElement(vaa, "samletVerdiBakAksjeneISelskapet")
        beloep = SubElement(svb, "beloep")
        SubElement(beloep, "beloepSomHeltall").text = str(int(round(samlet_verdi_bak_aksjene)))
        erov = SubElement(svb, "erOverstyrt")
        SubElement(erov, "boolsk").text = "true"

    return tostring(root, encoding="unicode").encode("utf-8")


def beregn_verdi_bak_aksjene(
    regnskap: Aarsregnskap, konfig: SkattemeldingKonfig
) -> int | None:
    """
    Beregner netto skattemessig formuesverdi bak selskapets egne aksjer.

    = formuesverdi av aksjene selskapet eier (fra aksjeoppgaven RF-1088S)
      + øvrige formuesposter (bankinnskudd, fordringer)
      - sum gjeld

    Bokført verdi av aksjeposter (anleggsmidler) erstattes av formuesverdien.
    Returnerer None hvis verken formuesverdi_aksjer eller en eksplisitt
    overstyring (samlet_verdi_bak_aksjene) er satt. Gulv på 0.

    NB: dette tallet inngår i grunnlaget for eierens formuesskatt. Sammensetningen
    (netto, før verdsettingsrabatt) bør bekreftes mot Skatteetatens regler.
    """
    if konfig.samlet_verdi_bak_aksjene is not None:
        return max(0, int(round(konfig.samlet_verdi_bak_aksjene)))
    if not konfig.formuesverdi_aksjer:
        return None
    b = regnskap.balanse
    eiendeler_formue = (
        konfig.formuesverdi_aksjer
        + b.eiendeler.omloepmidler.bankinnskudd
        + b.eiendeler.omloepmidler.kortsiktige_fordringer
        + b.eiendeler.anleggsmidler.langsiktige_fordringer
    )
    gjeld = (
        b.egenkapital_og_gjeld.langsiktig_gjeld.sum
        + b.egenkapital_og_gjeld.kortsiktig_gjeld.sum
    )
    return max(0, int(round(eiendeler_formue - gjeld)))


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
    return generer_skattemelding_upersonlig(
        partsnummer=partsnummer,
        inntektsaar=regnskap.regnskapsaar,
        fremfoert_underskudd=int(konfig.underskudd_til_fremfoering),
        boersnotert=konfig.boersnotert,
        harytelse=harytelse,
        samlet_verdi_bak_aksjene=beregn_verdi_bak_aksjene(regnskap, konfig),
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
