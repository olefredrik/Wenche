# Wenche hosted (MVP)

Separat, hostet multi-tenant-variant av Wenche. Importerer `wenche`-pakken som bibliotek og
gjenbruker domene-, auth- og klientlaget. Self-hosted NiceGUI-appen (`wenche` / `wenche dev`)
er **upåvirket** av alt her, og denne mappen er ikke en del av `wenche`-wheelen som publiseres
til PyPI.

Status: bygges fasevis (se `docs/hosted/mvp-plan.md`). Fase 2 = backend-skjelett.

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
Åpne http://localhost:5173, logg inn med allowlist-eposten (`test@example.no`), koble
systembruker for en godkjent test-org, lim inn data og kjør dry-run/innsending.

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
| `HOSTED_ALLOWLIST` | Komma-separert liste over inviterte e-poster. |
| `HOSTED_CORS_ORIGINS` | Tillatte frontend-origins (default `http://localhost:5173`). |
| `HOSTED_VENDOR_CLIENT_ID` | Operatørens Maskinporten-klient-ID. |
| `HOSTED_VENDOR_KID` | Operatørens nøkkel-ID (KID). |
| `HOSTED_VENDOR_KEY_PATH` | Sti til operatørens private RSA-nøkkel (PEM). I prod: hent fra KMS. |
