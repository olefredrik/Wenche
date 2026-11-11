"""
Lesing av config.yaml (eller en alt parset dict) til datamodellene i wenche.models.

Én leser for alle tre innsendingene. Før hadde årsregnskapet, skattemeldingen og
aksjonærregisteroppgaven hver sin, med ulik tvang av tall og datoer, og en manglende seksjon ga
en KeyError som endte som HTTP 500 eller en traceback. Her tvinges alt likt, og det som mangler
eller ikke lar seg lese blir en KonfigFeil med feltstien (`felt`), som CLI-en og web-lagene
viser som en rettbar melding.

Leserne tåler det skjemaet sender: tomme strenger for urørte felt (leses som 0 eller tom
tekst) og hele underseksjoner som mangler i fjorårstallene. Det som må finnes, er seksjonene
selskap, resultatregnskap og balanse, regnskapsåret, selskapets navn, org.nr. og adresse, og
stiftelsesår og aksjekapital som tall.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import yaml

from wenche.feil import KonfigFeil
from wenche.models import (
    Aarsregnskap,
    Aksjonaer,
    Aksjonaerregisteroppgave,
    Anleggsmidler,
    Balanse,
    Driftsinntekter,
    Driftskostnader,
    Egenkapital,
    EgenkapitalOgGjeld,
    Eiendeler,
    Finansposter,
    KortsiktigGjeld,
    LangsiktigGjeld,
    Omloepmidler,
    Resultatregnskap,
    Selskap,
)

# Lesbare navn på seksjonene som må finnes, til feilmeldinger.
SEKSJONSNAVN = {
    "selskap": "Selskapsopplysningene",
    "resultatregnskap": "Resultatregnskapet",
    "balanse": "Balansen",
    "regnskapsaar": "Regnskapsåret",
    "aksjonaerer": "Aksjonærene",
}


# ---------------------------------------------------------------------------
# Byggesteiner: kilde, seksjoner og enkeltfelt
# ---------------------------------------------------------------------------


def les_raa(kilde: str | dict) -> dict:
    """Config som dict: en alt parset dict, eller en YAML-fil. En tom fil er en tom config."""
    if isinstance(kilde, dict):
        return kilde
    with open(kilde, encoding="utf-8") as f:
        raa = yaml.safe_load(f)
    if raa is None:
        return {}
    if not isinstance(raa, dict):
        raise KonfigFeil(
            f"{kilde} inneholder ikke en config (forventet nøkler som selskap og regnskapsaar)."
        )
    return raa


def er_tom(verdi: Any) -> bool:
    return verdi is None or (isinstance(verdi, str) and not verdi.strip())


def seksjon(raa: dict, navn: str) -> dict:
    """En påkrevd seksjon. Mangler den (eller står tom i YAML), er det en KonfigFeil med feltet."""
    verdi = raa.get(navn)
    if verdi is None:
        navn_tekst = SEKSJONSNAVN.get(navn, f"Seksjonen «{navn}»")
        raise KonfigFeil(f"{navn_tekst} mangler i configen.", felt=navn)
    if not isinstance(verdi, dict):
        raise KonfigFeil(f"{navn} i configen må være en seksjon med undernøkler.", felt=navn)
    return verdi


def _hent(s: dict, nokkel: str, felt: str) -> Any:
    """Et felt som må finnes i configen (verdien kan være tom)."""
    if nokkel not in s:
        raise KonfigFeil(f"Feltet «{felt}» mangler i configen.", felt=felt)
    return s[nokkel]


def tekst(verdi: Any) -> str:
    return "" if verdi is None else str(verdi)


def tall(verdi: Any, felt: str = "") -> float:
    """Valgfritt tallfelt. Tomt (None, "", whitespace) er 0.0, ellers float, eller KonfigFeil.

    Skjemaet utelater urørte felt og sender tom streng for blanke. Et passivt holdingselskap
    har legitimt mange slike, særlig i fjorårstallene.
    """
    if er_tom(verdi):
        return 0.0
    try:
        return float(verdi)
    except (TypeError, ValueError):
        raise KonfigFeil(
            f"{felt or 'Feltet'} må være et tall (fikk {verdi!r}).", felt=felt
        ) from None


def _til_heltall(verdi: Any) -> int:
    """int av 2018, '2018' og 2018.0; 2018.5 er en feil."""
    som_tall = float(verdi)
    if not som_tall.is_integer():
        raise ValueError(verdi)
    return int(som_tall)


def heltall(verdi: Any, felt: str = "") -> int:
    """Valgfritt heltallsfelt. Tomt er 0, ellers heltall, eller KonfigFeil."""
    if er_tom(verdi):
        return 0
    try:
        return _til_heltall(verdi)
    except (TypeError, ValueError):
        raise KonfigFeil(
            f"{felt or 'Feltet'} må være et heltall (fikk {verdi!r}).", felt=felt
        ) from None


def paakrevd_tall(
    verdi: Any, felt: str, etikett: str, konverter: Any = float, *, hvor: str = "i configen"
) -> Any:
    """Påkrevd tallfelt med lesbar feil, aldri en rå int('')/float('')-ValueError."""
    if er_tom(verdi):
        raise KonfigFeil(f"{etikett} mangler {hvor}.", felt=felt)
    try:
        return konverter(verdi)
    except (TypeError, ValueError):
        raise KonfigFeil(f"{etikett} må være et tall (fikk {verdi!r}).", felt=felt) from None


def dato(verdi: Any, felt: str = "") -> date | None:
    """Tolererer tomme og manglende datofelt som None, ellers en date.

    YAML tolker en naken YYYY-MM-DD som date, mens skjemaet sender streng. Begge godtas.
    En ugyldig dato blir en lesbar feil, ikke en naken ValueError fra fromisoformat.
    """
    if er_tom(verdi):
        return None
    if isinstance(verdi, date):
        return verdi
    tekst_ = str(verdi).strip()
    # En ISO-datetime ("2025-10-24T00:00:00.000Z") er ikke noe skjemaet sender, men den
    # oppstår når et JS Date serialiseres til JSON. Kilden er rettet (SPA-en parser YAML
    # med CORE_SCHEMA), men gamle lagrede configer kan bære formen, og en dato med
    # tidsdel er utvetydig nok til å ta imot i stedet for å avvise med formatfeil.
    if "T" in tekst_:
        tekst_ = tekst_.split("T", 1)[0]
    try:
        return date.fromisoformat(tekst_)
    except ValueError:
        raise KonfigFeil(
            f"«{verdi}» er ikke en gyldig dato. Bruk formatet ÅÅÅÅ-MM-DD.", felt=felt
        ) from None


def eierandel_eller_none(verdi: Any) -> float | None:
    """Eierandelen som prosent, eller None når den mangler eller ikke er et tall.

    Bare til advarsler. Ugyldige verdier avvises av skattemeldingens validering, så her er det
    nok å ikke kaste.
    """
    if er_tom(verdi):
        return None
    try:
        if isinstance(verdi, str):
            return float(verdi.replace(" ", "").replace(" ", "").replace(",", "."))
        return float(verdi)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Seksjonslesere
# ---------------------------------------------------------------------------


def les_selskap(raa: dict) -> Selskap:
    s = seksjon(raa, "selskap")
    return Selskap(
        navn=tekst(_hent(s, "navn", "selskap.navn")),
        org_nummer=tekst(_hent(s, "org_nummer", "selskap.org_nummer")).strip(),
        daglig_leder=tekst(s.get("daglig_leder")),
        styreleder=tekst(s.get("styreleder")),
        forretningsadresse=tekst(_hent(s, "forretningsadresse", "selskap.forretningsadresse")),
        stiftelsesaar=paakrevd_tall(
            s.get("stiftelsesaar"),
            "selskap.stiftelsesaar",
            "Stiftelsesår",
            _til_heltall,
            hvor="i selskapsopplysningene",
        ),
        aksjekapital=paakrevd_tall(
            s.get("aksjekapital"),
            "selskap.aksjekapital",
            "Aksjekapital",
            hvor="i selskapsopplysningene",
        ),
        kontakt_epost=tekst(s.get("kontakt_epost")),
        stiftelsesdato=dato(s.get("stiftelsesdato"), "selskap.stiftelsesdato"),
        tinginnskudd_ved_stiftelse=tall(
            s.get("tinginnskudd_ved_stiftelse"), "selskap.tinginnskudd_ved_stiftelse"
        ),
    )


def les_resultat(r: dict | None, felt: str = "resultatregnskap") -> Resultatregnskap:
    # .get(..., {}) på hver underseksjon: et delvis utfylt år (typisk fjoråret) utelater hele
    # seksjoner brukeren ikke rørte, så et direkte oppslag ville kastet KeyError.
    r = r or {}
    di = r.get("driftsinntekter") or {}
    dk = r.get("driftskostnader") or {}
    fp = r.get("finansposter") or {}

    def _t(seksjon_: dict, nokkel: str, sti: str) -> float:
        return tall(seksjon_.get(nokkel), f"{felt}.{sti}.{nokkel}")

    return Resultatregnskap(
        driftsinntekter=Driftsinntekter(
            salgsinntekter=_t(di, "salgsinntekter", "driftsinntekter"),
            andre_driftsinntekter=_t(di, "andre_driftsinntekter", "driftsinntekter"),
        ),
        driftskostnader=Driftskostnader(
            loennskostnader=_t(dk, "loennskostnader", "driftskostnader"),
            avskrivninger=_t(dk, "avskrivninger", "driftskostnader"),
            andre_driftskostnader=_t(dk, "andre_driftskostnader", "driftskostnader"),
        ),
        finansposter=Finansposter(
            utbytte_fra_datterselskap=_t(fp, "utbytte_fra_datterselskap", "finansposter"),
            andre_finansinntekter=_t(fp, "andre_finansinntekter", "finansposter"),
            rentekostnader=_t(fp, "rentekostnader", "finansposter"),
            andre_finanskostnader=_t(fp, "andre_finanskostnader", "finansposter"),
            gevinst_ved_realisasjon_av_aksjer=_t(
                fp, "gevinst_ved_realisasjon_av_aksjer", "finansposter"
            ),
            tap_ved_realisasjon_av_aksjer=_t(fp, "tap_ved_realisasjon_av_aksjer", "finansposter"),
            utbytte_fra_andre_aksjer=_t(fp, "utbytte_fra_andre_aksjer", "finansposter"),
        ),
        skattekostnad=tall(r.get("skattekostnad"), f"{felt}.skattekostnad"),
    )


def les_balanse(b: dict | None, felt: str = "balanse") -> Balanse:
    b = b or {}
    eiendeler = b.get("eiendeler") or {}
    am = eiendeler.get("anleggsmidler") or {}
    om = eiendeler.get("omloepmidler") or {}
    ekg = b.get("egenkapital_og_gjeld") or {}
    ek = ekg.get("egenkapital") or {}
    lg = ekg.get("langsiktig_gjeld") or {}
    kg = ekg.get("kortsiktig_gjeld") or {}

    def _t(seksjon_: dict, nokkel: str, sti: str) -> float:
        return tall(seksjon_.get(nokkel), f"{felt}.{sti}.{nokkel}")

    return Balanse(
        eiendeler=Eiendeler(
            anleggsmidler=Anleggsmidler(
                aksjer_i_datterselskap=_t(am, "aksjer_i_datterselskap", "eiendeler.anleggsmidler"),
                andre_aksjer=_t(am, "andre_aksjer", "eiendeler.anleggsmidler"),
                langsiktige_fordringer=_t(am, "langsiktige_fordringer", "eiendeler.anleggsmidler"),
            ),
            omloepmidler=Omloepmidler(
                kortsiktige_fordringer=_t(om, "kortsiktige_fordringer", "eiendeler.omloepmidler"),
                bankinnskudd=_t(om, "bankinnskudd", "eiendeler.omloepmidler"),
            ),
        ),
        egenkapital_og_gjeld=EgenkapitalOgGjeld(
            egenkapital=Egenkapital(
                aksjekapital=_t(ek, "aksjekapital", "egenkapital_og_gjeld.egenkapital"),
                overkursfond=_t(ek, "overkursfond", "egenkapital_og_gjeld.egenkapital"),
                annen_egenkapital=_t(ek, "annen_egenkapital", "egenkapital_og_gjeld.egenkapital"),
            ),
            langsiktig_gjeld=LangsiktigGjeld(
                laan_fra_aksjonaer=_t(
                    lg, "laan_fra_aksjonaer", "egenkapital_og_gjeld.langsiktig_gjeld"
                ),
                andre_langsiktige_laan=_t(
                    lg, "andre_langsiktige_laan", "egenkapital_og_gjeld.langsiktig_gjeld"
                ),
            ),
            kortsiktig_gjeld=KortsiktigGjeld(
                leverandoergjeld=_t(
                    kg, "leverandoergjeld", "egenkapital_og_gjeld.kortsiktig_gjeld"
                ),
                betalbar_skatt=_t(kg, "betalbar_skatt", "egenkapital_og_gjeld.kortsiktig_gjeld"),
                skyldige_offentlige_avgifter=_t(
                    kg, "skyldige_offentlige_avgifter", "egenkapital_og_gjeld.kortsiktig_gjeld"
                ),
                avsatt_utbytte=_t(kg, "avsatt_utbytte", "egenkapital_og_gjeld.kortsiktig_gjeld"),
                annen_kortsiktig_gjeld=_t(
                    kg, "annen_kortsiktig_gjeld", "egenkapital_og_gjeld.kortsiktig_gjeld"
                ),
            ),
        ),
    )


def les_foregaaende(raa: dict) -> tuple[Resultatregnskap, Balanse]:
    """Fjorårets tall. Seksjoner som mangler gir tomme modeller (første regnskapsår)."""
    fa = raa.get("foregaaende_aar") or {}
    resultat = (
        les_resultat(fa["resultatregnskap"], "foregaaende_aar.resultatregnskap")
        if fa.get("resultatregnskap") is not None
        else Resultatregnskap()
    )
    balanse = (
        les_balanse(fa["balanse"], "foregaaende_aar.balanse")
        if fa.get("balanse") is not None
        else Balanse()
    )
    return resultat, balanse


def les_regnskapsaar(raa: dict) -> int:
    return paakrevd_tall(raa.get("regnskapsaar"), "regnskapsaar", "Regnskapsår", _til_heltall)


def les_utbytte_utbetalt(raa: dict) -> float:
    """Samlet utbytte utbetalt i året, summert fra aksjonærene (0 uten aksjonærer)."""
    return sum(
        tall(a.get("utbytte_utbetalt"), f"aksjonaerer[{i}].utbytte_utbetalt")
        for i, a in enumerate(raa.get("aksjonaerer") or [], 1)
        if isinstance(a, dict)
    )


def les_aksjonaerer(raa: dict) -> list[Aksjonaer]:
    liste = raa.get("aksjonaerer") or []
    if not isinstance(liste, list):
        raise KonfigFeil("aksjonaerer i configen må være en liste.", felt="aksjonaerer")
    aksjonaerer = []
    for i, a in enumerate(liste, 1):
        felt = f"aksjonaerer[{i}]"
        if not isinstance(a, dict):
            raise KonfigFeil(
                f"Aksjonær {i} i configen må ha undernøkler (navn, fodselsnummer, antall_aksjer).",
                felt=felt,
            )
        aksjonaerer.append(
            Aksjonaer(
                navn=tekst(a.get("navn")),
                fodselsnummer=tekst(a.get("fodselsnummer")),
                antall_aksjer=heltall(a.get("antall_aksjer"), f"{felt}.antall_aksjer"),
                aksjeklasse=tekst(_hent(a, "aksjeklasse", f"{felt}.aksjeklasse")),
                utbytte_utbetalt=tall(a.get("utbytte_utbetalt"), f"{felt}.utbytte_utbetalt"),
                innbetalt_kapital_per_aksje=tall(
                    a.get("innbetalt_kapital_per_aksje"), f"{felt}.innbetalt_kapital_per_aksje"
                ),
            )
        )
    return aksjonaerer


# ---------------------------------------------------------------------------
# Hele modeller
# ---------------------------------------------------------------------------


def les_aarsregnskap(raa: dict) -> Aarsregnskap:
    """Årsregnskapet (også grunnlaget for skattemeldingen) fra en parset config."""
    selskap = les_selskap(raa)
    resultat = les_resultat(seksjon(raa, "resultatregnskap"))
    balanse = les_balanse(seksjon(raa, "balanse"))
    foregaaende_resultat, foregaaende_balanse = les_foregaaende(raa)
    return Aarsregnskap(
        selskap=selskap,
        regnskapsaar=les_regnskapsaar(raa),
        resultatregnskap=resultat,
        balanse=balanse,
        foregaaende_aar_resultat=foregaaende_resultat,
        foregaaende_aar_balanse=foregaaende_balanse,
        utbytte_utbetalt=les_utbytte_utbetalt(raa),
        regnskapsstart=dato(raa.get("regnskapsstart"), "regnskapsstart"),
        regnskapsslutt=dato(raa.get("regnskapsslutt"), "regnskapsslutt"),
        eierandel_for_utbytte=eierandel_eller_none(
            (raa.get("skattemelding") or {}).get("eierandel_for_fritaksmetoden")
        ),
    )


def les_aksjonaerregisteroppgave(raa: dict) -> Aksjonaerregisteroppgave:
    """Aksjonærregisteroppgaven (RF-1086) fra en parset config. Tallene i regnskapet leses ikke."""
    return Aksjonaerregisteroppgave(
        selskap=les_selskap(raa),
        regnskapsaar=les_regnskapsaar(raa),
        aksjonaerer=les_aksjonaerer(raa),
        utbytte_vedtaksdato=dato(raa.get("utbytte_vedtaksdato"), "utbytte_vedtaksdato"),
    )
