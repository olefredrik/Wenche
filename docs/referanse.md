# Referanse

Komplett dokumentasjon for konfigurasjonsfilen `config.yaml` og miljøvariabler (`.env`).

---

## config.yaml

Alle beløp oppgis i hele kroner (NOK). Bruk `0` for poster som ikke er aktuelle.

### `selskap`

| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `navn` | tekst | ja | Selskapets registrerte navn |
| `org_nummer` | tekst | ja | Organisasjonsnummer, 9 siffer uten mellomrom |
| `daglig_leder` | tekst | ja | Fullt navn på daglig leder |
| `styreleder` | tekst | ja | Fullt navn på styreleder (kan være samme som daglig leder) |
| `forretningsadresse` | tekst | ja | Gateadresse, postnummer og poststed |
| `stiftelsesaar` | heltall | ja | Året selskapet ble stiftet |
| `stiftelsesdato` | dato | nei | Eksakt stiftelsesdato (ÅÅÅÅ-MM-DD). Hentes fra Enhetsregisteret. Brukes som stiftelsesdato i aksjonærregisteroppgaven, og som start på et forlenget første regnskapsår. Uten den brukes 1. januar i stiftelsesåret |
| `aksjekapital` | heltall | ja | Innbetalt aksjekapital i NOK, fra stiftelsesdokumentene |

### `regnskapsaar`

| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `regnskapsaar` | heltall | ja | Året regnskapet gjelder for, f.eks. `2024` |

### `resultatregnskap`

#### `driftsinntekter`

| Felt | Type | Beskrivelse |
|---|---|---|
| `salgsinntekter` | heltall | Inntekter fra salg av varer eller tjenester |
| `andre_driftsinntekter` | heltall | Andre løpende driftsinntekter |

#### `driftskostnader`

| Felt | Type | Beskrivelse |
|---|---|---|
| `loennskostnader` | heltall | Lønn, arbeidsgiveravgift og lignende |
| `avskrivninger` | heltall | Planmessige avskrivninger på anleggsmidler |
| `andre_driftskostnader` | heltall | Bank- og regnskapsgebyrer, kontorkostnader o.l. |

#### `finansposter`

| Felt | Type | Beskrivelse |
|---|---|---|
| `utbytte_fra_datterselskap` | heltall | Utbytte mottatt fra datterselskaper (dekkes av fritaksmetoden) |
| `andre_finansinntekter` | heltall | Renteinntekter og andre finansinntekter |
| `rentekostnader` | heltall | Renter på lån |
| `andre_finanskostnader` | heltall | Andre finanskostnader |

#### Regnskapsperiode

Feltene ligger på toppnivå i `config.yaml`, ved siden av `regnskapsaar`. Begge er valgfrie.

| Felt | Type | Beskrivelse |
|---|---|---|
| `regnskapsstart` | dato | Første dag i regnskapsperioden (ÅÅÅÅ-MM-DD). Tom = 1. januar i regnskapsåret |
| `regnskapsslutt` | dato | Siste dag i regnskapsperioden. Tom = 31. desember i regnskapsåret |

Regnskapsåret er normalt kalenderåret (regnskapsloven § 1-7 første ledd), og da skal begge stå tomme. De oppgis bare ved **forlenget første regnskapsår** etter § 1-7 andre ledd: et selskap stiftet sent på året kan la det første regnskapsåret løpe i inntil 18 måneder, fram til 31. desember året etter. Perioden starter da på stiftelsesdatoen, og `regnskapsaar` skal være året perioden avsluttes.

Wenche stopper innsendingen hvis perioden ikke kan tolkes entydig: over 18 måneder, slutt som ikke er 31. desember, slutt før start, eller `regnskapsaar` som ikke er sluttåret. En periode over 12 måneder gir en advarsel som viser hvilket inntektsår den fastsettes i.

#### Skattekostnad

Feltet ligger direkte under `resultatregnskap`, ikke i en underseksjon.

| Felt | Type | Beskrivelse |
|---|---|---|
| `skattekostnad` | heltall | Skattekostnad på ordinært resultat (rskl. § 6-1). Egen linje mellom resultat før skatt og årsresultat. 0 for et selskap uten skattepliktig inntekt |

Årsresultatet utledes som resultat før skatt minus skattekostnad. Har selskapet skattepliktig inntekt (for eksempel renteinntekt, eller 3 %-tillegget på fritatt utbytte), skal skatten føres her, og som `betalbar_skatt` i balansen hvis den ikke er betalt ved årsslutt. Wenche kan foreslå tallet: knappen «Foreslå skattekostnad» i Tall-steget regner ut 22 % av skattepliktig inntekt. Forslaget føres aldri automatisk.

### `balanse`

#### `eiendeler.anleggsmidler`

| Felt | Type | Beskrivelse |
|---|---|---|
| `aksjer_i_datterselskap` | heltall | Kostpris for aksjer i heleide datterselskaper |
| `andre_aksjer` | heltall | Aksjer i selskaper der eierandelen er under 90 % |
| `langsiktige_fordringer` | heltall | Lån gitt til andre med løpetid over 1 år |

