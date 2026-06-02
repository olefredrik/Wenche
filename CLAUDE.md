# CLAUDE.md, Wenche

Kontekst for å jobbe i koden. Brukerrettet «hva er Wenche / kom i gang» ligger i
[README.md](README.md) og [docs/](docs/); denne fila utfyller med arkitektur, konvensjoner
og rekkverk for bidragsytere og agenter.

Wenche er et innsendingsverktøy for **passive holdingselskaper og småaksjeselskaper**: det
bygger og sender årsregnskap, skattemelding/næringsspesifikasjon og aksjonærregisteroppgave
til norske myndigheter (Altinn, Skatteetaten, Brønnøysund). Autentisering via Maskinporten
med et selvgenerert RSA-nøkkelpar, ingen virksomhetssertifikat eller BankID.

## Arkitektur

Repoet inneholder tre ting som henger sammen via et npm-workspace + en Python-pakke:

- **`wenche/`** — Python-kjernen og CLI-en (`wenche` → `wenche.cli:main`). Bygger XBRL/XML
  for hvert skjema (`*_xml.py`, `xbrl.py`, `brg_xml.py`), autentiserer (`auth.py`,
  `systembruker.py`) og sender inn (`altinn_client.py`, `skd_client.py`, `innsending.py`).
  Forretningslogikken bor her; alt annet er presentasjon.
- **`wenche/web/frontend`** — self-hosted SPA (React + Tailwind). Bygges til
  `wenche/web/static` og force-includes i wheelen, så `pip install wenche` får et ferdig
  webgrensesnitt. `wenche`-kommandoen starter en lokal server som serverer denne.
- **`hosted/`** — den hostede tjenesten: FastAPI-backend (`hosted/api/`) + egen SPA
  (`hosted/web`). Pakkes som Docker-image (multi-stage, se [Dockerfile](Dockerfile)) og
  kjøres på Fly. Session-only (in-memory), **én worker** med vilje. Brukeren kobler til via
  invite-token; operatøren har satt opp Maskinporten på forhånd.
- **`packages/ui`** — delt designsystem (React + Tailwind, OKLCH-palett, se
  `packages/ui/src/theme.css`). Konsumeres som *kildekode* av begge SPA-ene via alias, ikke
  som bygd pakke.

## Miljøsegregering (kritisk)

`WENCHE_ENV` styrer hvilket myndighetsmiljø som treffes:
- `test` → Skatteetatens testmiljø **tt02**. Ingenting når ekte myndigheter.
- `prod` → ekte innsending.

Demo- og prod-utgavene av den hostede tjenesten er **separate Fly-apper med separate
vendor-creds**, slik at en demo aldri kan røre prod. Bland aldri test- og prod-config.
Hemmeligheter settes som Fly-secrets, **aldri** i repoet (`*.pem`, `config.yaml` er
gitignored).

## Scope-rekkverk

Wenche støtter **bare passive holdingselskaper** (uten ansatte/drift). Det er et bevisst,
avgrenset scope, ikke en mangel. Driftsselskap er utenfor scope og ikke planlagt
(issue #82 lukket som not planned). Wenche er et innsendingsverktøy, **ikke en
regnskapsfører**: den forutsetter at tallene finnes. For å føre regnskapet finnes
søsterprosjektet [Bodil](https://github.com/olefredrik/Bodil), som produserer en
`config.yaml` Wenche leser direkte.

## Konvensjoner

- **Commit-meldinger og PR-titler**: Conventional Commits (`feat:`, `fix:`, `docs:`, …).
- **Brukerrettet tekst er norsk (bokmål).** Aldri em-dash (—) eller en-dash (–); bruk komma,
  parentes, punktum eller vanlig bindestrek.
- **«Jeg», ikke «Vi»** i Wenches utadrettede stemme (solo-prosjekt).
- Følg stilen i koden rundt deg (kommentartetthet, navngivning, idiom).

## Utvikling og test

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
pytest                                  # testsuite
npm ci                                  # workspace for SPA-ene
npm run build --workspace hosted/web    # hostet SPA
npm run build --workspace wenche/web/frontend   # self-hosted SPA
```

Dokumentasjon bygges med mkdocs (`mkdocs.yml`, `docs/`).
