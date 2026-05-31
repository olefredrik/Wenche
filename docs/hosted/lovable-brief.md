# Wenche, design-brief for Lovable

> Lim hele dette inn i Lovable (eller Figma AI). Målet er en informativ marketing-/info-side
> for Wenche med en egen, varm identitet, bevisst ulik andre prosjekter. Når du har en retning
> du liker, gir du meg outputen (eksport, lenke eller skjermbilder), så produksjonssetter jeg
> den i repoet (Next.js + Tailwind 4, koblet til app-en).

## Kontekst
Wenche er en hostet, invite-only nettjeneste som sender inn årsregnskap, skattemelding og
aksjonærregisteroppgave for små, passive holdingselskaper, rett til Altinn og Skatteetaten.
Brukeren fyller inn tallene; Wenche bygger skjemaene, sjekker dem og sender. Det finnes også en
gratis open-source self-hosted versjon. Dette er den offentlige info-siden (ikke selve appen);
den skal forklare hva Wenche er på en menneskelig måte og lede inviterte til innlogging.

## Persona og stemme
Wenche er en erfaren, varm, lett tørrvittig norsk dame som har gjort tusen årsoppgjør og ikke
lar seg skremme av Altinn. Hun maser ikke, hun ordner opp.
- Tone: rolig, jordnær, betryggende, klar tale. Litt lun humor er lov.
- Stemme: Wenche i første person («Jeg tar årsoppgjøret») eller varmt om henne i tredje person.
  Unngå korporativt «vi».
- Språk: norsk bokmål.
- Kopi-regel: IKKE bruk tankestrek (em-dash eller en-dash). Bruk komma, parentes, punktum eller
  vanlig bindestrek.

## Målgruppe
Eiere av små passive holdingselskaper. Ofte ikke regnskapskyndige, motiverte, men vil ha det
enkelt og trygt. B2B, men snakk til et menneske.

## Visuell retning
Utgangspunkt (fritt å videreutvikle): varm regnskaps-ro.
- Farger: kremhvit `#FBF7F0`, blekk `#1C2A24`, grangrønn aksent `#1F5C3D`. Juster/utvid fritt.
- Skrift-forslag: Fraunces (serif) til overskrifter + Inter til brødtekst. Åpent for andre
  kombinasjoner med samme varme, ordentlige følelse.
- Stemning: varm, rolig, ordentlig, tillitvekkende, et snev norsk håndlaget kvalitet. IKKE
  generisk SaaS, IKKE neon-gradienter, IKKE stockfoto.
- Personlighet: Wenche kan ha en tegnet illustrasjon (en vennlig, eldre norsk dame), gjerne med
  litt liv (subtil animasjon). Men hun trenger ikke dominere som et stort sentrert portrett.

## Må-ikke (for å unngå en generisk/kopiert layout)
- Ikke sentrer alt. Tør asymmetri, venstrejustert redaksjonell layout, ulik seksjonsrytme.
- Ikke led med et stort portrett-på-toppen-hero.
- Ikke fall tilbake på malen «3 funksjonskort + 3 tillit-søyler».
- Ikke bruk tankestrek i teksten.

## Innhold som må være med (du bestemmer rekkefølge og form)
- Hva Wenche er, kort og menneskelig.
- Slik fungerer det: logg inn → koble selskapet (godkjenn i Altinn med BankID, én gang) → fyll
  inn tallene → send inn. Gjerne et annet grep enn kort på rad.
- Hvem hun er for: KUN passive holdingselskaper (bevisst avgrensning).
- Hva hun IKKE gjør: innsendingsverktøy, ikke regnskapsfører. Du eier tallene og kontrollen.
- Trygghet: ingenting lagres (kun i økten, slettes etter innsending), åpen kildekode.
- Invite-only: «foreløpig kun for spesielt inviterte».
- En personlig «Hvem er Wenche?»-flate i hennes stemme.
- Footer: laget av Ole Fredrik Lie, lenke til Om og GitHub.
- Primær CTA: «Logg inn».

## Layout-retninger å utforske (velg én å gå dypt på)
1. **Redaksjonell/asymmetrisk:** venstrejustert, som en rolig artikkel eller et brev. Wenche
   som et lite, konsekvent nærvær i margen.
2. **Brev fra Wenche:** hun introduserer seg i første person, typografisk og varmt, nesten som
   et håndskrevet notat.
3. **Verktøy-først:** vis selve flyten/app-en (skjermbilde/mock) tidlig, mindre persona-tungt.
4. **Frist-ro:** led med følelsen («fristen nærmer seg, men ta det med ro»), en rolig
   sjekkliste-metafor.

## Output
React + Tailwind er perfekt (jeg tar det inn i Next.js + Tailwind 4 etterpå). Hold det
komponentbasert, tilgjengelig og mobil-først. Norsk tekst.
