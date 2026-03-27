"""
Generator for naeringsspesifikasjon XML (RF-1167 / v6).

Produserer næringsoppgaven som pakkes inn i konvolutten og sendes til
Skatteetaten via Altinn3, sammen med skattemeldingUpersonlig.

Namespace: urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6
XSD: naeringsspesifikasjon_v6_ekstern.xsd

Kodeliste: 2025_resultatregnskapOgBalanse.xml
  Feltene erAvledet="true" i XSD-en beregnes av Skatteetaten — disse
  settes ikke av Wenche.

Implementasjonen dekker en typisk norsk holding AS med:
  - Salgsinntekter (3200) og andre driftsinntekter (3900)
  - Lønnskostnader (5000), avskrivninger (6000), andre driftskostnader (6700)
  - Finansinntekter: utbytte fra datterselskap (8090), andre (8050)
  - Finanskostnader: rentekostnader (8150), andre (8160)
  - Anleggsmidler: aksjer i datterselskap (1313), andre aksjer (1350),
    langsiktige fordringer (1390)
  - Omløpsmidler: kortsiktige fordringer (1500), bankinnskudd (1920)
  - Egenkapital: aksjekapital (2000), overkurs (2020), annen (2050/2080)
  - Langsiktig gjeld: gjeld til eiere (2250), annen (2290)
  - Kortsiktig gjeld: leverandørgjeld (2400), offentlige avgifter (2600),
    annen (2990)
"""

from __future__ import annotations

import uuid
from xml.etree.ElementTree import Element, SubElement, tostring

from wenche.models import Aarsregnskap

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "naeringsspesifikasjon:ekstern:v6"
)


def _uid() -> str:
    return str(uuid.uuid4())


def _beloep_element(parent: Element, tag: str, beloep: float) -> Element:
    """
    Bygger et element av typen BeloepMedSkattemessigeEgenskaper:
      <{tag}>
        <beloep>           <!-- BeloepMedInnkapsling -->
          <beloep>123.00</beloep>
        </beloep>
      </{tag}>
    """
    el = SubElement(parent, tag)
    outer = SubElement(el, "beloep")     # BeloepMedSkattemessigeEgenskaper
    inner = SubElement(outer, "beloep")  # BeloepMedInnkapsling → BeloepMed2Desimaler
    inner.text = f"{round(beloep, 2):.2f}"
    return el


def _resultatforekomst(
    parent: Element,
    child_tag: str,
    beloep: float,
    type_kode: str,
) -> None:
    """
    Legger til én Resultatregnskapsforekomst under parent:
      <{child_tag}>
        <beloep><beloep>123.00</beloep></beloep>
        <id>uuid</id>
        <type><resultatOgBalanseregnskapstype>KODE</resultatOgBalanseregnskapstype></type>
      </{child_tag}>
    """
    el = SubElement(parent, child_tag)
    _beloep_element(el, "beloep", beloep)
    SubElement(el, "id").text = _uid()
    type_el = SubElement(el, "type")
    SubElement(type_el, "resultatOgBalanseregnskapstype").text = type_kode


def _balanseforekomst(
    parent: Element,
    child_tag: str,
    beloep: float,
    type_kode: str,
) -> None:
    """
    Legger til én Balanseregnskapsforekomst under parent:
      <{child_tag}>
        <id>uuid</id>
        <beloep><beloep>123.00</beloep></beloep>
        <type><resultatOgBalanseregnskapstype>KODE</resultatOgBalanseregnskapstype></type>
      </{child_tag}>
    """
    el = SubElement(parent, child_tag)
    SubElement(el, "id").text = _uid()
    _beloep_element(el, "beloep", beloep)
    type_el = SubElement(el, "type")
    SubElement(type_el, "resultatOgBalanseregnskapstype").text = type_kode


