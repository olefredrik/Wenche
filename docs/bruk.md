# Bruk

Wenche brukes via webgrensesnittet. Start med `wenche` i terminalen, og nettleseren åpner `http://localhost:8080` automatisk.

---

## Hjem-fanen

Når du åpner `wenche` lander du på **Hjem**-fanen. Den viser tre fristkort, ett for hver årlige innsending:

- **Skattemelding** (frist 31. mai)
- **Årsregnskap** (frist 31. juli)
- **Aksjonærregisteroppgave** (frist 31. januar)

Hvert kort viser hvor mange dager det er igjen til neste frist, og kjører en automatisk statussjekk mot offentlige API-er for å se om innsendingen allerede er gjort:

| Kort | Statuskilde |
|---|---|
| Skattemelding | Skatteetatens skattemelding-API |
| Årsregnskap | Brønnøysundregistrenes åpne Regnskapsregister |
| Aksjonærregisteroppgave | Ingen offentlig status-API, sjekk manuelt hos Skatteetaten |

Når statussjekken bekrefter at innsendingen er gjort, vises kortet grønt med «Levert» og en lenke til Altinn-kvitteringen. Knappen **Oppdater status** kjører sjekkene på nytt.

Statussjekkene gjøres mot regnskapsåret som tilhører neste frist (f.eks. 31. juli 2026 → regnskapsår 2025).

---

## Oppsett-fanen

Under **Oppsett** finner du:

- **Maskinporten-credentials:** Klient-ID og Nøkkel-ID fra Digdirs selvbetjeningsportal, og ditt eget organisasjonsnummer (9 siffer). Klikk **Lagre konfigurasjon** for å skrive verdiene til `~/.wenche/.env`.
- **Privat nøkkel:** Last opp RSA-nøkkelen (.pem) Wenche bruker mot Maskinporten. Den lagres lokalt og sendes aldri videre.
- **Status og tilkoblingstest:** Et statuskort viser hva som mangler eller er klart, og knappen **Test tilkobling** sjekker Maskinporten, Altinn-veksling og systembruker under ett.
- **Systembruker i Altinn:** Knapper for å registrere systemet, opprette systembruker, sjekke status og oppdatere rettigheter. Når du oppretter en systembruker, vises en godkjenningslenke du åpner og bekrefter i Altinn med BankID.

---

## Skattemelding (frist 31. mai)

Wenche fyller ut næringsspesifikasjonen og skattemeldingen og sender dem digitalt til Skatteetaten via Altinn. Du fullfører ved å signere med BankID i Altinn.

!!! note "Inntektsår og skjemaversjon"
    Wenche leverer skattemelding etter Skatteetatens gjeldende skjema (for tiden v5) og støtter inneværende og nylige inntektsår. Eldre år som Skatteetaten kun tar imot i et tidligere skjema (for eksempel inntektsår 2024 i v4), kan ikke sendes via Wenche. Årsregnskap og aksjonærregisteroppgave er ikke berørt av dette.

Gå til fanen **Send** og klikk **Fortsett til innsending** ved siden av **Skattemelding**.

Wenche validerer først skattemeldingen mot Skatteetaten og viser en oppsummering. Er noe feil, stopper Wenche uten å sende noe og viser hva som må rettes. Når valideringen er OK, bekrefter du og skattemeldingen lastes opp. Wenche viser en lenke til Altinn-innboksen. Åpne lenken og signer med BankID for å fullføre innsendingen.

!!! info "Automatisk validering før innsending"
    Webgrensesnittet kjører Skatteetatens valideringstjeneste som første steg. Blir innsendingen avvist (`validertMedFeil`), sendes ingenting inn og du får en tydelig feilmelding om hva som må rettes. Validering lagrer ikke data hos Skatteetaten.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Skatteetaten krever at en personlig bruker bekrefter skattemeldingen via ID-porten. Wenche laster opp innholdet med systembruker, men selve innsendingen fullføres først når du signerer med BankID i Altinn. Dette kan ikke gjøres maskinelt.

!!! tip "Formuesverdi av aksjer (aksjeoppgaven RF-1088S)"
    Eier selskapet aksjer i andre selskap, fyll inn **formuesverdien** fra aksjeoppgaven (RF-1088S, post 209) i feltet «Formuesverdi aksjer» (Tall-fanen → Skattemelding, eller `formuesverdi_aksjer` i config.yaml). Wenche bruker den til å beregne formuesverdien bak selskapets egne aksjer, som er grunnlaget for eiernes formuesskatt. Uten den blir feltet stående tomt og Skatteetaten gir en merknad.

