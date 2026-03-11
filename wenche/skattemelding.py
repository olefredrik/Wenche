"""
Generering av skattemelding for AS (RF-1028 og RF-1167).

Wenche produserer et ferdig utfylt sammendrag lokalt som du bruker som
referanse når du leverer skattemeldingen manuelt på skatteetaten.no.

Innsending via API krever registrering som systemleverandør hos Skatteetaten.
Se modulens docstring i skattemelding.py for detaljer.
"""

import math

import yaml

from wenche.models import (
    Aarsregnskap,
    SkattemeldingKonfig,
    Selskap,
    Resultatregnskap,
    Driftsinntekter,
    Driftskostnader,
    Finansposter,
    Balanse,
    Eiendeler,
    Anleggsmidler,
    Omloepmidler,
    EgenkapitalOgGjeld,
    Egenkapital,
    LangsiktigGjeld,
    KortsiktigGjeld,
)

SKATTESATS = 0.22  # 22 % selskapsskatt


def les_config(config_fil: str) -> tuple[Aarsregnskap, SkattemeldingKonfig]:
    """Leser config.yaml og returnerer (Aarsregnskap, SkattemeldingKonfig)."""
    with open(config_fil, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    s = raw["selskap"]
    selskap = Selskap(
        navn=s["navn"],
        org_nummer=str(s["org_nummer"]),
        daglig_leder=s["daglig_leder"],
        styreleder=s["styreleder"],
        forretningsadresse=s["forretningsadresse"],
        stiftelsesaar=int(s["stiftelsesaar"]),
        aksjekapital=int(s["aksjekapital"]),
    )

    rr = raw["resultatregnskap"]
    resultatregnskap = Resultatregnskap(
        driftsinntekter=Driftsinntekter(**rr["driftsinntekter"]),
        driftskostnader=Driftskostnader(**rr["driftskostnader"]),
        finansposter=Finansposter(**rr["finansposter"]),
    )

    b = raw["balanse"]
    balanse = Balanse(
        eiendeler=Eiendeler(
            anleggsmidler=Anleggsmidler(**b["eiendeler"]["anleggsmidler"]),
            omloepmidler=Omloepmidler(**b["eiendeler"]["omloepmidler"]),
        ),
        egenkapital_og_gjeld=EgenkapitalOgGjeld(
            egenkapital=Egenkapital(**b["egenkapital_og_gjeld"]["egenkapital"]),
            langsiktig_gjeld=LangsiktigGjeld(
                **b["egenkapital_og_gjeld"]["langsiktig_gjeld"]
            ),
            kortsiktig_gjeld=KortsiktigGjeld(
                **b["egenkapital_og_gjeld"]["kortsiktig_gjeld"]
            ),
        ),
    )

    regnskap = Aarsregnskap(
        selskap=selskap,
        regnskapsaar=int(raw["regnskapsaar"]),
        resultatregnskap=resultatregnskap,
        balanse=balanse,
    )

    sm_raw = raw.get("skattemelding", {})
    konfig = SkattemeldingKonfig(
        underskudd_til_fremfoering=int(sm_raw.get("underskudd_til_fremfoering", 0)),
        anvend_fritaksmetoden=bool(sm_raw.get("anvend_fritaksmetoden", True)),
        eierandel_datterselskap=int(sm_raw.get("eierandel_datterselskap", 100)),
    )

    return regnskap, konfig


def _nok(beloep: int) -> str:
    """Formaterer beløp som NOK med tusenskilletegn."""
    return f"{beloep:>12,} kr".replace(",", " ")


def generer(regnskap: Aarsregnskap, konfig: SkattemeldingKonfig) -> str:
    """
    Genererer et ferdig utfylt sammendrag for RF-1167 og RF-1028.
    Returnerer teksten som streng.
    """
    r = regnskap.resultatregnskap
    b = regnskap.balanse
    s = regnskap.selskap
    år = regnskap.regnskapsaar

    # --- RF-1167: Næringsoppgave ---

    driftsinntekter = r.driftsinntekter.sum
    driftskostnader = r.driftskostnader.sum
    driftsresultat = r.driftsresultat

    fin_inntekter = r.finansposter.sum_inntekter
    fin_kostnader = r.finansposter.sum_kostnader
    resultat_foer_skatt = r.resultat_foer_skatt

    # --- RF-1028: Skatteberegning ---

    # Fritaksmetoden (sktl. § 2-38): utbytte fra kvalifiserende selskaper er skattefritt.
    # Ved eierandel < 90 % gjelder sjablonregelen (§ 2-38 sjette ledd): 3 % er skattepliktig.
    # Ved eierandel ≥ 90 % er hele utbyttet fritatt (0 % skattepliktig).
    # Merk: dette er basert på faglig vurdering — sjekk alltid mot gjeldende regelverk.
    utbytte = r.finansposter.utbytte_fra_datterselskap
    if konfig.anvend_fritaksmetoden and utbytte > 0:
        if konfig.eierandel_datterselskap >= 90:
            skattepliktig_utbytte = 0
            fritatt_utbytte = utbytte
        else:
            skattepliktig_utbytte = math.ceil(utbytte * 0.03)
            fritatt_utbytte = utbytte - skattepliktig_utbytte
    else:
        skattepliktig_utbytte = utbytte
        fritatt_utbytte = 0

    # Skattepliktig inntekt før underskuddsfradrag
    andre_finansinntekter = r.finansposter.andre_finansinntekter
    skattepliktig_inntekt_brutto = (
        driftsresultat
        + skattepliktig_utbytte
        + andre_finansinntekter
        - fin_kostnader
    )

    # Fradrag for fremførbart underskudd (kun hvis positiv inntekt)
    if skattepliktig_inntekt_brutto > 0 and konfig.underskudd_til_fremfoering > 0:
        fradrag_underskudd = min(
            konfig.underskudd_til_fremfoering, skattepliktig_inntekt_brutto
        )
    else:
        fradrag_underskudd = 0

    skattepliktig_inntekt_netto = skattepliktig_inntekt_brutto - fradrag_underskudd

    # Underskudd til fremføring neste år
    if skattepliktig_inntekt_brutto < 0:
        nytt_underskudd = konfig.underskudd_til_fremfoering + abs(
            skattepliktig_inntekt_brutto
        )
    else:
        nytt_underskudd = konfig.underskudd_til_fremfoering - fradrag_underskudd

    # Beregnet skatt
    if skattepliktig_inntekt_netto > 0:
        beregnet_skatt = math.ceil(skattepliktig_inntekt_netto * SKATTESATS)
    else:
        beregnet_skatt = 0

    # --- Balansesjekk ---
    i_balanse = b.er_i_balanse()
    differanse = b.differanse()

    # --- Bygg rapport ---
    linje = "─" * 60
    bred = "═" * 60

    linjer = [
        bred,
        f"  SKATTEMELDING FOR AS — {år}",
        f"  {s.navn}  |  Org.nr. {s.org_nummer}",
        bred,
        "",
        linje,
        "  RF-1167  NÆRINGSOPPGAVE",
        linje,
        "",
        "  DRIFTSINNTEKTER",
        f"    Salgsinntekter               {_nok(r.driftsinntekter.salgsinntekter)}",
        f"    Andre driftsinntekter        {_nok(r.driftsinntekter.andre_driftsinntekter)}",
        f"  Sum driftsinntekter            {_nok(driftsinntekter)}",
        "",
        "  DRIFTSKOSTNADER",
        f"    Lønnskostnader               {_nok(r.driftskostnader.loennskostnader)}",
        f"    Avskrivninger                {_nok(r.driftskostnader.avskrivninger)}",
        f"    Andre driftskostnader        {_nok(r.driftskostnader.andre_driftskostnader)}",
        f"  Sum driftskostnader            {_nok(driftskostnader)}",
        "",
        f"  DRIFTSRESULTAT                 {_nok(driftsresultat)}",
        "",
        "  FINANSPOSTER",
        f"    Utbytte fra datterselskap    {_nok(utbytte)}",
        f"    Andre finansinntekter        {_nok(andre_finansinntekter)}",
        f"    Rentekostnader               {_nok(r.finansposter.rentekostnader)}",
        f"    Andre finanskostnader        {_nok(r.finansposter.andre_finanskostnader)}",
        "",
        f"  RESULTAT FØR SKATT             {_nok(resultat_foer_skatt)}",
        f"  Skattekostnad                  {_nok(-beregnet_skatt)}",
        f"  ÅRSRESULTAT                    {_nok(resultat_foer_skatt - beregnet_skatt)}",
        "",
        linje,
        "  RF-1028  SKATTEMELDING FOR AS",
        linje,
        "",
        "  INNTEKTER OG FRADRAG",
        f"    Driftsresultat               {_nok(driftsresultat)}",
    ]

    if konfig.anvend_fritaksmetoden and utbytte > 0:
        if konfig.eierandel_datterselskap >= 90:
            linjer += [
                f"    Utbytte (100 % fritatt)      {_nok(fritatt_utbytte)}",
            ]
        else:
            linjer += [
                f"    Utbytte (fritatt, 97 %)      {_nok(fritatt_utbytte)}",
                f"    Utbytte (sjablonregel, 3 %)  {_nok(skattepliktig_utbytte)}",
            ]
    else:
        linjer += [
            f"    Utbytte                      {_nok(utbytte)}",
        ]

    linjer += [
        f"    Andre finansinntekter        {_nok(andre_finansinntekter)}",
        f"    Finanskostnader             -{_nok(fin_kostnader)}",
        f"  Skattepliktig inntekt (brutto) {_nok(skattepliktig_inntekt_brutto)}",
    ]

    if fradrag_underskudd > 0:
        linjer += [
            f"  Fradrag: fremf. underskudd  -{_nok(fradrag_underskudd)}",
        ]

    linjer += [
        f"  SKATTEPLIKTIG INNTEKT (NETTO)  {_nok(skattepliktig_inntekt_netto)}",
        "",
        f"  Beregnet skatt (22 %)          {_nok(beregnet_skatt)}",
        "",
    ]

    if nytt_underskudd > 0:
        linjer.append(
            f"  Underskudd til fremføring      {_nok(nytt_underskudd)}"
        )
        linjer.append("  (føres på skattemeldingen under «Underskudd til fremføring»)")
        linjer.append("")

    linjer += [
        linje,
        "  RF-1167  BALANSE",
        linje,
        "",
        "  EIENDELER",
        "    Anleggsmidler:",
        f"      Aksjer i datterselskap      {_nok(b.eiendeler.anleggsmidler.aksjer_i_datterselskap)}",
        f"      Andre aksjer                {_nok(b.eiendeler.anleggsmidler.andre_aksjer)}",
        f"      Langsiktige fordringer      {_nok(b.eiendeler.anleggsmidler.langsiktige_fordringer)}",
        f"    Sum anleggsmidler             {_nok(b.eiendeler.anleggsmidler.sum)}",
        "",
        "    Omløpsmidler:",
        f"      Kortsiktige fordringer      {_nok(b.eiendeler.omloepmidler.kortsiktige_fordringer)}",
        f"      Bankinnskudd                {_nok(b.eiendeler.omloepmidler.bankinnskudd)}",
        f"    Sum omløpsmidler              {_nok(b.eiendeler.omloepmidler.sum)}",
        "",
        f"  SUM EIENDELER                  {_nok(b.eiendeler.sum)}",
        "",
        "  EGENKAPITAL OG GJELD",
        "    Egenkapital:",
        f"      Aksjekapital                {_nok(b.egenkapital_og_gjeld.egenkapital.aksjekapital)}",
        f"      Overkursfond                {_nok(b.egenkapital_og_gjeld.egenkapital.overkursfond)}",
        f"      Annen egenkapital           {_nok(b.egenkapital_og_gjeld.egenkapital.annen_egenkapital)}",
        f"    Sum egenkapital               {_nok(b.egenkapital_og_gjeld.egenkapital.sum)}",
        "",
        "    Langsiktig gjeld:",
        f"      Lån fra aksjonær            {_nok(b.egenkapital_og_gjeld.langsiktig_gjeld.laan_fra_aksjonaer)}",
        f"      Andre langsiktige lån       {_nok(b.egenkapital_og_gjeld.langsiktig_gjeld.andre_langsiktige_laan)}",
        f"    Sum langsiktig gjeld          {_nok(b.egenkapital_og_gjeld.langsiktig_gjeld.sum)}",
        "",
        "    Kortsiktig gjeld:",
        f"      Leverandørgjeld             {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.leverandoergjeld)}",
        f"      Skyldige offentlige avgifter {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.skyldige_offentlige_avgifter)}",
        f"      Annen kortsiktig gjeld      {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.annen_kortsiktig_gjeld)}",
        f"    Sum kortsiktig gjeld          {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.sum)}",
        "",
        f"  SUM EGENKAPITAL OG GJELD       {_nok(b.egenkapital_og_gjeld.sum)}",
        "",
    ]

    if i_balanse:
        linjer.append("  Balansekontroll: OK")
    else:
        linjer.append(f"  ADVARSEL: Balansen stemmer ikke! Differanse: {_nok(differanse)}")

    if beregnet_skatt > 0:
        linjer += [
            "",
            f"  NB: Beregnet skatt er {_nok(beregnet_skatt).strip()}. Husk å føre dette",
            "  som «Skyldig skatt» (konto 2500) under kortsiktig gjeld i balansen,",
            "  og kontroller at balansen fortsatt går opp.",
        ]

    linjer += [
        "",
        bred,
        "  NESTE STEG",
        bred,
        "",
        "  1. Gå til https://www.skatteetaten.no/ og logg inn med BankID.",
        "  2. Åpne skattemeldingen for AS for " + str(år) + ".",
        "  3. Fyll inn tallene fra RF-1167 og RF-1028 ovenfor.",
        "  4. Kontroller at skatteetaten beregner samme skatt.",
        "  5. Send inn innen 31. mai.",
        "",
        bred,
    ]

    return "\n".join(linjer) + "\n"
