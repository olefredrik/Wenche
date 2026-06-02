# Testing mot tt02

!!! info "For utviklere og bidragsytere"
    Denne siden er for de som vil utvikle på Wenche eller tørrtrene innsending uten å sende ekte data til myndighetene. Vanlig bruk dekkes av webgrensesnittet, se [Bruk](../bruk.md).

Wenche kan kjøres mot Skatteetatens testmiljø (tt02) i stedet for produksjon. Testmiljøet er et separat økosystem:

- Egne Maskinporten-klienter i Digdirs test-portal
- Egen systembruker i Altinn tt02
- Syntetiske organisasjoner fra Tenor (din ekte org.nr. finnes ikke i testmiljøet)
- TestID-innlogging i stedet for BankID

---

## Start UI i testmodus

```bash
wenche dev
```

UI starter på `http://localhost:8080` med en diskret `TEST`-tag i headeren. Alle innsendinger går til Skatteetatens tt02-API, ingen ekte innsending til myndighetene.

`wenche` (uten args) starter alltid mot produksjon. `wenche dev` starter alltid mot test. De to modusene er låst og kan ikke veksles mellom uten å starte UI på nytt.

## Separate config-filer

`wenche` leser og skriver `config.yaml` med dine virkelige selskapsdata. `wenche dev` leser og skriver `config.dev.yaml` med Tenor-testdata. Filene er fullstendig adskilt, slik at testdata ikke kan overskrive dine ekte tall ved et uhell.

Første gang du kjører `wenche dev` er `config.dev.yaml` tom. Fyll inn syntetiske data fra Tenor i fanen **Tall**, og klikk **Lagre data**. (I testmodus kan du også klikke **Fyll inn eksempeldata (test)** for et raskt utgangspunkt.)

Begge filer er listet i `.gitignore` og skal aldri legges i git.

---

## Sett opp test-credentials

Test-credentials lagres i samme `~/.wenche/.env`-fil som prod-credentials, men med `_TEST`-suffix:

```
MASKINPORTEN_CLIENT_ID_TEST=test-klient-uuid-her
MASKINPORTEN_KID_TEST=test-nokkel-uuid-her
SKD_TEST_ORG_NUMMER=syntetisk-tenor-orgnr-her
MASKINPORTEN_PRIVAT_NOKKEL=maskinporten_privat.pem
```

Prod-credentials (uten suffix eller med `_PROD`-suffix) påvirkes ikke og forblir tilgjengelige for `wenche`-kommandoen.

| Variabel | Beskrivelse |
|---|---|
| `MASKINPORTEN_CLIENT_ID_TEST` | Klient-ID fra Digdirs test-portal |
| `MASKINPORTEN_KID_TEST` | UUID for offentlig nøkkel registrert på test-klienten |
| `SKD_TEST_ORG_NUMMER` | Syntetisk Tenor-orgnr som brukes som systembruker_org og party |
| `SKD_TEST_PARTSNUMMER` | Valgfritt. Partsnummer fra Tenor for skattemelding-test. Hopper over kallet til SKDs forhåndsutfylt-API og bruker partsnummeret direkte |

---

## Maskinporten-klient i test-portalen

Test- og prod-klienter er separate UUID-er i to ulike portaler:

- **Produksjon:** [sjolvbetjening.samarbeid.digdir.no](https://sjolvbetjening.samarbeid.digdir.no)
- **Test:** [sjolvbetjening.test.samarbeid.digdir.no](https://sjolvbetjening.test.samarbeid.digdir.no)

Gjenta steg 2d og 2e i [oppsett](../oppsett.md) i test-portalen. Samme private RSA-nøkkel kan brukes i begge miljø, du laster bare opp den offentlige nøkkelen til begge klienter.

For test-scopes hos Skatteetaten (`skatteetaten:innrapporteringaksjonaerregisteroppgave`, `skatteetaten:formueinntekt/skattemelding`), kontakt [SKDs brukerstøtteportal](https://eksternjira.sits.no/plugins/servlet/desk/site/global) og oppgi at du ønsker tilgang i testmiljø.

---

## Syntetiske Tenor-organisasjoner

Altinn tt02 og SKDs testmiljø er populert med data fra Tenor. Din egen organisasjon finnes ikke i testregisteret, og innsending vil feile (typisk med en uventet 500-feil) hvis du forsøker å bruke ekte org.nr. i test.

Hent et test-AS fra [skatteetaten.no/testdata](https://www.skatteetaten.no/testdata/) og bruk dette som `SKD_TEST_ORG_NUMMER`.

---

## Systembruker i test-Altinn

Gå til Oppsett-fanen i `wenche dev` og klikk **Opprett systembruker**. Lenken peker til Altinn tt02 hvor du logger inn med TestID, bruk fødselsnummeret til daglig leder for Tenor-orgen din (finnes under **Kildedata → rollegrupper → DAGL** i [Tenor testdatasøk](https://www.skatteetaten.no/testdata/)).

---

## CLI mot testmiljø

For å kjøre CLI-kommandoer mot testmiljø, sett `WENCHE_ENV=test`:

```bash
WENCHE_ENV=test wenche send-skattemelding --dry-run
```

Dette krever at `_TEST`-variablene er satt i `~/.wenche/.env`. Se [Kommandolinje](cli.md) for detaljer om de enkelte kommandoene.
