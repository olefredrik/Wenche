# Referanse

Komplett dokumentasjon for konfigurasjonsfilen `config.yaml` og miljøvariabler (`.env`).

---

## config.yaml

Alle beløp oppgis i hele kroner (NOK). Bruk `0` for poster som ikke er aktuelle.

Feltnavnene må stå nøyaktig som i tabellene under. Wenche advarer om felt den ikke kjenner, hvor som helst i `config.yaml`, siden et beløp i et slikt felt ikke kommer med i innsendingen. Det skjer typisk når feltnavnet er feilstavet, eller når configen er laget for en nyere Wenche-versjon.

Tabellene er generert fra Wenches datamodell, samme kilde som [JSON Schema-et](#json-schema) `wenche skjema` skriver ut, så de viser nøyaktig det Wenche leser.

### `selskap`

<!-- skjema: selskap -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `navn` | tekst | ja | Selskapets registrerte navn |
| `org_nummer` | tekst | ja | Organisasjonsnummer, 9 siffer uten mellomrom |
| `daglig_leder` | tekst | delvis | Fullt navn på daglig leder. Minst én av `daglig_leder` og `styreleder` må være fylt ut |
| `styreleder` | tekst | delvis | Fullt navn på styreleder (kan være samme som daglig leder). Minst én av `daglig_leder` og `styreleder` må være fylt ut |
| `forretningsadresse` | tekst | ja | Gateadresse, postnummer og poststed |
| `stiftelsesaar` | heltall | ja | Året selskapet ble stiftet |
| `aksjekapital` | heltall | ja | Innbetalt aksjekapital i NOK, fra stiftelsesdokumentene |
| `kontakt_epost` | tekst | for RF-1086 | E-postadressen Skatteetaten sender tilbakemeldingen på aksjonærregisteroppgaven til, altså om den er godkjent eller avvist. Bruk en adresse du leser |
| `stiftelsesdato` | dato | nei | Eksakt stiftelsesdato (ÅÅÅÅ-MM-DD). Hentes fra Enhetsregisteret. Brukes som stiftelsesdato i aksjonærregisteroppgaven, og som start på et kort første regnskapsår. Uten den brukes 1. januar i stiftelsesåret |
| `tinginnskudd_ved_stiftelse` | heltall | nei | Den delen av stiftelsesinnskuddet som ble gjort som tinginnskudd, i NOK. Brukes bare i selskapets første regnskapsår, der egenkapitalavstemmingen skiller kontantinnskudd og tinginnskudd på hver sin kode. Tom eller 0 = hele innskuddet var kontant |
<!-- /skjema -->

### `regnskapsaar`

<!-- skjema: . regnskapsaar -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `regnskapsaar` | heltall | ja | Året regnskapet gjelder for, f.eks. `2024` |
<!-- /skjema -->

### `resultatregnskap`

#### `driftsinntekter`

<!-- skjema: resultatregnskap.driftsinntekter -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `salgsinntekter` | heltall | nei | Inntekter fra salg av varer eller tjenester |
| `andre_driftsinntekter` | heltall | nei | Andre løpende driftsinntekter |
<!-- /skjema -->

#### `driftskostnader`

<!-- skjema: resultatregnskap.driftskostnader -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `loennskostnader` | heltall | nei | Lønn, arbeidsgiveravgift og lignende |
| `avskrivninger` | heltall | nei | Planmessige avskrivninger på anleggsmidler |
| `andre_driftskostnader` | heltall | nei | Bank- og regnskapsgebyrer, kontorkostnader o.l. |
<!-- /skjema -->

#### `finansposter`

<!-- skjema: resultatregnskap.finansposter -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `utbytte_fra_datterselskap` | heltall | nei | Utbytte mottatt fra datterselskaper (dekkes av fritaksmetoden) |
| `andre_finansinntekter` | heltall | nei | Renteinntekter og andre finansinntekter |
| `rentekostnader` | heltall | nei | Renter på lån |
| `andre_finanskostnader` | heltall | nei | Andre finanskostnader |
| `gevinst_ved_realisasjon_av_aksjer` | heltall | nei | Gevinst ved salg av aksjer innenfor fritaksmetoden (kode 8074). Skattefri når `anvend_fritaksmetoden` er `true`, uansett eierandel |
| `tap_ved_realisasjon_av_aksjer` | heltall | nei | Tap ved salg av aksjer innenfor fritaksmetoden (kode 8174). Ikke fradragsberettiget når `anvend_fritaksmetoden` er `true` |
| `utbytte_fra_andre_aksjer` | heltall | nei | Utbytte fra selskaper som verken er datterselskap eller tilknyttet selskap, typisk en eierandel under 20 %. Egen linje i årsregnskapet («Inntekt på andre investeringer»). I skattemeldingen skattlegges det som utbytte fra datterselskap, alltid med 3 %-sjablonen når `anvend_fritaksmetoden` er `true` |
<!-- /skjema -->

#### Regnskapsperiode

Feltene ligger på toppnivå i `config.yaml`, ved siden av `regnskapsaar`. Begge er valgfrie.

<!-- skjema: . regnskapsstart regnskapsslutt -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `regnskapsstart` | dato | nei | Første dag i regnskapsperioden (ÅÅÅÅ-MM-DD). Tom = 1. januar i regnskapsåret |
| `regnskapsslutt` | dato | nei | Siste dag i regnskapsperioden. Tom = 31. desember i regnskapsåret |
<!-- /skjema -->

Regnskapsåret er normalt kalenderåret (regnskapsloven § 1-7 første ledd), og da skal begge stå tomme. Det eneste unntaket er et **kort første regnskapsår**: et selskap stiftet i løpet av året har sitt første regnskapsår fra stiftelsesdatoen til 31. desember samme år, og da settes `regnskapsstart` til stiftelsesdatoen.

**Forlenget første regnskapsår støttes ikke.** Regnskapsloven § 1-7 andre ledd lar et selskap stiftet sent på året la det første regnskapsåret løpe i inntil 18 måneder. Skattemeldingen skal likevel leveres for hvert kalenderår, og Wenche bygger årsregnskap og skattemelding fra samme periode. Et selskap som vil bruke Wenche, velger derfor et kort første regnskapsår.

Wenche stopper innsendingen av både årsregnskap og skattemelding hvis perioden går over to kalenderår, slutter på en annen dag enn 31. desember, slutter før den starter, eller `regnskapsaar` ikke er året perioden slutter.

#### Skattekostnad

Feltet ligger direkte under `resultatregnskap`, ikke i en underseksjon.

<!-- skjema: resultatregnskap skattekostnad -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `skattekostnad` | heltall | nei | Skattekostnad på ordinært resultat (rskl. § 6-1). Egen linje mellom resultat før skatt og årsresultat. 0 for et selskap uten skattepliktig inntekt |
<!-- /skjema -->

Årsresultatet utledes som resultat før skatt minus skattekostnad. Har selskapet skattepliktig inntekt (for eksempel renteinntekt, eller 3 %-tillegget på fritatt utbytte), skal skatten føres her, og som `betalbar_skatt` i balansen hvis den ikke er betalt ved årsslutt. Wenche kan foreslå tallet: knappen «Foreslå skattekostnad» i Tall-steget regner ut 22 % av skattepliktig inntekt. Forslaget føres aldri automatisk.

### `balanse`

#### `eiendeler.anleggsmidler`

<!-- skjema: balanse.eiendeler.anleggsmidler -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `aksjer_i_datterselskap` | heltall | nei | Kostpris for aksjer i datterselskaper, det vil si selskaper du kontrollerer (normalt over 50 % av stemmene, rskl. § 1-3) |
| `andre_aksjer` | heltall | nei | Aksjer i selskaper som ikke er datterselskaper. Grensen her er kontroll, ikke 90 %-grensen i fritaksmetoden |
| `langsiktige_fordringer` | heltall | nei | Lån gitt til andre med løpetid over 1 år |
<!-- /skjema -->

#### `eiendeler.omloepmidler`

<!-- skjema: balanse.eiendeler.omloepmidler -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `kortsiktige_fordringer` | heltall | nei | Kundefordringer og andre kortsiktige krav |
| `bankinnskudd` | heltall | nei | Saldo på driftskonto per 31.12 |
<!-- /skjema -->

#### `egenkapital_og_gjeld.egenkapital`

<!-- skjema: balanse.egenkapital_og_gjeld.egenkapital -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `aksjekapital` | heltall | nei | Innbetalt aksjekapital (fra stiftelsesdokumentene) |
| `overkursfond` | heltall | nei | Innbetalt over pålydende ved emisjon |
| `annen_egenkapital` | heltall | nei | Akkumulert overskudd/underskudd. Negativ verdi = akkumulert underskudd |
<!-- /skjema -->

#### `egenkapital_og_gjeld.langsiktig_gjeld`

<!-- skjema: balanse.egenkapital_og_gjeld.langsiktig_gjeld -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `laan_fra_aksjonaer` | heltall | nei | Lån fra eier med avtalt løpetid over 1 år |
| `andre_langsiktige_laan` | heltall | nei | Banklån og andre lån med løpetid over 1 år |
<!-- /skjema -->

#### `egenkapital_og_gjeld.kortsiktig_gjeld`

<!-- skjema: balanse.egenkapital_og_gjeld.kortsiktig_gjeld -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `leverandoergjeld` | heltall | nei | Ubetalte fakturaer per 31.12 |
| `betalbar_skatt` | heltall | nei | Skyldig selskapsskatt per 31.12 (konto 2500), motposten til `skattekostnad` |
| `skyldige_offentlige_avgifter` | heltall | nei | Skyldig mva, arbeidsgiveravgift o.l. |
| `avsatt_utbytte` | heltall | nei | Utbytte styret har foreslått for regnskapsåret (konto 2800). Forslaget er en forpliktelse ved årsslutt og reduserer egenkapitalen i avsetningsåret, ikke i året det utbetales. Er utbyttet i stedet vedtatt og utbetalt i året uten forutgående avsetning, skal feltet stå tomt og utbetalingen oppgis per aksjonær |
| `annen_kortsiktig_gjeld` | heltall | nei | Annen gjeld med forfall innen 1 år |
<!-- /skjema -->

### `foregaaende_aar` (valgfritt)

Obligatorisk etter regnskapslovens § 6-6, men kan utelates for selskaper som er stiftet i inneværende regnskapsår.

Har nøyaktig samme struktur som `resultatregnskap` og `balanse` ovenfor. Kopier inn tilsvarende tall fra fjorårets regnskap.

```yaml
foregaaende_aar:
  resultatregnskap:
    # samme struktur som resultatregnskap
  balanse:
    # samme struktur som balanse
```

### `skattemelding`

<!-- skjema: skattemelding -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `underskudd_til_fremfoering` | heltall | nei | Fremførbart underskudd fra tidligere år (NOK). Finnes i fjorårets skattemelding. Standard: `0` |
| `anvend_fritaksmetoden` | boolsk | nei | `true` for holdingselskaper som eier aksjer (sktl. § 2-38). Gjelder utbytte og gevinst eller tap ved salg av aksjer. Standard: `true` |
| `eierandel_for_fritaksmetoden` | desimaltall | nei | Eierandel i selskapet som deler ut utbytte, i prosent (0-100, desimaler tillatt, for eksempel `90.5`). Brukes bare når `anvend_fritaksmetoden` er `true`. Over 90 %: hele utbyttet fritatt. 90 % eller lavere: 3 % skattepliktig (sjablonregelen, sktl. § 2-38 sjette ledd). Standard: `100` |
| `boersnotert` | boolsk | nei | `true` hvis selskapet er børsnotert. Standard: `false` |
| `formuesverdi_aksjer` | heltall | nei | Formuesverdi av aksjer selskapet eier i andre selskap, fra aksjeoppgaven (RF-1088S, post 209). Brukes til å beregne netto formuesverdi bak selskapets egne aksjer. Standard: `0` |
| `samlet_verdi_bak_aksjene` | heltall | nei | Overstyrer den beregnede netto formuesverdien bak aksjene direkte. Utelat for å la Wenche beregne den fra `formuesverdi_aksjer` og balansen |
<!-- /skjema -->

### `naeringsspesifikasjon.poster` (integrasjonsflate)

`naeringsspesifikasjon.poster` er et valgfritt felt for regnskapssystemer som må bevare
eksakte grupperingskoder i næringsspesifikasjonen. Ved vanlig bruk skal seksjonen utelates.
Når listen finnes, bruker Wenche den i stedet for den forenklede standardfordelingen.

Hver post har disse feltene:

<!-- skjema: naeringsspesifikasjon.poster -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `kategori` | tekst (én av `salgsinntekt`, `annenDriftsinntekt`, `loennskostnad`, `annenDriftskostnad`, `finansinntekt`, `finanskostnad`, `skattekostnad`, `balanseverdiForAnleggsmiddel`, `balanseverdiForOmloepsmiddel`, `egenkapital`, `langsiktigGjeld`, `kortsiktigGjeld`) | ja | Kategorien posten tilhører |
| `kode` | tekst | ja | Firesifret kode fra Skatteetatens grupperingskodeliste, for eksempel `6350` |
| `beloep` | tall | ja | Beløpet som skal rapporteres på koden |
<!-- /skjema -->

```yaml
naeringsspesifikasjon:
  poster:
    - kategori: annenDriftskostnad
      kode: "6350"
      beloep: 1000
    - kategori: annenDriftskostnad
      kode: "7700"
      beloep: 250
```

Listen må være komplett og summere nøyaktig til hver tilsvarende kategori i
`resultatregnskap` og `balanse`. Wenche stopper XML-genereringen hvis postlisten ikke
avstemmer. Nullposter inngår i avstemmingen, men tas bort før XML-en bygges.

Balansebeløp må være positive. Negativ annen egenkapital uttrykkes med kode `2080` og
et positivt beløp. Andre negative balansebeløp avvises.

Koden må finnes i Skatteetatens kodeliste `2025_resultatregnskapOgBalanse`. Wenche kan ikke
sjekke det lokalt, fordi XSD-en ikke lister opp de gyldige kodeverdiene. En ukjent kode
oppdages derfor først av Skatteetaten, som svarer med et blokkerende avvik
(`UgyldigKodelisteverdi`) og navngir koden. Innsendingen stopper da før noe er sendt, så en
feil kode kan ikke gi en gal innsending, men den må rettes i konfigurasjonen før du kommer
videre. Merk også at kodelisten for rapportering er grovere enn en vanlig kontoplan: enkelte
bokføringskoder skal aggregeres, for eksempel hører `7770` hjemme under `6700`.

Feltet er bare en integrasjonsflate. Postlisten vises ikke i webgrensesnittet og droppes
ved SAF-T-import. Hvis et aggregert tall endres i webgrensesnittet etter import, vil
postlisten ikke lenger avstemme. Da må integrasjonen levere en ny komplett liste, eller
seksjonen må fjernes slik at Wenche bruker standardfordelingen.

### `aksjonaerer`

Liste over alle aksjonærer per 31.12 i regnskapsåret.

<!-- skjema: aksjonaerer -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `navn` | tekst | ja | Aksjonærens fulle navn |
| `fodselsnummer` | tekst | ja | Fødselsnummer (personnummer), 11 siffer |
| `antall_aksjer` | heltall | ja | Antall aksjer eid per 31.12 |
| `aksjeklasse` | tekst | ja | Aksjeklasse, f.eks. `ordinære` |
| `utbytte_utbetalt` | heltall | nei | Utbytte utbetalt til denne aksjonæren i løpet av året (NOK). Standard: `0` |
| `innbetalt_kapital_per_aksje` | heltall | nei | Innbetalt kapital per aksje i NOK. Beregnes som aksjekapital / antall aksjer. Standard: `0` |
<!-- /skjema -->

#### Utbytte i aksjonærregisteroppgaven

Når en aksjonær har `utbytte_utbetalt` over 0, rapporterer Wenche utdelingen i RF-1086: totalt utbytte og utbytte per aksje for selskapet (post 8), og hver aksjonærs andel (post 21). Skatteetaten krever da også tidspunktet for vedtaket, i feltet under. Det ligger på toppnivå i `config.yaml`, ved siden av `regnskapsaar`.

<!-- skjema: . utbytte_vedtaksdato -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `utbytte_vedtaksdato` | dato | når det er utbetalt utbytte | Datoen generalforsamlingen vedtok utbyttet (ÅÅÅÅ-MM-DD). Må ligge i inntektsåret |
<!-- /skjema -->

Wenche rapporterer én utdeling per år, for én aksjeklasse. Alle aksjonærer må derfor ha fått like mye per aksje (en krones avvik for avrunding godtas), ellers stopper Wenche innsendingen, fordi post 8 og post 21 da ikke ville gått opp hos Skatteetaten.

### `noter` (valgfritt)

Grunnlaget for de obligatoriske notene (se [Bruk](bruk.md)). Notene sendes ikke inn digitalt, men `antall_ansatte` går også inn som årsverk i årsregnskapet til Brønnøysund, så noten og skjemaet sier det samme.

<!-- skjema: noter -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `antall_ansatte` | heltall | nei | Antall ansatte i regnskapsåret. Settes også som årsverk i årsregnskapet, og dry-run advarer når det er over 0, siden lønn og a-melding ligger utenfor det Wenche sender inn. Standard: `0` |
| `laan_til_naerstaaende` | liste | nei | Lån til eller fra nærstående per 31.12, ett innslag per lån (se tabellen under). Standard: tom liste |
<!-- /skjema -->

#### `laan_til_naerstaaende`

Ett innslag per lån:

<!-- skjema: noter.laan_til_naerstaaende -->
| Felt | Type | Påkrevd | Beskrivelse |
|---|---|---|---|
| `motpart` | tekst | ja | Navn på den nærstående parten (aksjonær, styremedlem e.l.) |
| `saldo` | tall | ja | Utestående saldo per 31.12 (NOK) |
| `retning` | tekst (`långiver` eller `låntaker`) | nei | `långiver` når selskapet har lånt ut, `låntaker` når det har lånt inn |
| `rente_prosent` | desimaltall | nei | Rentesats i prosent |
| `sikkerhet` | tekst | nei | Eventuell sikkerhet stilt for lånet |
<!-- /skjema -->

### JSON Schema

`wenche skjema` skriver ut et [JSON Schema](https://json-schema.org/) for `config.yaml`, generert fra samme datamodell som tabellene over. Skjemaet avviser felt Wenche ikke kjenner, så det fanger feilstavinger før du kjører Wenche, og det gir fullføring og feilmerking i editorer som forstår JSON Schema for YAML (VS Code med YAML-utvidelsen, blant andre):

```bash
wenche skjema --ut wenche-config.schema.json
```

Legg så denne linjen øverst i `config.yaml`:

```yaml
# yaml-language-server: $schema=wenche-config.schema.json
```

Verktøy som lager `config.yaml` for Wenche, som [Bodil](https://github.com/olefredrik/Bodil), kan validere filene sine mot skjemaet i sine egne tester.

---

## Miljøvariabler (.env)

| Variabel | Påkrevd | Beskrivelse |
|---|---|---|
| `MASKINPORTEN_CLIENT_ID` | ja | Klient-ID fra Digdirs selvbetjeningsportal |
| `MASKINPORTEN_KID` | ja | UUID for offentlig nøkkel registrert på klienten |
| `MASKINPORTEN_PRIVAT_NOKKEL` | ja | Sti til privat nøkkelfil. Standard: `maskinporten_privat.pem` |
| `ORG_NUMMER` | ja | Ditt eget organisasjonsnummer (9 siffer). Brukes som systembruker_org og party |
