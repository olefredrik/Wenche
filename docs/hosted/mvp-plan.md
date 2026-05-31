# Tynn hostet MVP, byggeplan (UTKAST)

> Gate 2-plan for en hostet, invite-only Wenche. **Separat hosted-app** (Option B): self-hosted
> `ui.py` (NiceGUI) røres ikke. Komponentnivå-bakgrunn ligger i beslutningsnotatet.

## Mål
Validere friksjonskuttet og den faktiske drifts-/supportbyrden med en minimal hostet tjeneste
for en lukket gruppe, uten å bygge mer enn nødvendig.

## Hard invariant
Self-hosted (`wenche` / `wenche dev`, NiceGUI) forblir **default og uendret**. Hosted er
additivt. Testsuiten skal være grønn etter hver fase, og self-hosted skal kunne kjøres lokalt
som før. I self-hosted er brukeren fortsatt sin egen vendor og kunde, og legger inn egne nøkler,
scopes og systembruker (uendret).

## Stack
- **Backend:** FastAPI JSON-API som importerer `wenche` (domene/auth/klienter) som bibliotek.
- **Frontend:** SPA (React + Vite + TypeScript, default) med **Tailwind 4**, egen byggekjede.
- **Plassering:** `hosted/` på `experiment/hostet-tjeneste` (samme repo, jf. repo-strategi).
- **Delt kjerne:** domenelaget + klientklassene er allerede UI-agnostiske og gjenbrukes uendret.
  Auth-kjernen parameteriseres (Fase 1) slik at både self-hosted (env) og hosted (server-creds +
  sesjons-org) bruker samme implementasjon.

## Scope

**Med i MVP:** lean magic-link-innlogging + invite-allowlist; per-sesjon ephemeral state (ingen
DB, ingenting på disk); én vendor-identitet (server-hemmeligheter/KMS) som handler på vegne av
innlogget kunde-org via systembruker; systembruker-onboarding i UI; de tre innsendingene
(gjenbruk); klient-side nedlasting av egen `config.yaml`; én FastAPI-prosess + TLS + EØS-host.

**Utenfor MVP:** betaling, full BankID/ID-porten, horisontal skalering, admin-dashboard, ren
delegert skattemelding ende-til-ende (testdata-restpunkt fra Gate 0).

## Byggefaser

**Fase 1, parameteriser auth-kjernen (delt `wenche`, eneste som berører eksisterende kode).**
Token-funksjonene i `auth.py` leser i dag env (`MASKINPORTEN_*`, `ORG_NUMMER`, nøkkelfil,
`WENCHE_ENV`). Refaktorer til en kjerne som tar **vendor-creds + kunde-org + scopes + env som
parametre**, og la dagens funksjoner bli **tynne env-wrappere** som bevarer self-hosted-oppførsel
1:1. Verifiser med `test_auth_env.py` + `test_token_cache.py` grønne. Ingen endring i `ui.py`.

**Fase 2, backend-skjelett.** FastAPI-app i `hosted/api`, importerer `wenche`. Server-side
ephemeral sesjon (signert cookie for identitet; data i minne), CORS/CSRF, helsesjekk. Vendor-creds
fra server-config/KMS, env pinnet til prod.

**Fase 3, innlogging.** Magic-link (e-post) + invite-allowlist. Bind sesjon → godkjent kunde-org.

**Fase 4, systembruker-onboarding.** Operatøren kjører `registrer_system` ÉN gang. Per kunde:
`opprett_forespørsel` + godkjenning (BankID i Altinn). Request-id i sesjon/per-kunde, ikke delte
`~/.wenche`-filer.

**Fase 5, SPA + innsending.** Tailwind 4-frontend (Selskap/Regnskap/Aksjonærer/Send, slankere enn
self-hosted), JSON-endepunkter som kaller domene/klienter via parameterisert auth. Ephemeral data,
klient-side `config.yaml`-nedlasting, SAF-T parses i minne.

**Fase 6, deploy tynt.** FastAPI (uvicorn) bak TLS (proxy/PaaS), EØS-region, nøkkel i KMS,
`storage_secret`, ingen DB.

## Gjenbruk
- Domenelaget + klientklassene (`AltinnClient`, `SkdAksjonaerClient`, `SkdSkattemeldingClient`),
  uendret, tar allerede token/env/orgnr som parametre.
- Parameterisert auth-kjerne (Fase 1) brukes av både self-hosted og hosted.

## Verifisering
- Etter hver fase: testsuiten grønn + `wenche dev` kjører lokalt som før (self-hosted-invariant).
- Hosted ende-til-ende: gjenskap Gate 0s to-org-bevis (310943223 + 314273818) gjennom hosted-
  appen, to innloggede sesjoner sender aksjonær uten kryssforurensning.

## Risiko
**Fase 1** er eneste fase som berører delt kode, sikres med backward-compatible env-wrappere +
grønne auth-tester. Resten er nytt og isolert i `hosted/`, så self-hosted kan ikke brekke.

---

## Live-verifisering (B), utført mot tt02

Før SPA-en (5b) ble hele den hostede backend-stien verifisert ende-til-ende mot tt02:
magic-link-innlogging → systembruker-onboarding → ephemeral data → **ekte aksjonær-innsending
gjennom det hostede API-et** for kunde-org `314273818` (≠ vendor). Resultat: HTTP 200 med
forsendelse-ID. Beviser at den parameteriserte auth-en + klientene faktisk sender inn via
FastAPI-laget, ikke bare i dry-run.

To funn underveis:
- **Forbedring (committet):** onboardingen oppdager nå eksisterende systembruker
  (`reporteeOrgNo`-treff) og binder kunde-org direkte, så gjenkommende kunder slipper ny
  BankID-godkjenning. Uten dette feilet Altinn med `AUTH-00004` for en allerede godkjent org.
- **Testmiljø-merknad (ikke prod):** `aksjonaerregister.send_inn` overstyrer i `env=test`
  XML-orgen med `SKD_TEST_ORG_NUMMER` (en self-hosted enkelt-kunde-konvensjon). Kjøres hosted
  i test, må denne settes lik kunde-orgen, ellers oppstår autorisasjonssprik. I prod
  (`env=prod`) skjer ingen slik overstyring.
