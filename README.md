# Wenche

![PyPI](https://img.shields.io/pypi/v/wenche)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)
![Tester](https://github.com/olefredrik/Wenche/actions/workflows/test.yml/badge.svg)
[![Dokumentasjon](https://img.shields.io/badge/docs-olefredrik.github.io%2FWenche-blue)](https://olefredrik.github.io/Wenche/)

Wenche er et verktøy for holdingselskaper og småaksjeselskaper som må levere regnskap og skattedokumenter til norske myndigheter, uten behov for et fullverdig regnskapsprogram.

Etter installasjon kjører du `wenche` for å åpne et grafisk webgrensesnitt i nettleseren der du fyller ut og sender inn alt.

Autentisering skjer via Maskinporten med et selvgenerert RSA-nøkkelpar, ingen virksomhetssertifikat eller BankID-innlogging nødvendig.

## Hva er støttet?

| Hva | Til hvem | Frist | Status |
|---|---|---|---|
| **Aksjonærregisteroppgave** (RF-1086) | Skatteetaten | 31. januar | Automatisk innsending |
| **Skattemelding for AS** (skattemelding + næringsspesifikasjon) | Skatteetaten | 31. mai | Automatisk innsending |
| **Årsregnskap** | Brønnøysundregistrene | 31. juli | Automatisk innsending |

## Trenger du å føre regnskapet først?

Wenche sender inn, men forutsetter at du allerede har tallene. For
**passive holdingselskaper** finnes søsterprosjektet
[Bodil](https://github.com/olefredrik/Bodil): et template-repo drevet av
Claude Code som gjør en bankeksport om til et lesbart regnskap, en
generalforsamlingsprotokoll og en ferdig `config.yaml` som Wenche leser
direkte. Trykk «Use this template» på repoet for å opprette ditt eget repo
med verktøyet i, og velg **Private** så regnskapstallene blir hos deg.

## Kom i gang

Wenche krever Python 3.11 eller nyere. Installer i et virtuelt miljø (macOS/Linux):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install wenche
```

> På Windows er kommandoene litt annerledes. Se [installasjonsveiledningen](https://olefredrik.github.io/Wenche/installasjon/) for fullstendig oppsett på macOS, Linux og Windows.

Start deretter webgrensesnittet:

```bash
wenche
```

Wenche åpner `http://localhost:8080` i nettleseren, der du fyller ut oppsett og sender inn.

Før første innsending må du generere et RSA-nøkkelpar og registrere en Maskinporten-klient. Hele veiledningen for installasjon, oppsett og bruk finner du i dokumentasjonen.

## Hostet variant (invite-only)

I tillegg til å kjøre Wenche selv, finnes en hostet, invite-only versjon på
**[wenche.cloud](https://wenche.cloud)**. Der er Maskinporten-/Altinn-oppsettet gjort én
gang av operatøren, så du slipper å generere egne nøkler: du åpner en invitasjonslenke,
godkjenner Wenche i Altinn med BankID, fyller inn tallene og sender. Dataene behandles kun
i økten og lagres ikke. Tjenesten er foreløpig kun for inviterte testere, og bygger på
nøyaktig samme åpne kildekode som denne self-hosted-versjonen.

Drifts- og deploy-dokumentasjon for operatøren: [`hosted/README.md`](hosted/README.md).

## Dokumentasjon

Fullstendig veiledning for installasjon, oppsett og bruk:

**[Les dokumentasjonen →](https://olefredrik.github.io/Wenche/)**

## For utviklere

Wenche kan kjøres mot Skatteetatens testmiljø (tt02) for å tørrtrene innsending uten å sende ekte data til myndighetene:

```bash
wenche dev
```

Krever egne credentials og syntetiske Tenor-orgnumre. Se [Testing mot tt02](https://olefredrik.github.io/Wenche/avansert/testing/) og [Kommandolinje](https://olefredrik.github.io/Wenche/avansert/cli/) i dokumentasjonen for fullstendig oppsett.

## Ansvar

Wenche er et hjelpeverktøy for enkle holdingselskaper og er i aktiv utvikling. Det er ikke en erstatning for profesjonell regnskapsbistand. Kontroller alltid at genererte dokumenter er korrekte før innsending. Du er selv ansvarlig for at innsendte opplysninger er riktige.

## Bidra

Bidrag er velkomne. Åpne gjerne en issue eller pull request.

## Lisens

MIT, se [LICENSE](LICENSE).

---

### Bonus: en helt unødvendig folkevise

En stillferdig, bittersøt og oppriktig kjærlighetsvise om skattemelding, aksjonærregister og maskinell innsending til Altinn.

🎧 Hør "Wenche": https://suno.com/s/QSz9P1EylWOF7vnz
