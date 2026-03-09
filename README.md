# Wenche

![PyPI](https://img.shields.io/pypi/v/wenche)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)
![Tester](https://github.com/olefredrik/Wenche/actions/workflows/test.yml/badge.svg)
[![Dokumentasjon](https://img.shields.io/badge/docs-olefredrik.github.io%2FWenche-blue)](https://olefredrik.github.io/Wenche/)

Wenche er et verktøy for holdingselskaper og småaksjeselskaper som må levere regnskap og skattedokumenter til norske myndigheter. Det kan brukes både fra kommandolinjen og via et grafisk webgrensesnitt — uten behov for et fullverdig regnskapsprogram.

Autentisering skjer via Maskinporten med et selvgenerert RSA-nøkkelpar — ingen virksomhetssertifikat eller BankID-innlogging nødvendig.

## Hva er støttet?

| Hva | Til hvem | Frist | Status |
|---|---|---|---|
| **Årsregnskap** | Brønnøysundregistrene | 31. juli | Automatisk innsending |
| **Aksjonærregisteroppgave** (RF-1086) | Skatteetaten via Altinn | 31. januar | Automatisk innsending |
| **Skattemelding for AS** (RF-1028 + RF-1167) | Skatteetaten | 31. mai | Genereres lokalt — sendes inn manuelt |

## Kom i gang

Fullstendig veiledning for installasjon, oppsett og bruk:

**[Les dokumentasjonen →](https://olefredrik.github.io/Wenche/)**

## Ansvarsfraskrivelse

Wenche er et hjelpeverktøy for enkle holdingselskaper og er i aktiv utvikling. Det er ikke en erstatning for profesjonell regnskapsbistand. Kontroller alltid at genererte dokumenter er korrekte før innsending — du er selv ansvarlig for at innsendte opplysninger er riktige.

## Bidra

Bidrag er velkomne. Åpne gjerne en issue eller pull request.

## Lisens

MIT — se [LICENSE](LICENSE).
