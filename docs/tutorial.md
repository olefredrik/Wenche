# Din første innsending

Denne veiledningen tar deg gjennom en komplett innsending fra start til slutt. Vi bruker et fiktivt selskap, **Eksempel Holding AS**, som eksempel gjennom hele prosessen.

!!! note "Forutsetninger"
    Du bør ha fullført [installasjon](installasjon.md) og [oppsett](oppsett.md) før du starter. Wenche skal være installert, `.env` skal være konfigurert, og systembrukeren skal være godkjent i Altinn.

---

## Selskapet vi bruker som eksempel

**Eksempel Holding AS** er et enkelt holdingselskap med følgende situasjon for regnskapsåret 2024:

- Eier 100 % av Fjordheim Teknologi AS
- Mottok **250 000 kr** i utbytte fra datterselskapet
- Betalte **5 500 kr** i regnskaps- og bankgebyrer
- Har **1 200 kr** på driftskonto per 31.12
- Aksjekapital: **30 000 kr**
- Daglig leder og styreleder: **Kari Nordmann**
- Én aksjonær: Kari Nordmann, 1 000 aksjer

---

## Steg 1 — Start webgrensesnittet

```bash
wenche
```

Wenche åpner `http://localhost:8080` i nettleseren. Du ser sju faner øverst: **Hjem**, **1. Oppsett**, **2. Selskap**, **3. Regnskap**, **4. Aksjonærer**, **5. Dokumenter** og **6. Send til Altinn**.

**Hjem**-fanen viser fristkort for de tre årlige innsendingene med live statussjekk, se [Bruk → Hjem-fanen](bruk.md#hjem-fanen) for detaljer. Resten av denne tutorialen går gjennom steg 1–6.

---

## Steg 2 — Fyll ut selskapsinformasjon

Gå til fanen **Selskap** og fyll inn:

- **Selskapsnavn:** Eksempel Holding AS
- **Organisasjonsnummer:** 123456789
- **Daglig leder:** Kari Nordmann
- **Styreleder:** Kari Nordmann
- **Forretningsadresse:** Eksempelveien 1, 0001 Oslo
- **Stiftelsesår:** 2020
- **Aksjekapital:** 30 000
- **Regnskapsår:** 2024

Klikk **Lagre konfigurasjon**.

!!! tip "Har du SAF-T fra regnskapssystemet ditt?"
    Klikk **Importer fra SAF-T Financial** øverst i fanen. Last opp XML-filen og Wenche fyller inn alle regnskapstall, kontakt-epost (hvis tilgjengelig), lån fra aksjonær (saldo og retning) og fremførbart underskudd (estimat fra konto 2080) automatisk. Du må fortsatt fylle inn daglig leder, styreleder, aksjonærdata, samt motpart, rente og sikkerhet for lån.

---

## Steg 3 — Fyll ut regnskapstall

Gå til fanen **Regnskap** og fyll inn tallene for Eksempel Holding AS:

**Resultatregnskap:**

- Utbytte fra datterselskap: 250 000
- Andre driftskostnader: 5 500

**Balanse — eiendeler:**

- Aksjer i datterselskap: (kostpris)
- Bankinnskudd: 1 200

**Balanse — egenkapital og gjeld:**

- Aksjekapital: 30 000
- Annen egenkapital: (akkumulert resultat)

Klikk **Lagre konfigurasjon**. Wenche viser en advarsel hvis balansen ikke går opp, sum eiendeler skal være lik sum egenkapital og gjeld.

---

## Steg 4 — Fyll ut aksjonærdata

Gå til fanen **Aksjonærer** og registrer aksjonærene per 31.12:

- **Navn:** Kari Nordmann
- **Fødselsnummer:** (11 siffer)
- **Antall aksjer:** 1 000
- **Aksjeklasse:** ordinære
- **Utbytte utbetalt:** (beløp, eller 0)

Klikk **Lagre konfigurasjon**.

---

## Steg 5 — Send skattemeldingen

Wenche fyller ut næringsspesifikasjonen og skattemeldingen og sender dem digitalt til Skatteetaten via Altinn. Du fullfører ved å signere med BankID i Altinn.

!!! tip "Formuesverdi av aksjer"
    Eier selskapet aksjer i andre selskap, fyll inn **formuesverdien** fra aksjeoppgaven (RF-1088S, post 209) i feltet «Formuesverdi av aksjer selskapet eier» under Dokumenter. Den brukes til å beregne formuesverdien bak selskapets egne aksjer, som er grunnlaget for eiernes formuesskatt.

1. Gå til fanen **Dokumenter**, fyll inn skattemelding-innstillingene og klikk **Last ned skattemelding** for å lese gjennom sammendraget. For Eksempel Holding AS med 100 % eierandel er utbyttet fritatt under fritaksmetoden, så skatten blir **0 kr**.
2. Gå til fanen **Send til Altinn** og klikk **Send skattemelding til Skatteetaten**. Wenche validerer skattemeldingen mot Skatteetaten først, og sender ingenting hvis noe er feil. Da får du en tydelig melding om hva som må rettes, slik at du kan oppdatere tallene og prøve igjen.
3. Når valideringen er OK, lastes skattemeldingen opp automatisk og Wenche viser en lenke til Altinn-innboksen. Åpne lenken og signer med BankID for å fullføre innsendingen.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Skatteetaten krever at en personlig bruker bekrefter skattemeldingen via ID-porten. Wenche laster opp innholdet, men selve innsendingen fullføres først når du signerer med BankID. Dette kan ikke gjøres maskinelt (SSV-5129).

---

## Steg 6 — Send årsregnskapet

Gå til fanen **Send til Altinn** og klikk **Send årsregnskap**.

Når opplastingen er ferdig vises knappen **Signer i Altinn**. Klikk den og signer med BankID som daglig leder eller styreleder.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Dette er et juridisk krav og kan ikke gjøres maskinelt.

---

## Steg 7 — Send aksjonærregisteroppgaven

Gå til fanen **Send til Altinn** og klikk **Send aksjonærregister til Skatteetaten**.

Forsendelse-ID vises i grensesnittet når innsendingen er fullført. Ingen manuell signering nødvendig.

---

## Ferdig

Du har nå:

- [x] Generert og sendt inn skattemelding og næringsspesifikasjon
- [x] Sendt inn årsregnskapet til Brønnøysundregistrene
- [x] Sendt inn aksjonærregisteroppgaven (RF-1086) til Skatteetaten

Neste år gjentar du fra steg 2 med oppdaterte tall, og husk å fylle ut `foregaaende_aar` med årets tall for å få med sammenligningstall (rskl. § 6-6).
