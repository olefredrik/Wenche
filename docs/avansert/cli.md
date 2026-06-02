# Kommandolinje

!!! info "For utviklere og automatisering"
    Denne siden er for de som vil automatisere innsending fra terminalen, kjøre Wenche fra CI/CD, eller skripte oppgaver. Vanlig bruk dekkes av webgrensesnittet, se [Bruk](../bruk.md).

Wenche kan brukes fra kommandolinjen som alternativ til webgrensesnittet. Alle kommandoer leser konfigurasjon fra `~/.wenche/.env` og `config.yaml` (eller en sti oppgitt med `--config`).

---

## Miljøvariabel for CLI

| Variabel | Beskrivelse |
|---|---|
| `WENCHE_ENV` | `prod` (standard) eller `test`. Styrer hvilket miljø CLI-kommandoene bruker. Påvirker ikke `wenche`/`wenche dev`, de er låst til hvert sitt miljø. |

For testmiljø-bruk med CLI må test-credentials være satt i `~/.wenche/.env` med `_TEST`-suffix. Se [Testing mot tt02](testing.md) for detaljer.

---

## `wenche login`

Autentiserer mot Maskinporten med RSA-nøkkel og lagrer Altinn-token lokalt.

```bash
wenche login
```

Tokenet lagres i `~/.wenche/token.json` og gjenbrukes automatisk av påfølgende kommandoer.

---

## `wenche logout`

Sletter lagret token.

```bash
wenche logout
```

---

## `wenche generer-skattemelding`

Genererer ferdig utfylt sammendrag av næringsspesifikasjonen og skattemeldingen.

```bash
wenche generer-skattemelding [--config FILSTI] [--ut FILSTI]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--ut` | Lagre sammendrag til fil i stedet for å skrive til skjermen |

---

## `wenche send-aarsregnskap`

Sender inn årsregnskap til Brønnøysundregistrene via Altinn.

```bash
wenche send-aarsregnskap [--config FILSTI] [--dry-run]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--dry-run` | Genererer XML-dokumentene lokalt uten å sende til Altinn |

---

## `wenche send-aksjonaerregister`

Sender inn aksjonærregisteroppgave (RF-1086) til Skatteetaten via Altinn.

```bash
wenche send-aksjonaerregister [--config FILSTI] [--dry-run]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--dry-run` | Genererer XML lokalt uten å sende til Altinn |

---

## `wenche send-skattemelding`

Sender inn skattemelding for AS til Skatteetaten via Altinn3.

```bash
wenche send-skattemelding [--config FILSTI] [--dry-run]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |
| `--dry-run` | Henter forhåndsutfylt og genererer XML lokalt (`skattemelding.xml` og `naeringsspesifikasjon.xml`) uten å validere eller sende |

Validerer mot Skatteetaten som første steg og laster ikke opp noe hvis resultatet ikke er `validertOK`. Etter opplasting skriver Wenche ut en lenke til Altinn-innboksen. Innsendingen fullføres først når en personlig bruker signerer med BankID i Altinn, det kan ikke gjøres maskinelt.

Krever at Maskinporten-klienten har fått scopet `skatteetaten:formueinntekt/skattemelding` innvilget. Se [steg 2g i oppsett](../oppsett.md#2g-sk-om-tilgang-til-skds-api-for-skattemelding).

---

## `wenche valider-skattemelding`

Validerer skattemeldingen mot Skatteetatens valideringstjeneste uten å sende inn, og skriver ut eventuelle avvik og merknader. Nyttig som forhåndskontroll før innsending.

```bash
wenche valider-skattemelding [--config FILSTI]
```

| Alternativ | Beskrivelse |
|---|---|
| `--config` | Sti til konfigurasjonsfil. Standard: `config.yaml` |

Validering lagrer ikke data hos Skatteetaten og er ikke en innsending. `send-skattemelding` (og webgrensesnittet) kjører den samme valideringen automatisk, så denne kommandoen er mest nyttig for å inspisere avvik og merknader uten å sende. Bruker samme scope som `send-skattemelding`.

---

## `wenche registrer-system`

Registrerer Wenche i Altinns systemregister. Kjøres én gang per miljø.

```bash
wenche registrer-system
```

Kan kjøres på nytt uten skade, oppdaterer automatisk hvis systemet allerede finnes.

---

## `wenche opprett-systembruker`

Oppretter en systembrukerforespørsel og skriver ut en `confirmUrl`.

```bash
wenche opprett-systembruker [--org ORGNR]
```

| Alternativ | Beskrivelse |
|---|---|
| `--org` | Org.nr. for systembrukeren. Standard: `ORG_NUMMER` fra `.env`. I testmiljø skal dette være et syntetisk org.nr. fra Tenor |

Åpne lenken i nettleseren og godkjenn tilgangen med ID-porten (produksjon) eller TestID (testmiljø).

---

## `wenche importer-saft`

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

!!! tip "I webgrensesnittet"
    SAF-T-import gjøres fra kommandolinjen (`wenche importer-saft`). I `wenche`-webgrensesnittet (fanen **Tall**) finner du i stedet **Hent tall fra Bodil**, som laster opp en ferdig `config.yaml`.
