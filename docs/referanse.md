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
| `underskudd_til_fremfoering` | heltall | nei | Fremførbart underskudd fra tidligere år (NOK). Finnes i fjorårets skattemelding (RF-1028). Standard: `0` |
| `anvend_fritaksmetoden` | boolsk | nei | `true` for holdingselskaper som eier aksjer i datterselskaper (sktl. § 2-38). Standard: `false` |
| `eierandel_datterselskap` | heltall | nei | Eierandel i datterselskapet i prosent (0–100). ≥ 90 %: hele utbyttet fritatt. < 90 %: 3 % skattepliktig (sjablonregelen, sktl. § 2-38 sjette ledd). Standard: `100` |

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
| `MASKINPORTEN_CLIENT_ID` | ja | Klient-ID fra Digdir selvbetjeningsportal |
| `MASKINPORTEN_KID` | ja | UUID som portalen tildelte den offentlige nøkkelen |
| `MASKINPORTEN_PRIVAT_NOKKEL` | ja | Sti til privat nøkkelfil. Standard: `maskinporten_privat.pem` |
| `WENCHE_ENV` | nei | `prod` for produksjon, `test` for Altinn tt02-testmiljø. Standard: `prod` |

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

Genererer ferdig utfylt sammendrag av RF-1167 (næringsoppgaven) og RF-1028 (skattemeldingen).

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

!!! tip "Tilgjengelig i webgrensesnittet"
    SAF-T-import er også tilgjengelig under fanen **Selskap** i `wenche ui`.

---

### `wenche ui`

Starter webgrensesnittet i nettleseren.

```bash
wenche ui
```

Åpner webgrensesnittet på `http://localhost:8080`.
