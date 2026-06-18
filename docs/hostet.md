# Hostet versjon

Du kan kjøre Wenche selv (se [Installasjon](installasjon.md) og [Oppsett](oppsett.md)),
eller bruke den hostede versjonen på **[wenche.cloud](https://wenche.cloud)**.

## Forskjellen

| | Self-hosted (resten av denne dokumentasjonen) | Hostet ([wenche.cloud](https://wenche.cloud)) |
|---|---|---|
| Oppsett | Du genererer RSA-nøkkel og registrerer en Maskinporten-klient | Gjort én gang av operatøren |
| Innlogging | Kjører lokalt på din maskin | Logg inn med ID-porten (BankID), så godkjenning i Altinn |
| Data | Blir på din maskin | Behandles kun i økten, ingenting lagres i database |
| Tilgang | Åpen kildekode, gratis | Foreløpig en tidlig testfase |

Den hostede tjenesten er for deg som heller vil slippe det tekniske oppsettet. Det er
nøyaktig samme åpne kildekode under panseret, så du kan når som helst velge å kjøre
self-hosted i stedet.

Du logger inn med **ID-porten** (BankID) og velger selskapet du vil sende inn for fra listen over
selskapene du kan representere i Altinn. Fødselsnummeret ditt brukes kun til innloggingen og lagres
ikke. (Mangler selskapet i listen, kan du taste organisasjonsnummeret manuelt; det bekreftes da mot
at du står registrert som daglig leder eller styreleder i Enhetsregisteret. Ved skjermet adresse
eller selskap uten registrert rolleinnehaver, ta kontakt, så ordner jeg en invitasjonslenke manuelt.)

Deretter følger du en enkel stegvis flyt: koble selskapet til Altinn (én gang, med BankID), fylle inn
tallene, eventuelt laste ned dokumentene (skattemelding, årsregnskap, aksjonæroppgave og noter)
for gjennomgang, og så sende inn. Noter sendes ikke inn digitalt, men kan lastes ned for
signering og arkivering hos selskapet.

Under **Tall** kan du fylle inn manuelt, hente tallene fra [Bodil](https://github.com/olefredrik/Bodil),
eller **importere fra SAF-T**. Laster du opp en SAF-T-fil, behandles den i minnet i EØS
for å fylle inn skjemaet, og forkastes umiddelbart, den lagres ikke.

!!! note "For operatører"
    Drifts- og deploy-dokumentasjon (Docker, Fly.io, secrets) ligger i `hosted/README.md`
    i kodebasen, ikke her. Denne siden er kun ment for sluttbrukere.
