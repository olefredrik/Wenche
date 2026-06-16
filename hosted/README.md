# Wenche hosted

Separat, hostet multi-tenant-variant av Wenche. Importerer `wenche`-pakken som bibliotek og
gjenbruker domene-, auth- og klientlaget. Self-hosted-appen (`wenche` / `wenche dev`, `wenche.web`)
er **upåvirket** av alt her, og denne mappen er ikke en del av `wenche`-wheelen som publiseres
til PyPI.

Status: **live på https://app.wenche.cloud**. Onboarding har to porter, og Altinn
systembruker-godkjenning (BankID) er uansett selve autorisasjonen til å sende inn. Ingen e-post,
passord eller database.

- **ID-porten-innlogging** (primær port i prod, se `api/idporten.py`): brukeren logger inn med
  BankID, vi får et **verifisert** navn, og `velg_org` bekrefter at navnet står som aktiv daglig
  leder/styreleder for det oppgitte orgnr i Enhetsregisteret før økten bindes. Fødselsnummeret
  (`pid`) er transient og lagres aldri. Skrus på ved å sette `HOSTED_IDPORTEN_*` (se under); uten
  dem er ID-porten av og invite er eneste port (slik demo kjører).
- **Per-org invite-lenke** (operatør-fallback): en signert token som bærer ETT orgnr, delt ut
  manuelt. Brukes når ID-porten-rollesjekken ikke kan treffe (skjermet person, selskap uten
  registrert rolleinnehaver). Org er ikke brukerinput.

Begge porter er sterke (invite er operatør-attestert, ID-porten er BankID-verifisert), så
AlreadyApproved-snarveien (binding til en alt godkjent systembruker uten ny BankID) gjelder begge.

**Fortsett på en annen enhet:** sesjonen lever per nettleser (signert cookie, ingen DB), så et
andre apparat står i utgangspunktet uten tilkobling. En alt koblet økt kan derfor lage en
kortvarig lenke (vist som QR + lenke på Hjem), som den nye enheten åpner for å arve samme
binding, uten ny BankID. Tilkoblingen **kopieres** (den flyttes ikke): begge enheter forblir
koblet, og hver enhet logges ut for seg. Lenken er forankret i en alt verifisert økt (bundet
`kunde_org`) og er ferskvare (5 min). Vises kun for **invite-baserte økter** (demo + fallback);
en ID-porten-bruker logger bare inn på nytt på den nye enheten (treffer AlreadyApproved), så
handoff er overflødig for dem og skjules.

## Komponenter
- `api/` — FastAPI JSON-API (importerer `wenche`).
- `web/` — SPA (React + Vite + TypeScript + Tailwind 4). Tynn happy-path: innlogging →
  systembruker-onboarding → lim inn data → dry-run/innsending. Snakker med `api/` via
  Vite-proxy (`/api` → `127.0.0.1:8077`), så alt er same-origin i dev.

## Kjøre lokalt mot tt02 (dev)
Enkleste vei, `dev_local.py` wirer test-credentials automatisk fra dine `.env`-filer:
```bash
# Terminal 1 (backend mot tt02):
./.venv/bin/python hosted/dev_local.py            # http://127.0.0.1:8077

# Terminal 2 (frontend):
cd hosted/web && npm install && npm run dev       # http://localhost:5173
```
`dev_local.py` skriver ut en **invite-lenke** ved oppstart. Åpne den (den setter økten som
invitert), koble systembruker for en godkjent test-org, lim inn data og kjør dry-run/innsending.
Per-org invite-lenker lages med `./.venv/bin/python hosted/mint_invite.py <orgnr>`.

