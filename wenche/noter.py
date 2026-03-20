"""
Generering av obligatoriske noter til årsregnskapet.

Notene er påkrevd etter regnskapsloven for små foretak:
  §7-35  Regnskapsprinsipper
  §7-43  Antall ansatte og lønnskostnader
  §7-45  Lån og sikkerhetsstillelse til nærstående
  §7-46  Fortsatt drift

VIKTIG: Notene sendes IKKE inn til Brønnøysundregistrene via Altinn.
RR-0002 (årsregnskap-skjemaet) har ingen felt for fritekstnoter.
Notene skal oppbevares av selskapet og er en del av det fullstendige
årsregnskapet som styret fastsetter. De bør arkiveres sammen med
det signerte årsregnskapet.
"""

from wenche.models import Aarsregnskap, Noter


def generer(regnskap: Aarsregnskap, noter: Noter) -> str:
    """Returnerer de fire obligatoriske notene som ferdig formatert tekst."""
    linjer: list[str] = []

    def linje(tekst: str = "") -> None:
        linjer.append(tekst)

    selskap = regnskap.selskap
    aar = regnskap.regnskapsaar

    linje(f"NOTER TIL ÅRSREGNSKAPET {aar}")
    linje(f"{selskap.navn}  •  Org.nr. {selskap.org_nummer}")
    linje("=" * 60)
    linje()

    # ------------------------------------------------------------------
    # Note 1 — Regnskapsprinsipper (rskl. § 7-35)
    # ------------------------------------------------------------------
    linje("NOTE 1 — REGNSKAPSPRINSIPPER (rskl. § 7-35)")
    linje("-" * 60)
    linje(
        "Årsregnskapet er satt opp i samsvar med regnskapsloven og "
        "god regnskapsskikk for små foretak."
    )
    linje()
    linje("Eiendeler bestemt til varig eie eller bruk er klassifisert "
          "som anleggsmidler. Øvrige eiendeler er klassifisert som "
          "omløpsmidler.")
    linje()
    linje("Aksjer i datterselskaper er vurdert til kostpris. "
          "Dersom virkelig verdi er lavere enn kostpris og verdifallet "
          "ikke er forbigående, nedskrives investeringen.")
    linje()
    linje("Fordringer er oppført til pålydende verdi etter fradrag "
          "for forventede tap.")
    linje()
    linje("Gjeld er oppført til nominell verdi.")
    linje()

    # ------------------------------------------------------------------
    # Note 2 — Ansatte og lønnskostnader (rskl. § 7-43)
    # ------------------------------------------------------------------
    linje("NOTE 2 — ANSATTE OG LØNNSKOSTNADER (rskl. § 7-43)")
    linje("-" * 60)
    antall = noter.antall_ansatte
    if antall == 0:
        linje("Selskapet har ingen ansatte.")
        linje()
        linje(
            "Det er ikke utbetalt lønn, honorar eller annen godtgjørelse "
            "til daglig leder eller styret i regnskapsåret."
        )
    elif antall == 1:
        linje(f"Selskapet hadde {antall} ansatt i regnskapsåret.")
        loennskostnader = regnskap.resultatregnskap.driftskostnader.loennskostnader
        linje(f"Lønnskostnader inkl. arbeidsgiveravgift: {loennskostnader:,} kr".replace(",", "\u202f"))
    else:
        linje(f"Selskapet hadde {antall} ansatte i regnskapsåret.")
        loennskostnader = regnskap.resultatregnskap.driftskostnader.loennskostnader
        linje(f"Lønnskostnader inkl. arbeidsgiveravgift: {loennskostnader:,} kr".replace(",", "\u202f"))
    linje()

    # ------------------------------------------------------------------
    # Note 3 — Lån og sikkerhetsstillelse til nærstående (rskl. § 7-45)
    # ------------------------------------------------------------------
    linje("NOTE 3 — LÅN TIL NÆRSTÅENDE (rskl. § 7-45)")
    linje("-" * 60)
    if not noter.laan_til_naerstaaende:
        linje(
            "Selskapet har ikke ytet lån til aksjonærer, styremedlemmer "
            "eller andre nærstående parter."
        )
    else:
        linje(
            "Selskapet har følgende lån til nærstående parter "
            "per 31.12." + str(aar) + ":"
        )
        linje()
        for laan in noter.laan_til_naerstaaende:
            linje(f"  Mottaker:  {laan.mottaker}")
            linje(f"  Beløp:     {laan.beloep:,} kr".replace(",", "\u202f"))
            linje(f"  Rente:     {laan.rente_prosent:.2f} %")
            if laan.sikkerhet:
                linje(f"  Sikkerhet: {laan.sikkerhet}")
            else:
                linje("  Sikkerhet: Ingen")
            linje()
    linje()

    # ------------------------------------------------------------------
    # Note 4 — Fortsatt drift (rskl. § 7-46)
    # ------------------------------------------------------------------
    linje("NOTE 4 — FORTSATT DRIFT (rskl. § 7-46)")
    linje("-" * 60)
    linje(
        "Forutsetningen om fortsatt drift er lagt til grunn ved "
        "utarbeidelsen av årsregnskapet. Etter styrets vurdering er "
        "forutsetningene for fortsatt drift til stede."
    )
    linje()

    linje("=" * 60)
    linje()
    linje(
        "Disse notene utgjør en del av det fullstendige årsregnskapet "
        f"for {selskap.navn} for regnskapsåret {aar}."
    )
    linje(
        "Notene sendes ikke digitalt til Brønnøysundregistrene, men "
        "skal oppbevares av selskapet og fremlegges på forespørsel."
    )

    return "\n".join(linjer)
