"""
Generator for naeringsspesifikasjon XML (RF-1167 / v6).

Produserer næringsoppgaven som pakkes inn i konvolutten og sendes til
Skatteetaten via Altinn3, sammen med skattemeldingUpersonlig.

Namespace: urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6
XSD: naeringsspesifikasjon_v6_ekstern.xsd

Kodeliste: 2025_resultatregnskapOgBalanse.xml
  Feltene erAvledet="true" i XSD-en beregnes også av Skatteetaten, men
  tilbakemeldingen fra en innsending 2026-05 (OFL Holding) viste at SKD
  forventer at vi echo-er våre egne beregnede summer for kryssvalidering.
  Manglende summer flagges som «manglerSkattemelding»/«manglerNaerings-
  opplysninger» i avvikEtterBeregning selv om resultatAvValidering blir
  «validertOK». Wenche emitterer derfor de avledede sumemene eksplisitt.

Implementasjonen dekker en typisk norsk holding AS med:
  - Salgsinntekter (3200) og andre driftsinntekter (3900)
  - Lønnskostnader (5000), avskrivninger (6000), andre driftskostnader (6700)
  - Finansinntekter: utbytte fra datterselskap (8090), andre (8050)
  - Finanskostnader: rentekostnader (8150), andre (8160)
  - Skattekostnad: betalbar skatt på ordinært resultat (8300), tilbakeført som
    permanent forskjell (positivSkattekostnad, kodeliste 2025_permanentForskjellstype)
  - Anleggsmidler: aksjer i datterselskap (1313), andre aksjer (1350),
    langsiktige fordringer (1390)
  - Omløpsmidler: kortsiktige fordringer (1500), bankinnskudd (1920)
  - Egenkapital: aksjekapital (2000), overkurs (2020), annen (2050/2080)
  - Langsiktig gjeld: gjeld til eiere (2250), annen (2290)
  - Kortsiktig gjeld: leverandørgjeld (2400), betalbar skatt (2500),
    offentlige avgifter (2600), annen (2990)
"""

from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement, tostring

from wenche.models import Aarsregnskap, SkattemeldingKonfig
from wenche.skatteberegning import beregn_skatt

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "naeringsspesifikasjon:ekstern:v6"
)


def _beloep_element(parent: Element, tag: str, beloep: float) -> Element:
    """
    Bygger et element av typen BeloepMedSkattemessigeEgenskaper:
      <{tag}>
        <beloep>           <!-- BeloepMedInnkapsling -->
          <beloep>123.00</beloep>
        </beloep>
      </{tag}>

    Beløp rundes til hele kroner (formatet beholder to desimaler, «.00»).
    Skatteetaten avkorter ører i visningen av næringsspesifikasjonen, mens
    årsregnskapet til Brønnøysund (brg_xml.py) rundes til hele kroner. Øre her
    ga derfor 1-krones sprik mellom de to innsendingene og en balanse som ikke
    gikk opp visuelt. Hele kroner gjør innsendingene konsistente; siden både
    linjeposter og de avledede summene (jf. #92) går gjennom denne helperen,
    rundes de likt og SKDs etterBeregning-kryssvalidering forblir ren.
    """
    el = SubElement(parent, tag)
    outer = SubElement(el, "beloep")     # BeloepMedSkattemessigeEgenskaper
    inner = SubElement(outer, "beloep")  # BeloepMedInnkapsling → BeloepMed2Desimaler
    inner.text = f"{round(beloep):.2f}"
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
        <id>KODE</id>
        <type><resultatOgBalanseregnskapstype>KODE</resultatOgBalanseregnskapstype></type>
      </{child_tag}>

    Skatteetaten krever at <id> er lik kodeverdien (resultatOgBalanseregnskaps-
    type), ikke en tilfeldig UUID. Avvik idAvvikerFraKrav ellers.
    """
    el = SubElement(parent, child_tag)
    _beloep_element(el, "beloep", beloep)
    SubElement(el, "id").text = type_kode
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
        <id>KODE</id>
        <beloep><beloep>123.00</beloep></beloep>
        <type><resultatOgBalanseregnskapstype>KODE</resultatOgBalanseregnskapstype></type>
      </{child_tag}>

    Skatteetaten krever at <id> er lik kodeverdien (resultatOgBalanseregnskaps-
    type), ikke en tilfeldig UUID. Avvik idAvvikerFraKrav ellers.
    """
    el = SubElement(parent, child_tag)
    SubElement(el, "id").text = type_kode
    _beloep_element(el, "beloep", beloep)
    type_el = SubElement(el, "type")
    SubElement(type_el, "resultatOgBalanseregnskapstype").text = type_kode


