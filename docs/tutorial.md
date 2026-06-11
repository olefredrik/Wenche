# Din første innsending

Denne veiledningen tar deg gjennom en komplett innsending fra start til slutt. Vi bruker et fiktivt selskap, **Eksempel Holding AS**, som eksempel gjennom hele prosessen.

!!! note "Forutsetninger"
    Du bør ha fullført [installasjon](installasjon.md) og [oppsett](oppsett.md) før du starter. Wenche skal være installert, `.env` skal være konfigurert, og systembrukeren skal være godkjent i Altinn.

---

## Selskapet vi bruker som eksempel

**Eksempel Holding AS** er et enkelt holdingselskap med følgende situasjon for regnskapsåret 2025:

- Eier 100 % av Fjordheim Teknologi AS
- Mottok **250 000 kr** i utbytte fra datterselskapet
- Betalte **5 500 kr** i regnskaps- og bankgebyrer
- Har **1 200 kr** på driftskonto per 31.12
- Aksjekapital: **30 000 kr**
- Daglig leder og styreleder: **Kari Nordmann**
- Én aksjonær: Kari Nordmann, 1 000 aksjer

---

## Steg 1: Start webgrensesnittet

```bash
wenche
```

Wenche åpner `http://localhost:8080` i nettleseren. Øverst ser du fanene **Hjem**, **Oppsett**, **Tall**, **Dokumenter** og **Send**.

**Hjem**-fanen viser fristkort for de tre årlige innsendingene med live statussjekk, se [Bruk → Hjem-fanen](bruk.md#hjem-fanen) for detaljer. Resten av denne tutorialen går gjennom **Tall**, **Dokumenter** og **Send**.

---

## Steg 2: Fyll ut tallene

Gå til fanen **Tall**. Her fyller du ut alt på én side: selskapsopplysninger, resultatregnskap, balanse, skattemelding-innstillinger, fjorårets sammenligningstall, aksjonærer og noter.

**Selskap:**

- **Selskapsnavn:** Eksempel Holding AS
- **Organisasjonsnummer:** 123456789
- **Daglig leder:** Kari Nordmann
- **Styreleder:** Kari Nordmann
- **Forretningsadresse:** Eksempelveien 1, 0001 Oslo
- **Stiftelsesår:** 2020
- **Aksjekapital:** 30 000
- **Regnskapsår:** 2025

**Resultatregnskap:**

- Utbytte fra datterselskap: 250 000
- Andre driftskostnader: 5 500

**Balanse, eiendeler:**

- Aksjer i datterselskap: (kostpris)
- Bankinnskudd: 1 200

**Balanse, egenkapital og gjeld:**

- Aksjekapital: 30 000
- Annen egenkapital: (akkumulert resultat)

Wenche viser fortløpende om balansen går opp, sum eiendeler skal være lik sum egenkapital og gjeld.

**Aksjonærer** (per 31.12):

- **Navn:** Kari Nordmann
- **Fødselsnummer:** (11 siffer)
- **Antall aksjer:** 1 000
- **Aksjeklasse:** ordinære
- **Utbytte utbetalt:** (beløp, eller 0)

Klikk **Lagre data** nederst for å skrive til `config.yaml`.

!!! tip "Fører du regnskapet i Bodil, eller har du SAF-T?"
    Klikk **Hent tall fra Bodil** øverst i skjemaet og last opp `config.yaml` fra [Bodil](https://github.com/olefredrik/Bodil), så fylles regnskapstallene inn for deg. Har du en SAF-T-eksport fra regnskapssystemet i stedet, klikk **Importer fra SAF-T** og last opp filen. Begge forhåndsfyller skjemaet, du ser over og lagrer selv. (SAF-T finnes også på kommandolinjen med `wenche importer-saft`, se [Kommandolinje](avansert/cli.md).)

---

## Steg 3: Se gjennom dokumentene (valgfritt)

Gå til fanen **Dokumenter** for å generere og laste ned dokumentene før innsending: skattemelding (tekstsammendrag), årsregnskap (XML), aksjonærregister (XML) og noter. Ingenting sendes inn her, dette er kun for gjennomgang.

!!! tip "Formuesverdi av aksjer"
    Eier selskapet aksjer i andre selskap, fyll inn **formuesverdien** fra aksjeoppgaven (RF-1088S, post 209) i feltet «Formuesverdi aksjer» under **Tall** → Skattemelding. Den brukes til å beregne formuesverdien bak selskapets egne aksjer, som er grunnlaget for eiernes formuesskatt.

For Eksempel Holding AS med 100 % eierandel er utbyttet fritatt under fritaksmetoden, så skatten blir **0 kr**.

---

## Steg 4: Send inn

Gå til fanen **Send**. Her finner du en knapp for hver av de tre innsendingene: **Årsregnskap**, **Aksjonærregister** og **Skattemelding**.

For hver innsending fungerer det slik:

1. Klikk **Fortsett til innsending**. Wenche kontrollerer tallene (en lokal dry-run, for skattemeldingen også Skatteetatens valideringstjeneste) og viser en oppsummering. Blir noe avvist, sendes ingenting, og du får en tydelig melding om hva som må rettes.
2. Ser alt riktig ut, huk av bekreftelsen og klikk **Bekreft og send inn**.

### Skattemelding

Wenche fyller ut næringsspesifikasjonen og skattemeldingen og laster dem opp. Når opplastingen er ferdig, viser Wenche en lenke til Altinn-innboksen.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Skatteetaten krever at en personlig bruker bekrefter skattemeldingen via ID-porten. Wenche laster opp innholdet, men selve innsendingen fullføres først når du signerer med BankID. Dette kan ikke gjøres maskinelt (SSV-5129).

### Årsregnskap

Når opplastingen er ferdig, vises lenken **Signer i Altinn**. Klikk den og signer med BankID som daglig leder eller styreleder.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Dette er et juridisk krav og kan ikke gjøres maskinelt.

### Aksjonærregister

Forsendelse-ID vises i grensesnittet når innsendingen er fullført. Ingen manuell signering nødvendig.

---

## Ferdig

Du har nå:

- [x] Generert og sendt inn skattemelding og næringsspesifikasjon
- [x] Sendt inn årsregnskapet til Brønnøysundregistrene
- [x] Sendt inn aksjonærregisteroppgaven (RF-1086) til Skatteetaten

Neste år gjentar du fra steg 2 med oppdaterte tall, og husk å fylle ut «Fjorårets tall» med årets tall for å få med sammenligningstall (rskl. § 6-6).
