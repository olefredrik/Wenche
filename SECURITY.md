# Sikkerhetspolicy

Wenche sender årsregnskap, skattemelding og aksjonærregisteroppgave til norske myndigheter.
Den håndterer derfor ting som må være i orden: private RSA-nøkler, Maskinporten- og
ID-porten-tokener, organisasjonsnummer, fødselsnummer og regnskapstall. Finner du en
sårbarhet, vil jeg gjerne høre om det.

## Støttede versjoner

Wenche er et soloprosjekt og følger [semantisk versjonering](https://semver.org/lang/no/).
**Kun den nyeste utgitte versjonen støttes med sikkerhetsfikser.** Fikser kommer som en ny
patch-versjon på nyeste minor, og backportes ikke til eldre versjoner.

[![Støttet versjon](https://img.shields.io/pypi/v/wenche?label=st%C3%B8ttet%20versjon)](https://pypi.org/project/wenche/)

Merket over hentes fra PyPI og viser alltid gjeldende støttede versjon. Er du på noe eldre,
gjelder ikke policyen for din versjon før du har oppgradert. Alle utgivelser med
endringsbeskrivelse ligger under [Releases](https://github.com/olefredrik/Wenche/releases) og i
[CHANGELOG.md](CHANGELOG.md).

Den hostede tjenesten på [wenche.cloud](https://wenche.cloud) kjører alltid nyeste versjon, og
oppdateres av meg. Kjører du self-hosted, er det ditt ansvar å oppgradere:

```bash
pip install --upgrade wenche
```

## Rapportere en sårbarhet

**Ikke opprett et vanlig issue for sikkerhetsfeil.** Issues er offentlige, og gir alle andre
oppskriften før det finnes en fiks.

Bruk i stedet GitHubs private rapportering:

**[Rapporter en sårbarhet](https://github.com/olefredrik/Wenche/security/advisories/new)**

Får du ikke det til å fungere, send e-post til **hello@olefredrik.com** med «Wenche sikkerhet» i
emnefeltet.

### Ta med i rapporten

- Hvilken versjon eller commit du testet mot
- Om det gjelder self-hosted eller hostet ([wenche.cloud](https://wenche.cloud) eller
  [demo.wenche.cloud](https://demo.wenche.cloud))
- Hvilket miljø (`WENCHE_ENV=test` mot tt02, eller `prod`)
- Stegene som reproduserer feilen, og hva du faktisk oppnådde med den
- Gjerne et forslag til fiks, hvis du har et

### Ikke ta med i rapporten

Send aldri ekte hemmeligheter eller personopplysninger, verken egne eller andres:

- Private nøkler (`*.pem`), tokener eller sesjonscookies. Beskriv at de lekket, ikke lim dem inn
- Fødselsnumre, navn eller andre personopplysninger. Anonymiser eksemplene
- `config.yaml` eller SAF-T-filer med reelle regnskapstall. Bruk oppdiktede tall

Har du funnet en hemmelighet som ligger i git-historikken eller i et bygget artefakt, si det
privat, så roterer jeg den før noe publiseres.

## Hva du kan forvente

Wenche er et soloprosjekt jeg driver på fritiden, gratis. Jeg setter derfor ingen svarfrister jeg
ikke kan garantere at jeg holder. Det jeg lover er dette:

- **Jeg leser og svarer på alle rapporter.** Du blir ikke ignorert, og en rapport i god tro blir
  aldri møtt med juridiske trusler. Vanligvis svarer jeg innen noen dager, men det kan gå lenger i
  travle perioder
- Blir rapporten **akseptert**, fikser jeg den og slipper en patch-versjon til PyPI, deployer
  hostet, og publiserer en GitHub Security Advisory med kreditering til deg (si fra hvis du vil
  være anonym). Fiksen beskrives også i [CHANGELOG.md](CHANGELOG.md). Alvorlige funn i den
  hostede tjenesten prioriteres foran alt annet
- Blir rapporten **avvist**, får du en begrunnelse. Er vi uenige, si det gjerne, jeg vurderer på
  nytt
- **Hold funnet privat mens jeg jobber med det**, gjerne til fiksen er ute. Hører du ingenting fra
  meg på 30 dager, står du fritt til å offentliggjøre. Blir jeg forsinket, sier jeg det til deg i
  stedet for å bli stille
- Det finnes **ingen bug bounty**. Jeg kan ikke betale for funn. Kreditering og en oppriktig takk
  er det jeg har å gi

## Hva som er i scope

Kode i dette repoet, og tjenestene jeg selv drifter:

- Python-kjernen og CLI-en (`wenche/`): autentisering, token- og nøkkelhåndtering, XML-bygging,
  innsending
- Det self-hostede webgrensesnittet (`wenche/web/`) og den lokale serveren `wenche` starter
- Den hostede tjenesten (`hosted/`), inkludert `app.wenche.cloud` og `demo.wenche.cloud`
- Det delte designsystemet (`packages/ui/`)

Typiske funn jeg vil vite om: lekkasje av nøkler eller tokener (til disk, logg, nettverk eller
nettleser), svakheter i sesjonsbinding eller cookie-signering, forfalskning av invitasjonstokener,
at én bruker kan nå en annen brukers økt eller sende inn for et selskap de ikke representerer,
injeksjon, XSS, path traversal, og avhengigheter med kjente sårbarheter som faktisk er utnyttbare
i Wenche.

## Hva som ikke er i scope

- **Myndighetenes egne API-er og tjenester.** Altinn, Skatteetaten, Brønnøysundregistrene,
  ID-porten og Maskinporten er ikke mine systemer, Wenche er bare en klient mot dem. Funn der
  meldes til [servicedesk@altinn.no](mailto:servicedesk@altinn.no) eller
  [Skatteetatens brukerstøtteportal](https://eksternjira.sits.no/plugins/servlet/desk/site/global)
- **Manglende herding uten demonstrert effekt**, for eksempel savnede sikkerhetsheadere,
  TLS-karakterer eller rå skannerrapporter, når det ikke følger et konkret angrep med det
- **Tjenestenekt og lastgenerering.** Ikke kjør last- eller stresstesting mot
  `app.wenche.cloud` eller `demo.wenche.cloud`, og aldri mot myndighets-API-er, verken tt02 eller
  prod. Dette er én liten maskin per app, og misbruk av testmiljøene rammer alle som bruker dem
- **Sosial manipulering, phishing og fysisk tilgang**
- **Din egen maskin og dine egne nøkler i self-hosted bruk.** At noen med tilgang til din
  brukerkonto kan lese `~/.wenche/token.json` eller din `config.yaml` er forventet, det er derfor
  fila har rettigheter begrenset til din bruker

## Regler for testing

Test mot din egen installasjon, med `WENCHE_ENV=test` slik at du treffer Skatteetatens testmiljø
tt02 og aldri ekte myndigheter. Bruk aldri andres fødselsnummer eller organisasjonsnummer.
Tester du på `demo.wenche.cloud`, hold deg til demo-selskapet og din egen økt, og ikke prøv å nå
andre brukeres data. Stopp og rapporter i stedet for å grave videre om du kommer over noe som ser
ut som en annen brukers opplysninger.

## Kjente forutsetninger

- Wenche sender data kun til Maskinporten, ID-porten, Altinn, Skatteetaten og
  Brønnøysundregistrene
- `.env`, `config.yaml` og `*.pem` er gitignored, og skal aldri i git
- Den hostede tjenesten er session-only: opplysninger behandles i økten og lagres ikke i noen
  database. Fødselsnummer brukes kun til innlogging og lagres ikke
- Demo og prod er separate Fly-apper med separate credentials, slik at en demo aldri kan røre
  prod

Wenche er lisensiert under [MIT](LICENSE) og leveres uten garantier. Denne policyen er et løfte om
å ta sikkerhetsrapporter på alvor og svare på dem, ikke en garanti for at koden er feilfri.