def generer_naeringsspesifikasjon(
    regnskap: Aarsregnskap,
    partsnummer: int,
    konfig: SkattemeldingKonfig | None = None,
) -> bytes:
    """
    Genererer naeringsspesifikasjon XML for innsending til Skatteetaten.

    Næringsoppgaven er obligatorisk for AS — uten den avviser Skatteetaten
    konvolutten. Avledede summer (sumDriftsinntekt, aarsresultat,
    sumBalanseverdiFor*, sumGjeldOgEgenkapital, skattemessigResultat osv.)
    emitteres eksplisitt for å unngå avvik i SKDs etterBeregning.

    Args:
        regnskap:     Årsregnskap med resultatregnskap og balanse.
        partsnummer:  Skatteetatens interne partsnummer (fra forhåndsutfylt API).
        konfig:       Skattemelding-konfigurasjonen. Nødvendig fordi det skattemessige
                      resultatet avhenger av fritaksmetoden og eierandelen: uten den
                      ville næringsspesifikasjonen oppgitt brutto utbytte som
                      skattepliktig inntekt. Utelates den, brukes standardvalgene
                      (fritaksmetoden på, 100 % eierandel).

    Returns:
        XML-bytes klar for innpakking i konvolutt via generer_konvolutt().
    """
    konfig = konfig or SkattemeldingKonfig()
    beregning = beregn_skatt(regnskap.resultatregnskap, konfig)
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

    # Driftsinntekter. sumDriftsinntekt må stå først i Driftsinntekt per XSD.
    driftsinntekt_el = SubElement(resultatregnskap, "driftsinntekt")
    if di.sum:
        _beloep_element(driftsinntekt_el, "sumDriftsinntekt", di.sum)

    if di.salgsinntekter:
        salgsinntekt_el = SubElement(driftsinntekt_el, "salgsinntekt")
        _resultatforekomst(salgsinntekt_el, "inntekt", di.salgsinntekter, "3200")

    if di.andre_driftsinntekter:
        annen_di_el = SubElement(driftsinntekt_el, "annenDriftsinntekt")
        _resultatforekomst(annen_di_el, "inntekt", di.andre_driftsinntekter, "3900")

    # Driftskostnader. sumDriftskostnad må stå først i Driftskostnad per XSD.
    driftskostnad_el = SubElement(resultatregnskap, "driftskostnad")
    if dk.sum:
        _beloep_element(driftskostnad_el, "sumDriftskostnad", dk.sum)

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

    # Sum-finansposter må stå på resultatregnskap-nivå før finansinntekt/-kostnad
    # per XSD-sekvensen.
    if fp.sum_inntekter:
        _beloep_element(resultatregnskap, "sumFinansinntekt", fp.sum_inntekter)
    if fp.sum_kostnader:
        _beloep_element(resultatregnskap, "sumFinanskostnad", fp.sum_kostnader)
    # sumSkattekostnad står etter sumFinanskostnad og før finansinntekt per XSD-sekvensen.
    if res.skattekostnad:
        _beloep_element(resultatregnskap, "sumSkattekostnad", res.skattekostnad)

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

    # Skattekostnad-forekomsten står etter finanskostnad per XSD-sekvensen.
    if res.skattekostnad:
        skattekostnad_el = SubElement(resultatregnskap, "skattekostnad")
        _resultatforekomst(skattekostnad_el, "kostnad", res.skattekostnad, "8300")

    # aarsresultat står sist i Resultatregnskap-sekvensen.
    if res.aarsresultat:
        _beloep_element(resultatregnskap, "aarsresultat", res.aarsresultat)

    # -----------------------------------------------------------------------
    # Balanseregnskap
    # -----------------------------------------------------------------------
    bal = regnskap.balanse
    am = bal.eiendeler.anleggsmidler
    om = bal.eiendeler.omloepmidler
    eg = bal.egenkapital_og_gjeld

    balanseregnskap = SubElement(root, "balanseregnskap")

    # Anleggsmidler. sumBalanseverdiForAnleggsmiddel må stå først per XSD.
    am_poster = [
        (am.aksjer_i_datterselskap, "1313"),
        (am.andre_aksjer, "1350"),
        (am.langsiktige_fordringer, "1390"),
    ]
    am_poster = [(b, k) for b, k in am_poster if b]
    if am_poster or am.sum:
        anleggsmiddel_el = SubElement(balanseregnskap, "anleggsmiddel")
        if am.sum:
            _beloep_element(anleggsmiddel_el, "sumBalanseverdiForAnleggsmiddel", am.sum)
        if am_poster:
            bv_am_el = SubElement(anleggsmiddel_el, "balanseverdiForAnleggsmiddel")
            for beloep, kode in am_poster:
                _balanseforekomst(bv_am_el, "balanseverdi", beloep, kode)

    # Omløpsmidler. sumBalanseverdiForOmloepsmiddel må stå først per XSD.
    om_poster = [
        (om.kortsiktige_fordringer, "1500"),
        (om.bankinnskudd, "1920"),
    ]
    om_poster = [(b, k) for b, k in om_poster if b]
    if om_poster or om.sum:
        omloepsmiddel_el = SubElement(balanseregnskap, "omloepsmiddel")
        if om.sum:
            _beloep_element(omloepsmiddel_el, "sumBalanseverdiForOmloepsmiddel", om.sum)
        if om_poster:
            bv_om_el = SubElement(omloepsmiddel_el, "balanseverdiForOmloepsmiddel")
            for beloep, kode in om_poster:
                _balanseforekomst(bv_om_el, "balanseverdi", beloep, kode)

    # Gjeld og egenkapital
    # XSD-sekvensen i GjeldOgEgenkapital:
    #   sumLangsiktigGjeld -> sumKortsiktigGjeld -> sumEgenkapital
    #   -> langsiktigGjeld -> kortsiktigGjeld -> egenkapital.
    # Feil rekkefølge gjør XML-en ugyldig mot naeringsspesifikasjon_v6 og er
    # årsaken til SMEVB-005 fra Skatteetatens visning-API (SSV-5187).
    gek_el = SubElement(balanseregnskap, "gjeldOgEgenkapital")

    lg = eg.langsiktig_gjeld
    kg = eg.kortsiktig_gjeld
    ek = eg.egenkapital

    if lg.sum:
        _beloep_element(gek_el, "sumLangsiktigGjeld", lg.sum)
    if kg.sum:
        _beloep_element(gek_el, "sumKortsiktigGjeld", kg.sum)
    if ek.sum:
        _beloep_element(gek_el, "sumEgenkapital", ek.sum)

    # Langsiktig gjeld
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
    kg_poster = [
        (kg.leverandoergjeld, "2400"),
        (kg.betalbar_skatt, "2500"),
        (kg.skyldige_offentlige_avgifter, "2600"),
        (kg.annen_kortsiktig_gjeld, "2990"),
    ]
    kg_poster = [(b, k) for b, k in kg_poster if b]
    if kg_poster:
        kortsiktig_gjeld_el = SubElement(gek_el, "kortsiktigGjeld")
        for beloep, kode in kg_poster:
            _balanseforekomst(kortsiktig_gjeld_el, "gjeld", beloep, kode)

    # Egenkapital
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

    # Balanse-totaler står sist i Balanseregnskap-sekvensen.
    if bal.eiendeler.sum:
        _beloep_element(balanseregnskap, "sumBalanseverdiForEiendel", bal.eiendeler.sum)
    gek_total = lg.sum + kg.sum + ek.sum
    if gek_total:
        _beloep_element(balanseregnskap, "sumGjeldOgEgenkapital", gek_total)

    # -----------------------------------------------------------------------
    # BeregnetNaeringsinntekt (XSD-pos: etter balanseregnskap, før virksomhet)
    # For et upersonlig skattesubjekt (AS) fordeles skattemessig resultat på
    # «forekomst 1» (én virksomhet). SKD krysstillegger feltet mot
    # skattemeldingens inntektOgUnderskudd-poster.
    #
    # Grunnlaget er den skattepliktige inntekten slik skatteberegningen definerer den,
    # ikke årsresultatet og ikke resultat før skatt. Forskjellen er reell for et
    # holdingselskap: utbytte som er fritatt etter fritaksmetoden (sktl. § 2-38) er ikke
    # skattepliktig inntekt, mens skattekostnaden ikke er fradragsberettiget (§ 6-1).
    # Én kilde til tallet (skatteberegning.beregn_skatt) gjør at næringsspesifikasjonen
    # og skatteberegningen ikke kan sprike.
    #
    # SKD utleder sitt eget skattemessige resultat som ÅRSRESULTAT + permanente
    # forskjeller. Hver forskjell må derfor emitteres eksplisitt nedenfor, ellers
    # svarer SKD validertMedFeil (avvikNaeringsopplysninger). Verifisert mot tt02
    # 2026-08-05.
    # -----------------------------------------------------------------------
    skattemessig_resultat = beregning.skattepliktig_inntekt_brutto
    # Emitteres også når resultatet er 0, så lenge det er aktivitet i resultatregnskapet.
    # Et holdingselskap med bare fritatt utbytte har legitimt 0 i skattepliktig inntekt, og
    # da savner SKD påstanden vår: de beregner 0 selv og flagger manglerNaeringsopplysninger
    # (verifisert mot tt02 2026-08-05). Et helt hvilende selskap uten poster i det hele tatt
    # skal derimot fortsatt utelate seksjonen, for der forventer ikke SKD den, og innsendingen
    # er ren uten avvik i dag.
    har_resultatposter = bool(
        res.driftsinntekter.sum
        or res.driftskostnader.sum
        or res.finansposter.sum_inntekter
        or res.finansposter.sum_kostnader
        or res.skattekostnad
    )
    if skattemessig_resultat or har_resultatposter:
        bni_el = SubElement(root, "beregnetNaeringsinntekt")
        fordelt_el = SubElement(
            bni_el, "fordeltBeregnetNaeringsinntektForUpersonligSkattepliktig"
        )
        SubElement(fordelt_el, "id").text = "1"
        _beloep_element(fordelt_el, "fordeltSkattemessigResultat", skattemessig_resultat)
        _beloep_element(
            fordelt_el,
            "fordeltSkattemessigResultatEtterKorreksjon",
            skattemessig_resultat,
        )
        _beloep_element(bni_el, "skattemessigResultat", skattemessig_resultat)

    # -----------------------------------------------------------------------
    # ForskjellMellomRegnskapsmessigOgSkattemessigVerdi
    # (XSD-pos: etter beregnetNaeringsinntekt, før virksomhet)
    #
    # Broen mellom regnskapet og skattegrunnlaget. SKD regner årsresultat + tillegg -
    # fradrag og krysstjekker mot skattemessigResultat over, så denne seksjonen må
    # forklare hele differansen. Kodene er hentet fra kodelisten
    # 2025_permanentForskjellstype, og id settes lik koden (samme krav som for
    # resultat- og balanseforekomstene, ellers avvik idAvvikerFraKrav).
    #
    # To forskjeller er aktuelle for et passivt holdingselskap:
    #
    #   Skattekostnaden er ikke fradragsberettiget (sktl. § 6-1) og legges tilbake.
    #
    #   Utbytte som er fritatt etter fritaksmetoden (sktl. § 2-38) er inntektsført i
    #   regnskapet, men er ikke skattepliktig. Hele utbyttet tilbakeføres derfor, og
    #   den skattepliktige delen legges til igjen: 0 ved eierandel >= 90 %, ellers
    #   3 %-sjablonen (§ 2-38 sjette ledd). Uten dette paret oppgav
    #   næringsspesifikasjonen brutto utbytte som skattepliktig inntekt.
    #
    # Regnestykket, med utbytte U, skattepliktig del S og skattekostnad K:
    #   årsresultat + (K + S) - U == resultat før skatt - U + S == skattepliktig inntekt.
    # -----------------------------------------------------------------------
    tillegg: list[tuple[str, float]] = []
    fradrag: list[tuple[str, float]] = []

    if res.skattekostnad > 0:
        tillegg.append(("positivSkattekostnad", res.skattekostnad))
    elif res.skattekostnad < 0:
        fradrag.append(("negativSkattekostnad", abs(res.skattekostnad)))

    # Bare når fritaksmetoden faktisk er anvendt: er den av, er utbyttet skattepliktig i
    # sin helhet, og et par som nullet hverandre ut ville bare vært støy i innsendingen.
    utbytte = res.finansposter.utbytte_fra_datterselskap
    if konfig.anvend_fritaksmetoden and utbytte > 0:
        fradrag.append(("tilbakefoeringAvInntektsfoertUtbytte", utbytte))
        if beregning.skattepliktig_utbytte > 0:
            tillegg.append(
                ("skattepliktigDelAvUtbytterOgUtdelinger", beregning.skattepliktig_utbytte)
            )

    if tillegg or fradrag:
        forskjell_el = SubElement(root, "forskjellMellomRegnskapsmessigOgSkattemessigVerdi")
        # Alle permanentForskjell-elementene først, så de avledede summene, per XSD-sekvensen.
        for kode, beloep in tillegg + fradrag:
            perm_el = SubElement(forskjell_el, "permanentForskjell")
            SubElement(perm_el, "id").text = kode
            type_el = SubElement(perm_el, "permanentForskjellstype")
            SubElement(type_el, "permanentForskjellstype").text = kode
            _beloep_element(perm_el, "beloep", beloep)
        # Avledede summer, emitteres eksplisitt som de øvrige (jf. modulens docstring).
        if tillegg:
            _beloep_element(
                forskjell_el, "sumTilleggINaeringsinntekt", sum(b for _, b in tillegg)
            )
        if fradrag:
            _beloep_element(
                forskjell_el, "sumFradragINaeringsinntekt", sum(b for _, b in fradrag)
            )

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
    # Egenkapitalavstemming (XSD-pos: etter virksomhet, før andreForhold)
    # inngående EK (foregående års utgående) + endring = utgående (avledet).
    # -----------------------------------------------------------------------
    inngaaende_ek = round(regnskap.foregaaende_aar_balanse.egenkapital_og_gjeld.egenkapital.sum)
    utgaaende_ek = round(eg.egenkapital.sum)
    if inngaaende_ek or utgaaende_ek:
        ekavst = SubElement(root, "egenkapitalavstemming")
        _beloep_element(ekavst, "inngaaendeEgenkapital", inngaaende_ek)
        # Endringen utledes fra de allerede rundede verdiene, slik at
        # inngaaende ± endring == utgaaende går nøyaktig opp i hele kroner.
        endring = utgaaende_ek - inngaaende_ek
        # sumTilleggIEgenkapital / sumFradragIEgenkapital må stå før
        # egenkapitalendring-listen per XSD-sekvensen.
        if endring > 0:
            _beloep_element(ekavst, "sumTilleggIEgenkapital", endring)
        elif endring < 0:
            _beloep_element(ekavst, "sumFradragIEgenkapital", abs(endring))
        if endring:
            # aaretsUnderskudd er kategori "fradrag", aaretsOverskudd "tillegg":
            # utgaaende = inngaaende + tillegg - fradrag. Beløpet føres derfor
            # som positiv magnitude, og fortegnet styres av kodevalget.
            kode = "aaretsOverskudd" if endring > 0 else "aaretsUnderskudd"
            endring_el = SubElement(ekavst, "egenkapitalendring")
            # id må være lik kodeverdien (jf. idAvvikerFraKrav-regelen).
            SubElement(endring_el, "id").text = kode
            ekt = SubElement(endring_el, "egenkapitalendringstype")
            SubElement(ekt, "egenkapitalendringstype").text = kode
            _beloep_element(endring_el, "beloep", abs(endring))
        # utgaaendeEgenkapital står sist i Egenkapitalavstemming.
        _beloep_element(ekavst, "utgaaendeEgenkapital", utgaaende_ek)

    # -----------------------------------------------------------------------
    # andreForhold: spesifiser ytelse mellom aksjonær og selskap (lån fra
    # aksjonær). Kreves når opplysningOmSkattesubjekt.harYtelse=true.
    # -----------------------------------------------------------------------
    laan_fra_aksjonaer = eg.langsiktig_gjeld.laan_fra_aksjonaer
    if laan_fra_aksjonaer and laan_fra_aksjonaer > 0:
        andre = SubElement(root, "andreForhold")
        ytelse = SubElement(andre, "ytelseFraAksjonaerDeltakerEllerNaerstaaende")
        laan = SubElement(ytelse, "laan")
        SubElement(laan, "laanesaldoVedUtgangAvInntektsaar").text = str(
            int(round(laan_fra_aksjonaer))
        )

    # -----------------------------------------------------------------------
    # skalBekreftesAvRevisor (obligatorisk)
    # -----------------------------------------------------------------------
    SubElement(root, "skalBekreftesAvRevisor").text = (
        "true" if regnskap.revideres else "false"
    )

    return tostring(root, encoding="unicode").encode("utf-8")
