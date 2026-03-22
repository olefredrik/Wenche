# Bruk

Wenche kan brukes enten via **kommandolinjen** eller via **webgrensesnittet** (`wenche ui`). Begge gir tilgang til de samme funksjonene.

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

!!! note "Skattemeldingen sendes ikke digitalt"
    Wenche genererer et sammendrag som du fyller inn manuelt på [skatteetaten.no](https://www.skatteetaten.no/). Digital innsending av skattemelding støttes ikke.

Wenche genererer et ferdig utfylt sammendrag av RF-1167 (næringsoppgaven) og RF-1028 (skattemeldingen).

=== "Kommandolinje"

    Genererer fra tallene i `config.yaml`:

    ```bash
    wenche generer-skattemelding
    ```

    Lagre til fil:

    ```bash
    wenche generer-skattemelding --ut skattemelding.txt
    ```

=== "Webgrensesnitt"

    Gå til fanen **Dokumenter** og klikk **Last ned skattemelding**.

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

**Send inn manuelt:**

1. Gå til [skatteetaten.no](https://www.skatteetaten.no/) og logg inn med BankID
2. Åpne skattemeldingen for AS for gjeldende regnskapsår
3. Fyll inn tallene fra sammendraget Wenche har generert
4. Kontroller at Skatteetaten beregner samme skatt
5. Send inn

---

## Årsregnskap (frist 31. juli)

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

=== "Webgrensesnitt"

    Gå til fanen **Send til Altinn** og klikk **Send årsregnskap**.

    Når opplastingen er ferdig vises en knapp **Signer i Altinn**. Klikk den og signer med BankID for å fullføre innsendingen.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Wenche laster opp regnskapet og klargjør det for signering. Selve signeringen må gjøres av daglig leder eller styreleder i Altinn med BankID — dette er et juridisk krav og kan ikke gjøres maskinelt.

!!! info "Sammenligningstall (rskl. § 6-6)"
    Årsregnskapet inkluderer automatisk sammenligningstall fra foregående år når `foregaaende_aar` er utfylt i `config.yaml`. Dette er obligatorisk etter regnskapsloven § 6-6. For selskaper stiftet i inneværende regnskapsår kan seksjonen utelates.

---

## Aksjonærregisteroppgave (frist 31. januar)

Wenche sender RF-1086 direkte til Skatteetatens eget REST-API — ikke via Altinn-instansflyt. Innsendingen er maskinell og krever ikke manuell signering.

!!! note "Forutsetninger"
    - Maskinporten-klienten din må ha fått scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` innvilget. Se [steg 2d i oppsett](oppsett.md#2d-sok-om-tilgang-til-skds-api-for-aksjonaerregisteroppgave).
    - Systembrukeren for din organisasjon må inkludere SKD-rettigheten. Denne settes opp automatisk av `wenche opprett-systembruker` — se [steg 5 i oppsett](oppsett.md#steg-5-registrer-systembruker-i-altinn).
    - `kontakt_epost` må være utfylt under `selskap` i `config.yaml` (eller i Wenche UI under **Selskap**).

!!! warning "Testmiljø krever syntetiske testdata"
    Bruker du `WENCHE_ENV=test` må systembrukeren tilhøre en syntetisk testorganisasjon fra Tenor, og `SKD_TEST_ORG_NUMMER` må være satt i `.env`. Se [steg 5b i oppsett](oppsett.md#5b-opprett-systembrukerforespørsel) for fullstendig veiledning.

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

=== "Webgrensesnitt"

    Gå til fanen **Send til Altinn** og klikk **Send aksjonærregister til Skatteetaten**.

    Forsendelse-ID vises i grensesnittet når innsendingen er fullført.

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
  generer-skattemelding    Generer ferdig utfylt RF-1167 og RF-1028
  send-aarsregnskap        Send inn arsregnskap til Bronnoysundregistrene
  send-aksjonaerregister   Send inn aksjonaerregisteroppgave (RF-1086)
  importer-saft            Importer SAF-T Financial XML og generer config.yaml
  ui                       Start webgrensesnittet i nettleseren

Alternativer (send-aarsregnskap og send-aksjonaerregister):
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
