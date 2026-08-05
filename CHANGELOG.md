# Endringslogg

Alle vesentlige endringer i Wenche dokumenteres her. Formatet bygger på
[Keep a Changelog](https://keepachangelog.com/no/), og prosjektet følger
[semantisk versjonering](https://semver.org/lang/no/).

## [1.2.0] - 2026-08-05

### Rettet

- Årsregnskapet manglet **skattekostnad som egen linje** før årsresultatet, slik
  regnskapsloven § 6-1 krever. Modellen regnet resultat før skatt som årsresultat direkte,
  altså implisitt skattekostnad 0. Det gikk bra for et selskap uten skattepliktig inntekt,
  men et passivt holdingselskap med renteinntekt (eller 3 %-tillegget på fritatt utbytte) har
  en reell skattekostnad. Årsresultatet ble da rapportert for høyt til både Brønnøysund og
  Skatteetaten, og balansen hadde ingen riktig plass til skattegjelden.

- Næringsspesifikasjonen tilbakefører nå skattekostnaden som permanent forskjell
  (`positivSkattekostnad`). Skatteetaten utleder sitt eget skattemessige resultat fra
  årsresultatet pluss permanente forskjeller, så uten tilbakeføringen ville et selskap med
  skattekostnad fått «Ugyldig innsending» med avvik i næringsopplysningene. Verifisert mot
  Skatteetatens testmiljø.
- **Utbytte som er fritatt etter fritaksmetoden ble oppgitt som skattepliktig inntekt** i
  næringsspesifikasjonen. Skattegrunnlaget var dermed brutto utbytte, selv om bare
  3 %-sjablonen (eller ingenting, ved eierandel fra 90 %) faktisk er skattepliktig. Utbyttet
  tilbakeføres nå som permanent forskjell, og den skattepliktige delen legges til igjen, slik
  at skattegrunnlaget stemmer med skatteberegningen. Sammen med skattekostnad-linjen var dette
  en innsending som påsto et skattegrunnlag som ikke stemte med sin egen skattekostnad.
- Et selskap med regnskapsmessig overskudd men skattemessig underskudd (fritatt utbytte og
  fradragsberettigede kostnader) mistet underskuddet til fremføring, fordi underskuddet ble
  regnet av regnskapets resultat i stedet for det skattepliktige. Nå føres det riktig.
- Skattemessig resultat oppgis nå også når det er 0, så lenge det er poster i
  resultatregnskapet. Et holdingselskap med bare fritatt utbytte har legitimt 0 i
  skattepliktig inntekt, og Skatteetaten savnet påstanden. Helt hvilende selskap er uendret.

- **Regnskapsperioden var hardkodet til 1. januar til 31. desember.** Et selskap stiftet sent
  på året kan ha et forlenget første regnskapsår på inntil 18 måneder (regnskapsloven § 1-7
  andre ledd), og rapporterte da en periode som ikke var den faktiske, både til Brønnøysund og
  Skatteetaten. Tallene var riktige, men periodeangivelsen er en del av det signerte
  regnskapet. Perioden kan nå oppgis med `regnskapsstart` og `regnskapsslutt`; står de tomme,
  er den fortsatt hele kalenderåret. Skatteetaten godtar en periode over 12 måneder, verifisert
  mot testmiljøet.
- Aksjonærregisteroppgaven oppgav 1. januar som stiftelsesdato for alle selskap, fordi
  Enhetsregister-oppslaget kastet bort dag og måned. Den eksakte datoen brukes nå.

### Endret

- SAF-T-importen leser nå skattekostnaden (kontoserie 83xx) inn i den nye linjen. Den falt
  tidligere ut av importen, slik at balansen ikke gikk opp for et selskap med skattepliktig
  inntekt. Betalbar skatt (konto 2500 og 2510) havner nå på egen linje i balansen i stedet
  for i skyldige offentlige avgifter. Summen av kortsiktig gjeld er uendret.

### Lagt til

- Feltet `skattekostnad` under `resultatregnskap` og `betalbar_skatt` under
  `balanse.egenkapital_og_gjeld.kortsiktig_gjeld`. Begge er 0 som standard, så et regnskap
  uten skattepliktig inntekt gir nøyaktig samme innsending som før.
- Knappen «Foreslå skattekostnad» i Tall-steget regner ut 22 % av skattepliktig inntekt
  (etter fritaksmetoden og fremført underskudd) og viser den som forslag. Forslaget føres
  aldri automatisk: du fører selv tallet du signerer på.
- Sammendraget for skattemeldingen kontrollerer ført skattekostnad mot beregningen, og sier
  fra hvis skatten er beregnet men ikke ført, eller hvis de to spriker. Valideringen av
  årsregnskapet varsler også hvis en ført skattekostnad ikke har en motpost i balansen.

## [1.1.1] - 2026-07-29

### Sikkerhet

- Oppdatert `js-yaml` (4.2.0 til 4.3.0), som er bundlet i webgrensesnittet og leser
  `config.yaml` når du importerer fra Bodil. Den gamle versjonen kunne bruke svært lang tid på
  en fil med visse nøstede `<<`-referanser, slik at nettleserfanen ble hengende. Filen leses
  kun i nettleseren din, så en slik fil kunne ikke påvirke andre brukere eller den hostede
  tjenesten.
- Oppdatert `postcss` (8.5.15 til 8.5.24), som kun brukes når prosjektet bygges, ikke av
  ferdig installert Wenche.

### Lagt til

- Sikkerhetspolicy (`SECURITY.md`) som beskriver hvordan sårbarheter rapporteres privat, hva
  som er i og utenfor scope, og hvilke regler som gjelder for testing. README lenker til den.

### Rettet

- Lenkene til `LICENSE` og `hosted/README.md` i README var relative, og virket derfor bare på
  GitHub. På PyPI ga de 404. Nå er de absolutte.

## [1.1.0] - 2026-07-15

### Rettet

- Tallfeltene i skjemaet starter nå blanke i stedet for å være forhåndsutfylt med `0`, og du
  kan tømme et felt helt uten at nullen spretter tilbake. Lagrede verdier (også et bevisst `0`)
  vises som før. Ved innsending fylles blanke påkrevde felt til `0`, så payloaden til
  myndighetene er uendret.

### Endret

- Beløps- og tallfelt viser tusenskille (`1 000 000`) når feltet ikke er i fokus, så det er
  lettere å lese av at tallet er riktig. Formateringen er kun visning; SAF-T-/Bodil-import,
  skjembygging og innsending bruker samme rene tall som før.

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
