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

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "skattemelding:upersonlig:ekstern:v5"
)


def generer_skattemelding_upersonlig(
    partsnummer: int,
    inntektsaar: int,
    fremfoert_underskudd: int = 0,
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

    return tostring(root, encoding="unicode").encode("utf-8")


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
