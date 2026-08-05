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

import httpx
import yaml

from wenche.models import Aksjonaer, Aksjonaerregisteroppgave, Selskap
from wenche.skd_client import SkdAksjonaerClient

# Brønnøysundregistrenes åpne Enhetsregister-API.
# Brukes for å verifisere stiftelsesår mot SKDs forventning (MAKS_025-klassen).
_BRG_ENHET_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"


def _stiftelsestidspunkt(selskap: Selskap) -> str:
    """
    Stiftelsestidspunkt for RF-1086, som ISO-datetime.

    Bruker den eksakte stiftelsesdatoen når den er kjent (Enhetsregisteret har den), og faller
    ellers tilbake på 1. januar i stiftelsesåret. Fallbacket er en tilnærming: for et selskap
    stiftet sent på året oppgav Wenche før 1. januar selv om registeret hadde riktig dato.
    """
    if selskap.stiftelsesdato:
        return f"{selskap.stiftelsesdato.isoformat()}T00:00:00"
    return f"{selskap.stiftelsesaar}-01-01T00:00:00"


def _format_paalydende(verdi: float) -> str:
    """
    Formater pålydende per aksje for RF-1086-XMLen.

    RF-1086 tillater opptil 6 desimaler i pålydende-feltet (bekreftet av
    Skatteetaten i SSV-5278). Verdien rundes derfor til 6 desimaler for å
    fjerne flyttalls-støy fra divisjonen og overhold spec-grensen. Resultatet
    returneres som heltallstreng for hele kroner (f.eks. 300 → "300") og
    desimalstreng uten unødvendige etterstilte nuller ellers (f.eks. 0,10
    → "0.1", 0,123456 → "0.123456"), slik at selskaper med fri pålydende
    (lovlig siden 2013) representeres kompakt i skjemaet.
    """
    rundet = round(verdi, 6)
    if rundet.is_integer():
        return str(int(rundet))
    return f"{rundet:.6f}".rstrip("0").rstrip(".")


def les_config(config_fil: str | dict) -> Aksjonaerregisteroppgave:
    """Leser config (filsti eller allerede parset dict) og returnerer en Aksjonaerregisteroppgave."""
    if isinstance(config_fil, dict):
        cfg = config_fil
    else:
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


