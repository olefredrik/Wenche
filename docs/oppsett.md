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

!!! tip "Hva skal stå under «Hvilken API-tilbyder skal dere konsumere fra?»"
    Oppgi **Altinn 3** og **Skatteetaten**. Wenche bruker scopes fra begge: Altinn 3 for `altinn:instances.*` og `altinn:authentication/*`, og Skatteetaten for skattemelding og aksjonærregister. Årsregnskap til Brønnøysundregistrene går via Altinn 3 og krever ikke separat brreg-tilgang.

!!! info "Behandlingstid"
    Dette kan ta noen virkedager. Maskinporten er gratis for konsumenter.

Når bruksvilkårene er signert, fortsett til steg 2b.

### 2b. Søk om tilgang i selvbetjeningsportalen

Gå til [sjolvbetjening.samarbeid.digdir.no](https://sjolvbetjening.samarbeid.digdir.no) og logg inn. Første gang du logger inn, vil du bli møtt av et skjema — **Be om tilgang**:

1. Fyll inn organisasjonsnummeret ditt
2. Kryss av **Opprette og endre integrasjoner i ID-porten/Maskinporten Selvbetjening**
3. Klikk **Gå til Altinn for å fullføre** og godkjenn forespørselen i Altinn

!!! info "Behandlingstid"
    Tilgang gis vanligvis samme dag, men kan ta noe lenger tid.

### 2c. Registrer Wenche som sluttbrukersystem hos Digdir

!!! info "Gjelder deg?"
    Dette steget gjelder **kun virksomheter som ikke tidligere har integrert et eget sluttbrukersystem mot Altinn 3**. Har virksomheten din allerede gjort dette (du ser de fem Altinn-scopene under steg 2d som søkbare), kan du hoppe rett til steg 2d.

De fem Altinn 3-scopene som Wenche bruker (`altinn:instances.read`, `altinn:instances.write`, `altinn:authentication/systemregister.write`, `altinn:authentication/systemuser.request.read`, `altinn:authentication/systemuser.request.write`) er ikke åpent tilgjengelige. Virksomheten din må registreres som sluttbrukersystem-leverandør hos Digdir før scopene blir søkbare i selvbetjeningsportalen.

Følg veiledningen [Kom i gang med integrasjon mot Altinn 3](https://samarbeid.digdir.no/altinn/kom-i-gang/2868) på Samarbeidsportalen. Hovedstegene er:

1. **Godkjenn bruksvilkår for sluttbrukersystemleverandør** (punkt 0.3 i Digdirs veiledning). Selv om Wenche er ditt eget verktøy for din egen virksomhet, regnes du som både leverandør og kunde av sluttbrukersystemet.
2. **Fyll ut registreringsskjemaet for sluttbrukersystem** (punkt 1.1). Oppgi at du trenger de fem scopene listet over, og om du ønsker tilgang i produksjon, testmiljø (tt02), eller begge.
3. **Vent på e-post fra Digdir** med bekreftelse på at scopene er tildelt (punkt 1.3). Dette tar typisk noen virkedager.

!!! tip "Hvis scopene ikke blir tilgjengelige etter forventet behandlingstid"
    Ta kontakt med [servicedesk@altinn.no](mailto:servicedesk@altinn.no). Oppgi organisasjonsnummeret ditt og hvilke scopes du venter på. De kan sjekke status manuelt og innvilge tilgang om noe har stoppet opp.

### 2d. Opprett integrasjon

!!! info "Produksjon eller test?"
    De fleste trenger kun å sette opp **Produksjon**. Testmiljøet (Altinn tt02) er for utviklere som vil teste innsending uten å sende ekte data til myndighetene. De to miljøene har hver sin portal:

    - **Produksjon:** [sjolvbetjening.samarbeid.digdir.no](https://sjolvbetjening.samarbeid.digdir.no)
    - **Test:** [sjolvbetjening.test.samarbeid.digdir.no](https://sjolvbetjening.test.samarbeid.digdir.no)

    Setter du opp begge miljøene, gjenta steg 2d og 2e i begge portaler.

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
        | `skatteetaten:innrapporteringaksjonaerregisteroppgave` | Aksjonærregisteroppgave (RF-1086) — se steg 2f |
        | `skatteetaten:formueinntekt/skattemelding` | Skattemelding for AS — se steg 2g |

4. Kopier **klient-ID** — du trenger den i steg 3

### 2e. Last opp offentlig nøkkel

Under klienten, klikk **Legg til nøkkel** og lim inn innholdet i `maskinporten_offentlig.pem`. Lagre klienten.

Nøkkelen vil vises i listen med en UUID (f.eks. `9bc5078c-...`). Kopier denne UUID-en — dette er din **KID**, som du trenger i steg 3.

### 2f. Søk om tilgang til SKDs API for aksjonærregisteroppgave

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

Når SKD bekrefter at tilgangen er innvilget, logg inn i Digdirs selvbetjeningsportal (se steg 2d) og legg til scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` på Maskinporten-klienten din. Scopet vil nå være søkbart i portalen.

!!! warning "Begge steg er nødvendige"
    Tilgangen fra SKD aktiveres ikke automatisk på klienten. Du må eksplisitt legge til scopet i Digdirs portal etter at SKD har innvilget det.

### 2g. Søk om tilgang til SKDs API for skattemelding

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

Når SKD bekrefter at tilgangen er innvilget, logg inn i Digdirs selvbetjeningsportal (se steg 2d) og legg til scopet `skatteetaten:formueinntekt/skattemelding` på Maskinporten-klienten din. Scopet vil nå være søkbart i portalen.

!!! warning "Begge steg er nødvendige"
    Tilgangen fra SKD aktiveres ikke automatisk på klienten. Du må eksplisitt legge til scopet i Digdirs portal etter at SKD har innvilget det.

---

## Steg 3 — Konfigurer miljøvariabler

!!! tip "Webgrensesnittet håndterer dette for deg"
    Starter du `wenche ui` og går til **Oppsett**-fanen, kan du fylle inn alle credentials direkte i nettleseren. Hvert miljø (Test og Produksjon) har sitt eget kort der du angir klient-ID, nøkkel-ID og organisasjonsnummer. Lagre-knappen skriver til `~/.wenche/.env` for deg (på Windows: `%USERPROFILE%\.wenche\.env`). Manuell redigering under er for de som foretrekker terminal.

!!! info "Hvor lagres credentials?"
    `~/.wenche/.env` (Mac/Linux) eller `%USERPROFILE%\.wenche\.env` (Windows) er den primære lokasjonen. Wenche leser også fra `.env` i den mappen du starter `wenche ui` fra som fallback, slik at oppsett gjort med tidligere versjoner fortsatt fungerer. Når du lagrer via UI-en, migreres innholdet til den faste lokasjonen automatisk.

Kopier eksempelfilen til den faste lokasjonen:

```bash
mkdir -p ~/.wenche
cp .env.example ~/.wenche/.env
chmod 600 ~/.wenche/.env
```

På Windows tilsvarende i PowerShell:

```powershell
New-Item -ItemType Directory -Force $env:USERPROFILE\.wenche
Copy-Item .env.example $env:USERPROFILE\.wenche\.env
```

Åpne `~/.wenche/.env` og fyll inn verdiene fra portalen. Variabelnavnene har miljø-suffix (`_TEST` / `_PROD`) slik at samme `.env`-fil kan inneholde begge oppsett:

```
# Test (Altinn tt02)
MASKINPORTEN_CLIENT_ID_TEST=test-klient-uuid-her
MASKINPORTEN_KID_TEST=test-nokkel-uuid-her
SKD_TEST_ORG_NUMMER=syntetisk-tenor-orgnr-her

# Produksjon
MASKINPORTEN_CLIENT_ID_PROD=prod-klient-uuid-her
MASKINPORTEN_KID_PROD=prod-nokkel-uuid-her
ORG_NUMMER=ditt-eget-organisasjonsnummer

# Felles for begge miljø
MASKINPORTEN_PRIVAT_NOKKEL=maskinporten_privat.pem
WENCHE_ENV=prod
```

!!! warning "Ikke bruk anførselstegn"
    Verdiene skal skrives direkte uten hermetegn.

| Variabel | Hva det er |
|---|---|
| `MASKINPORTEN_CLIENT_ID_TEST` / `_PROD` | Klient-ID fra Digdirs selvbetjeningsportal — egen UUID per miljø |
| `MASKINPORTEN_KID_TEST` / `_PROD` | UUID som portalen tildelte den offentlige nøkkelen for klienten |
| `ORG_NUMMER` | Ditt eget organisasjonsnummer (9 siffer). Brukes som systembruker_org i prod |
| `SKD_TEST_ORG_NUMMER` | Syntetisk Tenor-orgnr som brukes som systembruker_org i testmiljø. Påkrevd hvis du faktisk skal sende inn i test |
| `MASKINPORTEN_PRIVAT_NOKKEL` | Sti til din private nøkkelfil (samme nøkkel kan brukes i begge miljø) |
| `WENCHE_ENV` | `prod` (standard) eller `test`. Påvirker CLI-kommandoer; Send-fanen i UI-et har egen test/prod-velger som overstyrer per innsending |

!!! info "Hvorfor separate test/prod-credentials?"
    Maskinporten test og prod er adskilte registre. En klient registrert i test-portalen finnes ikke i prod-portalen og motsatt, så samme UUID fungerer ikke i begge. På samme måte krever Altinn tt02 og SKD test syntetiske Tenor-orgnumre — din ekte org.nr. er ikke kjent der.

!!! tip "Bare ett miljø?"
    Hvis du kun skal bruke prod, kan du droppe `_TEST`-variablene og `SKD_TEST_ORG_NUMMER`. Hvis du kun skal teste, dropp `_PROD`-variablene. Generiske navn uten suffix (`MASKINPORTEN_CLIENT_ID`, `MASKINPORTEN_KID`) fungerer fortsatt som fallback for bakoverkompatibilitet, men vi anbefaler suffix-formen.

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

Altinn 3 krever at datasystemer som handler på vegne av virksomheter bruker **systemtilgang** — en mekanisme der systemet registreres i Altinns systemregister og virksomheten godkjenner tilgangen eksplisitt. Wenche er bygget rundt denne modellen fra starten av, og bruker ikke den eldre virksomhetsbruker-funksjonaliteten. Mottar du e-post fra Digitaliseringsdirektoratet om at systemer mot Altinn må tilpasses innen 31. mai 2026, trenger du ikke gjøre noe med Wenche — kravet er allerede oppfylt.

Hvert miljø (test og prod) trenger sin egen systembruker. Settes opp uavhengig.

### Anbefalt: bruk webgrensesnittet

Start `wenche ui` og gå til **1. Oppsett**-fanen. Under «Per miljø-oppsett» finner du to kort — Testmiljø (tt02) og Produksjon. Hvert kort viser status for systembrukeren i det miljøet, og har knapper for å sette den opp.

**For å opprette en ny systembruker:**

1. Sørg for at Maskinporten-credentials og organisasjonsnummer er fylt inn i kortet (og lagret).
2. Klikk **Opprett systembruker**. Wenche registrerer seg i Altinns systemregister automatisk hvis det ikke er gjort, oppretter en forespørsel, og viser en «Godkjenn i Altinn →»-lenke.
3. Åpne lenken og godkjenn:
    - **Produksjon:** Logg inn med BankID som daglig leder eller styreleder.
    - **Testmiljø:** Logg inn med TestID. Bruk fødselsnummeret til daglig leder for Tenor-orgen din (finnes under **Kildedata → rollegrupper → DAGL** i [Tenor testdatasøk](https://www.skatteetaten.no/testdata/)).
4. Tilbake i Wenche: klikk **Jeg har godkjent — sjekk status** ved siden av lenken. Status oppdateres til **Systembruker godkjent**.

**Hvis status fortsatt sier «venter»:** Vent 10-20 sekunder og klikk knappen igjen — Altinn trenger noen sekunder på å registrere godkjenningen.

### Når trenger jeg å gjøre dette på nytt?

| Situasjon | Handling |
|---|---|
| Setter opp Wenche for første gang | Steg 5 (registrer + opprett systembruker) |
| Vil bruke et annet miljø også (test ↔ prod) | Steg 5 for det andre miljøet — uavhengig |
| Har lagt til nye scopes (f.eks. skattemelding etter at årsregnskap allerede er satt opp) | Bruk **Oppdater rettigheter** i Avansert-ekspansjonen — sender en endringsforespørsel som beholder eksisterende rettigheter og bare legger til nye |
| Systembrukeren er Avvist eller har utløpt | Klikk **Opprett (ny) systembruker** i Avansert — lager en fersk forespørsel |

### Verifiser oppsett

I Oppsett-fanen → **Tilkoblingstest** → klikk **Test tilkobling mot Altinn**. Resultatet viser tre sjekker per miljø:

1. ✓ Maskinporten og Altinn-veksling (credentials gyldige)
2. ✓ Systembruker (godkjent og aktiv)
3. ✓ Klar for innsending

Hvis alt er grønt, er du klar til å sende inn.

### Alternativ: kommandolinje

```bash
wenche registrer-system            # Registrer system (samme som UI-knappen)
wenche opprett-systembruker        # Opprett systembruker for ORG_NUMMER (prod)
wenche opprett-systembruker --org <tenor-orgnr>  # For test, oppgi Tenor-orgnr eksplisitt
wenche login                       # Test tilkobling (henter token mot aktivt miljø)
```

`WENCHE_ENV` i `.env` styrer hvilket miljø CLI-kommandoene gjelder. UI-et håndterer test/prod uavhengig av denne variabelen.

!!! warning "Test krever syntetiske Tenor-orgnumre"
    Altinn tt02 og SKDs testmiljø er populert med data fra Tenor. Din egen organisasjon finnes ikke i testregisteret, og innsending vil feile (typisk med en uventet 500-feil) hvis du forsøker å bruke ekte org.nr. i test. Bruk alltid et test-AS fra [skatteetaten.no/testdata](https://www.skatteetaten.no/testdata/) når du tester.

[Gå videre til bruk →](bruk.md){ .md-button .md-button--primary }
