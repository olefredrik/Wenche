# Oppsett

Wenche bruker Maskinporten for å autentisere deg som konsument overfor Altinn — uten nettleserinnlogging. Oppsettet består av fire steg:

1. Generer et RSA-nøkkelpar lokalt
2. Registrer en Maskinporten-klient hos Digdir
3. Konfigurer miljøvariabler (`.env`)
4. Fyll ut selskapsinformasjon (`config.yaml`)

!!! note "Bruker du webgrensesnittet?"
    Steg 3 og 4 kan gjøres direkte i nettleseren: start `wenche ui` og gå til fanen **Oppsett**. Steg 1 og 2 må uansett gjøres manuelt — de krever terminalkommandoer og registrering hos Digdir.

---

## Steg 1 — Generer RSA-nøkkelpar

Nøklene brukes til å identifisere deg overfor Maskinporten. Den private nøkkelen beholdes lokalt; den offentlige lastes opp til Digdir i steg 2.

Kjør disse to kommandoene i terminalen fra mappen der Wenche er installert:

```bash
openssl genrsa -out maskinporten_privat.pem 2048
openssl rsa -in maskinporten_privat.pem -pubout -out maskinporten_offentlig.pem
```

Du skal nå ha to filer: `maskinporten_privat.pem` og `maskinporten_offentlig.pem`.

!!! warning "Ikke del den private nøkkelen"
    `maskinporten_privat.pem` skal aldri deles med andre eller legges i git. Filen er lagt til i `.gitignore`.

---

## Steg 2 — Registrer Maskinporten-klient hos Digdir

### 2a. Søk om tilgang

Gå til [samarbeid.digdir.no](https://samarbeid.digdir.no) og søk om tilgang som **Maskinporten-konsument**. Du vil motta en e-post med bekreftelse og lenke til selvbetjeningsportalen.

!!! info "Behandlingstid"
    Tilgang til selvbetjeningsportalen gis vanligvis samme dag, men kan ta noe lenger tid. Steg 2b og 2c gjøres etter at du har fått tilgang.

### 2b. Opprett integrasjon

Logg inn på [selvbetjeningsportalen.digdir.no](https://selvbetjeningsportalen.digdir.no):

1. Velg **Produksjon** (eller **Test** for testmiljø)
2. Velg **Klienter** → **Maskinporten & KRR**
3. Klikk **Ny integrasjon** og fyll ut:
    - Visningsnavn: `wenche`
    - Access token levetid: `120`
4. Legg til følgende scopes:

    | Scope | Formål |
    |---|---|
    | `altinn:instances.read` | Lese instanser ved innsending |
    | `altinn:instances.write` | Opprette instanser ved innsending |
    | `altinn:authentication/systemregister.write` | Registrere Wenche som leverandørsystem (steg 5) |
    | `altinn:authentication/systemuser.request.read` | Sjekke status for systembrukerforespørsel (steg 5) |
    | `altinn:authentication/systemuser.request.write` | Opprette systembrukerforespørsel (steg 5) |

5. Kopier **klient-ID** — du trenger den i steg 3

### 2c. Last opp offentlig nøkkel

Under klienten, klikk **Legg til nøkkel** og lim inn innholdet i `maskinporten_offentlig.pem`. Lagre klienten.

Nøkkelen vil vises i listen med en UUID (f.eks. `9bc5078c-...`). Kopier denne UUID-en — dette er din **KID**, som du trenger i steg 3.

---

## Steg 3 — Konfigurer miljøvariabler

Kopier eksempelfilen:

```bash
cp .env.example .env
```

Åpne `.env` og fyll inn verdiene fra portalen:

```
MASKINPORTEN_CLIENT_ID=din-klient-id-her
MASKINPORTEN_KID=uuid-fra-portalen-her
MASKINPORTEN_PRIVAT_NOKKEL=maskinporten_privat.pem
WENCHE_ENV=prod
```

!!! warning "Ikke bruk anførselstegn"
    Verdiene skal skrives direkte uten hermetegn, slik som vist ovenfor.

| Variabel | Hva det er |
|---|---|
| `MASKINPORTEN_CLIENT_ID` | Klient-ID fra selvbetjeningsportalen |
| `MASKINPORTEN_KID` | UUID som portalen tildelte nøkkelen din |
| `MASKINPORTEN_PRIVAT_NOKKEL` | Sti til din private nøkkelfil (standard: `maskinporten_privat.pem`) |
| `WENCHE_ENV` | `prod` for produksjon, `test` for Altinn tt02-testmiljø |

---

## Steg 4 — Fyll ut config.yaml

Kopier eksempelfilen:

```bash
cp config.example.yaml config.yaml
```

Åpne `config.yaml` og fyll inn selskapets opplysninger, regnskapstall og aksjonærdata. Filen er kommentert og selvforklarende. Alle beløp oppgis i hele kroner (NOK).

!!! tip "Webgrensesnittet"
    Bruker du `wenche ui` kan du fylle ut all informasjon om selskapet, regnskapet og aksjonærene direkte i nettleseren under fanene **Selskap**, **Regnskap og balanse** og **Aksjonærer** — ingen manuell filredigering nødvendig.

---

## Steg 5 — Registrer Wenche som leverandørsystem

Altinn 3 krever at Wenche er registrert som et leverandørsystem, og at organisasjonen din har godkjent en systembruker. Dette gjøres **én gang per miljø** (test/prod).

!!! note "Bruker du webgrensesnittet?"
    Disse stegene kan gjøres direkte i nettleseren: start `wenche ui` og gå til **Oppsett → Systembruker-oppsett**.

### 5a. Registrer system

```bash
wenche registrer-system
```

Registrerer Wenche i Altinns systemregister med riktige tilgangsrettigheter. Kan kjøres på nytt uten skade — oppdaterer automatisk hvis systemet allerede finnes.

### 5b. Opprett systembrukerforespørsel

```bash
wenche opprett-systembruker
```

Oppretter en forespørsel og skriver ut en `confirmUrl`. Åpne lenken i nettleseren, logg inn med TestID (testmiljø) eller ID-porten (produksjon), og godkjenn tilgangen.

---

## Verifiser oppsett

Når forespørselen er godkjent, test at innlogging fungerer:

```bash
wenche login
```

Vellykket utskrift:

```
Autentiserer mot Maskinporten (systembruker)...
Maskinporten-token mottatt. Henter Altinn-token...
Autentisering vellykket.
```

Logg deretter ut igjen:

```bash
wenche logout
```

Får du feilen `invalid_altinn_customer_configuration` betyr det at systembrukeren ikke er godkjent ennå — fullfør steg 5b. Dobbeltsjekk ellers at klient-ID og KID i `.env` stemmer med det som vises i selvbetjeningsportalen.

[Gå videre til bruk →](bruk.md){ .md-button .md-button--primary }
