"""
Generering av skattemelding for AS (RF-1028 og RF-1167).

Wenche produserer et ferdig utfylt sammendrag lokalt som du bruker som
referanse når du leverer skattemeldingen manuelt på skatteetaten.no.

Innsending via API krever registrering som systemleverandør hos Skatteetaten.
Se modulens docstring i skattemelding.py for detaljer.
"""

import math

import yaml

from wenche.aarsregnskap import _dato, _les_resultat, _les_balanse, _tall as _belop
# Re-eksporteres bevisst: kallsteder (endepunkter, tester, CLI) har brukt sm.beregn_skatt
# og sm.SKATTESATS siden før beregningen fikk egen modul.
from wenche.skatteberegning import SKATTESATS, Skatteberegning, beregn_skatt
from wenche.models import (
    Aarsregnskap,
    Balanse,
    Resultatregnskap,
    SkattemeldingKonfig,
    Selskap,
    Driftsinntekter,
    Driftskostnader,
    Finansposter,
    Eiendeler,
    Anleggsmidler,
    Omloepmidler,
    EgenkapitalOgGjeld,
    Egenkapital,
    LangsiktigGjeld,
    KortsiktigGjeld,
    BALANSEKATEGORIER,
    NAERINGSKATEGORIER,
    NaeringsspesifikasjonPost,
)


# Selskapsfelt skattemeldingen krever (org-nr utledes på annet vis ved innsending). I motsetning
# til årsregnskapet konverterer skattemeldingen stiftelsesår og aksjekapital til tall, så en tom
# verdi måtte før bli en naken int('')/float('')-500. En SAF-T-import bærer ikke disse feltene
# (issue #130), derfor er en tom verdi et reelt og vanlig tilfelle, ikke en kantsak.
PAAKREVDE_SELSKAPSFELT: list[tuple[str, str]] = [
    ("navn", "Selskapsnavn"),
    ("org_nummer", "Organisasjonsnummer"),
    ("forretningsadresse", "Forretningsadresse"),
    ("stiftelsesaar", "Stiftelsesår"),
    ("aksjekapital", "Aksjekapital"),
]
_NUMERISKE_SELSKAPSFELT = {"stiftelsesaar", "aksjekapital"}


