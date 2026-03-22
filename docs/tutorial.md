# Din første innsending

Denne veiledningen tar deg gjennom en komplett innsending fra start til slutt. Vi bruker et fiktivt selskap — **Eksempel Holding AS** — som eksempel gjennom hele prosessen.

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

=== "Webgrensesnitt"

    ```bash
    wenche ui
    ```

    Wenche åpner `http://localhost:8080` i nettleseren. Du ser fem faner øverst: **Selskap**, **Regnskap**, **Aksjonærer**, **Dokumenter** og **Send til Altinn**.

=== "Kommandolinje"

    Ingen oppstart nødvendig — alle kommandoer kjøres direkte i terminalen. Se neste steg.

---

## Steg 2 — Fyll ut selskapsinformasjon

=== "Webgrensesnitt"

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
        Klikk **Importer fra SAF-T Financial** øverst i fanen. Last opp XML-filen og Wenche fyller inn alle regnskapstall automatisk. Du må fortsatt fylle inn daglig leder, styreleder og aksjonærdata manuelt.

=== "Kommandolinje"

    Kopier eksempelfilen og rediger den:

    ```bash
    cp config.example.yaml config.yaml
    ```

    Åpne `config.yaml` i en teksteditor og erstatt verdiene under `selskap` med dine egne tall. Se [Referanse](referanse.md) for beskrivelse av alle felt.

---

## Steg 3 — Fyll ut regnskapstall

=== "Webgrensesnitt"

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

    Klikk **Lagre konfigurasjon**. Wenche viser en advarsel hvis balansen ikke går opp — sum eiendeler skal være lik sum egenkapital og gjeld.

=== "Kommandolinje"

    Fyll inn tallene direkte i `config.yaml` under `resultatregnskap` og `balanse`. Balansen må stemme — sum eiendeler = sum egenkapital og gjeld.

---

## Steg 4 — Fyll ut aksjonærdata

=== "Webgrensesnitt"

    Gå til fanen **Aksjonærer** og registrer aksjonærene per 31.12:

    - **Navn:** Kari Nordmann
    - **Fødselsnummer:** (11 siffer)
    - **Antall aksjer:** 1 000
    - **Aksjeklasse:** ordinære
    - **Utbytte utbetalt:** (beløp, eller 0)

    Klikk **Lagre konfigurasjon**.

=== "Kommandolinje"

    Fyll inn aksjonærene under `aksjonaerer` i `config.yaml`. Se [Referanse](referanse.md) for feltoversikt.

---

## Steg 5 — Generer skattemeldingen

Skattemeldingen (RF-1167 + RF-1028) genereres lokalt og sendes inn manuelt på skatteetaten.no.

=== "Webgrensesnitt"

    Gå til fanen **Dokumenter** og klikk **Last ned skattemelding**.

    Sammendraget inneholder næringsoppgaven (RF-1167) og skatteberegningen. For Eksempel Holding AS med 100 % eierandel er utbyttet fritatt under fritaksmetoden — skatten blir **0 kr**.

=== "Kommandolinje"

    ```bash
    wenche generer-skattemelding --ut skattemelding_2024.txt
    ```

**Send inn manuelt:**

1. Gå til [skatteetaten.no](https://www.skatteetaten.no/) og logg inn med BankID
2. Åpne **Skattemelding for AS** for 2024
3. Fyll inn tallene fra sammendraget
4. Kontroller beregnet skatt og send inn

---

## Steg 6 — Send årsregnskapet

=== "Webgrensesnitt"

    Gå til fanen **Send til Altinn** og klikk **Send årsregnskap**.

    Når opplastingen er ferdig vises knappen **Signer i Altinn**. Klikk den og signer med BankID som daglig leder eller styreleder.

=== "Kommandolinje"

    Test uten å sende (anbefalt første gang):

    ```bash
    wenche send-aarsregnskap --dry-run
    ```

    Send inn:

    ```bash
    wenche login
    wenche send-aarsregnskap
    wenche logout
    ```

    Wenche skriver ut en lenke til Altinn-innboksen. Åpne lenken og signer med BankID.

!!! note "Signering skjer i Altinn, ikke i Wenche"
    Dette er et juridisk krav og kan ikke gjøres maskinelt.

---

## Steg 7 — Send aksjonærregisteroppgaven

=== "Webgrensesnitt"

    Gå til fanen **Send til Altinn** og klikk **Send aksjonærregister til Skatteetaten**.

    Forsendelse-ID vises i grensesnittet når innsendingen er fullført. Ingen manuell signering nødvendig.

=== "Kommandolinje"

    ```bash
    wenche login
    wenche send-aksjonaerregister
    wenche logout
    ```

    Wenche skriver ut forsendelse-ID når innsendingen er fullført.

---

## Ferdig

Du har nå:

- [x] Generert og sendt inn skattemeldingen (RF-1167 + RF-1028)
- [x] Sendt inn årsregnskapet til Brønnøysundregistrene
- [x] Sendt inn aksjonærregisteroppgaven (RF-1086) til Skatteetaten

Neste år gjentar du fra steg 2 med oppdaterte tall — og husk å fylle ut `foregaaende_aar` med årets tall for å få med sammenligningstall (rskl. § 6-6).
