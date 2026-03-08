# Wenche

![PyPI](https://img.shields.io/pypi/v/wenche)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)

Wenche er et enkelt kommandolinjeverktøy for holdingselskaper og småaksjeselskaper som må levere regnskap og skattedokumenter til norske myndigheter. Verktøyet hjelper deg å fylle ut og sende inn de obligatoriske skjemaene uten behov for et fullverdig regnskapsprogram.

Autentisering skjer via Maskinporten med et selvgenerert RSA-nøkkelpar — ingen virksomhetssertifikat eller BankID-innlogging nødvendig.

## Hva er støttet?

Alle AS plikter å levere tre ting hvert år. Wenche hjelper med alle tre:

| Hva | Til hvem | Frist | Status |
|---|---|---|---|
| **Årsregnskap** | Brønnøysundregistrene | 31. juli | Automatisk innsending |
| **Aksjonærregisteroppgave** (RF-1086) | Skatteetaten via Altinn | 31. januar | Automatisk innsending |
| **Skattemelding for AS** (RF-1028 + RF-1167) | Skatteetaten | 31. mai | Genereres lokalt — sendes inn manuelt |

> **Merk om skattemeldingen:** Automatisk innsending av skattemelding krever registrering som systemleverandør hos Skatteetaten. Wenche genererer i stedet et ferdig utfylt sammendrag som du raskt kopierer inn på skatteetaten.no.

## Hva er de ulike skjemaene?

Har du aldri hørt om disse skjemaene? Her er en kort forklaring:

- **Årsregnskapet** er en oppsummering av selskapets økonomi — hva selskapet eier, hva det skylder, og hva det tjente eller tapte i løpet av året. Dette er offentlig informasjon.
- **Aksjonærregisteroppgaven (RF-1086)** forteller Skatteetaten hvem som eier aksjer i selskapet og om det er utbetalt utbytte. Brukes blant annet til å forhåndsutfylle aksjonærenes personlige skattemelding.
- **Næringsoppgaven (RF-1167)** er en detaljert oppstilling av selskapets inntekter og kostnader for skatteformål. Grunnlaget for skatteberegningen.
- **Skattemeldingen for AS (RF-1028)** er selve skattemeldingen der Skatteetaten beregner om selskapet skylder skatt. For holdingselskaper som eier aksjer i andre selskaper gjelder **fritaksmetoden**: utbytte fra datterselskaper er i praksis 97 % skattefritt.

## Forutsetninger

- Python 3.11 eller nyere (sjekk med `python3 --version`, installer via `brew install python@3.11` om nødvendig)
- Registrert Maskinporten-klient hos Digdir (se [Registrer Maskinporten-klient](#registrer-maskinporten-klient)) — kun nødvendig for automatisk innsending
- OpenSSL (følger med macOS og de fleste Linux-distribusjoner)

## Installasjon

Sjekk først at du har Python 3.11 eller nyere:

```bash
python3 --version
```

Viser den 3.9 eller eldre, installer en nyere versjon:

```bash
brew install python@3.11
```

Installer deretter Wenche i et virtuelt miljø:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install wenche
```

Wenche er nå tilgjengelig som kommandoen `wenche` i terminalen din. Husk å aktivere miljøet (`source .venv/bin/activate`) i nye terminalvinduer.

### Webgrensesnitt (valgfritt)

Foretrekker du å fylle ut skjemaer i nettleseren fremfor terminalen? Installer Wenche med UI-støtte:

```bash
pip install "wenche[ui]"
```

Start deretter webgrensesnittet:

```bash
wenche ui
```

En nettleser åpner seg automatisk. Du kan fylle inn selskapsinformasjon og regnskapstall i skjemaene, laste ned dokumenter og sende inn direkte fra grensesnittet — ingen konfigurasjonsfil nødvendig.

### For utviklere

Vil du bidra til koden eller kjøre siste versjon fra GitHub?

```bash
git clone https://github.com/olefredrik/wenche.git
cd wenche
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Kjør testsuiten for å verifisere at alt fungerer:

```bash
pytest tests/ -v
```

Testene kjøres også automatisk på GitHub ved push og pull request.

## Oppsett

### 1. Generer RSA-nøkkelpar

Dette er nøklene som brukes til å identifisere deg overfor Maskinporten. Tenk på dem som brukernavn og passord, men sikrere.

```bash
openssl genrsa -out maskinporten_privat.pem 2048
openssl rsa -in maskinporten_privat.pem -pubout -out maskinporten_offentlig.pem
```

Den private nøkkelen (`maskinporten_privat.pem`) skal aldri deles eller legges i git. Den offentlige nøkkelen lastes opp til Digdir under registrering.

### 2. Konfigurasjonsfil

```bash
cp config.example.yaml config.yaml
```

Åpne `config.yaml` og fyll inn selskapets opplysninger, regnskapstall og aksjonærdata. Filen er kommentert og selvforklarende. Alle beløp oppgis i hele kroner (NOK).

### 3. Miljøvariabler

```bash
cp .env.example .env
```

Fyll inn verdiene fra Digdirs selvbetjeningsportal (se [Registrer Maskinporten-klient](#registrer-maskinporten-klient)):

```
MASKINPORTEN_CLIENT_ID=din-client-id-her
MASKINPORTEN_PRIVAT_NOKKEL=maskinporten_privat.pem
MASKINPORTEN_KID=uuid-fra-portalen-her
WENCHE_ENV=prod
```

`MASKINPORTEN_KID` er UUID-en som portalen tildeler nøkkelen din — synlig i nøkkellisten under klienten.

For testmiljø (Maskinporten test + Altinn tt02):

```
WENCHE_ENV=test
```

### Registrer Maskinporten-klient

Wenche bruker Maskinporten for maskin-til-maskin-autentisering. Registrering er gratis og tar ca. 15 minutter.

**Steg 1 — Søk om tilgang**

Gå til [samarbeid.digdir.no](https://samarbeid.digdir.no) og søk om tilgang som **Maskinporten-konsument**. Du vil motta en e-post med bekreftelse og lenke til selvbetjeningsportalen.

**Steg 2 — Opprett integrasjon**

Logg inn på [selvbetjeningsportalen.digdir.no](https://selvbetjeningsportalen.digdir.no):

1. Velg **Test** (for testmiljø) eller **Produksjon**
2. Velg **Klienter** → **Maskinporten & KRR**
3. Klikk **Ny integrasjon** og fyll ut:
   - Visningsnavn: `wenche`
   - Beskrivelse: valgfri
   - Access token levetid: `120` (standard)
4. Legg til scopes: `altinn:instances.read` og `altinn:instances.write`
5. Kopier **klient-ID** inn i `.env` som `MASKINPORTEN_CLIENT_ID`

**Steg 3 — Last opp offentlig nøkkel**

Under klienten, klikk **Legg til nøkkel** og lim inn innholdet i `maskinporten_offentlig.pem` (PEM-format). Lagre klienten.

Nøkkelen vil vises i listen med en UUID (f.eks. `9bc5078c-...`). Kopier denne UUID-en inn i `.env` som `MASKINPORTEN_KID`.

> **Merk:** Endringer i testmiljøet kan ta noen minutter å synkronisere.

## Bruk

### Skattemelding (frist 31. mai)

Wenche genererer et ferdig utfylt sammendrag av RF-1167 (næringsoppgaven) og RF-1028 (skattemeldingen) basert på tallene i `config.yaml`.

```bash
wenche generer-skattemelding
```

Du kan også lagre sammendraget til en fil:

```bash
wenche generer-skattemelding --ut skattemelding.txt
```

Sammendraget inneholder:
- Alle felt i næringsoppgaven (RF-1167) ferdig utfylt
- Skatteberegning med fritaksmetoden der det er aktuelt
- Beregnet skatt (22 %)
- Fremførbart underskudd hvis selskapet gikk med tap
- Konkrete instruksjoner for hva du gjør videre på skatteetaten.no

**Sende inn manuelt:**
1. Gå til [skatteetaten.no](https://www.skatteetaten.no/) og logg inn med BankID
2. Åpne skattemeldingen for AS for gjeldende regnskapsår
3. Fyll inn tallene fra sammendraget Wenche har generert
4. Kontroller at Skatteetaten beregner samme skatt
5. Send inn

### Årsregnskap (frist 31. juli)

Test uten innsending først (anbefalt):

```bash
wenche send-aarsregnskap --dry-run
```

`--dry-run` lagrer de genererte XML-dokumentene lokalt slik at du kan inspisere dem.

Send inn til Brønnøysundregistrene:

```bash
wenche login
wenche send-aarsregnskap
wenche logout
```

### Aksjonærregisteroppgave (frist 31. januar)

Test uten innsending:

```bash
wenche send-aksjonaerregister --dry-run
```

Send inn til Altinn:

```bash
wenche login
wenche send-aksjonaerregister
wenche logout
```

`wenche login` autentiserer mot Maskinporten med din private nøkkel og lagrer et token lokalt. Tokenet gjenbrukes for påfølgende kommandoer i samme sesjon.

### Alle kommandoer

```
wenche --help

Kommandoer:
  login                    Autentiser mot Maskinporten med RSA-nokkel
  logout                   Logg ut og slett lagret token
  generer-skattemelding    Generer ferdig utfylt RF-1167 og RF-1028 fra config.yaml
  send-aarsregnskap        Send inn arsregnskap til Bronnoysundregistrene
  send-aksjonaerregister   Send inn aksjonaerregisteroppgave (RF-1086)

Alternativer (send-aarsregnskap og send-aksjonaerregister):
  --config TEXT            Sti til konfigurasjonsfil [standard: config.yaml]
  --dry-run                Generer dokument lokalt uten a sende til Altinn

Alternativer (generer-skattemelding):
  --config TEXT            Sti til konfigurasjonsfil [standard: config.yaml]
  --ut TEXT                Lagre sammendrag til fil
```

## Frister

| Innsending | Frist |
|---|---|
| Aksjonærregisteroppgave | 31. januar |
| Skattemelding for AS | 31. mai |
| Årsregnskap | 31. juli |

## Sikkerhet

- `.env` og `config.yaml` skal aldri legges i git (de er lagt til i `.gitignore`)
- Innloggingstokenet lagres i `~/.wenche/token.json` med rettigheter begrenset til din bruker
- Wenche sender aldri data andre steder enn til Maskinporten og Altinn

## Bidra

Bidrag er velkomne. Åpne gjerne en issue eller pull request. Særlig nyttig:

- Implementasjon av automatisk skattemeldingsinnsending (krever systemleverandør-registrering hos Skatteetaten)
- Testing mot Altinn testmiljø (tt02)

## Lisens

MIT — se [LICENSE](LICENSE).
