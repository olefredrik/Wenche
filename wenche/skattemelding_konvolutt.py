"""
Konvolutt-wrapper for skattemelding API-innsending.

Skatteetaten krever at skattemeldingUpersonlig-XML pakkes inn i en
skattemeldingOgNaeringsspesifikasjonRequest-konvolutt (base64-kodet)
før innsending via Altinn3.

Namespace: no:skatteetaten:fastsetting:formueinntekt:
           skattemeldingognaeringsspesifikasjon:request:v2

XSD: skattemeldingognaeringsspesifikasjonrequest_v2.xsd
"""

from __future__ import annotations

import base64
from xml.etree.ElementTree import Element, SubElement, tostring

_NAMESPACE = (
    "no:skatteetaten:fastsetting:formueinntekt:"
    "skattemeldingognaeringsspesifikasjon:request:v2"
)


def generer_konvolutt(
    skattemelding_xml: bytes,
    inntektsaar: int,
    orgnr: str | None = None,
    naeringsspesifikasjon_xml: bytes | None = None,
    innsendingsformaal: str = "egenfastsetting",
    innsendingstype: str = "komplett",
) -> bytes:
    """
    Pakker skattemeldingUpersonlig-XML inn i konvolutten som Skatteetaten krever.

    Args:
        skattemelding_xml:        Rå XML-bytes for skattemeldingUpersonlig.
        inntektsaar:              Inntektsår (f.eks. 2024).
        orgnr:                    Organisasjonsnummer (TIN). Valgfritt, men anbefalt.
        naeringsspesifikasjon_xml: Valgfri næringsoppgave-XML (RF-1167).
        innsendingsformaal:       'egenfastsetting' | 'klage' | 'endringsanmodning'.
        innsendingstype:          'komplett' | 'ikkeKomplett'.

    Returns:
        Ferdig konvolutt som XML-bytes, klar for opplasting til Altinn3.
    """
    if innsendingsformaal not in {"egenfastsetting", "klage", "endringsanmodning"}:
        raise ValueError(f"Ugyldig innsendingsformaal: {innsendingsformaal!r}")
    if innsendingstype not in {"komplett", "ikkeKomplett"}:
        raise ValueError(f"Ugyldig innsendingstype: {innsendingstype!r}")

    root = Element(
        "skattemeldingOgNaeringsspesifikasjonRequest",
        xmlns=_NAMESPACE,
    )

    # --- dokumenter ---
    dokumenter = SubElement(root, "dokumenter")
    _legg_til_dokument(dokumenter, "skattemeldingUpersonlig", skattemelding_xml)
    if naeringsspesifikasjon_xml is not None:
        _legg_til_dokument(dokumenter, "naeringsspesifikasjon", naeringsspesifikasjon_xml)

    # --- inntektsaar ---
    SubElement(root, "inntektsaar").text = str(inntektsaar)

    # --- innsendingsinformasjon ---
    info = SubElement(root, "innsendingsinformasjon")
    SubElement(info, "innsendingstype").text = innsendingstype
    SubElement(info, "opprettetAv").text = "Wenche"
    if orgnr:
        SubElement(info, "tin").text = orgnr
    SubElement(info, "innsendingsformaal").text = innsendingsformaal

    return tostring(root, encoding="unicode").encode("utf-8")


def _legg_til_dokument(
    dokumenter: Element,
    dokumenttype: str,
    xml_bytes: bytes,
) -> None:
    dokument = SubElement(dokumenter, "dokument")
    SubElement(dokument, "type").text = dokumenttype
    SubElement(dokument, "encoding").text = "utf-8"
    SubElement(dokument, "content").text = base64.b64encode(xml_bytes).decode("ascii")
