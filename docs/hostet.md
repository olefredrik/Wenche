# Hostet versjon (invite-only)

Du kan kjøre Wenche selv (se [Installasjon](installasjon.md) og [Oppsett](oppsett.md)),
eller bruke den hostede, invite-only versjonen på
**[wenche.cloud](https://wenche.cloud)**.

## Forskjellen

| | Self-hosted (resten av denne dokumentasjonen) | Hostet ([wenche.cloud](https://wenche.cloud)) |
|---|---|---|
| Oppsett | Du genererer RSA-nøkkel og registrerer en Maskinporten-klient | Gjort én gang av operatøren |
| Innlogging | Kjører lokalt på din maskin | Invitasjonslenke + godkjenning i Altinn med BankID |
| Data | Blir på din maskin | Behandles kun i økten, ingenting lagres i database |
| Tilgang | Åpen kildekode, gratis | Foreløpig kun for inviterte testere |

Den hostede tjenesten er for deg som heller vil slippe det tekniske oppsettet. Det er
nøyaktig samme åpne kildekode under panseret, så du kan når som helst velge å kjøre
self-hosted i stedet.

!!! note "For operatører"
    Drifts- og deploy-dokumentasjon (Docker, Fly.io, secrets) ligger i `hosted/README.md`
    i kodebasen, ikke her. Denne siden er kun ment for sluttbrukere.
