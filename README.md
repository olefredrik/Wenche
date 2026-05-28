# Wenche

![PyPI](https://img.shields.io/pypi/v/wenche)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)
![Tester](https://github.com/olefredrik/Wenche/actions/workflows/test.yml/badge.svg)
[![Dokumentasjon](https://img.shields.io/badge/docs-olefredrik.github.io%2FWenche-blue)](https://olefredrik.github.io/Wenche/)

Wenche er et verktøy for holdingselskaper og småaksjeselskaper som må levere regnskap og skattedokumenter til norske myndigheter, uten behov for et fullverdig regnskapsprogram.

Kjør `wenche` for å åpne et grafisk webgrensesnitt i nettleseren der du fyller ut og sender inn alt.

Autentisering skjer via Maskinporten med et selvgenerert RSA-nøkkelpar, ingen virksomhetssertifikat eller BankID-innlogging nødvendig.

## Hva er støttet?

| Hva | Til hvem | Frist | Status |
|---|---|---|---|
| **Aksjonærregisteroppgave** (RF-1086) | Skatteetaten | 31. januar | Automatisk innsending |
| **Skattemelding for AS** (skattemelding + næringsspesifikasjon) | Skatteetaten | 31. mai | Automatisk innsending |
| **Årsregnskap** | Brønnøysundregistrene | 31. juli | Automatisk innsending |

## Kom i gang

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