def generer_hovedskjema_xml(
    oppgave: Aksjonaerregisteroppgave, innsending_org: str = ""
) -> bytes:
    """
    Genererer RF-1086 Hovedskjema XML for SKDs API.

    Inneholder selskapsopplysninger, aksjekapital og utstedelse ved stiftelse.
    Valideres mot: aksjonaerregisteroppgaveHovedskjema.xsd

    innsending_org overstyrer org.nr. i XML (brukes i SKDs testmiljø der syntetisk
    org fra Tenor er påkrevd — sett SKD_TEST_ORG_NUMMER i .env).
    """
    s = oppgave.selskap
    org = innsending_org or s.org_nummer
    aar = oppgave.regnskapsaar
    totalt_aksjer = oppgave.totalt_antall_aksjer
    paalydende = (
        _format_paalydende(s.aksjekapital / totalt_aksjer)
        if totalt_aksjer > 0
        else "0"
    )
    stiftelsesdato = _stiftelsestidspunkt(s)

    # Fjorår-felter og stiftelsestransaksjon skal kun inkluderes i stiftelsesåret.
    # For påfølgende år er beholdningen uendret fra foregående år, og SKDs MTRA_004-regel
    # krever at transaksjonsdatoer er innenfor inntektsåret.
    er_stiftelsesaar = s.stiftelsesaar == aar
    fjoraret_aksjekapital = 0 if er_stiftelsesaar else round(s.aksjekapital)
    fjoraret_aksjer = 0 if er_stiftelsesaar else totalt_aksjer
    fjoraret_paalydende = "0" if er_stiftelsesaar else paalydende
    if er_stiftelsesaar:
        stiftelse_innhold = f"""
            <AksjerNyutstedteStiftelseMvAntall-datadef-17668 orid="17668">{totalt_aksjer}</AksjerNyutstedteStiftelseMvAntall-datadef-17668>
            <AksjerStiftelseMvAntall-datadef-17669 orid="17669">{totalt_aksjer}</AksjerStiftelseMvAntall-datadef-17669>
            <AksjerNyutstedteStiftelseMvType-datadef-17670 orid="17670">N</AksjerNyutstedteStiftelseMvType-datadef-17670>
            <AksjerNyutstedteStiftelseMvTidspunkt-datadef-17671 orid="17671">{stiftelsesdato}</AksjerNyutstedteStiftelseMvTidspunkt-datadef-17671>
            <AksjerNyutstedteStiftelseMvPalydende-datadef-23947 orid="23947">{paalydende}</AksjerNyutstedteStiftelseMvPalydende-datadef-23947>"""
    else:
        stiftelse_innhold = ""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Skjema skjemanummer="890" spesifikasjonsnummer="12144"
        blankettnummer="RF-1086" gruppeid="2586" etatid="974761076">
    <GenerellInformasjon-grp-2587 gruppeid="2587">
        <Selskap-grp-2588 gruppeid="2588">
            <EnhetOrganisasjonsnummer-datadef-18 orid="18">{escape(org)}</EnhetOrganisasjonsnummer-datadef-18>
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
            <AksjekapitalFjoraret-datadef-7129 orid="7129">{fjoraret_aksjekapital}</AksjekapitalFjoraret-datadef-7129>
            <Aksjekapital-datadef-87 orid="87">{round(s.aksjekapital)}</Aksjekapital-datadef-87>
        </AksjekapitalForHeleSelskapet-grp-3443>
        <AksjekapitalIDenneAksjeklassen-grp-3444 gruppeid="3444">
            <AksjekapitalISINAksjetypeFjoraret-datadef-17663 orid="17663">{fjoraret_aksjekapital}</AksjekapitalISINAksjetypeFjoraret-datadef-17663>
            <AksjekapitalISINAksjetype-datadef-17664 orid="17664">{round(s.aksjekapital)}</AksjekapitalISINAksjetype-datadef-17664>
        </AksjekapitalIDenneAksjeklassen-grp-3444>
        <PalydendePerAksje-grp-3447 gruppeid="3447">
            <AksjeMvPalydendeFjoraret-datadef-23944 orid="23944">{fjoraret_paalydende}</AksjeMvPalydendeFjoraret-datadef-23944>
            <AksjeMvPalydende-datadef-23945 orid="23945">{paalydende}</AksjeMvPalydende-datadef-23945>
        </PalydendePerAksje-grp-3447>
        <AntallAksjerIDenneAksjeklassen-grp-3445 gruppeid="3445">
            <AksjerMvAntallFjoraret-datadef-29166 orid="29166">{fjoraret_aksjer}</AksjerMvAntallFjoraret-datadef-29166>
            <AksjerMvAntall-datadef-29167 orid="29167">{totalt_aksjer}</AksjerMvAntall-datadef-29167>
        </AntallAksjerIDenneAksjeklassen-grp-3445>
        <InnbetaltAksjekapitalIDenneAksjeklassen-grp-3446 gruppeid="3446">
            <AksjekapitalInnbetaltFjoraret-datadef-8020 orid="8020">{fjoraret_aksjekapital}</AksjekapitalInnbetaltFjoraret-datadef-8020>
            <AksjekapitalInnbetalt-datadef-5867 orid="5867">{round(s.aksjekapital)}</AksjekapitalInnbetalt-datadef-5867>
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
        <AntallNyutstedteAksjer-grp-3453 gruppeid="3453">{stiftelse_innhold}
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
    aksjonaer: Aksjonaer, oppgave: Aksjonaerregisteroppgave, innsending_org: str = ""
) -> bytes:
    """
    Genererer RF-1086-U Underskjema XML for én aksjonær.

    Inneholder aksjonæridentifikasjon, beholdning og ervervstransaksjon.
    Valideres mot: aksjonaerregisteroppgaveUnderskjema.xsd
    """
    s = oppgave.selskap
    org = innsending_org or s.org_nummer
    aar = oppgave.regnskapsaar
    anskaffelsesverdi = round(aksjonaer.innbetalt_kapital_per_aksje * aksjonaer.antall_aksjer)
    stiftelsesdato = _stiftelsestidspunkt(s)

    # Transaksjoner skal kun inkluderes hvis stiftelsesåret er inntektsåret.
    # For påfølgende år er det ingen transaksjon — aksjonæren hadde samme beholdning
    # foregående år, og SKDs MTRA_004-regel krever at transaksjonsdatoer er innenfor
    # inntektsåret.
    er_stiftelsesaar = s.stiftelsesaar == aar
    fjoraret_aksjer = 0 if er_stiftelsesaar else aksjonaer.antall_aksjer
    if er_stiftelsesaar:
        tilgang_innhold = f"""
                <AksjerKjopAntall-datadef-12153 orid="12153">{aksjonaer.antall_aksjer}</AksjerKjopAntall-datadef-12153>
                <AksjeErvervType-datadef-17745 orid="17745">N</AksjeErvervType-datadef-17745>
                <AksjerErvervsdato-datadef-17746 orid="17746">{stiftelsesdato}</AksjerErvervsdato-datadef-17746>
                <AksjeAnskaffelsesverdi-datadef-17636 orid="17636">{anskaffelsesverdi}</AksjeAnskaffelsesverdi-datadef-17636>"""
    else:
        tilgang_innhold = ""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Skjema skjemanummer="923" spesifikasjonsnummer="12232"
        blankettnummer="RF-1086-U" tittel="Aksjonærregisteroppgaven - underskjema"
        gruppeid="3983" etatid="974761076">
    <SelskapsOgAksjonaropplysninger-grp-3987 gruppeid="3987">
        <Selskapsidentifikasjon-grp-3986 gruppeid="3986">
            <EnhetOrganisasjonsnummer-datadef-18 orid="18">{escape(org)}</EnhetOrganisasjonsnummer-datadef-18>
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
            <AksjerAntallFjoraret-datadef-29168 orid="29168">{fjoraret_aksjer}</AksjerAntallFjoraret-datadef-29168>
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
            <AntallAksjerITilgang-grp-3998 gruppeid="3998">{tilgang_innhold}
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


