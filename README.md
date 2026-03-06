# Wenche

Wenche er et enkelt kommandolinjeverktøy for elektronisk innsending av regnskap og skattedokumenter til norske myndigheter via Altinn. Verktøyet er laget for holdingselskaper og småaksjeselskaper med lav aktivitet som ikke har behov for et fullverdig regnskapsprogram.

Autentisering skjer med BankID via ID-porten — ingen virksomhetssertifikat nødvendig.

## Støttede innsendinger

| Innsending | Mottaker | Status |
|---|---|---|
| Årsregnskap | Brønnøysundregistrene | Implementert |
| Aksjonærregisteroppgave (RF-1086) | Skatteetaten via Altinn | Implementert |
| Skattemelding for AS | Skatteetaten | Planlagt (fase 2) |

## Forutsetninger

- Python 3.11 eller nyere
- En registrert ID-porten klient-ID (se [Registrer ID-porten klient](#registrer-id-porten-klient))
- BankID

## Installasjon

```bash
git clone https://github.com/ditt-brukernavn/wenche.git
cd wenche
pip install -e .
```

## Oppsett

### 1. Konfigurasjonsfil

Kopier eksempelfilen og fyll inn dine verdier:

```bash
cp config.example.yaml config.yaml
```

Åpne `config.yaml` og fyll inn selskapsinfo, regnskapstall og aksjonærdata. Filen er kommentert og selvforklarende.

### 2. Miljøvariabler

```bash
cp .env.example .env
```

Åpne `.env` og lim inn din ID-porten klient-ID:

```
IDPORTEN_CLIENT_ID=din-client-id-her
```

For å bruke testmiljøet i stedet for produksjon:

```
WENCHE_ENV=test
```

### Registrer ID-porten klient

For å sende inn via API må du ha en registrert OIDC-klient hos Digdir. Dette er gratis og tar normalt 1–2 virkedager.

1. Gå til [samarbeid.digdir.no](https://samarbeid.digdir.no) og logg inn
2. Opprett en ny integrasjon under **ID-porten**
3. Velg klienttype **public** (ingen client secret nødvendig)
4. Sett redirect URI til `http://localhost:7777/callback`
5. Legg til scope: `openid profile altinn:instances.read altinn:instances.write`
6. Kopier klient-IDen inn i `.env`

## Bruk

### Test uten innsending (anbefalt første gang)

Generer og valider dokumentene lokalt uten å sende noe til Altinn:

```bash
wenche send-aarsregnskap --dry-run
wenche send-aksjonaerregister --dry-run
```

Dry-run lagrer de genererte filene i gjeldende mappe slik at du kan inspisere dem.

### Send inn

```bash
wenche login
wenche send-aarsregnskap
wenche send-aksjonaerregister
wenche logout
```

Du blir sendt til nettleseren for BankID-innlogging første gang. Tokenet gjenbrukes for påfølgende kommandoer i samme sesjon.

### Alle kommandoer

```
wenche --help

Kommandoer:
  login                    Logg inn med BankID via ID-porten
  logout                   Logg ut og slett lagret token
  send-aarsregnskap        Send inn årsregnskap til Brønnøysundregistrene
  send-aksjonaerregister   Send inn aksjonærregisteroppgave (RF-1086)
  send-skattemelding       Send inn skattemelding for AS (ikke tilgjengelig ennå)

Alternativer:
  --config TEXT            Sti til konfigurasjonsfil [standard: config.yaml]
  --dry-run                Generer dokument lokalt uten å sende til Altinn
```

## Frister

| Innsending | Frist |
|---|---|
| Aksjonærregisteroppgave | 31. januar |
| Årsregnskap | 31. juli |
| Skattemelding for AS | 31. mai |

## Sikkerhet

- `.env` og `config.yaml` skal aldri legges i git (de er lagt til i `.gitignore`)
- Innloggingstokenet lagres i `~/.wenche/token.json` med rettigheter begrenset til din bruker
- Wenche sender aldri data andre steder enn til ID-porten og Altinn

## Bidra

Bidrag er velkomne. Åpne gjerne en issue eller pull request. Særlig nyttig:

- Verifisering av iXBRL-format mot Brønnøysundregistrenes gjeldende taksonomi
- Implementasjon av skattemelding (krever systemleverandør-registrering hos Skatteetaten)
- Testing mot Altinn testmiljø (tt02)

## Lisens

MIT — se [LICENSE](LICENSE).