Sammendraget inneholder:

- Alle felt i næringsspesifikasjonen ferdig utfylt
- Skatteberegning med fritaksmetoden der det er aktuelt
- Beregnet skatt (22 %), og en kontroll mot skattekostnaden du har ført
- Skattekostnad ført i resultatregnskapet
- Fremførbart underskudd hvis selskapet gikk med tap
- **Egenkapitalnote** (rskl. § 7-2b) med bevegelse per egenkapitalpost (inngående balanse, årsresultat, utbytte og utgående balanse)

!!! info "Fritaksmetoden og sjablonregelen"
    Wenche håndterer **to tilfeller** avhengig av eierandelen i selskapet som deler ut utbytte (`eierandel_for_fritaksmetoden` i config.yaml):

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

Gå til fanen **Send** og klikk **Fortsett til innsending** ved siden av **Årsregnskap**, og bekreft.

Når opplastingen er ferdig vises en lenke **Signer i Altinn**. Klikk den og signer med BankID for å fullføre innsendingen.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Wenche laster opp regnskapet og klargjør det for signering. Selve signeringen må gjøres av daglig leder eller styreleder i Altinn med BankID, dette er et juridisk krav og kan ikke gjøres maskinelt.

!!! info "Sammenligningstall (rskl. § 6-6)"
    Årsregnskapet inkluderer automatisk sammenligningstall fra foregående år når `foregaaende_aar` er utfylt i `config.yaml`. Dette er obligatorisk etter regnskapsloven § 6-6. For selskaper stiftet i inneværende regnskapsår kan seksjonen utelates.

---

## Aksjonærregisteroppgave (frist 31. januar)

Wenche sender RF-1086 direkte til Skatteetatens eget REST-API, ikke via Altinn-instansflyt. Innsendingen er maskinell og krever ikke manuell signering.

!!! note "Forutsetninger"
    - Maskinporten-klienten din må ha fått scopet `skatteetaten:innrapporteringaksjonaerregisteroppgave` innvilget. Se [steg 2f i oppsett](oppsett.md#2f-sk-om-tilgang-til-skds-api-for-aksjonrregisteroppgave).
    - Systembrukeren for din organisasjon må inkludere SKD-rettigheten. Denne settes opp automatisk når du oppretter systembruker fra Oppsett-fanen, se [steg 5 i oppsett](oppsett.md#steg-5-registrer-systembruker-i-altinn).
    - `kontakt_epost` må være utfylt under `selskap` i `config.yaml` (eller i Wenche under **Tall**).

Gå til fanen **Send** og klikk **Fortsett til innsending** ved siden av **Aksjonærregister**, og bekreft.

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

Notene sendes **ikke** inn digitalt til Brønnøysundregistrene. Skjemaet RR-0002 har ingen felt for fritekstnoter, det er kun tall som overføres via Altinn. Notene er et dokument du oppbevarer selv.

### Hvordan bruke notene i Wenche?

1. Gå til fanen **Tall** og finn seksjonen **Obligatoriske noter**
2. Fyll inn antall ansatte (typisk 0 for holdingselskaper)
3. Fyll inn eventuelle lån til nærstående (aksjonærer, styremedlemmer), og klikk **Lagre data**
4. Gå til fanen **Dokumenter** og klikk **Last ned** ved siden av **Noter**, du får filen `noter_ÅÅÅÅ_ORGNR.txt`
5. Les gjennom teksten og tilpass om nødvendig
6. Arkiver filen sammen med det signerte årsregnskapet

!!! note "Tilpass gjerne noteteksten"
    Wenche genererer et standardoppsett som passer de fleste holdingselskaper. Har selskapet særskilte forhold som bør beskrives, for eksempel eierskapsbegrensninger, konsernforhold eller pantsettelse av aksjer, bør du tilpasse teksten i den nedlastede filen.

!!! warning "Notene er obligatoriske, men ikke verifiserbart fullstendige"
    Wenche dekker minimumskravene etter NRS 8 (God regnskapsskikk for små foretak). For selskaper med mer komplekse forhold kan ytterligere noter være påkrevd. Ved tvil, kontakt en regnskapsfører eller revisor.

---

## Sikkerhet

- `.env` og `config.yaml` skal aldri legges i git (de er lagt til i `.gitignore`)
- Innloggingstokenet lagres i `~/.wenche/token.json` med rettigheter begrenset til din bruker
- Wenche sender aldri data andre steder enn til Maskinporten og Altinn