def _fnr_modulus11_ok(fnr: str) -> bool:
    """Sjekker modulus-11-kontrollsifrene i et 11-sifret norsk fødselsnummer.

    Returnerer False hvis kontrollsifrene ikke stemmer. Forutsetter at fnr
    allerede er 11 siffer (kallsiden sjekker det først).
    """
    vekter1 = [3, 7, 6, 1, 8, 9, 4, 5, 2]
    vekter2 = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    siffer = [int(c) for c in fnr]
    k1 = (11 - sum(v * d for v, d in zip(vekter1, siffer[:9])) % 11) % 11
    k2 = (11 - sum(v * d for v, d in zip(vekter2, siffer[:10])) % 11) % 11
    return k1 < 10 and k2 < 10 and k1 == siffer[9] and k2 == siffer[10]


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
        elif not _fnr_modulus11_ok(fnr):
            feil.append(
                f"Fødselsnummeret for {a.navn} har ugyldige kontrollsifre. "
                "Dobbeltsjekk at sifrene er korrekt skrevet inn."
            )

    total_aksjer = oppgave.totalt_antall_aksjer
    if total_aksjer <= 0:
        feil.append("Totalt antall aksjer må være større enn 0.")

    if oppgave.selskap.stiftelsesaar > oppgave.regnskapsaar:
        feil.append(
            f"stiftelsesaar ({oppgave.selskap.stiftelsesaar}) kan ikke være etter "
            f"regnskapsåret ({oppgave.regnskapsaar})."
        )

    # Ved stiftelse i inntektsåret må innbetalt_kapital_per_aksje være > 0,
    # ellers blir AnskaffelsesverdiSamlet i stiftelsestransaksjonen 0 og SKD avviser.
    if oppgave.selskap.stiftelsesaar == oppgave.regnskapsaar:
        for a in oppgave.aksjonaerer:
            if a.innbetalt_kapital_per_aksje <= 0:
                feil.append(
                    f"innbetalt_kapital_per_aksje må være > 0 for {a.navn} "
                    f"når selskapet er stiftet i inntektsåret ({oppgave.regnskapsaar})."
                )

        # Sum av aksjonærenes innbetalte kapital må matche selskapets aksjekapital
        # ved nyemisjon. SKDs MAKH_053-regel: post 9 (selskap) = post 23 (aksjonærer).
        sum_innbetalt = sum(
            a.innbetalt_kapital_per_aksje * a.antall_aksjer for a in oppgave.aksjonaerer
        )
        if round(sum_innbetalt) != round(oppgave.selskap.aksjekapital):
            feil.append(
                f"Sum innbetalt kapital fra aksjonærer ({round(sum_innbetalt):,} kr) "
                f"må matche selskapets aksjekapital ({round(oppgave.selskap.aksjekapital):,} kr) "
                "ved nyemisjon. Juster antall_aksjer eller innbetalt_kapital_per_aksje per "
                "aksjonær slik at summen blir lik aksjekapital."
            )

    return feil