## Miljøvariabler (server-hemmeligheter, aldri i koden)
| Variabel | Beskrivelse |
|---|---|
| `WENCHE_ENV` | `prod` (default) eller `test`. Pinnes i hostet drift. |
| `HOSTED_SESSION_SECRET` | Nøkkel for signerte sesjonscookies. |
| `HOSTED_INVITE_SECRET` | Signerer invite-lenken. Roter for å ugyldiggjøre utdelte lenker. |
| `HOSTED_CORS_ORIGINS` | Tillatte frontend-origins (default `http://localhost:5173`). |
| `HOSTED_PUBLIC_URL` | App-origin (invite-lenker + ID-porten-callbacken redirecter hit). Default `http://localhost:5173`. |
| `HOSTED_KONTAKT` | (valgfri) Kontaktvei som vises når ID-porten-rollesjekken ikke gir treff (skjermet person o.l.). `mailto:`- eller https-URL (default `mailto:hello@olefredrik.com`). |
| `HOSTED_IDPORTEN_CLIENT_ID` | (valgfri) ID-porten OIDC-klient-ID. Settes alle fire `HOSTED_IDPORTEN_*` skrus ID-porten-innlogging på; utelates de, er invite eneste port. |
| `HOSTED_IDPORTEN_KID` | (valgfri) Nøkkel-ID for ID-porten-klientens registrerte offentlige nøkkel. |
| `HOSTED_IDPORTEN_KEY_PEM` | (valgfri) PEM-innhold for ID-porten-klientens private nøkkel (egen, *ikke* vendor-nøkkelen). Foretrukket i prod (Fly-secret). |
| `HOSTED_IDPORTEN_KEY_PATH` | (valgfri) Sti til ID-porten-privatnøkkelen (PEM). Brukes i dev; `_PEM` har forrang. |
| `HOSTED_IDPORTEN_REDIRECT_URI` | (valgfri) Callback-URL registrert på klienten (HTTPS i prod, `http://127.0.0.1:5173/...` i dev). |
| `HOSTED_IDPORTEN_REPORTEES` | (valgfri, `1`/`true`) Be om `altinn:accessmanagement/authorizedparties` og hent selskapslista fra Altinn autoriserte parter. Krever at scopet er tildelt klienten (se under). Av som standard: da logger man inn med kun `openid profile` og taster orgnr manuelt. Skru ALDRI på før scopet faktisk er tildelt, ellers avviser ID-porten innloggingen (`invalid_scope`). |
| `HOSTED_VENDOR_ORGNR` | Operatørens organisasjonsnummer (vendor). |
| `HOSTED_VENDOR_CLIENT_ID` | Operatørens Maskinporten-klient-ID. |
| `HOSTED_VENDOR_KID` | Operatørens nøkkel-ID (KID). |
| `HOSTED_VENDOR_KEY_PATH` | Sti til operatørens private RSA-nøkkel (PEM). Brukes i dev. |
| `HOSTED_VENDOR_KEY_PEM` | Selve PEM-innholdet til nøkkelen. Foretrukket i prod/container (holder nøkkelen unna disk); settes som Fly-secret. Har forrang over `_PATH`. |
| `HOSTED_UMAMI_SRC` | (valgfri) URL til Umami-script. Injiseres i `index.html` ved servering. Tom = ingen analytics. (Self-host i EØS for region-garanti; cloud.umami.is sin region er ikke bekreftet.) |
| `HOSTED_UMAMI_WEBSITE_ID` | (valgfri) Umami website-id. Sammen med `_SRC` skrur det på anonymisert sporing (auto-track av; SPA-en sporer manuelt etter at invite-tokenet er fjernet fra URL-en). |

## ID-porten-innlogging (oppsett)

ID-porten er primær onboarding-port i prod. Vil du kjøre din egen hostede Wenche med
ID-porten-innlogging, gjør dette én gang per miljø (test og prod hver for seg):

1. **Opprett en ID-porten-klient** i [Digdir Selvbetjening](https://docs.digdir.no) (tjeneste
   «ID-porten & API-Klient»):
   - Applikasjonstype **web**, autentiseringsmetode **private_key_jwt**.
   - Grant **authorization_code** (ikke refresh), PKCE **S256**.
   - Eksterne scope **Nei** (`openid` + `profile` holder; fødselsnummer kommer som `pid`-claim).
   - **Redirect URI** = `https://<din-app>/api/auth/idporten/callback` (prod, HTTPS) eller
     `http://127.0.0.1:5173/api/auth/idporten/callback` (dev; loopback-IP, ikke `localhost`).
