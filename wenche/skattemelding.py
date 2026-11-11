"""
Generering av skattemelding for AS (RF-1028 og RF-1167).

Wenche produserer et ferdig utfylt sammendrag lokalt som du bruker som
referanse når du leverer skattemeldingen manuelt på skatteetaten.no.

Innsending via API krever registrering som systemleverandør hos Skatteetaten.
Se modulens docstring i skattemelding.py for detaljer.
"""

import math

from wenche import konfig
from wenche.feil import KonfigFeil
from wenche.models import (
    BALANSEKATEGORIER,
    NAERINGSKATEGORIER,
    Aarsregnskap,
    Balanse,
    NaeringsspesifikasjonPost,
    Resultatregnskap,
    SkattemeldingKonfig,
)

# Re-eksporteres bevisst: kallsteder (endepunkter, tester, CLI) har brukt sm.beregn_skatt
# og sm.SKATTESATS siden før beregningen fikk egen modul.
from wenche.skatteberegning import (
    Skatteberegning,
    beregn_skatt,
    har_fullt_utbyttefritak,
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


_raw = konfig.les_raa
_er_tom = konfig.er_tom


_EIERANDEL_FELT = "skattemelding.eierandel_for_fritaksmetoden"


def _eierandel(verdi) -> float:
    """Leser eierandelen for fritaksmetoden som prosent, med lesbar feil ved ugyldig verdi.

    Tom = 100 % (helt fritatt). Desimaler tillates, med komma eller punktum, fordi grensen for
    fullt fritak er MER enn 90 %: kuttes 90,5 til 90, blir utbyttet feilaktig skattlagt.
    Verdier utenfor 0-100 avvises i stedet for å gi en stille, meningsløs skatteberegning.
    """
    etikett = "Eierandel for fritaksmetoden"
    if _er_tom(verdi):
        return 100.0
    try:
        if isinstance(verdi, str):
            tall = float(verdi.replace("\u00a0", "").replace(" ", "").replace(",", "."))
        else:
            tall = float(verdi)
    except (TypeError, ValueError):
        raise KonfigFeil(
            f"{etikett} må være et tall (fikk {verdi!r}).", felt=_EIERANDEL_FELT
        ) from None
    if not 0 <= tall <= 100:  # avviser også nan og inf
        raise KonfigFeil(
            f"{etikett} må være mellom 0 og 100 % (fikk {verdi!r}).", felt=_EIERANDEL_FELT
        )
    return tall


def valider_skattekonfig(config_fil: str | dict) -> list[str]:
    """Lesbare meldinger for ugyldige verdier i skattemelding-seksjonen. Tom liste betyr OK.

    Bruker samme leser som les_config, så valideringen og beregningen ikke kan være uenige.
    """
    sm_raw = _raw(config_fil).get("skattemelding") or {}
    try:
        _eierandel(sm_raw.get("eierandel_for_fritaksmetoden"))
    except ValueError as e:
        return [str(e)]
    return []


def valider_selskap(config_fil: str | dict) -> list[str]:
    """
    Returnerer lesbare meldinger for selskapsfelt skattemeldingen krever, men som mangler, er
    tomme eller (for tallfeltene) ikke er tall. Tom liste betyr OK.

    Kjøres lokalt før bygging, så et ufullstendig selskap (typisk rett etter en SAF-T-import som
    ikke bærer disse feltene) blir et avvik brukeren kan rette, ikke en naken HTTP 500.

    Tar også med valider_skattekonfig, siden dette er porten alle kallsteder går gjennom før
    skattemeldingen bygges.
    """
    s = (_raw(config_fil).get("selskap")) or {}
    feil: list[str] = []
    for key, etikett in PAAKREVDE_SELSKAPSFELT:
        verdi = s.get(key)
        if verdi is None or _er_tom(verdi):
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
    feil += valider_skattekonfig(config_fil)
    return feil


def les_config(config_fil: str | dict) -> tuple[Aarsregnskap, SkattemeldingKonfig]:
    """Leser config (filsti eller alt parset dict) til (Aarsregnskap, SkattemeldingKonfig)."""
    raw = _raw(config_fil)
    return konfig.les_aarsregnskap(raw), _les_skattekonfig(raw)


def _les_skattekonfig(raw: dict) -> SkattemeldingKonfig:
    """Leser skattemelding-seksjonen av config-en.

    Blanke tallfelt sendes som "" fra skjemaet, så vi tolererer dem (som leserne over) i
    stedet for å la float("")/int("") bli en naken 500. Tomt eierandel = 100 % (helt
    skattefritt), tom samlet_verdi = ingen overstyring.
    """
    sm_raw = raw.get("skattemelding") or {}
    _verdi_override = sm_raw.get("samlet_verdi_bak_aksjene")
    return SkattemeldingKonfig(
        underskudd_til_fremfoering=konfig.tall(
            sm_raw.get("underskudd_til_fremfoering"), "skattemelding.underskudd_til_fremfoering"
        ),
        anvend_fritaksmetoden=bool(sm_raw.get("anvend_fritaksmetoden", True)),
        eierandel_for_fritaksmetoden=_eierandel(sm_raw.get("eierandel_for_fritaksmetoden")),
        boersnotert=bool(sm_raw.get("boersnotert", False)),
        formuesverdi_aksjer=konfig.tall(
            sm_raw.get("formuesverdi_aksjer"), "skattemelding.formuesverdi_aksjer"
        ),
        samlet_verdi_bak_aksjene=(
            None
            if _er_tom(_verdi_override)
            else konfig.tall(_verdi_override, "skattemelding.samlet_verdi_bak_aksjene")
        ),
        naeringsspesifikasjonsposter=_les_naeringsspesifikasjonsposter(raw),
    )


def _les_naeringsspesifikasjonsposter(raw: dict) -> tuple[NaeringsspesifikasjonPost, ...]:
    seksjon = raw.get("naeringsspesifikasjon") or {}
    poster = seksjon.get("poster") or []
    if not isinstance(poster, list):
        raise KonfigFeil("naeringsspesifikasjon.poster må være en liste.")
    resultat: list[NaeringsspesifikasjonPost] = []
    sett: set[tuple[str, str]] = set()
    for nummer, post in enumerate(poster, start=1):
        if not isinstance(post, dict):
            raise KonfigFeil(f"Næringsspesifikasjonspost {nummer} må være et objekt.")
        kategori = str(post.get("kategori") or "").strip()
        kode = str(post.get("kode") or "").strip()
        if kategori not in NAERINGSKATEGORIER:
            raise KonfigFeil(
                f"Næringsspesifikasjonspost {nummer} har ukjent kategori {kategori!r}."
            )
        if len(kode) != 4 or not kode.isdigit():
            raise KonfigFeil(f"Næringsspesifikasjonspost {nummer} må ha en firesifret kode.")
        beloep_raa = post.get("beloep")
        if beloep_raa is None:
            raise KonfigFeil(f"Næringsspesifikasjonspost {nummer} må ha et numerisk beløp.")
        try:
            beloep = float(beloep_raa)
        except (TypeError, ValueError):
            raise KonfigFeil(
                f"Næringsspesifikasjonspost {nummer} må ha et numerisk beløp."
            ) from None
        if not math.isfinite(beloep):
            raise KonfigFeil(f"Næringsspesifikasjonspost {nummer} har ugyldig beløp.")
        if kategori in BALANSEKATEGORIER and beloep < 0:
            raise KonfigFeil(f"Næringsspesifikasjonspost {nummer} må ha positivt balansebeløp.")
        identitet = (kategori, kode)
        if identitet in sett:
            raise KonfigFeil(f"Næringsspesifikasjonen har duplikat for {kategori} kode {kode}.")
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
    resultat = konfig.les_resultat(raw.get("resultatregnskap") or {})
    return beregn_skatt(resultat, _les_skattekonfig(raw)), resultat.skattekostnad


_LINJE = "─" * 60
_BRED = "═" * 60


def _ekk(v: float) -> str:
    return f"{round(v):>12,}".replace(",", " ")


def _ek_rad(label: str, ak: float, ok: float, aek: float) -> str:
    """Rad i egenkapitalnoten: aksjekapital, overkursfond, annen egenkapital og sum."""
    return f"  {label:<20}{_ekk(ak)}{_ekk(ok)}{_ekk(aek)}{_ekk(ak + ok + aek)}"


def _del_resultat(r: Resultatregnskap) -> list[str]:
    """Næringsspesifikasjonens resultatdel, slik regnskapet er ført."""
    fp = r.finansposter
    finansposter = [f"    Utbytte fra datterselskap    {_nok(fp.utbytte_fra_datterselskap)}"]
    # Linjene for utbytte fra andre aksjer og realisasjon av aksjer vises bare når selskapet
    # har slike poster, så rapporten er uendret for alle andre.
    if fp.utbytte_fra_andre_aksjer:
        finansposter.append(f"    Utbytte fra andre aksjer     {_nok(fp.utbytte_fra_andre_aksjer)}")
    finansposter.append(f"    Andre finansinntekter        {_nok(fp.andre_finansinntekter)}")
    if fp.gevinst_ved_realisasjon_av_aksjer:
        finansposter.append(
            f"    Gevinst, realisasjon aksjer  {_nok(fp.gevinst_ved_realisasjon_av_aksjer)}"
        )
    finansposter += [
        f"    Rentekostnader               {_nok(fp.rentekostnader)}",
        f"    Andre finanskostnader        {_nok(fp.andre_finanskostnader)}",
    ]
    if fp.tap_ved_realisasjon_av_aksjer:
        finansposter.append(
            f"    Tap, realisasjon aksjer      {_nok(fp.tap_ved_realisasjon_av_aksjer)}"
        )
    return [
        _LINJE,
        "  NÆRINGSSPESIFIKASJON",
        _LINJE,
        "",
        "  DRIFTSINNTEKTER",
        f"    Salgsinntekter               {_nok(r.driftsinntekter.salgsinntekter)}",
        f"    Andre driftsinntekter        {_nok(r.driftsinntekter.andre_driftsinntekter)}",
        f"  Sum driftsinntekter            {_nok(r.driftsinntekter.sum)}",
        "",
        "  DRIFTSKOSTNADER",
        f"    Lønnskostnader               {_nok(r.driftskostnader.loennskostnader)}",
        f"    Avskrivninger                {_nok(r.driftskostnader.avskrivninger)}",
        f"    Andre driftskostnader        {_nok(r.driftskostnader.andre_driftskostnader)}",
        f"  Sum driftskostnader            {_nok(r.driftskostnader.sum)}",
        "",
        f"  DRIFTSRESULTAT                 {_nok(r.driftsresultat)}",
        "",
        "  FINANSPOSTER",
        *finansposter,
        "",
        f"  RESULTAT FØR SKATT             {_nok(r.resultat_foer_skatt)}",
        f"  Skattekostnad                  {_nok(-r.skattekostnad)}",
        f"  ÅRSRESULTAT                    {_nok(r.aarsresultat)}",
        "",
    ]


def _del_skattemelding(
    r: Resultatregnskap, konfig: SkattemeldingKonfig, beregning: Skatteberegning
) -> list[str]:
    """Skattemeldingens inntekter og fradrag, fram til beregnet skatt og eventuelt underskudd."""
    fp = r.finansposter
    linjer = [
        _LINJE,
        "  SKATTEMELDING FOR AS",
        _LINJE,
        "",
        "  INNTEKTER OG FRADRAG",
        f"    Driftsresultat               {_nok(r.driftsresultat)}",
    ]

    if konfig.anvend_fritaksmetoden and beregning.utbytte > 0:
        if har_fullt_utbyttefritak(konfig) and not fp.utbytte_fra_andre_aksjer:
            linjer.append(f"    Utbytte (100 % fritatt)      {_nok(beregning.fritatt_utbytte)}")
        elif har_fullt_utbyttefritak(konfig):
            # Utbyttet fra datterselskapet er helt fritatt, utbyttet fra andre aksjer får
            # 3 %-sjablonen, så andelen som er fritatt er verken 100 % eller 97 %.
            linjer += [
                f"    Utbytte (fritatt)            {_nok(beregning.fritatt_utbytte)}",
                f"    Utbytte (sjablonregel, 3 %)  {_nok(beregning.skattepliktig_utbytte)}",
            ]
        else:
            linjer += [
                f"    Utbytte (fritatt, 97 %)      {_nok(beregning.fritatt_utbytte)}",
                f"    Utbytte (sjablonregel, 3 %)  {_nok(beregning.skattepliktig_utbytte)}",
            ]
    else:
        linjer.append(f"    Utbytte                      {_nok(beregning.utbytte)}")

    linjer.append(f"    Andre finansinntekter        {_nok(fp.andre_finansinntekter)}")
    if fp.gevinst_ved_realisasjon_av_aksjer:
        if beregning.fritatt_gevinst_aksjer:
            linjer.append(
                f"    Aksjegevinst (100 % fritatt) {_nok(beregning.fritatt_gevinst_aksjer)}"
            )
        else:
            linjer.append(
                f"    Gevinst, realisasjon aksjer  {_nok(fp.gevinst_ved_realisasjon_av_aksjer)}"
            )
    linjer.append(
        f"    Finanskostnader             -{_nok(fp.sum_kostnader - beregning.ikke_fradragsberettiget_tap_aksjer)}"
    )
    if beregning.ikke_fradragsberettiget_tap_aksjer:
        linjer.append(
            f"    Aksjetap (ikke fradrag)      {_nok(beregning.ikke_fradragsberettiget_tap_aksjer)}"
        )
    linjer.append(
        f"  Skattepliktig inntekt (brutto) {_nok(beregning.skattepliktig_inntekt_brutto)}"
    )
    if beregning.fradrag_underskudd > 0:
        linjer.append(f"  Fradrag: fremf. underskudd  -{_nok(beregning.fradrag_underskudd)}")
    linjer += [
        f"  SKATTEPLIKTIG INNTEKT (NETTO)  {_nok(beregning.skattepliktig_inntekt_netto)}",
        "",
        f"  Beregnet skatt (22 %)          {_nok(beregning.beregnet_skatt)}",
        "",
    ]
    if beregning.nytt_underskudd > 0:
        linjer += [
            f"  Underskudd til fremføring      {_nok(beregning.nytt_underskudd)}",
            "  (føres på skattemeldingen under «Underskudd til fremføring»)",
            "",
        ]
    return linjer


def _del_balanse(b: Balanse) -> list[str]:
    """Balansen slik den er ført, eiendeler og egenkapital og gjeld."""
    am, om = b.eiendeler.anleggsmidler, b.eiendeler.omloepmidler
    eg = b.egenkapital_og_gjeld
    ek, lg, kg = eg.egenkapital, eg.langsiktig_gjeld, eg.kortsiktig_gjeld
    return [
        _LINJE,
        "  NÆRINGSSPESIFIKASJON  BALANSE",
        _LINJE,
        "",
        "  EIENDELER",
        "    Anleggsmidler:",
        f"      Aksjer i datterselskap      {_nok(am.aksjer_i_datterselskap)}",
        f"      Andre aksjer                {_nok(am.andre_aksjer)}",
        f"      Langsiktige fordringer      {_nok(am.langsiktige_fordringer)}",
        f"    Sum anleggsmidler             {_nok(am.sum)}",
        "",
        "    Omløpsmidler:",
        f"      Kortsiktige fordringer      {_nok(om.kortsiktige_fordringer)}",
        f"      Bankinnskudd                {_nok(om.bankinnskudd)}",
        f"    Sum omløpsmidler              {_nok(om.sum)}",
        "",
        f"  SUM EIENDELER                  {_nok(b.eiendeler.sum)}",
        "",
        "  EGENKAPITAL OG GJELD",
        "    Egenkapital:",
        f"      Aksjekapital                {_nok(ek.aksjekapital)}",
        f"      Overkursfond                {_nok(ek.overkursfond)}",
        f"      Annen egenkapital           {_nok(ek.annen_egenkapital)}",
        f"    Sum egenkapital               {_nok(ek.sum)}",
        "",
        "    Langsiktig gjeld:",
        f"      Lån fra aksjonær            {_nok(lg.laan_fra_aksjonaer)}",
        f"      Andre langsiktige lån       {_nok(lg.andre_langsiktige_laan)}",
        f"    Sum langsiktig gjeld          {_nok(lg.sum)}",
        "",
        "    Kortsiktig gjeld:",
        f"      Leverandørgjeld             {_nok(kg.leverandoergjeld)}",
        f"      Betalbar skatt              {_nok(kg.betalbar_skatt)}",
        f"      Skyldige offentlige avgifter {_nok(kg.skyldige_offentlige_avgifter)}",
        f"      Annen kortsiktig gjeld      {_nok(kg.annen_kortsiktig_gjeld)}",
        f"    Sum kortsiktig gjeld          {_nok(kg.sum)}",
        "",
        f"  SUM EGENKAPITAL OG GJELD       {_nok(eg.sum)}",
        "",
    ]


def _del_sammenligning(
    r: Resultatregnskap,
    b: Balanse,
    fr: Resultatregnskap,
    fb: Balanse,
    aar: int,
    har_fjoraar: bool,
) -> list[str]:
    """Sammenligningstall (rskl. § 6-6), eller en påminnelse når fjoråret ikke er lagt inn."""
    if not har_fjoraar:
        return [
            "",
            f"  NB: Sammenligningstall for {aar - 1} er ikke lagt inn.",
            "  Legg til 'foregaaende_aar' i config.yaml (påkrevd, jf. rskl. § 6-6).",
            "",
        ]
    netto_finans = r.finansposter.sum_inntekter - r.finansposter.sum_kostnader
    netto_finans_fjor = fr.finansposter.sum_inntekter - fr.finansposter.sum_kostnader
    return [
        "",
        _LINJE,
        "  NÆRINGSSPESIFIKASJON  SAMMENLIGNINGSTALL  (rskl. § 6-6)",
        _LINJE,
        f"                                 {aar:>12}   {aar - 1:>12}",
        f"  Sum driftsinntekter          {_nok2(r.driftsinntekter.sum, fr.driftsinntekter.sum)}",
        f"  Sum driftskostnader          {_nok2(r.driftskostnader.sum, fr.driftskostnader.sum)}",
        f"  Driftsresultat               {_nok2(r.driftsresultat, fr.driftsresultat)}",
        f"  Netto finansposter           {_nok2(netto_finans, netto_finans_fjor)}",
        f"  RESULTAT FØR SKATT           {_nok2(r.resultat_foer_skatt, fr.resultat_foer_skatt)}",
        f"  SUM EIENDELER                {_nok2(b.eiendeler.sum, fb.eiendeler.sum)}",
        f"  SUM EGENKAPITAL OG GJELD     {_nok2(b.egenkapital_og_gjeld.sum, fb.egenkapital_og_gjeld.sum)}",
        "",
    ]


def _del_egenkapitalnote(regnskap: Aarsregnskap, har_fjoraar: bool, aar: int) -> list[str]:
    """Egenkapitalnoten (rskl. § 7-2b): bevegelsen fra 01.01 til 31.12 når fjoråret finnes."""
    ek_ub = regnskap.balanse.egenkapital_og_gjeld.egenkapital
    linjer = [
        "",
        _LINJE,
        "  NOTE: EGENKAPITAL  (rskl. § 7-2b)",
        _LINJE,
        f"  {'':20}{'AK-kapital':>12}{'Overkursfond':>12}{'Annen EK':>12}{'Sum':>12}",
    ]
    ub_rad = _ek_rad(
        f"EK 31.12.{aar}", ek_ub.aksjekapital, ek_ub.overkursfond, ek_ub.annen_egenkapital
    )

    if har_fjoraar:
        aarsresultat = regnskap.resultatregnskap.aarsresultat
        ek_ib = regnskap.foregaaende_aar_balanse.egenkapital_og_gjeld.egenkapital
        delta_ak = ek_ub.aksjekapital - ek_ib.aksjekapital
        delta_ok = ek_ub.overkursfond - ek_ib.overkursfond
        # Det er årets avsetning som reduserer egenkapitalen. Er utbyttet avsatt, gjør
        # utbetalingen året etter bare opp en gjeldspost, og noten skal ikke trekke den en
        # gang til. Samme rekkefølge som i egenkapitalavstemmingen.
        avsatt_utbytte = regnskap.balanse.egenkapital_og_gjeld.kortsiktig_gjeld.avsatt_utbytte
        if avsatt_utbytte:
            utbytte_mot_ek, utbytte_etikett = avsatt_utbytte, "Avsatt utbytte"
        else:
            utbytte_mot_ek, utbytte_etikett = regnskap.utbytte_utbetalt, "Utbytte utbetalt"
        forklart_aek = ek_ib.annen_egenkapital + aarsresultat - utbytte_mot_ek
        andre_aek = ek_ub.annen_egenkapital - forklart_aek

        linjer.append(
            _ek_rad(
                f"EK 01.01.{aar}", ek_ib.aksjekapital, ek_ib.overkursfond, ek_ib.annen_egenkapital
            )
        )
        linjer.append(_ek_rad("Årsresultat", 0, 0, aarsresultat))
        if utbytte_mot_ek != 0:
            linjer.append(_ek_rad(utbytte_etikett, 0, 0, -utbytte_mot_ek))
        if delta_ak != 0 or delta_ok != 0 or andre_aek != 0:
            linjer.append(_ek_rad("Andre endringer", delta_ak, delta_ok, andre_aek))
        linjer.append(ub_rad)
    else:
        linjer += ["  NB: Egenkapitalbevegelse krever foregaaende_aar (rskl. § 7-2b).", ub_rad]

    linjer += ["  (beløp i hele kroner, NOK)", ""]
    return linjer


def _del_kontroller(b: Balanse, skattekostnad: float, beregnet_skatt: float) -> list[str]:
    """Balansekontroll, og kontroll av ført skattekostnad mot beregningen."""
    if b.er_i_balanse():
        linjer = ["  Balansekontroll: OK"]
    else:
        linjer = [f"  ADVARSEL: Balansen stemmer ikke! Differanse: {_nok(b.differanse())}"]

    # Skattekostnaden som faktisk er ført i regnskapet (rskl. § 6-1 nr. 19) er det som sendes
    # inn, ikke beregningen. Wenche fastsetter ikke tallet (beregningen modellerer ikke utsatt
    # skatt eller andre permanente forskjeller enn fritaksmetoden), men et sprik er verdt å se
    # før innsending.
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
    return linjer


def _del_neste_steg(aar: int) -> list[str]:
    return [
        "",
        _BRED,
        "  NESTE STEG",
        _BRED,
        "",
        "  1. Gå til https://www.skatteetaten.no/ og logg inn med BankID.",
        f"  2. Åpne skattemeldingen for AS for {aar}.",
        "  3. Fyll inn tallene fra næringsspesifikasjonen og skattemeldingen ovenfor.",
        "  4. Kontroller at skatteetaten beregner samme skatt.",
        "  5. Send inn innen 31. mai.",
        "",
        _BRED,
    ]


def generer(regnskap: Aarsregnskap, konfig: SkattemeldingKonfig) -> str:
    """
    Genererer et ferdig utfylt sammendrag for RF-1167 og RF-1028, som tekst.
    Hver del av rapporten bygges av sin egen funksjon, i den rekkefølgen de står.
    """
    r, b, s = regnskap.resultatregnskap, regnskap.balanse, regnskap.selskap
    aar = regnskap.regnskapsaar
    fr, fb = regnskap.foregaaende_aar_resultat, regnskap.foregaaende_aar_balanse
    har_fjoraar = fr != Resultatregnskap() or fb != Balanse()
    beregning = beregn_skatt(r, konfig)

    linjer = [
        _BRED,
        f"  SKATTEMELDING FOR AS {aar}",
        f"  {s.navn}  |  Org.nr. {s.org_nummer}",
        _BRED,
        "",
        *_del_resultat(r),
        *_del_skattemelding(r, konfig, beregning),
        *_del_balanse(b),
        *_del_sammenligning(r, b, fr, fb, aar, har_fjoraar),
        *_del_egenkapitalnote(regnskap, har_fjoraar, aar),
        *_del_kontroller(b, r.skattekostnad, beregning.beregnet_skatt),
        *_del_neste_steg(aar),
    ]
    return "\n".join(linjer) + "\n"