def valider_mot_brg(
    oppgave: Aksjonaerregisteroppgave, *, timeout: float = 5.0
) -> list[str]:
    """
    Sjekker stiftelsesår mot Brønnøysundregistrene som ekstra forhåndsvalidering.

    Returnerer liste med advarsler hvis stiftelsesåret i config ikke stemmer
    med BRGs registrering. Tom liste hvis alt stemmer eller hvis BRG ikke
    kan kontaktes (transient feil skal ikke blokkere innsending).

    Brukes kun mot reelle org.nr. — syntetiske Tenor-orger finnes ikke i BRG.
    """
    orgnr = oppgave.selskap.org_nummer
    try:
        resp = httpx.get(
            f"{_BRG_ENHET_URL}/{orgnr}",
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        return []

    if resp.status_code == 404:
        return [
            f"Org.nr. {orgnr} ble ikke funnet i Brønnøysundregistrene. "
            "Sjekk at org.nr. er korrekt."
        ]
    if not resp.is_success:
        return []

    try:
        data = resp.json()
    except ValueError:
        return []

    stiftelsesdato = data.get("stiftelsesdato")
    if not stiftelsesdato or len(stiftelsesdato) < 4:
        return []

    try:
        brg_stiftelsesaar = int(stiftelsesdato[:4])
    except ValueError:
        return []

    if brg_stiftelsesaar != oppgave.selskap.stiftelsesaar:
        return [
            f"stiftelsesaar i config ({oppgave.selskap.stiftelsesaar}) stemmer "
            f"ikke med Brønnøysundregistrenes registrering ({brg_stiftelsesaar}). "
            "Dette er en vanlig årsak til avvikskode MAKS_025 fra Skatteetaten. "
            "Oppdater stiftelsesaar i config.yaml før innsending."
        ]

    return []


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

    env = os.getenv("WENCHE_ENV", "prod")
    innsending_org = os.getenv("SKD_TEST_ORG_NUMMER", "") if env == "test" else ""
    if innsending_org:
        print(f"Testmodus: bruker syntetisk org.nr. {innsending_org} i XML (SKD_TEST_ORG_NUMMER).")

    hoved_xml = generer_hovedskjema_xml(oppgave, innsending_org)
    print(f"RF-1086 Hovedskjema generert ({len(hoved_xml):,} bytes).")

    under_xmler = [generer_underskjema_xml(a, oppgave, innsending_org) for a in oppgave.aksjonaerer]
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
