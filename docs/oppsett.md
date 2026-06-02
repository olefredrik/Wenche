# Oppsett

Wenche bruker Maskinporten for å autentisere deg som konsument overfor Altinn og Skatteetaten, uten nettleserinnlogging. Oppsettet består av fem steg:

1. Generer et RSA-nøkkelpar lokalt
2. Registrer en Maskinporten-klient hos Digdir
3. Konfigurer miljøvariabler (`.env`)
4. Fyll ut selskapsinformasjon (`config.yaml`)
5. Registrer systembruker i Altinn

Steg 1 og 2 må gjøres manuelt, de krever terminalkommandoer og registrering hos Digdir. Steg 3, 4 og 5 gjøres i Wenche etter at du har startet `wenche`.

---

## Steg 1: Generer RSA-nøkkelpar

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

## Steg 2: Registrer Maskinporten-klient hos Digdir

### 2a. Registrer virksomheten hos Digdir (kun første gang)

!!! info "Gjelder deg?"
    Dette steget gjelder **kun virksomheter som ikke tidligere har brukt Maskinporten eller ID-porten**, typisk holdingselskaper og nyopprettede AS. Har virksomheten din allerede en aktiv Maskinporten-tilknytning, hopp rett til steg 2b.

    Prøver du å logge inn på selvbetjeningsportalen uten å ha gjort dette, vil du få feilmeldingen:
    > PRECONDITION_REQUIRED: Virksomheten har ikke signert de relevante bruksvilkårene.

