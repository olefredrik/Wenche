# Wenche hosted

Separat, hostet multi-tenant-variant av Wenche. Importerer `wenche`-pakken som bibliotek og
gjenbruker domene-, auth- og klientlaget. Self-hosted-appen (`wenche` / `wenche dev`, `wenche.web`)
er **upåvirket** av alt her, og denne mappen er ikke en del av `wenche`-wheelen som publiseres
til PyPI.

Status: **live på https://app.wenche.cloud** (invite-only). Onboarding: en **per-org
invite-lenke** som invite-only-port, og Altinn systembruker-godkjenning (BankID) som selve
autorisasjonen. Ingen e-post, passord eller database.

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
| `HOSTED_PUBLIC_URL` | App-origin som invite-lenken peker på (default `http://localhost:5173`). |
| `HOSTED_VENDOR_ORGNR` | Operatørens organisasjonsnummer (vendor). |
| `HOSTED_VENDOR_CLIENT_ID` | Operatørens Maskinporten-klient-ID. |
| `HOSTED_VENDOR_KID` | Operatørens nøkkel-ID (KID). |
| `HOSTED_VENDOR_KEY_PATH` | Sti til operatørens private RSA-nøkkel (PEM). Brukes i dev. |
| `HOSTED_VENDOR_KEY_PEM` | Selve PEM-innholdet til nøkkelen. Foretrukket i prod/container (holder nøkkelen unna disk); settes som Fly-secret. Har forrang over `_PATH`. |
| `HOSTED_UMAMI_SRC` | (valgfri) URL til Umami-script. Injiseres i `index.html` ved servering. Tom = ingen analytics. (Self-host i EØS for region-garanti; cloud.umami.is sin region er ikke bekreftet.) |
| `HOSTED_UMAMI_WEBSITE_ID` | (valgfri) Umami website-id. Sammen med `_SRC` skrur det på anonymisert sporing (auto-track av; SPA-en sporer manuelt etter at invite-tokenet er fjernet fra URL-en). |

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
     HOSTED_VENDOR_KEY_PEM="$(cat operatør_prod.pem)"
   ```
   Sett også `HOSTED_PUBLIC_URL` (app-URL-en, til invite-lenkene), enten som secret eller i
   `fly.toml` `[env]`. Uten egne secrets nekter appen å starte i prod (fail-closed).

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
**test**-vendor-creds, `WENCHE_ENV=test`. Konfig ligger i `fly.demo.toml`. Banneren i SPA-en
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