#### `eiendeler.omloepmidler`

| Felt | Type | Beskrivelse |
|---|---|---|
| `kortsiktige_fordringer` | heltall | Kundefordringer og andre kortsiktige krav |
| `bankinnskudd` | heltall | Saldo på driftskonto per 31.12 |

#### `egenkapital_og_gjeld.egenkapital`

| Felt | Type | Beskrivelse |
|---|---|---|
| `aksjekapital` | heltall | Innbetalt aksjekapital (fra stiftelsesdokumentene) |
| `overkursfond` | heltall | Innbetalt over pålydende ved emisjon |
| `annen_egenkapital` | heltall | Akkumulert overskudd/underskudd. Negativ verdi = akkumulert underskudd |

#### `egenkapital_og_gjeld.langsiktig_gjeld`

| Felt | Type | Beskrivelse |
|---|---|---|
| `laan_fra_aksjonaer` | heltall | Lån fra eier med avtalt løpetid over 1 år |
| `andre_langsiktige_laan` | heltall | Banklån og andre lån med løpetid over 1 år |

#### `egenkapital_og_gjeld.kortsiktig_gjeld`

| Felt | Type | Beskrivelse |
|---|---|---|
| `leverandoergjeld` | heltall | Ubetalte fakturaer per 31.12 |
| `betalbar_skatt` | heltall | Skyldig selskapsskatt per 31.12 (konto 2500), motposten til `skattekostnad` |
| `skyldige_offentlige_avgifter` | heltall | Skyldig mva, arbeidsgiveravgift o.l. |
| `annen_kortsiktig_gjeld` | heltall | Annen gjeld med forfall innen 1 år |

### `foregaaende_aar` (valgfritt)

Obligatorisk etter regnskapslovens § 6-6, men kan utelates for selskaper som er stiftet i inneværende regnskapsår.

Har nøyaktig samme struktur som `resultatregnskap` og `balanse` ovenfor. Kopier inn tilsvarende tall fra fjorårets regnskap.

```yaml
foregaaende_aar:
  resultatregnskap:
    # samme struktur som resultatregnskap
  balanse:
    # samme struktur som balanse
```

### `skattemelding`

| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `underskudd_til_fremfoering` | heltall | nei | Fremførbart underskudd fra tidligere år (NOK). Finnes i fjorårets skattemelding. Standard: `0` |
| `anvend_fritaksmetoden` | boolsk | nei | `true` for holdingselskaper som eier aksjer i datterselskaper (sktl. § 2-38). Standard: `false` |
| `eierandel_for_fritaksmetoden` | heltall | nei | Eierandel i selskapet som deler ut utbytte, i prosent (0-100). Brukes bare når `anvend_fritaksmetoden` er `true`. ≥ 90 %: hele utbyttet fritatt. < 90 %: 3 % skattepliktig (sjablonregelen, sktl. § 2-38 sjette ledd). Standard: `100` |
| `boersnotert` | boolsk | nei | `true` hvis selskapet er børsnotert. Standard: `false` |
| `formuesverdi_aksjer` | heltall | nei | Formuesverdi av aksjer selskapet eier i andre selskap, fra aksjeoppgaven (RF-1088S, post 209). Brukes til å beregne netto formuesverdi bak selskapets egne aksjer. Standard: `0` |
| `samlet_verdi_bak_aksjene` | heltall | nei | Overstyrer den beregnede netto formuesverdien bak aksjene direkte. Utelat for å la Wenche beregne den fra `formuesverdi_aksjer` og balansen |

### `aksjonaerer`

Liste over alle aksjonærer per 31.12 i regnskapsåret.

| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `navn` | tekst | ja | Aksjonærens fulle navn |
| `fodselsnummer` | tekst | ja | Fødselsnummer (personnummer), 11 siffer |
| `antall_aksjer` | heltall | ja | Antall aksjer eid per 31.12 |
| `aksjeklasse` | tekst | ja | Aksjeklasse, f.eks. `ordinære` |
| `utbytte_utbetalt` | heltall | nei | Utbytte utbetalt til denne aksjonæren i løpet av året (NOK). Standard: `0` |
| `innbetalt_kapital_per_aksje` | heltall | nei | Innbetalt kapital per aksje i NOK. Beregnes som aksjekapital / antall aksjer. Standard: `0` |

---

## Miljøvariabler (.env)

| Variabel | Påkrevd | Beskrivelse |
|---|---|---|
| `MASKINPORTEN_CLIENT_ID` | ja | Klient-ID fra Digdirs selvbetjeningsportal |
| `MASKINPORTEN_KID` | ja | UUID for offentlig nøkkel registrert på klienten |
| `MASKINPORTEN_PRIVAT_NOKKEL` | ja | Sti til privat nøkkelfil. Standard: `maskinporten_privat.pem` |
| `ORG_NUMMER` | ja | Ditt eget organisasjonsnummer (9 siffer). Brukes som systembruker_org og party |