2. **Generer et eget RSA-nøkkelpar** (ikke gjenbruk vendor/Maskinporten-nøkkelen) og registrer
   den **offentlige** nøkkelen på klienten (lim inn PEM under «Nøkler»):
   ```sh
   openssl genrsa -out idporten_prod_privat.pem 2048
   openssl rsa -in idporten_prod_privat.pem -pubout -out idporten_prod_offentlig.pem
   ```
   Noter `kid`-en Digdir tildeler nøkkelen.
3. **Sett miljøvariablene** (`HOSTED_IDPORTEN_CLIENT_ID/_KID/_KEY_PEM/_REDIRECT_URI`). Settes
   alle fire, slås ID-porten på; utelates de (som på demo), kjører appen invite-only. Delvis
   config i prod gir fail-closed ved oppstart (alt eller intet).

Endepunkter og JWKS hentes fra ID-portens well-known-dokument ved kjøretid
(`test.idporten.no` / `idporten.no` etter `WENCHE_ENV`), så ingen URL-er hardkodes.

### Selskapsvalg fra Altinn (valgfritt, `altinn:accessmanagement/authorizedparties`)

Med kun `openid profile` taster brukeren inn organisasjonsnummeret selv, og det bekreftes mot
det åpne Enhetsregisteret (verifisert navn mot daglig leder/styreleder). Vil du i stedet vise en
liste over selskapene brukeren kan representere, hentet fra **Altinn autoriserte parter**, kreves
scopet **`altinn:accessmanagement/authorizedparties`** (Altinn III; det gamle `altinn:reportees`
er Altinn II og forsvinner når Altinn II skrus av):

1. Be Altinn/Digdir tildele org-en din tilgang til `altinn:accessmanagement/authorizedparties`
   (servicedesk@digdir.no), og legg deretter scopet på ID-porten-klienten i Samarbeidsportalen.
   Scopet eies av Altinn, så det dukker ikke opp i scope-velgeren før det er tildelt.
2. Sett `HOSTED_IDPORTEN_REPORTEES=1`.

Da veksles ID-porten-tokenet mot et Altinn-token (`exchange/id-porten`) og selskapslista hentes fra
`accessmanagement/api/v1/authorizedparties`. Er scopet ikke tildelt, MÅ flagget være av, ellers
avviser ID-porten hele innloggingen.

### Kjøre lokalt mot prod (røyktest uten deploy)

For å teste ID-porten-innloggingen mot ekte BankID og din egen org uten å deploye, kjør den hostede
appen lokalt med prod-miljø og prod-creds. ID-porten-login + manuell orgnr-inntasting (brreg-match)
kan testes slik; selskapslista krever at `altinn:accessmanagement/authorizedparties` er tildelt prod-klienten.

Forutsetning: prod-ID-porten-klienten må ha `http://127.0.0.1:5173/api/auth/idporten/callback`
registrert som redirect-URI (sjekk at prod-klienten godtar loopback-IP).

```sh
# Backend mot prod (egne prod-verdier; les fra ~/.wenche eller en prod-env-fil, aldri hardkod):
WENCHE_ENV=prod \
HOSTED_PUBLIC_URL=http://127.0.0.1:5173 \
HOSTED_SESSION_SECRET=$(openssl rand -hex 32) \
HOSTED_INVITE_SECRET=$(openssl rand -hex 32) \
HOSTED_VENDOR_ORGNR=<operatørens orgnr> \
HOSTED_VENDOR_CLIENT_ID=<maskinporten-klient-id, prod> \
HOSTED_VENDOR_KID=<kid, prod> \
HOSTED_VENDOR_KEY_PATH=<sti til prod-vendor.pem> \
HOSTED_IDPORTEN_CLIENT_ID=<id-porten-klient-id, prod> \
HOSTED_IDPORTEN_KID=<id-porten kid, prod> \
HOSTED_IDPORTEN_KEY_PATH=<sti til idporten_prod_privat.pem> \
HOSTED_IDPORTEN_REDIRECT_URI=http://127.0.0.1:5173/api/auth/idporten/callback \
  ./.venv/bin/python -m uvicorn hosted.api.main:app --host 127.0.0.1 --port 8077

# Frontend (egen terminal): cd hosted/web && npm run dev  -> åpne http://127.0.0.1:5173
```