def generer_naeringsspesifikasjon(
    regnskap: Aarsregnskap,
    partsnummer: int,
) -> bytes:
    """
    Genererer naeringsspesifikasjon XML for innsending til Skatteetaten.

    Næringsoppgaven er obligatorisk for AS — uten den avviser Skatteetaten
    konvolutten. Avledede felt (sumDriftsinntekt osv.) beregnes av
    Skatteetaten og settes ikke her.

    Args:
        regnskap:     Årsregnskap med resultatregnskap og balanse.
        partsnummer:  Skatteetatens interne partsnummer (fra forhåndsutfylt API).

    Returns:
        XML-bytes klar for innpakking i konvolutt via generer_konvolutt().
    """
    root = Element("naeringsspesifikasjon", xmlns=_NS)

    SubElement(root, "partsreferanse").text = str(partsnummer)
    SubElement(root, "inntektsaar").text = str(regnskap.regnskapsaar)

    # -----------------------------------------------------------------------
    # Resultatregnskap
    # -----------------------------------------------------------------------
    res = regnskap.resultatregnskap
    di = res.driftsinntekter
    dk = res.driftskostnader
    fp = res.finansposter

    resultatregnskap = SubElement(root, "resultatregnskap")

    # Driftsinntekter
    driftsinntekt_el = SubElement(resultatregnskap, "driftsinntekt")

    if di.salgsinntekter:
        salgsinntekt_el = SubElement(driftsinntekt_el, "salgsinntekt")
        _resultatforekomst(salgsinntekt_el, "inntekt", di.salgsinntekter, "3200")

    if di.andre_driftsinntekter:
        annen_di_el = SubElement(driftsinntekt_el, "annenDriftsinntekt")
        _resultatforekomst(annen_di_el, "inntekt", di.andre_driftsinntekter, "3900")

    # Driftskostnader
    driftskostnad_el = SubElement(resultatregnskap, "driftskostnad")

    if dk.loennskostnader:
        loenn_el = SubElement(driftskostnad_el, "loennskostnad")
        _resultatforekomst(loenn_el, "kostnad", dk.loennskostnader, "5000")

    annen_dk_poster = [
        (dk.avskrivninger, "6000"),
        (dk.andre_driftskostnader, "6700"),
    ]
    annen_dk_poster = [(b, k) for b, k in annen_dk_poster if b]
    if annen_dk_poster:
        annen_dk_el = SubElement(driftskostnad_el, "annenDriftskostnad")
        for beloep, kode in annen_dk_poster:
            _resultatforekomst(annen_dk_el, "kostnad", beloep, kode)

    # Finansinntekter
    fi_poster = [
        (fp.utbytte_fra_datterselskap, "8090"),
        (fp.andre_finansinntekter, "8050"),
    ]
    fi_poster = [(b, k) for b, k in fi_poster if b]
    if fi_poster:
        finansinntekt_el = SubElement(resultatregnskap, "finansinntekt")
        for beloep, kode in fi_poster:
            _resultatforekomst(finansinntekt_el, "inntekt", beloep, kode)

    # Finanskostnader
    fk_poster = [
        (fp.rentekostnader, "8150"),
        (fp.andre_finanskostnader, "8160"),
    ]
    fk_poster = [(b, k) for b, k in fk_poster if b]
    if fk_poster:
        finanskostnad_el = SubElement(resultatregnskap, "finanskostnad")
        for beloep, kode in fk_poster:
            _resultatforekomst(finanskostnad_el, "kostnad", beloep, kode)

    # -----------------------------------------------------------------------
    # Balanseregnskap
    # -----------------------------------------------------------------------
    bal = regnskap.balanse
    am = bal.eiendeler.anleggsmidler
    om = bal.eiendeler.omloepmidler
    eg = bal.egenkapital_og_gjeld

    balanseregnskap = SubElement(root, "balanseregnskap")

    # Anleggsmidler
    am_poster = [
        (am.aksjer_i_datterselskap, "1313"),
        (am.andre_aksjer, "1350"),
        (am.langsiktige_fordringer, "1390"),
    ]
    am_poster = [(b, k) for b, k in am_poster if b]
    if am_poster:
        anleggsmiddel_el = SubElement(balanseregnskap, "anleggsmiddel")
        bv_am_el = SubElement(anleggsmiddel_el, "balanseverdiForAnleggsmiddel")
        for beloep, kode in am_poster:
            _balanseforekomst(bv_am_el, "balanseverdi", beloep, kode)

    # Omløpsmidler
    om_poster = [
        (om.kortsiktige_fordringer, "1500"),
        (om.bankinnskudd, "1920"),
    ]
    om_poster = [(b, k) for b, k in om_poster if b]
    if om_poster:
        omloepsmiddel_el = SubElement(balanseregnskap, "omloepsmiddel")
        bv_om_el = SubElement(omloepsmiddel_el, "balanseverdiForOmloepsmiddel")
        for beloep, kode in om_poster:
            _balanseforekomst(bv_om_el, "balanseverdi", beloep, kode)

    # Gjeld og egenkapital
    gek_el = SubElement(balanseregnskap, "gjeldOgEgenkapital")

    # Egenkapital
    ek = eg.egenkapital
    ek_poster = [
        (ek.aksjekapital, "2000"),
        (ek.overkursfond, "2020"),
    ]
    # Annen egenkapital: 2050 (positiv) eller 2080 (udekket tap / negativ)
    if ek.annen_egenkapital >= 0:
        ek_poster.append((ek.annen_egenkapital, "2050"))
    else:
        ek_poster.append((abs(ek.annen_egenkapital), "2080"))

    ek_poster = [(b, k) for b, k in ek_poster if b]
    if ek_poster:
        egenkapital_el = SubElement(gek_el, "egenkapital")
        for beloep, kode in ek_poster:
            _balanseforekomst(egenkapital_el, "kapital", beloep, kode)

    # Langsiktig gjeld
    lg = eg.langsiktig_gjeld
    lg_poster = [
        (lg.laan_fra_aksjonaer, "2250"),
        (lg.andre_langsiktige_laan, "2290"),
    ]
    lg_poster = [(b, k) for b, k in lg_poster if b]
    if lg_poster:
        langsiktig_gjeld_el = SubElement(gek_el, "langsiktigGjeld")
        for beloep, kode in lg_poster:
            _balanseforekomst(langsiktig_gjeld_el, "gjeld", beloep, kode)

    # Kortsiktig gjeld
    kg = eg.kortsiktig_gjeld
    kg_poster = [
        (kg.leverandoergjeld, "2400"),
        (kg.skyldige_offentlige_avgifter, "2600"),
        (kg.annen_kortsiktig_gjeld, "2990"),
    ]
    kg_poster = [(b, k) for b, k in kg_poster if b]
    if kg_poster:
        kortsiktig_gjeld_el = SubElement(gek_el, "kortsiktigGjeld")
        for beloep, kode in kg_poster:
            _balanseforekomst(kortsiktig_gjeld_el, "gjeld", beloep, kode)

    # -----------------------------------------------------------------------
    # Virksomhet (obligatorisk)
    # -----------------------------------------------------------------------
    virksomhet = SubElement(root, "virksomhet")

    rpt = SubElement(virksomhet, "regnskapspliktstype")
    SubElement(rpt, "regnskapspliktstype").text = "fullRegnskapsplikt"

    regnskapsperiode = SubElement(virksomhet, "regnskapsperiode")
    start = SubElement(regnskapsperiode, "start")
    SubElement(start, "dato").text = f"{regnskap.regnskapsaar}-01-01"
    slutt = SubElement(regnskapsperiode, "slutt")
    SubElement(slutt, "dato").text = f"{regnskap.regnskapsaar}-12-31"

    vt = SubElement(virksomhet, "virksomhetstype")
    SubElement(vt, "virksomhetstype").text = "oevrigSelskap"

    rt = SubElement(virksomhet, "regeltypeForAarsregnskap")
    SubElement(rt, "regeltypeForAarsregnskap").text = "regnskapslovensReglerForSmaaForetak"

    # -----------------------------------------------------------------------
    # skalBekreftesAvRevisor (obligatorisk)
    # -----------------------------------------------------------------------
    SubElement(root, "skalBekreftesAvRevisor").text = (
        "true" if regnskap.revideres else "false"
    )

    return tostring(root, encoding="unicode").encode("utf-8")
