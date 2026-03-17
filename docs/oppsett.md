# Oppsett

Wenche bruker Maskinporten for å autentisere deg som konsument overfor Altinn og Skatteetaten — uten nettleserinnlogging. Oppsettet består av fem steg:

1. Generer et RSA-nøkkelpar lokalt
2. Registrer en Maskinporten-klient hos Digdir
3. Konfigurer miljøvariabler (`.env`)
4. Fyll ut selskapsinformasjon (`config.yaml`)
5. Registrer systembruker i Altinn

!!! note "Bruker du webgrensesnittet?"
    Steg 3 og 4 kan gjøres direkte i nettleseren: start `wenche ui` og gå til fanen **Oppsett**. Steg 1, 2 og 5 må uansett gjøres manuelt — de krever terminalkommandoer og registrering hos Digdir og Altinn.

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

!!! info "Produksjon eller test?"
    De fleste trenger kun å sette opp **Produksjon**. Testmiljøet (Altinn tt02) er for utviklere som vil teste innsending uten å sende ekte data til myndighetene. De to miljøene har hver sin portal:

    - **Produksjon:** [selvbetjeningsportalen.digdir.no](https://selvbetjeningsportalen.digdir.no)
    - **Test:** [sjolvbetjening.test.samarbeid.digdir.no](https://sjolvbetjening.test.samarbeid.digdir.no)

    Setter du opp begge miljøene, gjenta steg 2b og 2c i begge portaler.

Logg inn på riktig portal og følg stegene under:

1. Velg **Klienter** → **Maskinporten & KRR**
2. Klikk **Ny integrasjon** og fyll ut:
    - Visningsnavn: `wenche`
    - Access token levetid: `120`
3. Legg til følgende scopes:

    | Scope | Formål |
    |---|---|
    | `altinn:instances.read` | Lese instanser ved innsending av årsregnskap |
    | `altinn:instances.write` | Opprette instanser ved innsending av årsregnskap |
    | `altinn:authentication/systemregister.write` | Registrere Wenche som leverandørsystem (steg 5) |
    | `altinn:authentication/systemuser.request.read` | Sjekke status for systembrukerforespørsel (steg 5) |
    | `altinn:authentication/systemuser.request.write` | Opprette systembrukerforespørsel (steg 5) |

    !!! note "Aksjonærregisteroppgave krever ekstra scope"
        Innsending av aksjonærregisteroppgave (RF-1086) bruker SKDs eget REST-API og krever scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave`. Dette scopet søkes om separat — se steg 2d.

4. Kopier **klient-ID** — du trenger den i steg 3

### 2c. Last opp offentlig nøkkel

Under klienten, klikk **Legg til nøkkel** og lim inn innholdet i `maskinporten_offentlig.pem`. Lagre klienten.

Nøkkelen vil vises i listen med en UUID (f.eks. `9bc5078c-...`). Kopier denne UUID-en — dette er din **KID**, som du trenger i steg 3.

### 2d. Søk om tilgang til SKDs API for aksjonærregisteroppgave

!!! note "Valgfritt"
    Dette steget er kun nødvendig dersom du skal sende inn aksjonærregisteroppgave (RF-1086). Hopp over om du bare bruker Wenche til årsregnskap og skattemelding.

Scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` søkes om i to omganger:

**Del 1 — Søk om tilgang hos Skatteetaten**

1. Gå til [SKDs brukerstøtteportal](https://eksternjira.sits.no/plugins/servlet/desk/site/global) og logg inn
2. Opprett en ny sak under **Innrapportering → Aksjonærregisteret**, kategori **Teknisk**
3. Oppgi i henvendelsen:
    - At du ønsker tilgang til scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave`
    - Organisasjonsnummeret ditt
    - Om du ønsker tilgang til testmiljø, produksjon, eller begge

SKD behandler vanligvis slike forespørsler innen noen virkedager.

**Del 2 — Legg til scope i Digdirs selvbetjeningsportal**

Når SKD bekrefter at tilgangen er innvilget, logg inn i Digdirs selvbetjeningsportal (se steg 2b) og legg til scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` på Maskinporten-klienten din. Scopet vil nå være søkbart i portalen.

!!! warning "Begge steg er nødvendige"
    Tilgangen fra SKD aktiveres ikke automatisk på klienten. Du må eksplisitt legge til scopet i Digdirs portal etter at SKD har innvilget det.

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
ORG_NUMMER=ditt-organisasjonsnummer
WENCHE_ENV=prod
```

!!! warning "Ikke bruk anførselstegn"
    Verdiene skal skrives direkte uten hermetegn, slik som vist ovenfor.

| Variabel | Hva det er |
|---|---|
| `MASKINPORTEN_CLIENT_ID` | Klient-ID fra selvbetjeningsportalen |
| `MASKINPORTEN_KID` | UUID som portalen tildelte nøkkelen din |
| `MASKINPORTEN_PRIVAT_NOKKEL` | Sti til din private nøkkelfil (standard: `maskinporten_privat.pem`) |
| `ORG_NUMMER` | Ditt organisasjonsnummer (9 siffer) |
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

## Steg 5 — Registrer systembruker i Altinn

Altinn 3 krever at Wenche er registrert som et leverandørsystem, og at organisasjonen din har godkjent en systembruker. Dette gjøres **én gang per miljø** (test/prod).

!!! note "Bruker du webgrensesnittet?"
    Disse stegene kan gjøres direkte i nettleseren: start `wenche ui` og gå til **Oppsett → Systembruker-oppsett**.

### 5a. Registrer system

```bash
wenche registrer-system
```

Registrerer Wenche i Altinns systemregister med riktige tilgangsrettigheter. Kan kjøres på nytt uten skade — oppdaterer automatisk hvis systemet allerede finnes.

### 5b. Opprett systembrukerforespørsel

=== "Produksjon"

    ```bash
    wenche opprett-systembruker
    ```

    Oppretter en forespørsel på ditt eget organisasjonsnummer (`ORG_NUMMER` fra `.env`) og skriver ut en `confirmUrl`. Åpne lenken i nettleseren, logg inn med ID-porten, og godkjenn tilgangen.

=== "Testmiljø (tt02)"

    Altinns testmiljø bruker syntetiske testdata. Din egen organisasjon finnes ikke i testregisteret, og du må bruke en **syntetisk testorganisasjon fra Tenor**.

    **1. Finn en syntetisk test-AS i Tenor**

    Gå til [Tenor testdatasøk](https://www.skatteetaten.no/skjema/testdata/) og søk frem et aksjeselskap (AS). Noter deg:

    - Organisasjonsnummeret til selskapet
    - Fødselsnummeret til daglig leder (finnes under **Kildedata → rollegrupper → DAGL**)

    **2. Opprett systembrukerforespørsel for Tenor-org**

    ```bash
    wenche opprett-systembruker --org <tenor-orgnr>
    ```

    Erstatt `<tenor-orgnr>` med organisasjonsnummeret du fant i Tenor.

    **3. Godkjenn forespørselen**

    Kommandoen skriver ut en `confirmUrl`. Åpne lenken i nettleseren og logg inn med **TestID** (syntetisk BankID) ved å bruke fødselsnummeret til daglig leder fra steg 1.

    **4. Konfigurer testmiljøet i `.env`**

    Legg til følgende linje i `.env`:

    ```
    SKD_TEST_ORG_NUMMER=<tenor-orgnr>
    ```

    Wenche bruker da automatisk Tenor-org-et i XML-en og i Maskinporten-tokenet når `WENCHE_ENV=test`.

    !!! info "Hvorfor syntetiske data i test?"
        Skatteetaten og Altinns testmiljø er populert med data fra Tenor. Din reelle organisasjon eksisterer ikke i testregisteret, og innsending vil feile på bekreftelsessteget. Bruk av syntetisk org i test er ikke en begrensning i Wenche — det er et krav fra SKD og Altinn.

### 5c. Verifiser oppsett

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
