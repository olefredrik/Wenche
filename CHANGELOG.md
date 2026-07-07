# Endringslogg

Alle vesentlige endringer i Wenche dokumenteres her. Formatet bygger på
[Keep a Changelog](https://keepachangelog.com/no/), og prosjektet følger
[semantisk versjonering](https://semver.org/lang/no/).

## [1.0.3] - 2026-07-07

### Rettet

- Systembruker-tilkoblingen svarer nå med en lesbar melding hvis Altinn avviser med AUTH-00004
  («existing SystemUser tied to the given System-Id»), i stedet for en rå «HTTP 500». Selve
  årsaken til at feilen oppsto ble fjernet i 1.0.2 (paginering); dette er et ekstra sikkerhetsnett
  slik at en tilsvarende Altinn-avvisning fra en annen årsak gir brukeren en forståelig beskjed.

## [1.0.2] - 2026-07-07

### Rettet

- `hent_systembrukere` følger nå pagineringen fra Altinn (`links.next`) og henter alle
  sidene. Tidligere ble bare de første 50 systembrukerne hentet, så kunde nr. 51 og utover
  ble usynlig for gjenkjennings-sjekken ved ny tilkobling. Resultatet var at en kunde som
  allerede hadde godkjent Wenche med BankID fikk «HTTP 500» (AUTH-00004 fra Altinn) i stedet
  for å bli koblet til. Rammet både den hostede tjenesten og self-hosted-oppsettet.

## [1.0.1] - 2026-07-01

### Endret

- Den hostede tjenesten dvaler nå med `suspend` i stedet for `stop`. En maskin som har
  sovet våkner da på under et sekund i stedet for rundt to sekunders kaldstart, så en
  bruker som tar seg tid til å fylle ut skjemaet ikke merker pausen. Kostnadsprofilen er
  praktisk talt uendret.

### Fjernet

- Fjernet en keep-alive-heartbeat i den hostede webappen. Den kunne uansett ikke hindre
  Fly i å dvale og ga ingen reell effekt.

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
