# Referanse

Komplett dokumentasjon for konfigurasjonsfilen `config.yaml`, miljøvariabler (`.env`) og CLI-kommandoer.

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
| `skyldige_offentlige_avgifter` | heltall | Skyldig mva, arbeidsgiveravgift, skyldig skatt o.l. |
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
| `eierandel_datterselskap` | heltall | nei | Eierandel i datterselskapet i prosent (0–100). ≥ 90 %: hele utbyttet fritatt. < 90 %: 3 % skattepliktig (sjablonregelen, sktl. § 2-38 sjette ledd). Standard: `100` |
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

Maskinporten test og prod er separate registre med ulike klient-UUID-er. Wenche støtter to konvensjoner: miljø-spesifikke variabler (anbefalt) eller generiske variabler. Hvis begge er satt, vinner miljø-spesifikk variant.

### Miljø-spesifikke variabler (anbefalt)

| Variabel | Brukes når | Beskrivelse |
|---|---|---|
| `MASKINPORTEN_CLIENT_ID_TEST` | testmiljø | Klient-ID for test-Maskinporten fra Digdir |
| `MASKINPORTEN_KID_TEST` | testmiljø | UUID for offentlig nøkkel registrert på test-klienten |
| `MASKINPORTEN_CLIENT_ID_PROD` | prod | Klient-ID for prod-Maskinporten fra Digdir |
| `MASKINPORTEN_KID_PROD` | prod | UUID for offentlig nøkkel registrert på prod-klienten |

### Felles og generiske

| Variabel | Påkrevd | Beskrivelse |
|---|---|---|
| `MASKINPORTEN_PRIVAT_NOKKEL` | ja | Sti til privat nøkkelfil. Samme nøkkel kan brukes i begge miljø. Standard: `maskinporten_privat.pem` |
| `ORG_NUMMER` | ja (for prod) | Ditt eget organisasjonsnummer (9 siffer). Brukes som systembruker_org og party i prod |
| `SKD_TEST_ORG_NUMMER` | ja (for test) | Syntetisk Tenor-orgnr som brukes som systembruker_org og party i testmiljø |
| `WENCHE_ENV` | nei | `prod` (standard) eller `test`. Påvirker CLI-kommandoer. Send-fanen i UI-et har egen velger som overstyrer per innsending |
| `SKD_TEST_PARTSNUMMER` | nei | Partsnummer fra Tenor for skattemelding-test. Setter man denne hopper Wenche over kallet til SKDs forhåndsutfylt-API og bruker partsnummeret direkte |
| `MASKINPORTEN_CLIENT_ID` | nei | Generisk fallback. Brukes hvis ingen miljø-spesifikk variant er satt |
| `MASKINPORTEN_KID` | nei | Generisk fallback. Brukes hvis ingen miljø-spesifikk variant er satt |

---

## CLI-kommandoer

### `wenche login`

Autentiserer mot Maskinporten med RSA-nøkkel og lagrer Altinn-token lokalt.

```bash
wenche login
```

Tokenet lagres i `~/.wenche/token.json` og gjenbrukes automatisk av påfølgende kommandoer.

---

### `wenche logout`

Sletter lagret token.

```bash
wenche logout
```

---

### `wenche generer-skattemelding`

Genererer ferdig utfylt sammendrag av næringsspesifikasjonen og skattemeldingen.

```bash
wenche generer-skattemelding [--config FILSTI] [--ut FILSTI]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--ut` | Lagre sammendrag til fil i stedet for å skrive til skjermen |

---

### `wenche send-aarsregnskap`

Sender inn årsregnskap til Brønnøysundregistrene via Altinn.

```bash
wenche send-aarsregnskap [--config FILSTI] [--dry-run]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--dry-run` | Genererer XML-dokumentene lokalt uten å sende til Altinn |

---

### `wenche send-aksjonaerregister`

Sender inn aksjonærregisteroppgave (RF-1086) til Skatteetaten via Altinn.

```bash
wenche send-aksjonaerregister [--config FILSTI] [--dry-run]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--dry-run` | Genererer XML lokalt uten å sende til Altinn |

