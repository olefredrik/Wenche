# Bruk

Wenche brukes primært via **webgrensesnittet** (`wenche ui`) — et grafisk grensesnitt i nettleseren der du fyller ut og sender inn alt. Kommandolinjen er tilgjengelig som alternativ for de som foretrekker det.

---

## Hjem-fanen

Når du åpner `wenche ui` lander du på **Hjem**-fanen. Den viser tre fristkort — ett for hver årlige innsending:

- **Skattemelding** (frist 31. mai)
- **Årsregnskap** (frist 31. juli)
- **Aksjonærregisteroppgave** (frist 31. januar)

Hvert kort viser hvor mange dager det er igjen til neste frist, og kjører en automatisk statussjekk mot offentlige API-er for å se om innsendingen allerede er gjort:

| Kort | Statuskilde |
|---|---|
| Skattemelding | Skatteetatens skattemelding-API (krever prod-Maskinporten-konfig) |
| Årsregnskap | Brønnøysundregistrenes åpne Regnskapsregister |
| Aksjonærregisteroppgave | Ingen offentlig status-API — sjekk manuelt hos Skatteetaten |

Når statussjekken bekrefter at innsendingen er gjort, vises kortet grønt med «Levert» og en lenke til Altinn-kvitteringen. Knappen **Oppdater status** kjører sjekkene på nytt.

Statussjekkene refererer alltid til **produksjonsmiljøet**, uavhengig av om du har konfigurert test- eller prod-credentials i Oppsett. Frister og innsendinger er reelle hendelser for din virksomhet, og test-API-ene ville bare avvist din ekte org.nr. uansett. Hvis du ikke har prod-credentials konfigurert ennå, viser skattemelding-kortet en pen feilmelding i status-raden — det stopper deg ikke fra å bruke testmiljø-flyten i resten av appen.

Statussjekkene gjøres mot regnskapsåret som tilhører neste frist (f.eks. 31. juli 2026 → regnskapsår 2025).

---

## Oppsett-fanen

Under **1. Oppsett** finner du «Per miljø-oppsett» med to kort side om side — Testmiljø (tt02) og Produksjon. Hvert kort er et selvstendig oppsett for sitt miljø:

