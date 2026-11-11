// GENERERT av scripts/generer_skjema.py fra dataklassene i wenche/models.py. Ikke rediger
// for hånd: endre modellen og kjør skriptet. tests/test_skjema.py sjekker at fila er à jour.

export interface Selskap {
  /** Selskapets registrerte navn */
  navn: string;
  /** Organisasjonsnummer, 9 siffer uten mellomrom */
  org_nummer: string;
  /** Fullt navn på daglig leder. Minst én av `daglig_leder` og `styreleder` må være fylt ut */
  daglig_leder?: string;
  /** Fullt navn på styreleder (kan være samme som daglig leder). Minst én av `daglig_leder` og `styreleder` må være fylt ut */
  styreleder?: string;
  /** Gateadresse, postnummer og poststed */
  forretningsadresse: string;
  /** Året selskapet ble stiftet */
  stiftelsesaar: number;
  /** Innbetalt aksjekapital i NOK, fra stiftelsesdokumentene */
  aksjekapital: number;
  /** E-postadressen Skatteetaten sender tilbakemeldingen på aksjonærregisteroppgaven til, altså om den er godkjent eller avvist. Bruk en adresse du leser */
  kontakt_epost?: string;
  /** Eksakt stiftelsesdato (ÅÅÅÅ-MM-DD). Hentes fra Enhetsregisteret. Brukes som stiftelsesdato i aksjonærregisteroppgaven, og som start på et kort første regnskapsår. Uten den brukes 1. januar i stiftelsesåret */
  stiftelsesdato?: string | null;
  /** Den delen av stiftelsesinnskuddet som ble gjort som tinginnskudd, i NOK. Brukes bare i selskapets første regnskapsår, der egenkapitalavstemmingen skiller kontantinnskudd og tinginnskudd på hver sin kode. Tom eller 0 = hele innskuddet var kontant */
  tinginnskudd_ved_stiftelse?: number;
}

export interface Driftsinntekter {
  /** Inntekter fra salg av varer eller tjenester */
  salgsinntekter?: number;
  /** Andre løpende driftsinntekter */
  andre_driftsinntekter?: number;
}

export interface Driftskostnader {
  /** Lønn, arbeidsgiveravgift og lignende */
  loennskostnader?: number;
  /** Planmessige avskrivninger på anleggsmidler */
  avskrivninger?: number;
  /** Bank- og regnskapsgebyrer, kontorkostnader o.l. */
  andre_driftskostnader?: number;
}

export interface Finansposter {
  /** Utbytte mottatt fra datterselskaper (dekkes av fritaksmetoden) */
  utbytte_fra_datterselskap?: number;
  /** Renteinntekter og andre finansinntekter */
  andre_finansinntekter?: number;
  /** Renter på lån */
  rentekostnader?: number;
  /** Andre finanskostnader */
  andre_finanskostnader?: number;
  /** Gevinst ved salg av aksjer innenfor fritaksmetoden (kode 8074). Skattefri når `anvend_fritaksmetoden` er `true`, uansett eierandel */
  gevinst_ved_realisasjon_av_aksjer?: number;
  /** Tap ved salg av aksjer innenfor fritaksmetoden (kode 8174). Ikke fradragsberettiget når `anvend_fritaksmetoden` er `true` */
  tap_ved_realisasjon_av_aksjer?: number;
  /** Utbytte fra selskaper som verken er datterselskap eller tilknyttet selskap, typisk en eierandel under 20 %. Egen linje i årsregnskapet («Inntekt på andre investeringer»). I skattemeldingen skattlegges det som utbytte fra datterselskap, alltid med 3 %-sjablonen når `anvend_fritaksmetoden` er `true` */
  utbytte_fra_andre_aksjer?: number;
}

export interface Resultatregnskap {
  driftsinntekter?: Driftsinntekter;
  driftskostnader?: Driftskostnader;
  finansposter?: Finansposter;
  /** Skattekostnad på ordinært resultat (rskl. § 6-1). Egen linje mellom resultat før skatt og årsresultat. 0 for et selskap uten skattepliktig inntekt */
  skattekostnad?: number;
}

