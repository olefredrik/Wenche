"""
Innsending av aksjonærregisteroppgave (RF-1086) via SKDs REST-API.

Fristen er 31. januar året etter regnskapsåret.
Oppgaven rapporterer aksjonærer, beholdninger og eventuelle
utbytter og transaksjoner i løpet av året.

Innsendingsflyt (SKDs eget REST-API, ikke Altinn-instansflyt):
  1. POST Hovedskjema (RF-1086)    — selskapsopplysninger og aksjekapital
  2. POST Underskjema (RF-1086-U)  — ett per aksjonær med beholdning og transaksjoner
  3. POST bekreft                   — oppgaven klar til behandling hos SKD
"""

import os
from xml.sax.saxutils import escape

import yaml

from wenche.models import Aksjonaer, Aksjonaerregisteroppgave, Selskap
from wenche.skd_client import SkdAksjonaerClient


def les_config(config_fil: str) -> Aksjonaerregisteroppgave:
    """Leser config.yaml og returnerer en Aksjonaerregisteroppgave."""
    with open(config_fil, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    s = cfg["selskap"]
    selskap = Selskap(
        navn=s["navn"],
        org_nummer=s["org_nummer"],
        daglig_leder=s["daglig_leder"],
        styreleder=s["styreleder"],
        forretningsadresse=s["forretningsadresse"],
        stiftelsesaar=s["stiftelsesaar"],
        aksjekapital=s["aksjekapital"],
        kontakt_epost=s.get("kontakt_epost", ""),
    )

    aksjonaerer = [
        Aksjonaer(
            navn=a["navn"],
            fodselsnummer=str(a["fodselsnummer"]),
            antall_aksjer=a["antall_aksjer"],
            aksjeklasse=a["aksjeklasse"],
            utbytte_utbetalt=a["utbytte_utbetalt"],
            innbetalt_kapital_per_aksje=a["innbetalt_kapital_per_aksje"],
        )
        for a in cfg["aksjonaerer"]
    ]

    return Aksjonaerregisteroppgave(
        selskap=selskap,
        regnskapsaar=cfg["regnskapsaar"],
        aksjonaerer=aksjonaerer,
    )


def generer_hovedskjema_xml(oppgave: Aksjonaerregisteroppgave) -> bytes:
    """
    Genererer RF-1086 Hovedskjema XML for SKDs API.

    Inneholder selskapsopplysninger, aksjekapital og utstedelse ved stiftelse.
    Valideres mot: aksjonaerregisteroppgaveHovedskjema.xsd
    """
    s = oppgave.selskap
    aar = oppgave.regnskapsaar
    totalt_aksjer = oppgave.totalt_antall_aksjer
    paalydende = s.aksjekapital // totalt_aksjer if totalt_aksjer > 0 else 0
    stiftelsesdato = f"{s.stiftelsesaar}-01-01T00:00:00"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Skjema skjemanummer="890" spesifikasjonsnummer="12144"
        blankettnummer="RF-1086" gruppeid="2586" etatid="974761076">
    <GenerellInformasjon-grp-2587 gruppeid="2587">
        <Selskap-grp-2588 gruppeid="2588">
            <EnhetOrganisasjonsnummer-datadef-18 orid="18">{escape(s.org_nummer)}</EnhetOrganisasjonsnummer-datadef-18>
            <EnhetNavn-datadef-1 orid="1">{escape(s.navn)}</EnhetNavn-datadef-1>
            <EnhetAdresse-datadef-15 orid="15">{escape(s.forretningsadresse)}</EnhetAdresse-datadef-15>
            <AksjeType-datadef-17659 orid="17659">01</AksjeType-datadef-17659>
            <Inntektsar-datadef-692 orid="692">{aar}</Inntektsar-datadef-692>
        </Selskap-grp-2588>
        <Kontaktperson-grp-3442 gruppeid="3442">
            <KontaktpersonSkjemaEPost-datadef-30533 orid="30533">{escape(s.kontakt_epost)}</KontaktpersonSkjemaEPost-datadef-30533>
        </Kontaktperson-grp-3442>
        <AnnenKontaktperson-grp-5384 gruppeid="5384"></AnnenKontaktperson-grp-5384>
    </GenerellInformasjon-grp-2587>
    <Selskapsopplysninger-grp-2589 gruppeid="2589">
        <AksjekapitalForHeleSelskapet-grp-3443 gruppeid="3443">
            <AksjekapitalFjoraret-datadef-7129 orid="7129">0</AksjekapitalFjoraret-datadef-7129>
            <Aksjekapital-datadef-87 orid="87">{s.aksjekapital}</Aksjekapital-datadef-87>
        </AksjekapitalForHeleSelskapet-grp-3443>
        <AksjekapitalIDenneAksjeklassen-grp-3444 gruppeid="3444">
            <AksjekapitalISINAksjetypeFjoraret-datadef-17663 orid="17663">0</AksjekapitalISINAksjetypeFjoraret-datadef-17663>
            <AksjekapitalISINAksjetype-datadef-17664 orid="17664">{s.aksjekapital}</AksjekapitalISINAksjetype-datadef-17664>
        </AksjekapitalIDenneAksjeklassen-grp-3444>
        <PalydendePerAksje-grp-3447 gruppeid="3447">
            <AksjeMvPalydendeFjoraret-datadef-23944 orid="23944">0</AksjeMvPalydendeFjoraret-datadef-23944>
            <AksjeMvPalydende-datadef-23945 orid="23945">{paalydende}</AksjeMvPalydende-datadef-23945>
        </PalydendePerAksje-grp-3447>
        <AntallAksjerIDenneAksjeklassen-grp-3445 gruppeid="3445">
            <AksjerMvAntallFjoraret-datadef-29166 orid="29166">0</AksjerMvAntallFjoraret-datadef-29166>
            <AksjerMvAntall-datadef-29167 orid="29167">{totalt_aksjer}</AksjerMvAntall-datadef-29167>
        </AntallAksjerIDenneAksjeklassen-grp-3445>
        <InnbetaltAksjekapitalIDenneAksjeklassen-grp-3446 gruppeid="3446">
            <AksjekapitalInnbetaltFjoraret-datadef-8020 orid="8020">0</AksjekapitalInnbetaltFjoraret-datadef-8020>
            <AksjekapitalInnbetalt-datadef-5867 orid="5867">{s.aksjekapital}</AksjekapitalInnbetalt-datadef-5867>
        </InnbetaltAksjekapitalIDenneAksjeklassen-grp-3446>
        <InnbetaltOverkursIDenneAksjeklassen-grp-3448 gruppeid="3448">
            <AksjeOverkursISINAksjetypeFjoraret-datadef-17662 orid="17662">0</AksjeOverkursISINAksjetypeFjoraret-datadef-17662>
            <AksjeOverkursISINAksjetype-datadef-17661 orid="17661">0</AksjeOverkursISINAksjetype-datadef-17661>
        </InnbetaltOverkursIDenneAksjeklassen-grp-3448>
    </Selskapsopplysninger-grp-2589>
    <Utbytte-grp-3449 gruppeid="3449">
        <UtdeltSkatterettsligUtbytteILopetAvInntektsaret-grp-3451 gruppeid="3451"></UtdeltSkatterettsligUtbytteILopetAvInntektsaret-grp-3451>
    </Utbytte-grp-3449>
    <UtstedelseAvAksjerIfmStiftelseNyemisjonMv-grp-3452 gruppeid="3452">
        <AntallNyutstedteAksjer-grp-3453 gruppeid="3453">
            <AksjerNyutstedteStiftelseMvAntall-datadef-17668 orid="17668">{totalt_aksjer}</AksjerNyutstedteStiftelseMvAntall-datadef-17668>
            <AksjerStiftelseMvAntall-datadef-17669 orid="17669">{totalt_aksjer}</AksjerStiftelseMvAntall-datadef-17669>
            <AksjerNyutstedteStiftelseMvType-datadef-17670 orid="17670">N</AksjerNyutstedteStiftelseMvType-datadef-17670>
            <AksjerNyutstedteStiftelseMvTidspunkt-datadef-17671 orid="17671">{stiftelsesdato}</AksjerNyutstedteStiftelseMvTidspunkt-datadef-17671>
            <AksjerNyutstedteStiftelseMvPalydende-datadef-23947 orid="23947">{paalydende}</AksjerNyutstedteStiftelseMvPalydende-datadef-23947>
        </AntallNyutstedteAksjer-grp-3453>
    </UtstedelseAvAksjerIfmStiftelseNyemisjonMv-grp-3452>
    <UtstedelseAvAksjerIfmFondsemisjonSplittMv-grp-3454 gruppeid="3454">
        <NyutstedteAksjerOmfordeling-grp-3455 gruppeid="3455"></NyutstedteAksjerOmfordeling-grp-3455>
    </UtstedelseAvAksjerIfmFondsemisjonSplittMv-grp-3454>
    <SlettingAvAksjerIfmLikvidasjonPartiellLikvidasjonMv-grp-3456 gruppeid="3456">
        <SlettedeAksjerAvgang-grp-3457 gruppeid="3457"></SlettedeAksjerAvgang-grp-3457>
    </SlettingAvAksjerIfmLikvidasjonPartiellLikvidasjonMv-grp-3456>
    <SlettingAvAksjerIfmSpleisSkattefriFusjonFisjon-grp-3458 gruppeid="3458">
        <SlettedeAksjerOmfordeling-grp-3459 gruppeid="3459"></SlettedeAksjerOmfordeling-grp-3459>
    </SlettingAvAksjerIfmSpleisSkattefriFusjonFisjon-grp-3458>
    <EndringerIAksjekapitalOgOverkurs-grp-3460 gruppeid="3460">
        <NedsettelseAvInnbetaltOverkursMedTilbakebetalingTilAksjonarene-grp-3461 gruppeid="3461"></NedsettelseAvInnbetaltOverkursMedTilbakebetalingTilAksjonarene-grp-3461>
        <ForhoyelseAvAKVedOkningAvPalydende-grp-3462 gruppeid="3462"></ForhoyelseAvAKVedOkningAvPalydende-grp-3462>
        <ForhoyelseAvAKVedOkningAvPalydende-grp-3463 gruppeid="3463"></ForhoyelseAvAKVedOkningAvPalydende-grp-3463>
        <NedsettelseAvInnbetaltOgFondsemittertAK-grp-3464 gruppeid="3464"></NedsettelseAvInnbetaltOgFondsemittertAK-grp-3464>
        <NedsettelseAKVedReduksjonAvPalydende-grp-3465 gruppeid="3465"></NedsettelseAKVedReduksjonAvPalydende-grp-3465>
        <NedsettelseAvAKVedReduksjonUtfisjonering-grp-3466 gruppeid="3466"></NedsettelseAvAKVedReduksjonUtfisjonering-grp-3466>
    </EndringerIAksjekapitalOgOverkurs-grp-3460>
</Skjema>"""

    return xml.encode("UTF-8")


def generer_underskjema_xml(
    aksjonaer: Aksjonaer, oppgave: Aksjonaerregisteroppgave
) -> bytes:
    """
    Genererer RF-1086-U Underskjema XML for én aksjonær.

    Inneholder aksjonæridentifikasjon, beholdning og ervervstransaksjon.
    Valideres mot: aksjonaerregisteroppgaveUnderskjema.xsd
    """
    s = oppgave.selskap
    aar = oppgave.regnskapsaar
    anskaffelsesverdi = aksjonaer.innbetalt_kapital_per_aksje * aksjonaer.antall_aksjer
    stiftelsesdato = f"{s.stiftelsesaar}-01-01T00:00:00"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Skjema skjemanummer="923" spesifikasjonsnummer="12232"
        blankettnummer="RF-1086-U" tittel="Aksjonærregisteroppgaven - underskjema"
        gruppeid="3983" etatid="974761076">
    <SelskapsOgAksjonaropplysninger-grp-3987 gruppeid="3987">
        <Selskapsidentifikasjon-grp-3986 gruppeid="3986">
            <EnhetOrganisasjonsnummer-datadef-18 orid="18">{escape(s.org_nummer)}</EnhetOrganisasjonsnummer-datadef-18>
            <AksjeType-datadef-17659 orid="17659">01</AksjeType-datadef-17659>
            <Inntektsar-datadef-692 orid="692">{aar}</Inntektsar-datadef-692>
        </Selskapsidentifikasjon-grp-3986>
        <NorskUtenlandskAksjonar-grp-3988 gruppeid="3988">
            <AksjonarFodselsnummer-datadef-1156 orid="1156">{escape(aksjonaer.fodselsnummer)}</AksjonarFodselsnummer-datadef-1156>
            <Adresse-grp-7722 gruppeid="7722"></Adresse-grp-7722>
        </NorskUtenlandskAksjonar-grp-3988>
    </SelskapsOgAksjonaropplysninger-grp-3987>
    <AntallAksjerUtbytteOgTilbakebetalingAvTidligereInnbetaltKapit-grp-3990 gruppeid="3990">
        <AntallAksjerPerAksjonar-grp-3989 gruppeid="3989">
            <AksjerAntallFjoraret-datadef-29168 orid="29168">0</AksjerAntallFjoraret-datadef-29168>
            <AksjonarAksjerAntall-datadef-17741 orid="17741">{aksjonaer.antall_aksjer}</AksjonarAksjerAntall-datadef-17741>
        </AntallAksjerPerAksjonar-grp-3989>
        <UtdeltUtbyttePerAksjonar-grp-3991 gruppeid="3991">
            <AutomatiskMotregningOnskerIkke-datadef-37159 orid="37159">0</AutomatiskMotregningOnskerIkke-datadef-37159>
        </UtdeltUtbyttePerAksjonar-grp-3991>
        <UtdeltUtbytteKildeskatt-grp-9347 gruppeid="9347"></UtdeltUtbytteKildeskatt-grp-9347>
        <TilbakebetalingAvTidligereInnbetaltKapital-grp-7633 gruppeid="7633">
            <TilbakebetalingAvTidligereInnbetaltKapital-grp-7865 gruppeid="7865"></TilbakebetalingAvTidligereInnbetaltKapital-grp-7865>
        </TilbakebetalingAvTidligereInnbetaltKapital-grp-7633>
    </AntallAksjerUtbytteOgTilbakebetalingAvTidligereInnbetaltKapit-grp-3990>
    <Transaksjoner-grp-3992 gruppeid="3992">
        <KjopArvGaveStiftelseNyemisjonMv-grp-3993 gruppeid="3993">
            <AntallAksjerITilgang-grp-3998 gruppeid="3998">
                <AksjerKjopAntall-datadef-12153 orid="12153">{aksjonaer.antall_aksjer}</AksjerKjopAntall-datadef-12153>
                <AksjeErvervType-datadef-17745 orid="17745">N</AksjeErvervType-datadef-17745>
                <AksjerErvervsdato-datadef-17746 orid="17746">{stiftelsesdato}</AksjerErvervsdato-datadef-17746>
                <AksjeAnskaffelsesverdi-datadef-17636 orid="17636">{anskaffelsesverdi}</AksjeAnskaffelsesverdi-datadef-17636>
            </AntallAksjerITilgang-grp-3998>
        </KjopArvGaveStiftelseNyemisjonMv-grp-3993>
    </Transaksjoner-grp-3992>
    <FondsemisjonSplittSkattefriFusjonFisjonSammenslaingDelingAv-grp-3994 gruppeid="3994">
        <AntallAksjerITilgangIfmOmfordeling-grp-3999 gruppeid="3999"></AntallAksjerITilgangIfmOmfordeling-grp-3999>
    </FondsemisjonSplittSkattefriFusjonFisjonSammenslaingDelingAv-grp-3994>
    <SalgArvGaveLikvidasjonPartiellLikvidasjonMv-grp-3995 gruppeid="3995">
        <AksjerIAvgang-grp-4002 gruppeid="4002"></AksjerIAvgang-grp-4002>
    </SalgArvGaveLikvidasjonPartiellLikvidasjonMv-grp-3995>
    <SpleisSkattefriFusjonOgSkattefriFisjon-grp-3996 gruppeid="3996">
        <AntallAksjerIAvgangVedOmfordeling-grp-4003 gruppeid="4003"></AntallAksjerIAvgangVedOmfordeling-grp-4003>
    </SpleisSkattefriFusjonOgSkattefriFisjon-grp-3996>
    <EndringerIAksjekapitalOgOverkurs-grp-3997 gruppeid="3997">
        <TilbakebetaltInnbetaltOgFondsemittertAKVedReduksjonAvPalydende-grp-4000 gruppeid="4000"></TilbakebetaltInnbetaltOgFondsemittertAKVedReduksjonAvPalydende-grp-4000>
        <TilbakebetaltTidligereInnbetaltOverkursForAksjen-grp-4001 gruppeid="4001"></TilbakebetaltTidligereInnbetaltOverkursForAksjen-grp-4001>
        <ForhoyelseAvInnbetaltAksjekapitalVedOkning-grp-4987 gruppeid="4987"></ForhoyelseAvInnbetaltAksjekapitalVedOkning-grp-4987>
        <ReduksjonInnbetaltAksjekapital-grp-9857 gruppeid="9857"></ReduksjonInnbetaltAksjekapital-grp-9857>
    </EndringerIAksjekapitalOgOverkurs-grp-3997>
</Skjema>"""

    return xml.encode("UTF-8")


def valider(oppgave: Aksjonaerregisteroppgave) -> list[str]:
    feil = []

    if not oppgave.aksjonaerer:
        feil.append("Minst én aksjonær må være registrert.")

    if not oppgave.selskap.kontakt_epost:
        feil.append(
            "kontakt_epost mangler i config.yaml under selskap. "
            "Påkrevd av SKDs API."
        )

    for a in oppgave.aksjonaerer:
        fnr = a.fodselsnummer.replace(" ", "")
        if len(fnr) != 11 or not fnr.isdigit():
            feil.append(f"Ugyldig fødselsnummer for {a.navn}: må være 11 siffer.")

    total_aksjer = oppgave.totalt_antall_aksjer
    if total_aksjer <= 0:
        feil.append("Totalt antall aksjer må være større enn 0.")

    return feil


def send_inn(
    oppgave: Aksjonaerregisteroppgave,
    klient: SkdAksjonaerClient | None,
    dry_run: bool = False,
) -> dict | None:
    """
    Sender inn aksjonærregisteroppgaven via SKDs REST-API.

    dry_run=True genererer XML lokalt uten å sende til SKD.
    Returnerer svar fra bekreft-endepunktet, eller None ved dry_run.
    """
    feil = valider(oppgave)
    if feil:
        print("\nValidering mislyktes:")
        for f in feil:
            print(f"  - {f}")
        raise SystemExit(1)

    print("Validering OK.")

    hoved_xml = generer_hovedskjema_xml(oppgave)
    print(f"RF-1086 Hovedskjema generert ({len(hoved_xml):,} bytes).")

    under_xmler = [generer_underskjema_xml(a, oppgave) for a in oppgave.aksjonaerer]
    print(f"RF-1086-U Underskjema generert ({len(under_xmler)} stk).")

    if dry_run:
        base = f"aksjonaerregister_{oppgave.regnskapsaar}_{oppgave.selskap.org_nummer}"
        with open(f"{base}_hovedskjema.xml", "wb") as f:
            f.write(hoved_xml)
        for i, xml in enumerate(under_xmler, 1):
            with open(f"{base}_underskjema_{i}.xml", "wb") as f:
                f.write(xml)
        print(
            f"Dry-run: XML lagret til {base}_*.xml — ingenting sendt til SKD."
        )
        return None

    print("Sender RF-1086 Hovedskjema til SKD...")
    hovedskjemaid = klient.send_hovedskjema(oppgave.regnskapsaar, hoved_xml)
    print(f"Hovedskjema mottatt (ID: {hovedskjemaid}).")

    for i, (aksjonaer, xml) in enumerate(
        zip(oppgave.aksjonaerer, under_xmler), 1
    ):
        print(f"Sender underskjema {i}/{len(under_xmler)} ({aksjonaer.navn})...")
        klient.send_underskjema(oppgave.regnskapsaar, hovedskjemaid, xml)

    print("Bekrefter innsending...")
    svar = klient.bekreft(oppgave.regnskapsaar, hovedskjemaid, len(under_xmler))
    print(f"Aksjonærregisteroppgave sendt inn.")
    print(f"Forsendelse-ID: {svar.get('forsendelseId')}")
    return svar
