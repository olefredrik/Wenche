"""
Datamodeller for alle tre innsendingstyper.
Fylles ut fra config.yaml og valideres før innsending.

Monetære beløpsfelter bruker float for å bevare desimaler fra SAF-T-import.
Ved XML-generering til BRG/SKD rundes beløp til nærmeste krone (round()).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Felles selskapsinfo
# ---------------------------------------------------------------------------

@dataclass
class Selskap:
    navn: str
    org_nummer: str
    daglig_leder: str
    styreleder: str
    forretningsadresse: str
    stiftelsesaar: int
    aksjekapital: float
    kontakt_epost: str = ""     # Påkrevd for aksjonærregisteroppgave (RF-1086)


# ---------------------------------------------------------------------------
# Resultatregnskap
# ---------------------------------------------------------------------------

@dataclass
class Driftsinntekter:
    salgsinntekter: float = 0.0
    andre_driftsinntekter: float = 0.0

    @property
    def sum(self) -> float:
        return self.salgsinntekter + self.andre_driftsinntekter


@dataclass
class Driftskostnader:
    loennskostnader: float = 0.0
    avskrivninger: float = 0.0
    andre_driftskostnader: float = 0.0

    @property
    def sum(self) -> float:
        return self.loennskostnader + self.avskrivninger + self.andre_driftskostnader


@dataclass
class Finansposter:
    utbytte_fra_datterselskap: float = 0.0
    andre_finansinntekter: float = 0.0
    rentekostnader: float = 0.0
    andre_finanskostnader: float = 0.0

    @property
    def sum_inntekter(self) -> float:
        return self.utbytte_fra_datterselskap + self.andre_finansinntekter

    @property
    def sum_kostnader(self) -> float:
        return self.rentekostnader + self.andre_finanskostnader


@dataclass
class Resultatregnskap:
    driftsinntekter: Driftsinntekter = field(default_factory=Driftsinntekter)
    driftskostnader: Driftskostnader = field(default_factory=Driftskostnader)
    finansposter: Finansposter = field(default_factory=Finansposter)

    @property
    def driftsresultat(self) -> float:
        return self.driftsinntekter.sum - self.driftskostnader.sum

    @property
    def resultat_foer_skatt(self) -> float:
        return (
            self.driftsresultat
            + self.finansposter.sum_inntekter
            - self.finansposter.sum_kostnader
        )

    @property
    def aarsresultat(self) -> float:
        return self.resultat_foer_skatt  # Skattekostnad = 0 for holdingselskap uten skattbar inntekt


# ---------------------------------------------------------------------------
# Balanse
# ---------------------------------------------------------------------------

@dataclass
class Anleggsmidler:
    aksjer_i_datterselskap: float = 0.0
    andre_aksjer: float = 0.0
    langsiktige_fordringer: float = 0.0

    @property
    def sum(self) -> float:
        return self.aksjer_i_datterselskap + self.andre_aksjer + self.langsiktige_fordringer


@dataclass
class Omloepmidler:
    kortsiktige_fordringer: float = 0.0
    bankinnskudd: float = 0.0

    @property
    def sum(self) -> float:
        return self.kortsiktige_fordringer + self.bankinnskudd


@dataclass
class Eiendeler:
    anleggsmidler: Anleggsmidler = field(default_factory=Anleggsmidler)
    omloepmidler: Omloepmidler = field(default_factory=Omloepmidler)

    @property
    def sum(self) -> float:
        return self.anleggsmidler.sum + self.omloepmidler.sum


@dataclass
class Egenkapital:
    aksjekapital: float = 0.0
    overkursfond: float = 0.0
    annen_egenkapital: float = 0.0  # Kan være negativ ved akkumulert underskudd

    @property
    def sum(self) -> float:
        return self.aksjekapital + self.overkursfond + self.annen_egenkapital


@dataclass
class LangsiktigGjeld:
    laan_fra_aksjonaer: float = 0.0
    andre_langsiktige_laan: float = 0.0

    @property
    def sum(self) -> float:
        return self.laan_fra_aksjonaer + self.andre_langsiktige_laan


@dataclass
class KortsiktigGjeld:
    leverandoergjeld: float = 0.0
    skyldige_offentlige_avgifter: float = 0.0
    annen_kortsiktig_gjeld: float = 0.0

    @property
    def sum(self) -> float:
        return (
            self.leverandoergjeld
            + self.skyldige_offentlige_avgifter
            + self.annen_kortsiktig_gjeld
        )


@dataclass
class EgenkapitalOgGjeld:
    egenkapital: Egenkapital = field(default_factory=Egenkapital)
    langsiktig_gjeld: LangsiktigGjeld = field(default_factory=LangsiktigGjeld)
    kortsiktig_gjeld: KortsiktigGjeld = field(default_factory=KortsiktigGjeld)

    @property
    def sum(self) -> float:
        return (
            self.egenkapital.sum
            + self.langsiktig_gjeld.sum
            + self.kortsiktig_gjeld.sum
        )


@dataclass
class Balanse:
    eiendeler: Eiendeler = field(default_factory=Eiendeler)
    egenkapital_og_gjeld: EgenkapitalOgGjeld = field(default_factory=EgenkapitalOgGjeld)

    def er_i_balanse(self) -> bool:
        return abs(self.eiendeler.sum - self.egenkapital_og_gjeld.sum) < 0.01

    def differanse(self) -> float:
        return self.eiendeler.sum - self.egenkapital_og_gjeld.sum


# ---------------------------------------------------------------------------
# Årsregnskap
# ---------------------------------------------------------------------------

@dataclass
class Aarsregnskap:
    selskap: Selskap
    regnskapsaar: int
    resultatregnskap: Resultatregnskap
    balanse: Balanse
    fastsettelsesdato: Optional[date] = None   # Dato styret godkjente regnskapet; standard: i dag
    signatar: Optional[str] = None              # Navn på den som signerer; standard: daglig_leder
    revideres: bool = False                     # True hvis regnskapet er revidert
    foregaaende_aar_resultat: Resultatregnskap = field(default_factory=Resultatregnskap)
    foregaaende_aar_balanse: Balanse = field(default_factory=Balanse)
    utbytte_utbetalt: float = 0.0              # Totalt utbytte utbetalt til aksjonærer i løpet av året


# ---------------------------------------------------------------------------
# Aksjonærregisteroppgave
# ---------------------------------------------------------------------------

@dataclass
class Aksjonaer:
    navn: str
    fodselsnummer: str          # 11 siffer
    antall_aksjer: int
    aksjeklasse: str
    utbytte_utbetalt: float     # NOK utbetalt i løpet av regnskapsåret
    innbetalt_kapital_per_aksje: float


@dataclass
class Aksjonaerregisteroppgave:
    selskap: Selskap
    regnskapsaar: int
    aksjonaerer: list[Aksjonaer]

    @property
    def totalt_antall_aksjer(self) -> int:
        return sum(a.antall_aksjer for a in self.aksjonaerer)

    @property
    def totalt_utbytte_utbetalt(self) -> float:
        return sum(a.utbytte_utbetalt for a in self.aksjonaerer)


# ---------------------------------------------------------------------------
# Obligatoriske noter (rskl. §§ 7-35, 7-43, 7-45, 7-46)
# ---------------------------------------------------------------------------

@dataclass
class LaanTilNaerstaaende:
    motpart: str                    # Navn på nærstående part (aksjonær, styremedlem e.l.)
    saldo: float                    # Utestående saldo per 31.12 (NOK)
    retning: str = "långiver"       # "långiver" = selskapet lånte ut; "låntaker" = selskapet lånte inn
    rente_prosent: float = 0.0
    sikkerhet: str = ""


@dataclass
class Noter:
    antall_ansatte: int = 0
    laan_til_naerstaaende: list[LaanTilNaerstaaende] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Skattemelding-konfigurasjon
# ---------------------------------------------------------------------------

@dataclass
class SkattemeldingKonfig:
    underskudd_til_fremfoering: float = 0.0   # Ubenyttet underskudd fra tidligere år
    anvend_fritaksmetoden: bool = True         # True for holdingselskaper som eier aksjer
    eierandel_datterselskap: int = 100         # Eierandel i datterselskap (prosent, 0–100)