- **Maskinporten-credentials:** Klient-ID og Nøkkel-ID. Test og prod er separate Maskinporten-registre, så hver har sin UUID.
- **Organisasjonsnummer:** Test krever et syntetisk Tenor-orgnr fra [skatteetaten.no/testdata](https://www.skatteetaten.no/testdata/); prod bruker din egen org.
- **Systembruker i Altinn:** Status oppdateres automatisk ved sidelasting. Statuskortet viser hva som mangler eller hva som er klart, og **Avansert**-ekspansjonen har knapper for å registrere system, opprette eller fornye systembruker, og oppdatere rettigheter.

Under kortene ligger felles innstillinger (privat nøkkel), en **Lagre konfigurasjon**-knapp, og en **Tilkoblingstest** som sjekker alle tre forutsetninger per miljø (Maskinporten, Altinn-veksling og systembruker) og oppsummerer «klar for innsending» eller hva som mangler.

Når du senere sender inn, velger du test eller prod direkte i Send-fanen — Oppsett-fanen har ikke noen aktivt-miljø-bryter, fordi du kan ha begge miljø konfigurert samtidig.

---

## Autentisering

Innsending av årsregnskap og aksjonærregisteroppgave krever innlogging mot Maskinporten:

```bash
wenche login     # Autentiserer med systembruker-token og lagrer Altinn-token lokalt
wenche logout    # Sletter lagret token
```

Tokenet lagres i `~/.wenche/token.json` og gjenbrukes automatisk for påfølgende kommandoer. Bruker du webgrensesnittet håndteres innlogging derfra.

!!! note "Systembruker må settes opp først"
    `wenche login` forutsetter at systembrukeren er godkjent (steg 5 i [oppsett](oppsett.md)). Får du feilen `invalid_altinn_customer_configuration` betyr det at systembrukeren ikke er godkjent ennå.

---

## Skattemelding (frist 31. mai)

Wenche fyller ut næringsspesifikasjonen (RF-1167) og skattemeldingen (RF-1028) og sender dem digitalt til Skatteetaten via Altinn. Du fullfører ved å signere med BankID i Altinn.

=== "Webgrensesnitt"

    Gå til fanen **Send til Altinn** og klikk **Send skattemelding til Skatteetaten**. Når opplastingen er ferdig viser Wenche en lenke til Altinn-innboksen. Åpne lenken og signer med BankID for å fullføre innsendingen.

=== "Kommandolinje"

    Forhåndskontroller mot Skatteetatens valideringstjeneste uten å sende inn (anbefalt):

    ```bash
    wenche valider-skattemelding
    ```

    Send inn (krever API-tilgang, se under):

    ```bash
    wenche send-skattemelding
    ```

    Wenche skriver ut en lenke til Altinn-innboksen. Åpne lenken og signer med BankID for å fullføre.

    Test lokalt uten å sende (skriver `skattemelding.xml` og `naeringsspesifikasjon.xml`):

    ```bash
    wenche send-skattemelding --dry-run
    ```

    Generer tekstsammendrag for gjennomlesing:

    ```bash
    wenche generer-skattemelding
    ```

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Skatteetaten krever at en personlig bruker bekrefter skattemeldingen via ID-porten. Wenche laster opp innholdet med systembruker, men selve innsendingen fullføres først når du signerer med BankID i Altinn. Dette kan ikke gjøres maskinelt.

!!! tip "Formuesverdi av aksjer (aksjeoppgaven RF-1088S)"
    Eier selskapet aksjer i andre selskap, fyll inn **formuesverdien** fra aksjeoppgaven (RF-1088S, post 209) i feltet «Formuesverdi av aksjer selskapet eier» (Dokumenter-fanen, eller `formuesverdi_aksjer` i config.yaml). Wenche bruker den til å beregne formuesverdien bak selskapets egne aksjer, som er grunnlaget for eiernes formuesskatt. Uten den blir feltet stående tomt og Skatteetaten gir en merknad.

Sammendraget inneholder:

- Alle felt i næringsoppgaven (RF-1167) ferdig utfylt
- Skatteberegning med fritaksmetoden der det er aktuelt
- Beregnet skatt (22 %)
- Skattekostnad ført i resultatregnskapet
- Fremførbart underskudd hvis selskapet gikk med tap
- **Egenkapitalnote** (rskl. § 7-2b) med bevegelse per egenkapitalpost (inngående balanse, årsresultat, utbytte og utgående balanse)

!!! info "Fritaksmetoden og sjablonregelen"
    Wenche håndterer **to tilfeller** avhengig av eierandel i datterselskapet (`eierandel_datterselskap` i config.yaml):

    - **Eierandel ≥ 90 %:** Hele utbyttet er skattefritt (fritaksmetoden, sktl. § 2-38).
    - **Eierandel < 90 %:** 3 % av utbyttet er skattepliktig (sjablonregelen, sktl. § 2-38 sjette ledd). Skatteberegningen justeres automatisk.

!!! info "Egenkapitalnote"
    Egenkapitalnoten (rskl. § 7-2b) vises automatisk når `foregaaende_aar` er utfylt i `config.yaml`. Uten sammenligningstall vises kun utgående balanse med en advarsel om at inngående tall mangler.

!!! note "API-tilgang kreves"
    Automatisk innsending av skattemelding krever at systemleverandøren er registrert hos Skatteetaten. Se [Søke om API-tilgang](#soke-om-api-tilgang) for fremgangsmåte.

---

## Søke om API-tilgang for skattemelding { #soke-om-api-tilgang }

Skatteetaten krever at systemleverandører søker om tilgang før automatisk innsending kan tas i bruk. Innsending via skjema på skatteetaten.no er avviklet.

**Fremgangsmåte:**

1. Gå til [Skatteetatens servicedesk](https://eksternjira.sits.no/servicedesk/customer/user/login)
2. Send en henvendelse om tilgang til API for skattemelding
3. Oppgi at du skal levere for eget selskap (ikke som systemleverandør for andre)
4. Ved innvilgelse: aksepter bruksvilkårene og registrer integrasjonen i [Digdirs selvbetjeningsportal](https://samarbeid.digdir.no/) med scope `skatteetaten:formueinntekt/skattemelding`

Teknisk dokumentasjon: [github.com/Skatteetaten/skattemeldingen](https://github.com/Skatteetaten/skattemeldingen)

---

## Årsregnskap (frist 31. juli)

=== "Webgrensesnitt"

    Gå til fanen **Send til Altinn** og klikk **Send årsregnskap**.

    Når opplastingen er ferdig vises en knapp **Signer i Altinn**. Klikk den og signer med BankID for å fullføre innsendingen.

=== "Kommandolinje"

    Test uten innsending (anbefalt første gang):

    ```bash
    wenche send-aarsregnskap --dry-run
    ```

    `--dry-run` lagrer de genererte XML-dokumentene lokalt slik at du kan inspisere dem før du sender.

    Send inn:

    ```bash
    wenche login
    wenche send-aarsregnskap
    wenche logout
    ```

    Wenche skriver ut en lenke til Altinn-innboksen når opplastingen er ferdig. Åpne lenken i nettleseren, finn skjemaet i innboksen og signer med BankID for å fullføre innsendingen.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Wenche laster opp regnskapet og klargjør det for signering. Selve signeringen må gjøres av daglig leder eller styreleder i Altinn med BankID — dette er et juridisk krav og kan ikke gjøres maskinelt.

!!! info "Sammenligningstall (rskl. § 6-6)"
    Årsregnskapet inkluderer automatisk sammenligningstall fra foregående år når `foregaaende_aar` er utfylt i `config.yaml`. Dette er obligatorisk etter regnskapsloven § 6-6. For selskaper stiftet i inneværende regnskapsår kan seksjonen utelates.

---

## Aksjonærregisteroppgave (frist 31. januar)

Wenche sender RF-1086 direkte til Skatteetatens eget REST-API — ikke via Altinn-instansflyt. Innsendingen er maskinell og krever ikke manuell signering.

!!! note "Forutsetninger"
    - Maskinporten-klienten din må ha fått scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` innvilget. Se [steg 2e i oppsett](oppsett.md#2e-sk-om-tilgang-til-skds-api-for-aksjonrregisteroppgave).
    - Systembrukeren for din organisasjon må inkludere SKD-rettigheten. Denne settes opp automatisk av `wenche opprett-systembruker` — se [steg 5 i oppsett](oppsett.md#steg-5-registrer-systembruker-i-altinn).
    - `kontakt_epost` må være utfylt under `selskap` i `config.yaml` (eller i Wenche UI under **Selskap**).

!!! warning "Testmiljø krever syntetiske testdata"
    Bruker du `WENCHE_ENV=test` må systembrukeren tilhøre en syntetisk testorganisasjon fra Tenor, og `SKD_TEST_ORG_NUMMER` må være satt i `.env`. Se [steg 5 i oppsett](oppsett.md#steg-5-registrer-systembruker-i-altinn) for fullstendig veiledning.

=== "Webgrensesnitt"

    Gå til fanen **Send til Altinn** og klikk **Send aksjonærregister til Skatteetaten**.

    Forsendelse-ID vises i grensesnittet når innsendingen er fullført.

=== "Kommandolinje"

    Test og generer XML lokalt uten å sende:

    ```bash
    wenche send-aksjonaerregister --dry-run
    ```

    Send inn:

    ```bash
    wenche send-aksjonaerregister
    ```

    Wenche skriver ut forsendelse-ID når innsendingen er fullført.

---

## Obligatoriske noter (rskl. §§ 7-35, 7-43, 7-45, 7-46)

Regnskapsloven krever at alle foretak utarbeider noter til årsregnskapet. For små foretak gjelder minimumskravene i fire paragrafer:

| §     | Note                          | Innhold                                                              |
|-------|-------------------------------|----------------------------------------------------------------------|
| 7-35  | Regnskapsprinsipper           | Hvordan regnskapet er satt opp og hvilke vurderingsprinsipper som er brukt |
| 7-43  | Ansatte og lønnskostnader     | Antall ansatte, samlede lønnskostnader og godtgjørelse til ledelse  |
| 7-45  | Lån til nærstående            | Lån ytet til aksjonærer, styremedlemmer eller andre nærstående parter |
| 7-46  | Fortsatt drift                | Bekreftelse på at forutsetningen om fortsatt drift er til stede      |

### Hva er notene?

Notene er en juridisk del av årsregnskapet. Styret fastsetter regnskapet inkludert noter, og de bør undertegnes eller arkiveres sammen med det signerte årsregnskapet.

### Hva er notene ikke?

Notene sendes **ikke** inn digitalt til Brønnøysundregistrene. Skjemaet RR-0002 har ingen felt for fritekstnoter — det er kun tall som overføres via Altinn. Notene er et dokument du oppbevarer selv.

### Hvordan bruke notene i Wenche?

=== "Webgrensesnitt"

    1. Gå til fanen **Dokumenter** og scroll ned til **Obligatoriske noter**
    2. Fyll inn antall ansatte (typisk 0 for holdingselskaper)
    3. Fyll inn eventuelle lån til nærstående (aksjonærer, styremedlemmer)
    4. Klikk **Last ned noter** — du får en forhåndsvisning og en nedlastingsknapp for `noter_ÅÅÅÅ_ORGNR.txt`
    5. Les gjennom teksten og tilpass om nødvendig
    6. Arkiver filen sammen med det signerte årsregnskapet

!!! note "Tilpass gjerne noteteksten"
    Wenche genererer et standardoppsett som passer de fleste holdingselskaper. Har selskapet særskilte forhold som bør beskrives — for eksempel eierskapsbegrensninger, konsernforhold eller pantsettelse av aksjer — bør du tilpasse teksten i den nedlastede filen.

!!! warning "Notene er obligatoriske, men ikke verifiserbart fullstendige"
    Wenche dekker minimumskravene etter NRS 8 (God regnskapsskikk for små foretak). For selskaper med mer komplekse forhold kan ytterligere noter være påkrevd. Ved tvil, kontakt en regnskapsfører eller revisor.

---

## Alle kommandoer

```
wenche --help

Kommandoer:
  registrer-system         Registrer Wenche i Altinns systemregister (en gang per miljo)
  opprett-systembruker     Opprett systembrukerforespørsel og fa godkjenningslenke
  login                    Autentiser mot Maskinporten med RSA-nokkel
  logout                   Logg ut og slett lagret token
  generer-skattemelding    Generer ferdig utfylt RF-1167 og RF-1028 som tekstsammendrag
  send-skattemelding       Send inn skattemelding for AS til Skatteetaten via Altinn3
  send-aarsregnskap        Send inn arsregnskap til Bronnoysundregistrene
  send-aksjonaerregister   Send inn aksjonaerregisteroppgave (RF-1086)
  importer-saft            Importer SAF-T Financial XML og generer config.yaml
  ui                       Start webgrensesnittet i nettleseren

Alternativer (send-aarsregnskap, send-aksjonaerregister og send-skattemelding):
  --config TEXT            Sti til konfigurasjonsfil [standard: config.yaml]
  --dry-run                Generer dokument lokalt uten a sende til Altinn

Alternativer (generer-skattemelding):
  --config TEXT            Sti til konfigurasjonsfil [standard: config.yaml]
  --ut TEXT                Lagre sammendrag til fil

Alternativer (importer-saft):
  SAF-T-FIL                Sti til SAF-T Financial XML-fil (pakrevd argument)
  --ut TEXT                Sti til config.yaml som skal skrives [standard: config.yaml]
```

!!! note
    Kommandolisten viser utskriften slik den faktisk ser ut i terminalen. Noen norske tegn vises ikke korrekt i terminalutskriften.

---

## Sikkerhet

- `.env` og `config.yaml` skal aldri legges i git (de er lagt til i `.gitignore`)
- Innloggingstokenet lagres i `~/.wenche/token.json` med rettigheter begrenset til din bruker
- Wenche sender aldri data andre steder enn til Maskinporten og Altinn