export interface Anleggsmidler {
  /** Kostpris for aksjer i datterselskaper, det vil si selskaper du kontrollerer (normalt over 50 % av stemmene, rskl. § 1-3) */
  aksjer_i_datterselskap?: number;
  /** Aksjer i selskaper som ikke er datterselskaper. Grensen her er kontroll, ikke 90 %-grensen i fritaksmetoden */
  andre_aksjer?: number;
  /** Lån gitt til andre med løpetid over 1 år */
  langsiktige_fordringer?: number;
}

export interface Omloepmidler {
  /** Kundefordringer og andre kortsiktige krav */
  kortsiktige_fordringer?: number;
  /** Saldo på driftskonto per 31.12 */
  bankinnskudd?: number;
}

export interface Eiendeler {
  anleggsmidler?: Anleggsmidler;
  omloepmidler?: Omloepmidler;
}

export interface Egenkapital {
  /** Innbetalt aksjekapital (fra stiftelsesdokumentene) */
  aksjekapital?: number;
  /** Innbetalt over pålydende ved emisjon */
  overkursfond?: number;
  /** Akkumulert overskudd/underskudd. Negativ verdi = akkumulert underskudd */
  annen_egenkapital?: number;
}

export interface LangsiktigGjeld {
  /** Lån fra eier med avtalt løpetid over 1 år */
  laan_fra_aksjonaer?: number;
  /** Banklån og andre lån med løpetid over 1 år */
  andre_langsiktige_laan?: number;
}

export interface KortsiktigGjeld {
  /** Ubetalte fakturaer per 31.12 */
  leverandoergjeld?: number;
  /** Skyldig selskapsskatt per 31.12 (konto 2500), motposten til `skattekostnad` */
  betalbar_skatt?: number;
  /** Skyldig mva, arbeidsgiveravgift o.l. */
  skyldige_offentlige_avgifter?: number;
  /** Utbytte styret har foreslått for regnskapsåret (konto 2800). Forslaget er en forpliktelse ved årsslutt og reduserer egenkapitalen i avsetningsåret, ikke i året det utbetales. Er utbyttet i stedet vedtatt og utbetalt i året uten forutgående avsetning, skal feltet stå tomt og utbetalingen oppgis per aksjonær */
  avsatt_utbytte?: number;
  /** Annen gjeld med forfall innen 1 år */
  annen_kortsiktig_gjeld?: number;
}

export interface EgenkapitalOgGjeld {
  egenkapital?: Egenkapital;
  langsiktig_gjeld?: LangsiktigGjeld;
  kortsiktig_gjeld?: KortsiktigGjeld;
}

export interface Balanse {
  eiendeler?: Eiendeler;
  egenkapital_og_gjeld?: EgenkapitalOgGjeld;
}

export interface ForegaaendeAar {
  resultatregnskap?: Resultatregnskap;
  balanse?: Balanse;
}

export interface SkattemeldingKonfig {
  /** Fremførbart underskudd fra tidligere år (NOK). Finnes i fjorårets skattemelding. Standard: `0` */
  underskudd_til_fremfoering?: number;
  /** `true` for holdingselskaper som eier aksjer (sktl. § 2-38). Gjelder utbytte og gevinst eller tap ved salg av aksjer. Standard: `true` */
  anvend_fritaksmetoden?: boolean;
  /** Eierandel i selskapet som deler ut utbytte, i prosent (0-100, desimaler tillatt, for eksempel `90.5`). Brukes bare når `anvend_fritaksmetoden` er `true`. Over 90 %: hele utbyttet fritatt. 90 % eller lavere: 3 % skattepliktig (sjablonregelen, sktl. § 2-38 sjette ledd). Standard: `100` */
  eierandel_for_fritaksmetoden?: number;
  /** `true` hvis selskapet er børsnotert. Standard: `false` */
  boersnotert?: boolean;
  /** Formuesverdi av aksjer selskapet eier i andre selskap, fra aksjeoppgaven (RF-1088S, post 209). Brukes til å beregne netto formuesverdi bak selskapets egne aksjer. Standard: `0` */
  formuesverdi_aksjer?: number;
  /** Overstyrer den beregnede netto formuesverdien bak aksjene direkte. Utelat for å la Wenche beregne den fra `formuesverdi_aksjer` og balansen */
  samlet_verdi_bak_aksjene?: number | null;
}

