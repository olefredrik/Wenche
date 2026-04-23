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

### 2a. Registrer virksomheten hos Digdir (kun første gang)

!!! info "Gjelder deg?"
    Dette steget gjelder **kun virksomheter som ikke tidligere har brukt Maskinporten eller ID-porten** — typisk holdingselskaper og nyopprettede AS. Har virksomheten din allerede en aktiv Maskinporten-tilknytning, hopp rett til steg 2b.

    Prøver du å logge inn på selvbetjeningsportalen uten å ha gjort dette, vil du få feilmeldingen:
    > PRECONDITION_REQUIRED: Virksomheten har ikke signert de relevante bruksvilkårene.

Fyll ut [informasjonsskjemaet for Maskinporten-konsumenter](https://samarbeid.digdir.no/maskinporten/konsument/119) på Digdirs nettside. Digdir behandler søknaden og sender deg en e-post med instruksjoner om å signere bruksvilkårene («Bruksvilkår for private verksemder»).

!!! info "Behandlingstid"
    Dette kan ta noen virkedager. Maskinporten er gratis for konsumenter.

Når bruksvilkårene er signert, fortsett til steg 2b.

### 2b. Søk om tilgang i selvbetjeningsportalen

Gå til [sjolvbetjening.samarbeid.digdir.no](https://sjolvbetjening.samarbeid.digdir.no) og logg inn. Første gang du logger inn, vil du bli møtt av et skjema — **Be om tilgang**:

1. Fyll inn organisasjonsnummeret ditt
2. Kryss av **Opprette og endre integrasjoner i ID-porten/Maskinporten Selvbetjening**
3. Klikk **Gå til Altinn for å fullføre** og godkjenn forespørselen i Altinn

!!! info "Behandlingstid"
    Tilgang gis vanligvis samme dag, men kan ta noe lenger tid. Steg 2c og 2d gjøres etter at du har fått tilgang.

### 2c. Opprett integrasjon

!!! info "Produksjon eller test?"
    De fleste trenger kun å sette opp **Produksjon**. Testmiljøet (Altinn tt02) er for utviklere som vil teste innsending uten å sende ekte data til myndighetene. De to miljøene har hver sin portal:

    - **Produksjon:** [sjolvbetjening.samarbeid.digdir.no](https://sjolvbetjening.samarbeid.digdir.no)
    - **Test:** [sjolvbetjening.test.samarbeid.digdir.no](https://sjolvbetjening.test.samarbeid.digdir.no)

    Setter du opp begge miljøene, gjenta steg 2c og 2d i begge portaler.

Logg inn på riktig portal. Du vil bli bedt om å velge innloggingsmetode — velg **Med organisasjonsnummer** (ikke «Med syntetisk organisasjon»). Det forutsetter at du har fått tildelt rettigheter til selvbetjening av APIer og integrasjoner i Altinn, noe som skjer automatisk når du søker om tilgang som Maskinporten-konsument i steg 2b.

!!! warning "Ikke velg «Scopes» i menyen"
    «Scopes» i venstremenyen er for API-tilbydere som oppretter egne scopes. Du er konsument og skal ikke dit. Naviger via **Mine klienter** i stedet.

Følg stegene under:

1. Velg **Mine klienter** og klikk på Wenche-klienten din, eller klikk **Ny integrasjon** for å opprette en ny. Velg **Maskinporten & KRR** som integrasjonstype.
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

    !!! note "Aksjonærregisteroppgave og skattemelding krever ekstra scopes"
        Disse søkes om separat og legges til på klienten etter at tilgang er innvilget:

        | Scope | Formål |
        |---|---|
        | `skatteetaten:innrapporteringaksjonaerregisteroppgave` | Aksjonærregisteroppgave (RF-1086) — se steg 2e |
        | `skatteetaten:formueinntekt/skattemelding` | Skattemelding for AS — se steg 2f |

4. Kopier **klient-ID** — du trenger den i steg 3

### 2d. Last opp offentlig nøkkel

Under klienten, klikk **Legg til nøkkel** og lim inn innholdet i `maskinporten_offentlig.pem`. Lagre klienten.

Nøkkelen vil vises i listen med en UUID (f.eks. `9bc5078c-...`). Kopier denne UUID-en — dette er din **KID**, som du trenger i steg 3.

### 2e. Søk om tilgang til SKDs API for aksjonærregisteroppgave

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

Når SKD bekrefter at tilgangen er innvilget, logg inn i Digdirs selvbetjeningsportal (se steg 2c) og legg til scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` på Maskinporten-klienten din. Scopet vil nå være søkbart i portalen.

!!! warning "Begge steg er nødvendige"
    Tilgangen fra SKD aktiveres ikke automatisk på klienten. Du må eksplisitt legge til scopet i Digdirs portal etter at SKD har innvilget det.

### 2f. Søk om tilgang til SKDs API for skattemelding

!!! note "Valgfritt"
    Dette steget er kun nødvendig dersom du skal sende inn skattemelding for AS. Hopp over om du bare bruker Wenche til årsregnskap og aksjonærregisteroppgave.

Scopet `skatteetaten:formueinntekt/skattemelding` søkes om i to omganger:

**Del 1 — Søk om tilgang hos Skatteetaten**

1. Gå til [SKDs brukerstøtteportal](https://eksternjira.sits.no/plugins/servlet/desk/site/global) og logg inn
2. Opprett en ny sak under **Innrapportering → Skattemelding**, kategori **Teknisk**
3. Oppgi i henvendelsen:
    - At du ønsker tilgang til scopet `skatteetaten:formueinntekt/skattemelding`
    - Organisasjonsnummeret ditt
    - Om du ønsker tilgang til testmiljø, produksjon, eller begge

SKD behandler vanligvis slike forespørsler innen noen virkedager.

**Del 2 — Legg til scope i Digdirs selvbetjeningsportal**

Når SKD bekrefter at tilgangen er innvilget, logg inn i Digdirs selvbetjeningsportal (se steg 2c) og legg til scopet `skatteetaten:formueinntekt/skattemelding` på Maskinporten-klienten din. Scopet vil nå være søkbart i portalen.

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

Altinn 3 krever at datasystemer som handlar på vegne av virksomheter bruker **systemtilgang** — en mekanisme der systemet registreres i Altinns systemregister og virksomheten godkjenner tilgangen eksplisitt. Wenche er bygget rundt denne modellen fra starten av, og bruker ikke den eldre virksomhetsbruker-funksjonaliteten. Mottar du e-post fra Digitaliseringsdirektoratet om at systemer mot Altinn må tilpasses innen 31. mai 2026, trenger du ikke gjøre noe med Wenche — kravet er allerede oppfylt.

Selve oppsettet gjøres **én gang per miljø** (test/prod):

!!! note "Bruker du webgrensesnittet?"
    Disse stegene kan gjøres direkte i nettleseren: start `wenche ui` og gå til **Oppsett → Systembruker-oppsett**.

### 5a. Registrer system

```bash
wenche registrer-system
```

Registrerer Wenche i Altinns systemregister med riktige tilgangsrettigheter. Kan kjøres på nytt uten skade — oppdaterer automatisk hvis systemet allerede finnes.

### 5b. Oppdater rettigheter på eksisterende systembruker

!!! note "Valgfritt — kun hvis du allerede har en godkjent systembruker"
    Har du satt opp Wenche tidligere (f.eks. for årsregnskap) og nettopp lagt til et nytt scope (f.eks. skattemelding), skal du bruke dette steget — **ikke** steg 5c. Eksisterende rettigheter beholdes; kun de nye legges til.

Send en endringsforespørsel via webgrensesnittet: start `wenche ui`, gå til **Oppsett → Systembruker-oppsett**, og klikk **Oppdater systembruker-rettigheter**. Du får en lenke — åpne den i nettleseren, logg inn med ID-porten, og godkjenn endringen.

---

### 5c. Opprett systembrukerforespørsel

=== "Produksjon"

    ```bash
    wenche opprett-systembruker
    ```

    Oppretter en forespørsel på ditt eget organisasjonsnummer (`ORG_NUMMER` fra `.env`) og skriver ut en `confirmUrl`. Åpne lenken i nettleseren, logg inn med ID-porten, og godkjenn tilgangen.

=== "Testmiljø (tt02)"

    Altinns testmiljø bruker syntetiske testdata. Din egen organisasjon finnes ikke i testregisteret, og du må bruke en **syntetisk testorganisasjon fra Tenor**.

    **1. Finn en syntetisk test-AS i Tenor**

    Gå til [Tenor testdatasøk](https://www.skatteetaten.no/testdata/) og søk frem et aksjeselskap (AS). Noter deg:

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

Får du feilen `invalid_altinn_customer_configuration` betyr det at systembrukeren ikke er godkjent ennå — fullfør steg 5c. Dobbeltsjekk ellers at klient-ID og KID i `.env` stemmer med det som vises i selvbetjeningsportalen.

[Gå videre til bruk →](bruk.md){ .md-button .md-button--primary }