Dette treffer ekte myndigheter (Altinn/Maskinporten prod). En systembruker-forespørsel i denne
flyten er en reell handling mot Altinn, men ingenting sendes inn før du fullfører innsendingsstegene.

## Deploy (Fly.io)

Tjenesten kjøres som **én alltid-på container** på Fly.io i EØS-region (in-memory-sesjonen
krever én prosess). `Dockerfile` og `fly.toml` ligger i repo-roten. Engangsoppsett:

1. **Installer flyctl og logg inn:**
   ```sh
   curl -L https://fly.io/install.sh | sh
   flyctl auth signup     # eller: flyctl auth login
   ```
2. **Opprett appen** (fra repo-roten). Velg appnavn + region (arn/Stockholm eller ams),
   ikke deploy ennå:
   ```sh
   flyctl launch --no-deploy --copy-config --name <ditt-appnavn> --region arn
   ```
   Oppdater `app = "..."` i `fly.toml` til navnet du valgte.
3. **Sett prod-hemmeligheter** (aldri i repoet):
   ```sh
   flyctl secrets set \
     HOSTED_SESSION_SECRET="$(openssl rand -hex 32)" \
     HOSTED_INVITE_SECRET="$(openssl rand -hex 32)" \
     HOSTED_VENDOR_ORGNR="<operatørens orgnr>" \
     HOSTED_VENDOR_CLIENT_ID="<maskinporten-klient-id, prod>" \
     HOSTED_VENDOR_KID="<kid, prod>" \
     HOSTED_VENDOR_KEY_PEM="$(cat operatør_prod.pem)" \
     HOSTED_IDPORTEN_CLIENT_ID="<id-porten-klient-id, prod>" \
     HOSTED_IDPORTEN_KID="<id-porten kid, prod>" \
     HOSTED_IDPORTEN_KEY_PEM="$(cat idporten_prod_privat.pem)" \
     HOSTED_IDPORTEN_REDIRECT_URI="https://<din-app>/api/auth/idporten/callback"
   ```
   Sett også `HOSTED_PUBLIC_URL` (app-URL-en, til invite-lenker og ID-porten-callbacken), enten
   som secret eller i `fly.toml` `[env]`. Uten egne secrets nekter appen å starte i prod
   (fail-closed); delvis ID-porten-config gjør det samme. Vil du kjøre prod invite-only, utelat
   alle `HOSTED_IDPORTEN_*`.

   > **NB om anførselstegn:** skriv inn de rene verdiene. Henter du `client_id`/`kid` fra en
   > `.env`-fil med shell, pass på at omsluttende `'`/`"` ikke blir med (de stripper ikke seg
   > selv slik python-dotenv gjør) — stray anførselstegn i `HOSTED_VENDOR_CLIENT_ID`/`_KID`
   > gir `MP-100 «Invalid assertion»` fra Maskinporten.
4. **Første deploy:** `flyctl deploy`. Test på `https://<appnavn>.fly.dev` (helsesjekk: `/api/health`).

### Deploy fremover
Foreløpig deployer vi **manuelt**: `flyctl deploy --remote-only` fra repo-roten. Det er
bevisst, så merge til `main` ikke auto-deployer.

`.github/workflows/deploy-hosted.yml` finnes og kan kjøres **manuelt** (Actions →
«Deploy hosted» → Run workflow / `workflow_dispatch`). For at den skal virke:
- Lag en deploy-token: `flyctl tokens create deploy`, og legg den som **repo-secret**
  `FLY_API_TOKEN` (Settings → Secrets and variables → Actions).
- Opprett et **`production`-environment** (Settings → Environments).

