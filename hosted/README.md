# Wenche hosted (MVP)

Separat, hostet multi-tenant-variant av Wenche. Importerer `wenche`-pakken som bibliotek og
gjenbruker domene-, auth- og klientlaget. Self-hosted NiceGUI-appen (`wenche` / `wenche dev`)
er **upåvirket** av alt her, og denne mappen er ikke en del av `wenche`-wheelen som publiseres
til PyPI.

Status: backend + tynn SPA bygget og tt02-verifisert (se `docs/hosted/mvp-plan.md`).
Onboarding: **invite-lenke + BankID**, invite-lenke som invite-only-port, Altinn
systembruker-godkjenning (BankID) som selve innloggingen. Ingen e-post, passord eller database.

## Komponenter
- `api/` — FastAPI JSON-API (importerer `wenche`).
- `web/` — SPA (React + Vite + TypeScript + Tailwind 4). Tynn happy-path: innlogging →
  systembruker-onboarding → lim inn data → dry-run/innsending. Snakker med `api/` via
  Vite-proxy (`/api` → `127.0.0.1:8077`), så alt er same-origin i dev.

## Kjøre hele MVP-en lokalt (dev/test)
Enkleste vei, `dev_local.py` wirer test-credentials automatisk fra dine `.env`-filer:
```bash
# Terminal 1 (backend mot tt02):
./.venv/bin/python hosted/dev_local.py            # http://127.0.0.1:8077

# Terminal 2 (frontend):
cd hosted/web && npm install && npm run dev       # http://localhost:5173
```
`dev_local.py` skriver ut en **invite-lenke** ved oppstart. Åpne den (den setter økten som
invitert), koble systembruker for en godkjent test-org, lim inn data og kjør dry-run/innsending.
Lenken kan også lages med `./.venv/bin/python hosted/mint_invite.py`.

## Kjøre lokalt (dev)
```bash
pip install -r hosted/requirements.txt        # i samme venv som wenche
uvicorn hosted.api.main:app --reload --port 8000
# helse: http://localhost:8000/api/health
```

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
