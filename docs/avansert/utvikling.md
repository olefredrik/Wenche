# Utvikling

Denne siden er for deg som vil bidra til Wenche eller forstå hvordan koden henger sammen.

## Slik er koden bygd opp

Wenche har ett delt domenelag i Python og to grensesnitt oppå det: en self-hosted versjon (som følger med på PyPI) og en hostet versjon (på app.wenche.cloud). Begge bruker samme front-end-stack: FastAPI som API, og React + Vite + Tailwind 4 som SPA.

```
wenche/                 Python-kjerne (domene, auth, Altinn-/SKD-klienter, CLI)
  innsending.py         Delt innsendings-orkestrering (brukt av hostet + self-hosted)
  web/
    backend/            Self-hosted FastAPI-app (lag_app / kjor)
    frontend/           Self-hosted SPA (React)
    static/             Ferdigbygd SPA (genereres, ikke i git)
packages/ui/            Delt designsystem og komponenter (@wenche/ui)
hosted/
  api/                  Hostet FastAPI-app (invite + systembruker + vendor)
  web/                  Hostet SPA
```

Domenelaget i `wenche/` vet ingenting om grensesnittet. Det leser en config (fra fil eller dict), bygger XML og snakker med Altinn og Skatteetaten. Begge SPA-ene sender den samme config-strukturen som `config.yaml` til hvert sitt API.

Frontend-koden er en npm-workspace (`package.json` i repo-roten). Det delte designsystemet i `packages/ui` (skjema, send-flyt, dokument-nedlasting, noter, stegvis navigasjon, knapper, farger) konsumeres som kildekode av begge appene via et Vite-alias, så det finnes ingen separat byggesteg for pakken.

## Kjøre lokalt

Du trenger Python 3.11+ og Node 20+. Installer Wenche i et virtuelt miljø (`pip install -e .`) og front-end-avhengighetene med `npm install` fra repo-roten.

**Vanlig kjøring (mot testmiljøet tt02):**

```bash
wenche dev
```

Dette bygger ikke SPA-en. Har du ikke bygd den ennå, gjør det først:

```bash
npm run build --workspace wenche/web/frontend
```

**Med hot reload (når du jobber med UI-et):** kjør API og Vite hver for seg, så oppdateres grensesnittet umiddelbart når du endrer en fil.

```bash
# Terminal 1: API mot tt02 (auto-reloader ved Python-endringer)
python -m wenche.web.dev

# Terminal 2: SPA med hot reload
cd wenche/web/frontend && npm run dev
```

Åpne `http://localhost:5174`. Vite proxer `/api` til backenden, så alt er samme origin.

## Bygge og publisere

Den ferdigbygde SPA-en (`wenche/web/static`) pakkes inn i hjulet (wheel) fordi de fleste brukere installerer med `pip` og ikke har Node. `npm run build` for self-hosted-frontenden må derfor kjøres før `python -m build`. GitHub Actions (`publish.yml`) gjør dette automatisk når en versjons-tag pushes.

## Tester

```bash
pytest
```

Testene dekker domenelaget (validering, XML-generering, klientene). De krever ikke nettverk.

## Den hostede versjonen

Drifts- og deploy-dokumentasjon for operatøren (Docker, Fly.io, hemmeligheter, invitasjoner) ligger i [`hosted/README.md`](https://github.com/olefredrik/Wenche/blob/main/hosted/README.md) i kodebasen. Den hostede appen importerer `wenche`-pakken som bibliotek og gjenbruker domenelaget; self-hosted-versjonen er upåvirket av den.