Fyll ut [informasjonsskjemaet for Maskinporten-konsumenter](https://samarbeid.digdir.no/maskinporten/konsument/119) på Digdirs nettside. Digdir behandler søknaden og sender deg en e-post med instruksjoner om å signere bruksvilkårene («Bruksvilkår for private verksemder»).

!!! tip "Hva skal stå under «Hvilken API-tilbyder skal dere konsumere fra?»"
    Oppgi **Altinn 3** og **Skatteetaten**. Wenche bruker scopes fra begge: Altinn 3 for `altinn:instances.*` og `altinn:authentication/*`, og Skatteetaten for skattemelding og aksjonærregister. Årsregnskap til Brønnøysundregistrene går via Altinn 3 og krever ikke separat brreg-tilgang.

!!! info "Behandlingstid"
    Dette kan ta noen virkedager. Maskinporten er gratis for konsumenter.

Når bruksvilkårene er signert, fortsett til steg 2b.

### 2b. Søk om tilgang i selvbetjeningsportalen

Gå til [sjolvbetjening.samarbeid.digdir.no](https://sjolvbetjening.samarbeid.digdir.no) og logg inn. Første gang du logger inn, vil du bli møtt av et skjema, **Be om tilgang**:

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
2. **Fyll ut registreringsskjemaet for sluttbrukersystem** (punkt 1.1). Oppgi at du trenger de fem scopene listet over for produksjon.
3. **Vent på e-post fra Digdir** med bekreftelse på at scopene er tildelt (punkt 1.3). Dette tar typisk noen virkedager.

!!! tip "Hvis scopene ikke blir tilgjengelige etter forventet behandlingstid"
    Ta kontakt med [servicedesk@altinn.no](mailto:servicedesk@altinn.no). Oppgi organisasjonsnummeret ditt og hvilke scopes du venter på. De kan sjekke status manuelt og innvilge tilgang om noe har stoppet opp.

### 2d. Opprett integrasjon

Logg inn på Digdirs selvbetjeningsportal: [sjolvbetjening.samarbeid.digdir.no](https://sjolvbetjening.samarbeid.digdir.no). Du vil bli bedt om å velge innloggingsmetode, velg **Med organisasjonsnummer**. Det forutsetter at du har fått tildelt rettigheter til selvbetjening av APIer og integrasjoner i Altinn, noe som skjer automatisk når du søker om tilgang som Maskinporten-konsument i steg 2b.

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
        | `skatteetaten:innrapporteringaksjonaerregisteroppgave` | Aksjonærregisteroppgave (RF-1086), se steg 2f |
        | `skatteetaten:formueinntekt/skattemelding` | Skattemelding for AS, se steg 2g |

4. Kopier **klient-ID**, du trenger den i steg 3

### 2e. Last opp offentlig nøkkel

Under klienten, klikk **Legg til nøkkel** og lim inn innholdet i `maskinporten_offentlig.pem`. Lagre klienten.

Nøkkelen vil vises i listen med en UUID (f.eks. `9bc5078c-...`). Kopier denne UUID-en, dette er din **KID**, som du trenger i steg 3.

### 2f. Søk om tilgang til SKDs API for aksjonærregisteroppgave

!!! note "Valgfritt"
    Dette steget er kun nødvendig dersom du skal sende inn aksjonærregisteroppgave (RF-1086). Hopp over om du bare bruker Wenche til årsregnskap og skattemelding.

Scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` søkes om i to omganger:

**Del 1, Søk om tilgang hos Skatteetaten**

1. Gå til [SKDs brukerstøtteportal](https://eksternjira.sits.no/plugins/servlet/desk/site/global) og logg inn
2. Opprett en ny sak under **Innrapportering → Aksjonærregisteret**, kategori **Teknisk**
3. Oppgi i henvendelsen:
    - At du ønsker tilgang til scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` i produksjon
    - Organisasjonsnummeret ditt

SKD behandler vanligvis slike forespørsler innen noen virkedager.

**Del 2, Legg til scope i Digdirs selvbetjeningsportal**

Når SKD bekrefter at tilgangen er innvilget, logg inn i Digdirs selvbetjeningsportal (se steg 2d) og legg til scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` på Maskinporten-klienten din. Scopet vil nå være søkbart i portalen.

!!! warning "Begge steg er nødvendige"
    Tilgangen fra SKD aktiveres ikke automatisk på klienten. Du må eksplisitt legge til scopet i Digdirs portal etter at SKD har innvilget det.

### 2g. Søk om tilgang til SKDs API for skattemelding

!!! note "Valgfritt"
    Dette steget er kun nødvendig dersom du skal sende inn skattemelding for AS. Hopp over om du bare bruker Wenche til årsregnskap og aksjonærregisteroppgave.

Scopet `skatteetaten:formueinntekt/skattemelding` søkes om i to omganger:

**Del 1, Søk om tilgang hos Skatteetaten**

1. Gå til [SKDs brukerstøtteportal](https://eksternjira.sits.no/plugins/servlet/desk/site/global) og logg inn
2. Opprett en ny sak under **Innrapportering → Skattemelding**, kategori **Teknisk**
3. Oppgi i henvendelsen:
    - At du ønsker tilgang til scopet `skatteetaten:formueinntekt/skattemelding` i produksjon
    - Organisasjonsnummeret ditt

SKD behandler vanligvis slike forespørsler innen noen virkedager.

**Del 2, Legg til scope i Digdirs selvbetjeningsportal**

Når SKD bekrefter at tilgangen er innvilget, logg inn i Digdirs selvbetjeningsportal (se steg 2d) og legg til scopet `skatteetaten:formueinntekt/skattemelding` på Maskinporten-klienten din. Scopet vil nå være søkbart i portalen.

!!! warning "Begge steg er nødvendige"
    Tilgangen fra SKD aktiveres ikke automatisk på klienten. Du må eksplisitt legge til scopet i Digdirs portal etter at SKD har innvilget det.

---

## Steg 3: Fyll inn credentials

Start Wenche:

```bash
wenche
```

Gå til **Oppsett**-fanen. Fyll inn Maskinporten-feltene i **Steg 1** og last opp nøkkelen i **Steg 2**:

| Felt | Hva det er | Steg |
|---|---|---|
| Klient-ID | UUID fra Digdirs selvbetjeningsportal (steg 2d) | 1 |
| Nøkkel-ID | UUID portalen tildelte den offentlige nøkkelen (steg 2e) | 1 |
| Organisasjonsnummer | Ditt eget organisasjonsnummer (9 siffer) | 1 |
| Privat nøkkel | Last opp `maskinporten_privat.pem` fra steg 1 | 2 |

Klikk **Lagre konfigurasjon** i Steg 1. Wenche lagrer verdiene til `~/.wenche/.env` (Mac/Linux) eller `%USERPROFILE%\.wenche\.env` (Windows). Filen settes med rettigheter `0600` slik at den er lesbar kun for din bruker.

---

## Steg 4: Fyll inn selskapsinformasjon

I Wenche, gå til fanen **Tall** og fyll inn selskapets opplysninger, regnskapstall, balanse, skattemelding-innstillinger og aksjonærdata, alt på én side. Alle beløp oppgis i hele kroner (NOK). Klikk **Lagre data** når du er ferdig, dataene lagres til `config.yaml` i den mappen du startet Wenche fra.

!!! tip "Fører du regnskapet i Bodil, eller har du SAF-T?"
    Under **Tall** finner du to importknapper. **Hent tall fra Bodil** laster opp en `config.yaml` fra [Bodil](https://github.com/olefredrik/Bodil). **Importer fra SAF-T** lar deg laste opp en SAF-T Financial-fil eksportert fra regnskapssystemet (Fiken, Tripletex, Visma, PowerOffice m.fl.), så fylles resultat og balanse inn for deg, både for inneværende år og, via en egen fil for fjoråret, sammenligningstallene. Begge forhåndsfyller bare skjemaet, du ser over alt og lagrer selv. Daglig leder, styreleder og aksjonærdata finnes ikke i SAF-T og fylles inn manuelt. (SAF-T-import finnes også på kommandolinjen, se [Kommandolinje](avansert/cli.md).)

---

## Steg 5: Registrer systembruker i Altinn

Altinn 3 krever at datasystemer som handler på vegne av virksomheter bruker **systemtilgang**, en mekanisme der systemet registreres i Altinns systemregister og virksomheten godkjenner tilgangen eksplisitt. Wenche er bygget rundt denne modellen fra starten av, og bruker ikke den eldre virksomhetsbruker-funksjonaliteten. Mottar du e-post fra Digitaliseringsdirektoratet om at systemer mot Altinn må tilpasses innen 31. mai 2026, trenger du ikke gjøre noe med Wenche, kravet er allerede oppfylt.

Start `wenche` og gå til **Oppsett**-fanen. **Steg 3** viser status for systembrukeren og har knappene for å sette den opp.

**For å opprette en ny systembruker:**

1. Sørg for at Maskinporten-credentials og organisasjonsnummer er fylt inn (og lagret).
2. Klikk **Opprett systembruker**. Wenche registrerer seg i Altinns systemregister automatisk hvis det ikke er gjort, oppretter en forespørsel, og viser en «Godkjenn i Altinn →»-lenke.
3. Åpne lenken og logg inn med BankID som daglig leder eller styreleder.
4. Tilbake i Wenche: klikk **Sjekk status**. Status oppdateres til **✓ Wenche er koblet til Altinn**.

**Hvis status fortsatt sier «venter»:** Vent 10-20 sekunder og klikk knappen igjen, Altinn trenger noen sekunder på å registrere godkjenningen.

### Når trenger jeg å gjøre dette på nytt?

| Situasjon | Handling |
|---|---|
| Setter opp Wenche for første gang | Steg 5 (registrer + opprett systembruker) |
| Har lagt til nye scopes (f.eks. skattemelding etter at årsregnskap allerede er satt opp) | Bruk **Oppdater rettigheter** i Avansert-ekspansjonen, sender en endringsforespørsel som beholder eksisterende rettigheter og bare legger til nye |
| Systembrukeren er Avvist eller har utløpt | Klikk **Opprett (ny) systembruker** i Avansert, lager en fersk forespørsel |

### Verifiser oppsett

I Oppsett-fanen → **Tilkoblingstest** → klikk **Test tilkobling mot Altinn**. Resultatet viser tre sjekker:

1. ✓ Maskinporten og Altinn-veksling (credentials gyldige)
2. ✓ Systembruker (godkjent og aktiv)
3. ✓ Klar for innsending

Hvis alt er grønt, er du klar til å sende inn.

[Gå videre til bruk →](bruk.md){ .md-button .md-button--primary }
