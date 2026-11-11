"""
Datamodeller for alle tre innsendingstyper.
Fylles ut fra config.yaml og valideres før innsending.

Monetære beløpsfelter bruker float for å bevare desimaler fra SAF-T-import.
Ved XML-generering til BRG/SKD rundes beløp til nærmeste krone (round()).

Feltene som kommer fra config.yaml er annotert med `Dok` (tekst, om feltet er påkrevd, typenavn
og lovlige verdier), og `Konfig` nederst beskriver formen på hele fila. Det er den ene kilden
`wenche.skjema` lager JSON Schema, TypeScript-typen og referansetabellene i dokumentasjonen
fra, og `wenche.configfelt` bruker den til å varsle om ukjente felt. Beskrivelsene her ER
dokumentasjonen, så skriv dem for brukeren.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Annotated


@dataclass(frozen=True)
class Dok:
    """Dokumentasjon av et config-felt, brukt i `Annotated[type, Dok(...)]`."""

    tekst: str
    # "ja", "nei", "delvis", "for RF-1086", ... slik det skal stå i referansen. None betyr at
    # det utledes: påkrevd når feltet ikke har standardverdi.
    paakrevd: str | None = None
    # Typenavnet i referansen når det vanlige (heltall for beløp, tekst, dato ...) ikke passer.
    typenavn: str | None = None
    valg: tuple[str, ...] = ()  # lovlige verdier


class IkkeIConfig:
    """Markør for et modellfelt som ikke står i config.yaml (fylles fra et annet sted)."""


NOK = "Beløp i hele kroner."

# ---------------------------------------------------------------------------
# Felles selskapsinfo
# ---------------------------------------------------------------------------


@dataclass
class Selskap:
    navn: Annotated[str, Dok("Selskapets registrerte navn")]
    org_nummer: Annotated[str, Dok("Organisasjonsnummer, 9 siffer uten mellomrom")]
    daglig_leder: Annotated[
        str,
        Dok(
            "Fullt navn på daglig leder. Minst én av `daglig_leder` og `styreleder` må være "
            "fylt ut",
            paakrevd="delvis",
        ),
    ]
    styreleder: Annotated[
        str,
        Dok(
            "Fullt navn på styreleder (kan være samme som daglig leder). Minst én av "
            "`daglig_leder` og `styreleder` må være fylt ut",
            paakrevd="delvis",
        ),
    ]
    forretningsadresse: Annotated[str, Dok("Gateadresse, postnummer og poststed")]
    stiftelsesaar: Annotated[int, Dok("Året selskapet ble stiftet")]
    aksjekapital: Annotated[float, Dok("Innbetalt aksjekapital i NOK, fra stiftelsesdokumentene")]
    kontakt_epost: Annotated[
        str,
        Dok(
            "E-postadressen Skatteetaten sender tilbakemeldingen på aksjonærregisteroppgaven "
            "til, altså om den er godkjent eller avvist. Bruk en adresse du leser",
            paakrevd="for RF-1086",
        ),
    ] = ""
    # Eksakt stiftelsesdato når den er kjent (hentes fra Enhetsregisteret). Årstallet alene
    # holder ikke overalt: aksjonærregisteroppgaven oppgir stiftelsesdato, og et kort
    # første regnskapsår starter på stiftelsesdatoen, ikke 1. januar.
    stiftelsesdato: Annotated[
        date | None,
        Dok(
            "Eksakt stiftelsesdato (ÅÅÅÅ-MM-DD). Hentes fra Enhetsregisteret. Brukes som "
            "stiftelsesdato i aksjonærregisteroppgaven, og som start på et kort første "
            "regnskapsår. Uten den brukes 1. januar i stiftelsesåret"
        ),
    ] = None
    # Den delen av stiftelsesinnskuddet som ble gjort som tinginnskudd, typisk aksjer skutt
    # inn i et nystiftet holdingselskap. Egenkapitalavstemmingen skiller kontantinnskudd og
    # tinginnskudd på hver sin kode, og modellen kan ikke utlede hvilken som gjelder. 0 betyr
    # at hele innskuddet var kontant, som er det vanlige for et lite AS. Brukes bare i
    # selskapets første regnskapsår; senere år har ikke noe stiftelsesinnskudd å fordele.
    tinginnskudd_ved_stiftelse: Annotated[
        float,
        Dok(
            "Den delen av stiftelsesinnskuddet som ble gjort som tinginnskudd, i NOK. Brukes "
            "bare i selskapets første regnskapsår, der egenkapitalavstemmingen skiller "
            "kontantinnskudd og tinginnskudd på hver sin kode. Tom eller 0 = hele innskuddet "
            "var kontant"
        ),
    ] = 0.0


# ---------------------------------------------------------------------------
# Resultatregnskap
# ---------------------------------------------------------------------------


@dataclass
class Driftsinntekter:
    salgsinntekter: Annotated[float, Dok("Inntekter fra salg av varer eller tjenester")] = 0.0
    andre_driftsinntekter: Annotated[float, Dok("Andre løpende driftsinntekter")] = 0.0

    @property
    def sum(self) -> float:
        return self.salgsinntekter + self.andre_driftsinntekter


@dataclass
class Driftskostnader:
    loennskostnader: Annotated[float, Dok("Lønn, arbeidsgiveravgift og lignende")] = 0.0
    avskrivninger: Annotated[float, Dok("Planmessige avskrivninger på anleggsmidler")] = 0.0
    andre_driftskostnader: Annotated[
        float, Dok("Bank- og regnskapsgebyrer, kontorkostnader o.l.")
    ] = 0.0

    @property
    def sum(self) -> float:
        return self.loennskostnader + self.avskrivninger + self.andre_driftskostnader


@dataclass
class Finansposter:
    utbytte_fra_datterselskap: Annotated[
        float, Dok("Utbytte mottatt fra datterselskaper (dekkes av fritaksmetoden)")
    ] = 0.0
    andre_finansinntekter: Annotated[float, Dok("Renteinntekter og andre finansinntekter")] = 0.0
    rentekostnader: Annotated[float, Dok("Renter på lån")] = 0.0
    andre_finanskostnader: Annotated[float, Dok("Andre finanskostnader")] = 0.0
    # Gevinst og tap ved realisasjon av aksjer (grupperingskode 8074 og 8174). Egne linjer
    # fordi fritaksmetoden (sktl. § 2-38) gjør gevinsten skattefri og tapet ikke
    # fradragsberettiget, mens andre finansposter skattlegges fullt. Står sist, så eldre
    # kallsteder og config uten feltene gir samme resultat som før.
    gevinst_ved_realisasjon_av_aksjer: Annotated[
        float,
        Dok(
            "Gevinst ved salg av aksjer innenfor fritaksmetoden (kode 8074). Skattefri når "
            "`anvend_fritaksmetoden` er `true`, uansett eierandel"
        ),
    ] = 0.0
    tap_ved_realisasjon_av_aksjer: Annotated[
        float,
        Dok(
            "Tap ved salg av aksjer innenfor fritaksmetoden (kode 8174). Ikke "
            "fradragsberettiget når `anvend_fritaksmetoden` er `true`"
        ),
    ] = 0.0
    # Utbytte fra selskaper som verken er datterselskap eller tilknyttet selskap, typisk en
    # eierandel under 20 %. Egen linje fordi årsregnskapet skiller det fra utbytte fra
    # datterselskap og tilknyttet selskap. Skatten er den samme: fritaksmetoden med
    # 3 %-sjablon. Står sist, så eldre kallsteder og config uten feltet gir samme resultat.
    utbytte_fra_andre_aksjer: Annotated[
        float,
        Dok(
            "Utbytte fra selskaper som verken er datterselskap eller tilknyttet selskap, typisk "
            "en eierandel under 20 %. Egen linje i årsregnskapet («Inntekt på andre "
            "investeringer»). I skattemeldingen skattlegges det som utbytte fra datterselskap, "
            "alltid med 3 %-sjablonen når `anvend_fritaksmetoden` er `true`"
        ),
    ] = 0.0

    @property
    def sum_utbytte(self) -> float:
        """Mottatt utbytte i alt, fra datterselskap og fra andre aksjer."""
        return self.utbytte_fra_datterselskap + self.utbytte_fra_andre_aksjer

    @property
    def sum_inntekter(self) -> float:
        return (
            self.sum_utbytte + self.andre_finansinntekter + self.gevinst_ved_realisasjon_av_aksjer
        )

    @property
    def sum_kostnader(self) -> float:
        return self.rentekostnader + self.andre_finanskostnader + self.tap_ved_realisasjon_av_aksjer


@dataclass
class Resultatregnskap:
    driftsinntekter: Driftsinntekter = field(default_factory=Driftsinntekter)
    driftskostnader: Driftskostnader = field(default_factory=Driftskostnader)
    finansposter: Finansposter = field(default_factory=Finansposter)
    # Skattekostnad på ordinært resultat, oppgitt som positiv kostnad (rskl. § 6-1 nr. 19).
    # Egen linje fordi oppstillingsplanen krever den mellom resultat før skatt og årsresultat.
    # 0 for et selskap uten skattepliktig inntekt (typisk holding med bare fritatt utbytte),
    # men et selskap med renteinntekt har en reell skattekostnad som må stå her.
    skattekostnad: Annotated[
        float,
        Dok(
            "Skattekostnad på ordinært resultat (rskl. § 6-1). Egen linje mellom resultat før "
            "skatt og årsresultat. 0 for et selskap uten skattepliktig inntekt"
        ),
    ] = 0.0

    @property
    def driftsresultat(self) -> float:
        return self.driftsinntekter.sum - self.driftskostnader.sum

    @property
    def resultat_foer_skatt(self) -> float:
        return (
            self.driftsresultat + self.finansposter.sum_inntekter - self.finansposter.sum_kostnader
        )

    @property
    def aarsresultat(self) -> float:
        return self.resultat_foer_skatt - self.skattekostnad


# ---------------------------------------------------------------------------
# Balanse
# ---------------------------------------------------------------------------


@dataclass
class Anleggsmidler:
    aksjer_i_datterselskap: Annotated[
        float,
        Dok(
            "Kostpris for aksjer i datterselskaper, det vil si selskaper du kontrollerer "
            "(normalt over 50 % av stemmene, rskl. § 1-3)"
        ),
    ] = 0.0
    andre_aksjer: Annotated[
        float,
        Dok(
            "Aksjer i selskaper som ikke er datterselskaper. Grensen her er kontroll, ikke "
            "90 %-grensen i fritaksmetoden"
        ),
    ] = 0.0
    langsiktige_fordringer: Annotated[float, Dok("Lån gitt til andre med løpetid over 1 år")] = 0.0

    @property
    def sum(self) -> float:
        return self.aksjer_i_datterselskap + self.andre_aksjer + self.langsiktige_fordringer


@dataclass
class Omloepmidler:
    kortsiktige_fordringer: Annotated[float, Dok("Kundefordringer og andre kortsiktige krav")] = 0.0
    bankinnskudd: Annotated[float, Dok("Saldo på driftskonto per 31.12")] = 0.0

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
    aksjekapital: Annotated[float, Dok("Innbetalt aksjekapital (fra stiftelsesdokumentene)")] = 0.0
    overkursfond: Annotated[float, Dok("Innbetalt over pålydende ved emisjon")] = 0.0
    annen_egenkapital: Annotated[
        float, Dok("Akkumulert overskudd/underskudd. Negativ verdi = akkumulert underskudd")
    ] = 0.0

    @property
    def sum(self) -> float:
        return self.aksjekapital + self.overkursfond + self.annen_egenkapital


@dataclass
class LangsiktigGjeld:
    laan_fra_aksjonaer: Annotated[float, Dok("Lån fra eier med avtalt løpetid over 1 år")] = 0.0
    andre_langsiktige_laan: Annotated[float, Dok("Banklån og andre lån med løpetid over 1 år")] = (
        0.0
    )

    @property
    def sum(self) -> float:
        return self.laan_fra_aksjonaer + self.andre_langsiktige_laan


@dataclass
class KortsiktigGjeld:
    leverandoergjeld: Annotated[float, Dok("Ubetalte fakturaer per 31.12")] = 0.0
    # Betalbar skatt, ikke fastsatt (konto 2500). Motposten til skattekostnaden i
    # resultatregnskapet: uten denne linjen har et selskap med skattepliktig inntekt
    # ingen riktig plass å føre skattegjelden, og balansen går ikke opp.
    betalbar_skatt: Annotated[
        float,
        Dok("Skyldig selskapsskatt per 31.12 (konto 2500), motposten til `skattekostnad`"),
    ] = 0.0
    skyldige_offentlige_avgifter: Annotated[float, Dok("Skyldig mva, arbeidsgiveravgift o.l.")] = (
        0.0
    )
    # Utbytte styret har foreslått for regnskapsåret (konto 2800). Forslaget er en forpliktelse
    # ved årsslutt og reduserer egenkapitalen i avsetningsåret, ikke i utbetalingsåret. Uten
    # denne linjen måtte avsetningen føres som annen kortsiktig gjeld, og egenkapitalnedgangen
    # ble stående uten en utbyttekode Skatteetaten godtar.
    avsatt_utbytte: Annotated[
        float,
        Dok(
            "Utbytte styret har foreslått for regnskapsåret (konto 2800). Forslaget er en "
            "forpliktelse ved årsslutt og reduserer egenkapitalen i avsetningsåret, ikke i "
            "året det utbetales. Er utbyttet i stedet vedtatt og utbetalt i året uten "
            "forutgående avsetning, skal feltet stå tomt og utbetalingen oppgis per aksjonær"
        ),
    ] = 0.0
    annen_kortsiktig_gjeld: Annotated[float, Dok("Annen gjeld med forfall innen 1 år")] = 0.0

    @property
    def sum(self) -> float:
        return (
            self.leverandoergjeld
            + self.betalbar_skatt
            + self.skyldige_offentlige_avgifter
            + self.avsatt_utbytte
            + self.annen_kortsiktig_gjeld
        )


@dataclass
class EgenkapitalOgGjeld:
    egenkapital: Egenkapital = field(default_factory=Egenkapital)
    langsiktig_gjeld: LangsiktigGjeld = field(default_factory=LangsiktigGjeld)
    kortsiktig_gjeld: KortsiktigGjeld = field(default_factory=KortsiktigGjeld)

    @property
    def sum(self) -> float:
        return self.egenkapital.sum + self.langsiktig_gjeld.sum + self.kortsiktig_gjeld.sum


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
class LaanTilNaerstaaende:
    motpart: Annotated[str, Dok("Navn på den nærstående parten (aksjonær, styremedlem e.l.)")]
    saldo: Annotated[float, Dok("Utestående saldo per 31.12 (NOK)", typenavn="tall")]
    retning: Annotated[
        str,
        Dok(
            "`långiver` når selskapet har lånt ut, `låntaker` når det har lånt inn",
            valg=("långiver", "låntaker"),
        ),
    ] = "långiver"
    rente_prosent: Annotated[float, Dok("Rentesats i prosent", typenavn="desimaltall")] = 0.0
    sikkerhet: Annotated[str, Dok("Eventuell sikkerhet stilt for lånet")] = ""


@dataclass
class Noter:
    antall_ansatte: Annotated[
        int,
        Dok(
            "Antall ansatte i regnskapsåret. Settes også som årsverk i årsregnskapet, og "
            "dry-run advarer når det er over 0, siden lønn og a-melding ligger utenfor det "
            "Wenche sender inn. Standard: `0`"
        ),
    ] = 0
    laan_til_naerstaaende: Annotated[
        list[LaanTilNaerstaaende],
        Dok(
            "Lån til eller fra nærstående per 31.12, ett innslag per lån (se tabellen under). Standard: tom liste"
        ),
    ] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Skattemelding-konfigurasjon
# ---------------------------------------------------------------------------

NAERINGSKATEGORIER = (
    "salgsinntekt",
    "annenDriftsinntekt",
    "loennskostnad",
    "annenDriftskostnad",
    "finansinntekt",
    "finanskostnad",
    "skattekostnad",
    "balanseverdiForAnleggsmiddel",
    "balanseverdiForOmloepsmiddel",
    "egenkapital",
    "langsiktigGjeld",
    "kortsiktigGjeld",
)

BALANSEKATEGORIER = frozenset(
    {
        "balanseverdiForAnleggsmiddel",
        "balanseverdiForOmloepsmiddel",
        "egenkapital",
        "langsiktigGjeld",
        "kortsiktigGjeld",
    }
)


@dataclass(frozen=True)
class NaeringsspesifikasjonPost:
    """Eksakt resultat-/balansepost fra den offisielle grupperingskodelisten."""

    kategori: Annotated[str, Dok("Kategorien posten tilhører", valg=NAERINGSKATEGORIER)]
    kode: Annotated[
        str, Dok("Firesifret kode fra Skatteetatens grupperingskodeliste, for eksempel `6350`")
    ]
    beloep: Annotated[float, Dok("Beløpet som skal rapporteres på koden", typenavn="tall")]


@dataclass
class SkattemeldingKonfig:
    underskudd_til_fremfoering: Annotated[
        float,
        Dok(
            "Fremførbart underskudd fra tidligere år (NOK). Finnes i fjorårets skattemelding. Standard: `0`"
        ),
    ] = 0.0
    anvend_fritaksmetoden: Annotated[
        bool,
        Dok(
            "`true` for holdingselskaper som eier aksjer (sktl. § 2-38). Gjelder utbytte og "
            "gevinst eller tap ved salg av aksjer. Standard: `true`"
        ),
    ] = True
    eierandel_for_fritaksmetoden: Annotated[
        float,
        Dok(
            "Eierandel i selskapet som deler ut utbytte, i prosent (0-100, desimaler tillatt, "
            "for eksempel `90.5`). Brukes bare når `anvend_fritaksmetoden` er `true`. Over "
            "90 %: hele utbyttet fritatt. 90 % eller lavere: 3 % skattepliktig (sjablonregelen, "
            "sktl. § 2-38 sjette ledd). Standard: `100`",
            typenavn="desimaltall",
        ),
    ] = 100.0
    boersnotert: Annotated[bool, Dok("`true` hvis selskapet er børsnotert. Standard: `false`")] = (
        False
    )
    formuesverdi_aksjer: Annotated[
        float,
        Dok(
            "Formuesverdi av aksjer selskapet eier i andre selskap, fra aksjeoppgaven "
            "(RF-1088S, post 209). Brukes til å beregne netto formuesverdi bak selskapets "
            "egne aksjer. Standard: `0`"
        ),
    ] = 0.0
    samlet_verdi_bak_aksjene: Annotated[
        float | None,
        Dok(
            "Overstyrer den beregnede netto formuesverdien bak aksjene direkte. Utelat for å "
            "la Wenche beregne den fra `formuesverdi_aksjer` og balansen"
        ),
    ] = None
    # Valgfri, komplett kodefordeling for næringsspesifikasjonen. Når den er oppgitt,
    # valideres kategorisummene mot regnskapet før XML bygges. Leses fra toppnivået i
    # config.yaml (naeringsspesifikasjon.poster), ikke fra skattemelding-seksjonen.
    naeringsspesifikasjonsposter: Annotated[
        tuple[NaeringsspesifikasjonPost, ...], IkkeIConfig()
    ] = ()


@dataclass
class Aarsregnskap:
    selskap: Selskap
    regnskapsaar: int
    resultatregnskap: Resultatregnskap
    balanse: Balanse
    fastsettelsesdato: date | None = None  # Dato styret godkjente regnskapet; standard: i dag
    signatar: str | None = None  # Navn på den som signerer; standard: daglig_leder
    revideres: bool = False  # True hvis regnskapet er revidert
    foregaaende_aar_resultat: Resultatregnskap = field(default_factory=Resultatregnskap)
    foregaaende_aar_balanse: Balanse = field(default_factory=Balanse)
    utbytte_utbetalt: float = 0.0  # Totalt utbytte utbetalt til aksjonærer i løpet av året
    # Regnskapsperioden. Normalt hele kalenderåret (rskl. § 1-7 første ledd), og da kan begge
    # stå tomme. Settes bare når perioden avviker, i praksis et kort første regnskapsår fra
    # stiftelsesdatoen til 31.12. Forlenget første regnskapsår (§ 1-7 andre ledd) støttes
    # ikke, se `aarsregnskap.valider_periode`.
    regnskapsstart: date | None = None
    regnskapsslutt: date | None = None
    # Eierandelen (prosent) fra skattemelding.eierandel_for_fritaksmetoden, eller None når den
    # ikke er oppgitt. Brukes bare av advarselen om hvilken linje utbyttet står på: ved 20 %
    # eller mer er det et tilknyttet selskap, og da er linjen for datterselskap riktig selv om
    # aksjene står under andre aksjer i balansen.
    eierandel_for_utbytte: float | None = None
    # Notene (antall ansatte, lån til nærstående). Antall ansatte går også inn som årsverk i
    # årsregnskapet til Brønnøysund, så feltet og noten ikke sier to forskjellige ting.
    noter: Noter = field(default_factory=Noter)

    @property
    def periode_start(self) -> date:
        """Første dag i regnskapsperioden. 1. januar med mindre noe annet er oppgitt."""
        return self.regnskapsstart or date(self.regnskapsaar, 1, 1)

    @property
    def periode_slutt(self) -> date:
        """Siste dag i regnskapsperioden. 31. desember med mindre noe annet er oppgitt."""
        return self.regnskapsslutt or date(self.regnskapsaar, 12, 31)

    @property
    def er_foerste_regnskapsaar(self) -> bool:
        """
        Om dette er selskapets første regnskapsår.

        Faller stiftelsesdatoen innenfor perioden, teller det også. Det gjelder bare et
        forlenget første regnskapsår, som `aarsregnskap.valider_periode` avviser. Uten dette
        fikk brukeren i tillegg en misvisende advarsel om manglende fjorårstall.

        To kallsteder er avhengige av samme svar: fjorårsadvarselen i `aarsregnskap.valider`
        og stiftelsesinnskuddet i egenkapitalavstemmingen. Da de var to kopier rakk de å
        drive fra hverandre, derfor bor definisjonen her.
        """
        stiftet = self.selskap.stiftelsesdato
        stiftet_i_perioden = bool(stiftet and self.periode_start <= stiftet <= self.periode_slutt)
        return self.selskap.stiftelsesaar >= self.regnskapsaar or stiftet_i_perioden


# ---------------------------------------------------------------------------
# Aksjonærregisteroppgave
# ---------------------------------------------------------------------------


@dataclass
class Aksjonaer:
    navn: Annotated[str, Dok("Aksjonærens fulle navn")]
    fodselsnummer: Annotated[str, Dok("Fødselsnummer (personnummer), 11 siffer")]
    antall_aksjer: Annotated[int, Dok("Antall aksjer eid per 31.12")]
    aksjeklasse: Annotated[str, Dok("Aksjeklasse, f.eks. `ordinære`")]
    # De to siste leses med 0 som standard (konfig.les_aksjonaerer), så i config.yaml er de
    # valgfrie selv om modellen krever dem.
    utbytte_utbetalt: Annotated[
        float,
        Dok(
            "Utbytte utbetalt til denne aksjonæren i løpet av året (NOK). Standard: `0`",
            paakrevd="nei",
        ),
    ]
    innbetalt_kapital_per_aksje: Annotated[
        float,
        Dok(
            "Innbetalt kapital per aksje i NOK. Beregnes som aksjekapital / antall aksjer. "
            "Standard: `0`",
            paakrevd="nei",
        ),
    ]


@dataclass
class Aksjonaerregisteroppgave:
    selskap: Selskap
    regnskapsaar: int
    aksjonaerer: list[Aksjonaer]
    # Generalforsamlingens vedtak om utbytte. Skatteetaten krever det som tidspunkt for
    # utdelingen, likt i post 8 (selskapet) og post 21 (aksjonæren). Påkrevd bare når det
    # er utbetalt utbytte. Wenche rapporterer én utdeling per år.
    utbytte_vedtaksdato: date | None = None

    @property
    def totalt_antall_aksjer(self) -> int:
        return sum(a.antall_aksjer for a in self.aksjonaerer)

    @property
    def totalt_utbytte_utbetalt(self) -> float:
        return sum(a.utbytte_utbetalt for a in self.aksjonaerer)


# ---------------------------------------------------------------------------
# Obligatoriske noter (rskl. §§ 7-35, 7-43, 7-45, 7-46)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Formen på config.yaml
# ---------------------------------------------------------------------------


@dataclass
class ForegaaendeAar:
    resultatregnskap: Resultatregnskap = field(default_factory=Resultatregnskap)
    balanse: Balanse = field(default_factory=Balanse)


@dataclass
class Naeringsspesifikasjon:
    poster: Annotated[
        list[NaeringsspesifikasjonPost],
        Dok("Komplett liste over poster med grupperingskode, se avsnittet under"),
    ] = field(default_factory=list)


@dataclass
class Konfig:
    """
    config.yaml slik Wenche leser den. Instansieres aldri: leserne i wenche.konfig bygger
    domenemodellene direkte, men formen beskrives her, ett sted, så JSON Schema, TypeScript-
    typen, referansen og varselet om ukjente felt ikke kan drifte fra hverandre.
    """

    selskap: Annotated[Selskap, Dok("Selskapsopplysningene")]
    regnskapsaar: Annotated[int, Dok("Året regnskapet gjelder for, f.eks. `2024`")]
    resultatregnskap: Annotated[Resultatregnskap, Dok("Resultatregnskapet for året")]
    balanse: Annotated[Balanse, Dok("Balansen per 31.12")]
    foregaaende_aar: Annotated[
        ForegaaendeAar | None,
        Dok(
            "Fjorårets tall, med samme struktur som `resultatregnskap` og `balanse`. "
            "Obligatorisk etter regnskapslovens § 6-6, men kan utelates for selskaper stiftet "
            "i regnskapsåret"
        ),
    ] = None
    regnskapsstart: Annotated[
        date | None,
        Dok("Første dag i regnskapsperioden (ÅÅÅÅ-MM-DD). Tom = 1. januar i regnskapsåret"),
    ] = None
    regnskapsslutt: Annotated[
        date | None,
        Dok("Siste dag i regnskapsperioden. Tom = 31. desember i regnskapsåret"),
    ] = None
    skattemelding: Annotated[
        SkattemeldingKonfig, Dok("Opplysninger som bare skattemeldingen trenger")
    ] = field(default_factory=SkattemeldingKonfig)
    naeringsspesifikasjon: Annotated[
        Naeringsspesifikasjon | None,
        Dok("Integrasjonsflate for regnskapssystemer, se eget avsnitt. Utelates ved vanlig bruk"),
    ] = None
    aksjonaerer: Annotated[
        list[Aksjonaer],
        Dok("Alle aksjonærer per 31.12 i regnskapsåret", paakrevd="for RF-1086"),
    ] = field(default_factory=list)
    utbytte_vedtaksdato: Annotated[
        date | None,
        Dok(
            "Datoen generalforsamlingen vedtok utbyttet (ÅÅÅÅ-MM-DD). Må ligge i inntektsåret",
            paakrevd="når det er utbetalt utbytte",
        ),
    ] = None
    noter: Annotated[Noter, Dok("Grunnlaget for de obligatoriske notene")] = field(
        default_factory=Noter
    )