---

### `wenche send-skattemelding`

Sender inn skattemelding for AS til Skatteetaten via Altinn3.

```bash
wenche send-skattemelding [--config FILSTI] [--dry-run]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--dry-run` | Henter forhåndsutfylt og genererer XML lokalt (`skattemelding.xml` og `naeringsspesifikasjon.xml`) uten å validere eller sende |

Validerer mot Skatteetaten som første steg og laster ikke opp noe hvis resultatet ikke er `validertOK`. Etter opplasting skriver Wenche ut en lenke til Altinn-innboksen. Innsendingen fullføres først når en personlig bruker signerer med BankID i Altinn, det kan ikke gjøres maskinelt.

Krever at Maskinporten-klienten har fått scopet `skatteetaten:formueinntekt/skattemelding` innvilget. Se [steg 2f i oppsett](oppsett.md#2f-sk-om-tilgang-til-skds-api-for-skattemelding).

---

### `wenche valider-skattemelding`

Validerer skattemeldingen mot Skatteetatens valideringstjeneste uten å sende inn, og skriver ut eventuelle avvik og merknader. Nyttig som forhåndskontroll før innsending.

```bash
wenche valider-skattemelding [--config FILSTI]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |

Validering lagrer ikke data hos Skatteetaten og er ikke en innsending. `send-skattemelding` (og Send-knappen i UI) kjører den samme valideringen automatisk, så denne kommandoen er mest nyttig for å inspisere avvik og merknader uten å sende. Bruker samme scope som `send-skattemelding`.

---

### `wenche registrer-system`

Registrerer Wenche i Altinns systemregister. Kjøres én gang per miljø (test/prod).

```bash
wenche registrer-system
```

Kan kjøres på nytt uten skade — oppdaterer automatisk hvis systemet allerede finnes.

---

### `wenche opprett-systembruker`

Oppretter en systembrukerforespørsel og skriver ut en `confirmUrl`.

```bash
wenche opprett-systembruker
```

Åpne lenken i nettleseren og godkjenn tilgangen med TestID (testmiljø) eller ID-porten (produksjon).

---

### `wenche importer-saft`

Importerer en SAF-T Financial XML-fil og genererer `config.yaml` automatisk.

```bash
wenche importer-saft SAF-T-FIL [--ut FILSTI]
```

| Argument/alternativ | Beskrivelse |
|---|---|
| `SAF-T-FIL` | Sti til SAF-T Financial XML-filen eksportert fra regnskapssystemet (påkrevd) |
| `--ut` | Sti til `config.yaml` som skal skrives. Standard: `config.yaml` |

Etter import må følgende felt fylles inn manuelt i `config.yaml`:

- `selskap.daglig_leder`
- `selskap.styreleder`
- `selskap.stiftelsesaar`
- `aksjonaerer` (navn, fødselsnummer, antall aksjer, utbytte)
- `foregaaende_aar.resultatregnskap` (er ikke tilgjengelig i SAF-T)

Følgende felt fylles inn automatisk så langt det lar seg gjøre fra SAF-T, men bør verifiseres:

- `selskap.kontakt_epost` hentes fra `Company/Contact/Email` hvis SAF-T-fila inneholder det
- `noter.laan_til_naerstaaende` får en stub-oppføring med saldo og retning satt hvis konto 2250 (gjeld til eier) har saldo. Motpart, rentesats og sikkerhet må fortsatt fylles inn manuelt
- `skattemelding.underskudd_til_fremfoering` estimeres fra åpningssaldoen på konto 2080 (udekket tap). Verdien er regnskapsmessig og kan avvike fra det skattemessige fremførbare underskuddet; verifiser mot fjorårets skattemelding hvis selskapet har ikke-fradragsberettigede kostnader

!!! tip "Tilgjengelig i webgrensesnittet"
    SAF-T-import er også tilgjengelig under fanen **Selskap** i `wenche ui`.

---

### `wenche ui`

Starter webgrensesnittet i nettleseren.

```bash
wenche ui
```

Åpner webgrensesnittet på `http://localhost:8080`.