Vil du senere ha auto-deploy ved merge til `main`, legg tilbake en `push:`-trigger i
workflowen (fork-PR-er får uansett hverken secret eller deploy).

## Invitasjoner (prod)

Per-org invite-lenker myntes med:
```sh
hosted/invite.sh <orgnr>
```
Scriptet velger metode automatisk: **lokalt** hvis `~/.wenche/hosted-prod.env` finnes (med
`HOSTED_INVITE_SECRET` + `HOSTED_PUBLIC_URL`), ellers via **`flyctl ssh`** på Fly-maskinen
(krever `flyctl ssh issue --agent` én gang), slik at secret-en kan bli værende kun på
serveren. Del lenken via en privat kanal, den er knyttet til ett organisasjonsnummer.
Roter `HOSTED_INVITE_SECRET` for å ugyldiggjøre alle utdelte lenker på én gang.

## Demo-miljø (demo.wenche.cloud, mot tt02)

En **helt separat** Fly-app som lar hvem som helst prøve tjenesten mot Altinns testmiljø (tt02)
uten invitasjon, på syntetiske data. Den deler aldri prod-creds eller `env=prod`: egen app, egne
**test**-vendor-creds, `WENCHE_ENV=test`. ID-porten holdes **av** på demo (ingen
`HOSTED_IDPORTEN_*`), så demo kjører på invite-flyten uten BankID-dansen med syntetiske brukere.
Konfig ligger i `fly.demo.toml`. Banneren i SPA-en
styres av `HOSTED_DEMO_MODE=1` (rent informativt, endrer ikke funksjonalitet).

Engangsoppsett:

1. **Opprett appen:** `flyctl apps create wenche-demo`.
2. **Sett test-hemmeligheter** (de samme test-vendor-creds `dev_local.py` bruker mot tt02):
   ```sh
   flyctl secrets set -a wenche-demo \
     HOSTED_SESSION_SECRET="$(openssl rand -hex 32)" \
     HOSTED_INVITE_SECRET="$(openssl rand -hex 32)" \
     HOSTED_VENDOR_ORGNR="<test-orgnr>" \
     HOSTED_VENDOR_CLIENT_ID="<maskinporten-klient-id, test>" \
     HOSTED_VENDOR_KID="<kid, test>" \
     HOSTED_VENDOR_KEY_PEM="$(cat maskinporten_privat.pem)"
   ```
3. **Deploy:** `flyctl deploy -c fly.demo.toml --ha=false`. `--ha=false` hindrer at Fly lager to
   maskiner — appen MÅ kjøre på **én** maskin (in-memory-sesjon kan ikke spres mellom maskiner,
   samme grunn som prod). Lagde du to: `flyctl scale count 1 -a wenche-demo`.
4. **Domene:** `flyctl certs add demo.wenche.cloud -a wenche-demo`, legg deretter til DNS-postene
   Fly oppgir hos domene.shop. Vent til `flyctl certs show demo.wenche.cloud -a wenche-demo` er grønt.
5. **Forhåndsgodkjenn systembruker** for et syntetisk Tenor-demo-org (engang): åpne demo-appen via
   en demo-invite (steg 6), klikk «Koble systembruker», godkjenn i tt02-Altinn. Etterpå får alle
   demo-besøkende `AlreadyApproved` uten BankID.
6. **Offentlig demo-lenke:** mynt en invite-lenke for demo-org-et mot demo-appen (secret/URL
   hentes fra demo-appens eget miljø via ssh, så lenken peker på demo.wenche.cloud):
   ```sh
   WENCHE_HOSTED_APP=wenche-demo WENCHE_HOSTED_HEALTH=https://demo.wenche.cloud/api/health \
     hosted/invite.sh <demo-orgnr>
   ```
   Legg den bak «Demo»-knappen på wenche-web. Roter `HOSTED_INVITE_SECRET` på demo-appen for å
   ugyldiggjøre lenken. (Uten `WENCHE_HOSTED_APP`-overstyringen mynter scriptet for **prod**.)
