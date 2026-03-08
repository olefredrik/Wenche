"""
Datamodeller for alle tre innsendingstyper.
Fylles ut fra config.yaml og valideres før innsending.
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
    aksjekapital: int


# ---------------------------------------------------------------------------
# Resultatregnskap
# ---------------------------------------------------------------------------

@dataclass
class Driftsinntekter:
    salgsinntekter: int = 0
    andre_driftsinntekter: int = 0

    @property
    def sum(self) -> int:
        return self.salgsinntekter + self.andre_driftsinntekter


@dataclass
class Driftskostnader:
    loennskostnader: int = 0
    avskrivninger: int = 0
    andre_driftskostnader: int = 0

    @property
    def sum(self) -> int:
        return self.loennskostnader + self.avskrivninger + self.andre_driftskostnader


@dataclass
class Finansposter:
    utbytte_fra_datterselskap: int = 0
    andre_finansinntekter: int = 0
    rentekostnader: int = 0
    andre_finanskostnader: int = 0

    @property
    def sum_inntekter(self) -> int:
        return self.utbytte_fra_datterselskap + self.andre_finansinntekter

    @property
    def sum_kostnader(self) -> int:
        return self.rentekostnader + self.andre_finanskostnader


@dataclass
class Resultatregnskap:
    driftsinntekter: Driftsinntekter = field(default_factory=Driftsinntekter)
    driftskostnader: Driftskostnader = field(default_factory=Driftskostnader)
    finansposter: Finansposter = field(default_factory=Finansposter)

    @property
    def driftsresultat(self) -> int:
        return self.driftsinntekter.sum - self.driftskostnader.sum

    @property
    def resultat_foer_skatt(self) -> int:
        return (
            self.driftsresultat
            + self.finansposter.sum_inntekter
            - self.finansposter.sum_kostnader
        )

    @property
    def aarsresultat(self) -> int:
        return self.resultat_foer_skatt  # Skattekostnad = 0 for holdingselskap uten skattbar inntekt


# ---------------------------------------------------------------------------
# Balanse
# ---------------------------------------------------------------------------

@dataclass
class Anleggsmidler:
    aksjer_i_datterselskap: int = 0
    andre_aksjer: int = 0
    langsiktige_fordringer: int = 0

    @property
    def sum(self) -> int:
        return self.aksjer_i_datterselskap + self.andre_aksjer + self.langsiktige_fordringer


@dataclass
class Omloepmidler:
    kortsiktige_fordringer: int = 0
    bankinnskudd: int = 0

    @property
    def sum(self) -> int:
        return self.kortsiktige_fordringer + self.bankinnskudd


@dataclass
class Eiendeler:
    anleggsmidler: Anleggsmidler = field(default_factory=Anleggsmidler)
    omloepmidler: Omloepmidler = field(default_factory=Omloepmidler)

    @property
    def sum(self) -> int:
        return self.anleggsmidler.sum + self.omloepmidler.sum


@dataclass
class Egenkapital:
    aksjekapital: int = 0
    overkursfond: int = 0
    annen_egenkapital: int = 0  # Kan være negativ ved akkumulert underskudd

    @property
    def sum(self) -> int:
        return self.aksjekapital + self.overkursfond + self.annen_egenkapital


@dataclass
class LangsiktigGjeld:
    laan_fra_aksjonaer: int = 0
    andre_langsiktige_laan: int = 0

    @property
    def sum(self) -> int:
        return self.laan_fra_aksjonaer + self.andre_langsiktige_laan


@dataclass
class KortsiktigGjeld:
    leverandoergjeld: int = 0
    skyldige_offentlige_avgifter: int = 0
    annen_kortsiktig_gjeld: int = 0

    @property
    def sum(self) -> int:
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
    def sum(self) -> int:
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
        return self.eiendeler.sum == self.egenkapital_og_gjeld.sum

    def differanse(self) -> int:
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


# ---------------------------------------------------------------------------
# Aksjonærregisteroppgave
# ---------------------------------------------------------------------------

@dataclass
class Aksjonaer:
    navn: str
    fodselsnummer: str          # 11 siffer
    antall_aksjer: int
    aksjeklasse: str
    utbytte_utbetalt: int       # NOK utbetalt i løpet av regnskapsåret
    innbetalt_kapital_per_aksje: int


@dataclass
class Aksjonaerregisteroppgave:
    selskap: Selskap
    regnskapsaar: int
    aksjonaerer: list[Aksjonaer]

    @property
    def totalt_antall_aksjer(self) -> int:
        return sum(a.antall_aksjer for a in self.aksjonaerer)

    @property
    def totalt_utbytte_utbetalt(self) -> int:
        return sum(a.utbytte_utbetalt for a in self.aksjonaerer)


# ---------------------------------------------------------------------------
# Skattemelding-konfigurasjon
# ---------------------------------------------------------------------------

@dataclass
class SkattemeldingKonfig:
    underskudd_til_fremfoering: int = 0   # Ubenyttet underskudd fra tidligere år
    anvend_fritaksmetoden: bool = True    # True for holdingselskaper som eier aksjer
