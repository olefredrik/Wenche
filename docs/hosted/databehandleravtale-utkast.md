# Databehandleravtale (UTKAST)

> **UTKAST, ikke juridisk rådgivning.** Arbeidsdokument for hostet Wenche (invite-only MVP).
> Skal gjennomgås av jurist før bruk. `[…]` markerer felter som må fylles inn.

Avtale i henhold til personvernforordningen (GDPR) artikkel 28, mellom:

- **Behandlingsansvarlig:** kunden, `[selskapsnavn]`, org.nr. `[…]` («Kunden»)
- **Databehandler:** Operatørselskapet, `[nytt datterselskap av OFL Holding AS]`, org.nr. `[…]` («Operatøren»)

## 1. Bakgrunn og formål
Operatøren drifter en nettjeneste som lar Kunden sende inn årsregnskap, skattemelding og
aksjonærregisteroppgave til Skatteetaten/Altinn på vegne av Kundens eget selskap. Operatøren
behandler personopplysninger utelukkende for å levere denne innsendingstjenesten på Kundens
dokumenterte instruks.

## 2. Behandlingens art og varighet
- **Art:** mottak, validering, generering av innsendingsformat (XML) og videresending til
  Skatteetaten/Altinn via Maskinporten/systembruker.
- **Varighet:** kun for den enkelte innsendingssesjonen. Opplysningene behandles i minne under
  sesjonen og **slettes ved innsending eller utlogging**. Ingen lagring i database.

## 3. Typer personopplysninger og kategorier registrerte
- **Typer:** navn, fødselsnummer, aksjeinnehav/utbytte, samt selskapets regnskaps- og
  skattetall.
- **Registrerte:** Kundens aksjonærer og rolleinnehavere (daglig leder/styreleder).
- Ingen særlige kategorier (GDPR art. 9). Fødselsnummer behandles etter personopplysningsloven
  § 12 fordi Skatteetaten krever det for rapporteringen.

## 4. Operatørens plikter
Disse pliktene er **lovpålagte minimumskrav etter GDPR art. 28**, ikke frivillig påtatt
ekstraansvar, og dekkes i hovedsak automatisk av tjenestens session-only-arkitektur (ingen
lagring). Operatøren påtar seg **intet ansvar for innholdet** i opplysningene eller for
innsendingens korrekthet; det ansvaret ligger hos Kunden (se egne Vilkår og ansvarsfraskrivelse).

1. Behandler personopplysninger **kun etter Kundens dokumenterte instruks** (denne avtalen +
   bruk av tjenesten).
2. Sikrer **taushetsplikt** for alle med tilgang.
3. Iverksetter egnede **tekniske og organisatoriske tiltak** (art. 32): TLS, isolert
   nøkkelhåndtering (KMS/HSM), per-sesjon-isolasjon, ingen persistert kundedata, logging uten
   fødselsnummer/finansdata.
4. Bruker **underdatabehandlere** kun som angitt i punkt 6 og pålegger dem samme plikter
   (art. 28(4)).
5. **Bistår** Kunden med å oppfylle registrertes rettigheter og med sikkerhet/avvik/DPIA.
6. **Sletter** alle personopplysninger ved sesjonsslutt; ingen kopier beholdes.
7. **Varsler** Kunden uten ugrunnet opphold ved brudd på personopplysningssikkerheten.
8. Gjør tilgjengelig informasjon som viser etterlevelse, og muliggjør **revisjon**.

## 5. Kundens plikter
Kunden er ansvarlig for at opplysningene som legges inn er korrekte, at det finnes
behandlingsgrunnlag, og for den endelige kontrollen og godkjenningen av innsendingen.

## 6. Underdatabehandlere
| Underdatabehandler | Tjeneste | Lokasjon |
|---|---|---|
| Fly.io | Drift/hosting av tjenesten (server) | EØS-region |

Operatøren varsler Kunden ved endringer i underdatabehandlere. Behandlingen skjer i **EØS-region**.
Fly.io har morselskap utenfor EØS; for en eventuell overføring gjelder EUs standardavtalevilkår
(SCC), og fordi opplysningene kun behandles i minne under sesjonen og **aldri lagres**, er
overføringseksponeringen minimal.

Tjenesten benytter **ingen egen innloggings- eller e-postleverandør**: tilgang gis via en signert
per-org invitasjonslenke, og autorisasjonen skjer i Altinn (systembruker-godkjenning med BankID).
Markedsnettstedet (wenche-web) driftes separat av Vercel, men behandler **ingen** av
personopplysningene denne avtalen gjelder, og er derfor ikke en underdatabehandler her.

## 7. Varighet og opphør
Avtalen gjelder så lenge Kunden bruker tjenesten. Ved opphør beholdes ingen personopplysninger
(de er allerede slettet per sesjon).

## 8. Lovvalg
Norsk rett. Tvister løses ved `[verneting]`.

_Sted/dato og signatur for begge parter._
