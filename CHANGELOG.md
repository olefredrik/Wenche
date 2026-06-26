# Endringslogg

Alle vesentlige endringer i Wenche dokumenteres her. Formatet bygger på
[Keep a Changelog](https://keepachangelog.com/no/), og prosjektet følger
[semantisk versjonering](https://semver.org/lang/no/).

## [1.0.0] - 2026-06-26

Første stabile utgave. Wenche har sendt inn årsregnskap, skattemelding og
aksjonærregisteroppgave i produksjon for flere selskaper, og kjernen ansees stabil.
Tidligere 0.x-utgaver finnes i git-historikken og under [releases](https://github.com/olefredrik/Wenche/releases).

### Støttet

- **Aksjonærregisteroppgave** (RF-1086) til Skatteetaten.
- **Skattemelding for AS** med næringsspesifikasjon, for inntektsår 2025 og senere.
- **Årsregnskap** til Brønnøysundregistrene.
- Maskinporten-autentisering med selvgenerert RSA-nøkkelpar, uten virksomhetssertifikat.
- Self-hosted webgrensesnitt (kommandoen `wenche`) og en hostet variant på wenche.cloud.
- Forhåndsfyll av tall fra [Bodil](https://github.com/olefredrik/Bodil) eller via SAF-T-import.

### Målgruppe

Enkle aksjeselskaper uten ordinær drift: passive holdingselskaper og hvilende
småaksjeselskaper, det vil si selskaper uten ansatte, varelager, konsernregnskapsplikt
eller revisorkrav. Wenche er et innsendingsverktøy, ikke en regnskapsfører, og forutsetter
at tallene finnes fra før.