def _raw(config_fil: str | dict) -> dict:
    """Leser config som dict (allerede parset) eller fra YAML-fil."""
    if isinstance(config_fil, dict):
        return config_fil
    with open(config_fil, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _er_tom(verdi) -> bool:
    return verdi is None or (isinstance(verdi, str) and not verdi.strip())


def _tall(verdi, etikett: str, konverter):
    """Konverterer et påkrevd tallfelt med lesbar feil, aldri en rå int('')/float('')-ValueError."""
    if _er_tom(verdi):
        raise ValueError(f"{etikett} mangler i selskapsopplysningene.")
    try:
        return konverter(verdi)
    except (TypeError, ValueError):
        raise ValueError(f"{etikett} må være et tall (fikk {verdi!r}).")


def valider_selskap(config_fil: str | dict) -> list[str]:
    """
    Returnerer lesbare meldinger for selskapsfelt skattemeldingen krever, men som mangler, er
    tomme eller (for tallfeltene) ikke er tall. Tom liste betyr OK.

    Kjøres lokalt før bygging, så et ufullstendig selskap (typisk rett etter en SAF-T-import som
    ikke bærer disse feltene) blir et avvik brukeren kan rette, ikke en naken HTTP 500.
    """
    s = (_raw(config_fil).get("selskap")) or {}
    feil: list[str] = []
    for key, etikett in PAAKREVDE_SELSKAPSFELT:
        verdi = s.get(key)
        if _er_tom(verdi):
            feil.append(f"{etikett} mangler. Fyll inn under selskapsopplysninger.")
        elif key in _NUMERISKE_SELSKAPSFELT:
            try:
                float(verdi)
            except (TypeError, ValueError):
                feil.append(f"{etikett} må være et tall.")
    if _er_tom(s.get("daglig_leder")) and _er_tom(s.get("styreleder")):
        feil.append(
            "Daglig leder eller styreleder mangler. Fyll inn minst én bekreftende "
            "selskapsrepresentant."
        )
    return feil


def les_config(config_fil: str | dict) -> tuple[Aarsregnskap, SkattemeldingKonfig]:
    """Leser config (filsti eller allerede parset dict) og returnerer (Aarsregnskap, SkattemeldingKonfig)."""
    raw = _raw(config_fil)

    s = raw["selskap"]
    selskap = Selskap(
        navn=s["navn"],
        org_nummer=str(s["org_nummer"]),
        daglig_leder=str(s.get("daglig_leder") or ""),
        styreleder=str(s.get("styreleder") or ""),
        forretningsadresse=s["forretningsadresse"],
        stiftelsesaar=_tall(s.get("stiftelsesaar"), "Stiftelsesår", int),
        aksjekapital=_tall(s.get("aksjekapital"), "Aksjekapital", float),
        stiftelsesdato=_dato(s.get("stiftelsesdato")),
    )

    resultatregnskap = _les_resultat(raw["resultatregnskap"])
    balanse = _les_balanse(raw["balanse"])

    fa = raw.get("foregaaende_aar", {})
    foregaaende_resultat = _les_resultat(fa["resultatregnskap"]) if "resultatregnskap" in fa else Resultatregnskap()
    foregaaende_balanse = _les_balanse(fa["balanse"]) if "balanse" in fa else Balanse()

    utbytte_utbetalt = sum(
        float(a.get("utbytte_utbetalt", 0)) for a in raw.get("aksjonaerer", [])
    )

    regnskap = Aarsregnskap(
        selskap=selskap,
        regnskapsaar=int(raw["regnskapsaar"]),
        resultatregnskap=resultatregnskap,
        balanse=balanse,
        foregaaende_aar_resultat=foregaaende_resultat,
        foregaaende_aar_balanse=foregaaende_balanse,
        utbytte_utbetalt=utbytte_utbetalt,
        regnskapsstart=_dato(raw.get("regnskapsstart")),
        regnskapsslutt=_dato(raw.get("regnskapsslutt")),
    )

    return regnskap, _les_skattekonfig(raw)


def _les_skattekonfig(raw: dict) -> SkattemeldingKonfig:
    """Leser skattemelding-seksjonen av config-en.

    Blanke tallfelt sendes som "" fra skjemaet, så vi tolererer dem (som leserne over) i
    stedet for å la float("")/int("") bli en naken 500. Tomt eierandel = 100 % (helt
    skattefritt), tom samlet_verdi = ingen overstyring.
    """
    sm_raw = raw.get("skattemelding") or {}
    _eierandel = sm_raw.get("eierandel_for_fritaksmetoden")
    _verdi_override = sm_raw.get("samlet_verdi_bak_aksjene")
    return SkattemeldingKonfig(
        underskudd_til_fremfoering=_belop(sm_raw.get("underskudd_til_fremfoering")),
        anvend_fritaksmetoden=bool(sm_raw.get("anvend_fritaksmetoden", True)),
        eierandel_for_fritaksmetoden=100 if _er_tom(_eierandel) else int(float(_eierandel)),
        boersnotert=bool(sm_raw.get("boersnotert", False)),
        formuesverdi_aksjer=_belop(sm_raw.get("formuesverdi_aksjer")),
        samlet_verdi_bak_aksjene=None if _er_tom(_verdi_override) else float(_verdi_override),
        naeringsspesifikasjonsposter=_les_naeringsspesifikasjonsposter(raw),
    )


def _les_naeringsspesifikasjonsposter(raw: dict) -> tuple[NaeringsspesifikasjonPost, ...]:
    seksjon = raw.get("naeringsspesifikasjon") or {}
    poster = seksjon.get("poster") or []
    if not isinstance(poster, list):
        raise ValueError("naeringsspesifikasjon.poster må være en liste.")
    resultat: list[NaeringsspesifikasjonPost] = []
    sett: set[tuple[str, str]] = set()
    for nummer, post in enumerate(poster, start=1):
        if not isinstance(post, dict):
            raise ValueError(f"Næringsspesifikasjonspost {nummer} må være et objekt.")
        kategori = str(post.get("kategori") or "").strip()
        kode = str(post.get("kode") or "").strip()
        if kategori not in NAERINGSKATEGORIER:
            raise ValueError(
                f"Næringsspesifikasjonspost {nummer} har ukjent kategori {kategori!r}."
            )
        if len(kode) != 4 or not kode.isdigit():
            raise ValueError(
                f"Næringsspesifikasjonspost {nummer} må ha en firesifret kode."
            )
        try:
            beloep = float(post.get("beloep"))
        except (TypeError, ValueError):
            raise ValueError(
                f"Næringsspesifikasjonspost {nummer} må ha et numerisk beløp."
            )
        if not math.isfinite(beloep):
            raise ValueError(f"Næringsspesifikasjonspost {nummer} har ugyldig beløp.")
        if kategori in BALANSEKATEGORIER and beloep < 0:
            raise ValueError(
                f"Næringsspesifikasjonspost {nummer} må ha positivt balansebeløp."
            )
        identitet = (kategori, kode)
        if identitet in sett:
            raise ValueError(
                f"Næringsspesifikasjonen har duplikat for {kategori} kode {kode}."
            )
        sett.add(identitet)
        resultat.append(NaeringsspesifikasjonPost(kategori, kode, beloep))
    return tuple(sorted(resultat, key=lambda post: (post.kategori, post.kode)))


def _nok(beloep: float) -> str:
    """Formaterer beløp som NOK med tusenskilletegn (rundes til nærmeste krone)."""
    return f"{round(beloep):>12,} kr".replace(",", " ")


def _nok2(aarets: float, fjoraarets: float) -> str:
    """Formaterer to beløp side om side (inneværende og foregående år)."""
    return f"{round(aarets):>12,} kr   {round(fjoraarets):>12,} kr".replace(",", " ")


def beregn_skatt_fra_config(config_fil: str | dict) -> tuple[Skatteberegning, float]:
    """
    Beregner skatten direkte fra en config, og returnerer (beregning, ført skattekostnad).

    Leser bare resultatregnskapet og skattemelding-seksjonen, ikke selskapsopplysningene:
    forslaget hentes fra Tall-steget, der stiftelsesår og aksjekapital godt kan stå tomme
    ennå. les_config ville kastet på dem.
    """
    raw = _raw(config_fil)
    resultat = _les_resultat(raw.get("resultatregnskap") or {})
    return beregn_skatt(resultat, _les_skattekonfig(raw)), resultat.skattekostnad


def generer(regnskap: Aarsregnskap, konfig: SkattemeldingKonfig) -> str:
    """
    Genererer et ferdig utfylt sammendrag for RF-1167 og RF-1028.
    Returnerer teksten som streng.
    """
    r = regnskap.resultatregnskap
    b = regnskap.balanse
    s = regnskap.selskap
    år = regnskap.regnskapsaar
    fr = regnskap.foregaaende_aar_resultat
    fb = regnskap.foregaaende_aar_balanse
    har_fjoraar = fr != Resultatregnskap() or fb != Balanse()

    # --- RF-1167: Næringsoppgave ---

    driftsinntekter = r.driftsinntekter.sum
    driftskostnader = r.driftskostnader.sum
    driftsresultat = r.driftsresultat

    fin_inntekter = r.finansposter.sum_inntekter
    fin_kostnader = r.finansposter.sum_kostnader
    resultat_foer_skatt = r.resultat_foer_skatt

    # --- RF-1028: Skatteberegning ---

    beregning = beregn_skatt(r, konfig)
    utbytte = beregning.utbytte
    fritatt_utbytte = beregning.fritatt_utbytte
    skattepliktig_utbytte = beregning.skattepliktig_utbytte
    skattepliktig_inntekt_brutto = beregning.skattepliktig_inntekt_brutto
    fradrag_underskudd = beregning.fradrag_underskudd
    skattepliktig_inntekt_netto = beregning.skattepliktig_inntekt_netto
    nytt_underskudd = beregning.nytt_underskudd
    beregnet_skatt = beregning.beregnet_skatt
    andre_finansinntekter = r.finansposter.andre_finansinntekter

    # Skattekostnaden som faktisk er ført i regnskapet (rskl. § 6-1 nr. 19). Den, ikke
    # beregningen, er det som sendes inn; avvik mellom de to varsles nedenfor.
    skattekostnad = r.skattekostnad

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
        "  NÆRINGSSPESIFIKASJON",
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
        f"  Skattekostnad                  {_nok(-skattekostnad)}",
        f"  ÅRSRESULTAT                    {_nok(r.aarsresultat)}",
        "",
        linje,
        "  SKATTEMELDING FOR AS",
        linje,
        "",
        "  INNTEKTER OG FRADRAG",
        f"    Driftsresultat               {_nok(driftsresultat)}",
    ]

    if konfig.anvend_fritaksmetoden and utbytte > 0:
        if konfig.eierandel_for_fritaksmetoden >= 90:
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
        "  NÆRINGSSPESIFIKASJON  BALANSE",
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
        f"      Betalbar skatt              {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.betalbar_skatt)}",
        f"      Skyldige offentlige avgifter {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.skyldige_offentlige_avgifter)}",
        f"      Annen kortsiktig gjeld      {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.annen_kortsiktig_gjeld)}",
        f"    Sum kortsiktig gjeld          {_nok(b.egenkapital_og_gjeld.kortsiktig_gjeld.sum)}",
        "",
        f"  SUM EGENKAPITAL OG GJELD       {_nok(b.egenkapital_og_gjeld.sum)}",
        "",
    ]

    if har_fjoraar:
        netto_finans_fjor = fr.finansposter.sum_inntekter - fr.finansposter.sum_kostnader
        linjer += [
            "",
            linje,
            f"  NÆRINGSSPESIFIKASJON  SAMMENLIGNINGSTALL  (rskl. § 6-6)",
            linje,
            f"                                 {år:>12}   {år - 1:>12}",
            f"  Sum driftsinntekter          {_nok2(r.driftsinntekter.sum, fr.driftsinntekter.sum)}",
            f"  Sum driftskostnader          {_nok2(r.driftskostnader.sum, fr.driftskostnader.sum)}",
            f"  Driftsresultat               {_nok2(r.driftsresultat, fr.driftsresultat)}",
            f"  Netto finansposter           {_nok2(r.finansposter.sum_inntekter - r.finansposter.sum_kostnader, netto_finans_fjor)}",
            f"  RESULTAT FØR SKATT           {_nok2(r.resultat_foer_skatt, fr.resultat_foer_skatt)}",
            f"  SUM EIENDELER                {_nok2(b.eiendeler.sum, fb.eiendeler.sum)}",
            f"  SUM EGENKAPITAL OG GJELD     {_nok2(b.egenkapital_og_gjeld.sum, fb.egenkapital_og_gjeld.sum)}",
            "",
        ]
    else:
        linjer += [
            "",
            f"  NB: Sammenligningstall for {år - 1} er ikke lagt inn.",
            f"  Legg til 'foregaaende_aar' i config.yaml (påkrevd, jf. rskl. § 6-6).",
            "",
        ]

    # --- Egenkapitalnote (rskl. § 7-2b) ---

    def _ekk(v: float) -> str:
        return f"{round(v):>12,}".replace(",", " ")

    def _ek_rad(label: str, ak: float, ok: float, aek: float) -> str:
        s = ak + ok + aek
        return f"  {label:<20}{_ekk(ak)}{_ekk(ok)}{_ekk(aek)}{_ekk(s)}"

    aarsresultat = r.aarsresultat
    ek_ub = b.egenkapital_og_gjeld.egenkapital

    linjer += [
        "",
        linje,
        "  NOTE: EGENKAPITAL  (rskl. § 7-2b)",
        linje,
        f"  {'':20}{'AK-kapital':>12}{'Overkursfond':>12}{'Annen EK':>12}{'Sum':>12}",
    ]

    if har_fjoraar:
        ek_ib = fb.egenkapital_og_gjeld.egenkapital
        delta_ak = ek_ub.aksjekapital - ek_ib.aksjekapital
        delta_ok = ek_ub.overkursfond - ek_ib.overkursfond
        forklart_aek = ek_ib.annen_egenkapital + aarsresultat - regnskap.utbytte_utbetalt
        andre_aek = ek_ub.annen_egenkapital - forklart_aek

        linjer.append(_ek_rad(f"EK 01.01.{år}", ek_ib.aksjekapital, ek_ib.overkursfond, ek_ib.annen_egenkapital))
        linjer.append(_ek_rad("Årsresultat", 0, 0, aarsresultat))
        if regnskap.utbytte_utbetalt != 0:
            linjer.append(_ek_rad("Utbytte utbetalt", 0, 0, -regnskap.utbytte_utbetalt))
        if delta_ak != 0 or delta_ok != 0 or andre_aek != 0:
            linjer.append(_ek_rad("Andre endringer", delta_ak, delta_ok, andre_aek))
        linjer.append(_ek_rad(f"EK 31.12.{år}", ek_ub.aksjekapital, ek_ub.overkursfond, ek_ub.annen_egenkapital))
    else:
        linjer += [
            f"  NB: Egenkapitalbevegelse krever foregaaende_aar (rskl. § 7-2b).",
            _ek_rad(f"EK 31.12.{år}", ek_ub.aksjekapital, ek_ub.overkursfond, ek_ub.annen_egenkapital),
        ]

    linjer.append("  (beløp i hele kroner, NOK)")
    linjer.append("")

    if i_balanse:
        linjer.append("  Balansekontroll: OK")
    else:
        linjer.append(f"  ADVARSEL: Balansen stemmer ikke! Differanse: {_nok(differanse)}")

    # Kontroll av ført skattekostnad mot beregningen. Wenche fastsetter ikke tallet
    # (beregningen modellerer ikke utsatt skatt eller andre permanente forskjeller enn
    # fritaksmetoden), men et sprik er verdt å se før innsending.
    avvik_skatt = round(skattekostnad) - round(beregnet_skatt)
    if beregnet_skatt > 0 and round(skattekostnad) == 0:
        linjer += [
            "",
            f"  NB: Beregnet skatt er {_nok(beregnet_skatt).strip()}, men det er ikke ført",
            "  noen skattekostnad i resultatregnskapet. Regnskapsloven § 6-1 krever egen",
            "  linje for skattekostnad før årsresultatet. Fyll inn «Skattekostnad» under",
            "  resultatregnskapet, og «Betalbar skatt» (konto 2500) under kortsiktig gjeld",
            "  hvis skatten ikke er betalt ved årsslutt.",
        ]
    elif avvik_skatt != 0 and (beregnet_skatt > 0 or round(skattekostnad) != 0):
        linjer += [
            "",
            f"  NB: Ført skattekostnad er {_nok(skattekostnad).strip()}, mens Wenche beregner",
            f"  {_nok(beregnet_skatt).strip()} ({_nok(avvik_skatt).strip()} i avvik). Kontroller tallet.",
            "  Avvik er ikke nødvendigvis feil: beregningen dekker ikke utsatt skatt eller",
            "  andre permanente forskjeller enn fritaksmetoden.",
        ]

    linjer += [
        "",
        bred,
        "  NESTE STEG",
        bred,
        "",
        "  1. Gå til https://www.skatteetaten.no/ og logg inn med BankID.",
        "  2. Åpne skattemeldingen for AS for " + str(år) + ".",
        "  3. Fyll inn tallene fra næringsspesifikasjonen og skattemeldingen ovenfor.",
        "  4. Kontroller at skatteetaten beregner samme skatt.",
        "  5. Send inn innen 31. mai.",
        "",
        bred,
    ]

    return "\n".join(linjer) + "\n"