export interface NaeringsspesifikasjonPost {
  /** Kategorien posten tilhører */
  kategori: "salgsinntekt" | "annenDriftsinntekt" | "loennskostnad" | "annenDriftskostnad" | "finansinntekt" | "finanskostnad" | "skattekostnad" | "balanseverdiForAnleggsmiddel" | "balanseverdiForOmloepsmiddel" | "egenkapital" | "langsiktigGjeld" | "kortsiktigGjeld";
  /** Firesifret kode fra Skatteetatens grupperingskodeliste, for eksempel `6350` */
  kode: string;
  /** Beløpet som skal rapporteres på koden */
  beloep: number;
}

export interface Naeringsspesifikasjon {
  /** Komplett liste over poster med grupperingskode, se avsnittet under */
  poster?: NaeringsspesifikasjonPost[];
}

export interface Aksjonaer {
  /** Aksjonærens fulle navn */
  navn: string;
  /** Fødselsnummer (personnummer), 11 siffer */
  fodselsnummer: string;
  /** Antall aksjer eid per 31.12 */
  antall_aksjer: number;
  /** Aksjeklasse, f.eks. `ordinære` */
  aksjeklasse: string;
  /** Utbytte utbetalt til denne aksjonæren i løpet av året (NOK). Standard: `0` */
  utbytte_utbetalt?: number;
  /** Innbetalt kapital per aksje i NOK. Beregnes som aksjekapital / antall aksjer. Standard: `0` */
  innbetalt_kapital_per_aksje?: number;
}

export interface LaanTilNaerstaaende {
  /** Navn på den nærstående parten (aksjonær, styremedlem e.l.) */
  motpart: string;
  /** Utestående saldo per 31.12 (NOK) */
  saldo: number;
  /** `långiver` når selskapet har lånt ut, `låntaker` når det har lånt inn */
  retning?: "långiver" | "låntaker";
  /** Rentesats i prosent */
  rente_prosent?: number;
  /** Eventuell sikkerhet stilt for lånet */
  sikkerhet?: string;
}

export interface Noter {
  /** Antall ansatte i regnskapsåret. Settes også som årsverk i årsregnskapet, og dry-run advarer når det er over 0, siden lønn og a-melding ligger utenfor det Wenche sender inn. Standard: `0` */
  antall_ansatte?: number;
  /** Lån til eller fra nærstående per 31.12, ett innslag per lån (se tabellen under). Standard: tom liste */
  laan_til_naerstaaende?: LaanTilNaerstaaende[];
}

export interface WencheConfig {
  /** Selskapsopplysningene */
  selskap: Selskap;
  /** Året regnskapet gjelder for, f.eks. `2024` */
  regnskapsaar: number;
  /** Resultatregnskapet for året */
  resultatregnskap: Resultatregnskap;
  /** Balansen per 31.12 */
  balanse: Balanse;
  /** Fjorårets tall, med samme struktur som `resultatregnskap` og `balanse`. Obligatorisk etter regnskapslovens § 6-6, men kan utelates for selskaper stiftet i regnskapsåret */
  foregaaende_aar?: ForegaaendeAar | null;
  /** Første dag i regnskapsperioden (ÅÅÅÅ-MM-DD). Tom = 1. januar i regnskapsåret */
  regnskapsstart?: string | null;
  /** Siste dag i regnskapsperioden. Tom = 31. desember i regnskapsåret */
  regnskapsslutt?: string | null;
  /** Opplysninger som bare skattemeldingen trenger */
  skattemelding?: SkattemeldingKonfig;
  /** Integrasjonsflate for regnskapssystemer, se eget avsnitt. Utelates ved vanlig bruk */
  naeringsspesifikasjon?: Naeringsspesifikasjon | null;
  /** Alle aksjonærer per 31.12 i regnskapsåret */
  aksjonaerer?: Aksjonaer[];
  /** Datoen generalforsamlingen vedtok utbyttet (ÅÅÅÅ-MM-DD). Må ligge i inntektsåret */
  utbytte_vedtaksdato?: string | null;
  /** Grunnlaget for de obligatoriske notene */
  noter?: Noter;
}
