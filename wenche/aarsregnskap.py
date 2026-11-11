"""
Innsending av årsregnskap til Brønnøysundregistrene via Altinn 3.
"""

import logging

from wenche import konfig
from wenche.altinn_client import AltinnClient
from wenche.brg_xml import generer_aksjenote_vedlegg, generer_hovedskjema, generer_underskjema
from wenche.feil import ValideringsFeil
from wenche.models import (
    Aarsregnskap,
)
from wenche.naeringsspesifikasjon_xml import egenkapitalavstemming

# Lesingen bor i wenche.konfig (delt av alle tre innsendingene). Navnene under er beholdt for
# eldre kallsteder og tester.
_tall = konfig.tall
_dato = konfig.dato
_les_resultat = konfig.les_resultat
_les_balanse = konfig.les_balanse


def les_config(config_fil: str | dict) -> Aarsregnskap:
    """Leser config (filsti eller alt parset dict) til et Aarsregnskap. Se wenche.konfig."""
    return konfig.les_aarsregnskap(konfig.les_raa(config_fil))


def valider(regnskap: Aarsregnskap) -> list[str]:
    """
    Validerer regnskapet og returnerer en liste med feilmeldinger.
    Tom liste betyr OK.
    """
    feil = []

    if not regnskap.balanse.er_i_balanse():
        diff = regnskap.balanse.differanse()
        feil.append(
            f"Balansen går ikke opp: eiendeler og egenkapital+gjeld avviker med {diff:+,.2f} NOK."
        )

    if len(regnskap.selskap.org_nummer.replace(" ", "")) != 9:
        feil.append("Organisasjonsnummeret må være 9 siffer.")

    feil.extend(valider_periode(regnskap))
    feil.extend(_valider_tinginnskudd(regnskap))

    return feil


def _valider_tinginnskudd(regnskap: Aarsregnskap) -> list[str]:
    """
    Kontrollerer tinginnskuddet mot stiftelsesinnskuddet. Tom liste betyr OK.

    Tinginnskuddet er en oppdeling av økningen i innskutt egenkapital, ikke et beløp som
    kommer i tillegg til den. Er det større enn økningen, er minst ett av tallene feil, og
    egenkapitalavstemmingen ville rapportert et tinginnskudd selskapet ikke har hatt.
    """
    tinginnskudd = regnskap.selskap.tinginnskudd_ved_stiftelse
    if not tinginnskudd:
        return []

    if tinginnskudd < 0:
        return [f"Tinginnskudd ved stiftelse kan ikke være negativt ({tinginnskudd:,.2f} NOK)."]

    if not regnskap.er_foerste_regnskapsaar:
        # Ikke en feil: en config som bæres videre fra år til år (typisk fra Bodil) tar
        # feltet med seg, og da skal innsendingen gå. Advarselen forklarer at det ignoreres.
        return []

    ek = regnskap.balanse.egenkapital_og_gjeld.egenkapital
    fek = regnskap.foregaaende_aar_balanse.egenkapital_og_gjeld.egenkapital
    innskudd = (ek.aksjekapital + ek.overkursfond) - (fek.aksjekapital + fek.overkursfond)
    if tinginnskudd > innskudd + 0.01:
        return [
            f"Tinginnskudd ved stiftelse ({tinginnskudd:,.2f} NOK) er større enn økningen "
            f"i innskutt egenkapital ({innskudd:,.2f} NOK). Tinginnskuddet er den delen av "
            "aksjekapital og overkursfond som ble skutt inn som ting, ikke et beløp i "
            "tillegg til den."
        ]

    return []


def valider_periode(regnskap: Aarsregnskap) -> list[str]:
    """
    Kontrollerer regnskapsperioden. Tom liste betyr OK.

    Perioden er normalt kalenderåret (rskl. § 1-7 første ledd). Et selskap stiftet i løpet
    av året har et kort første regnskapsår fra stiftelsesdatoen, og da må start- og
    sluttdato oppgis. Reglene her er de som må holde for at både Brønnøysund og
    Skatteetaten skal kunne tolke perioden entydig.

    Forlenget første regnskapsår (§ 1-7 andre ledd) støttes ikke. Det spenner over to
    kalenderår, mens skattemeldingen leveres per inntektsår, som er kalenderåret
    (skatteloven § 14-1). Wenche bygger årsregnskap og skattemelding fra samme periode, så
    en periode over to år ville gitt en skattemelding for feil periode og ingen for
    stiftelsesåret.
    """
    feil = []
    start, slutt = regnskap.periode_start, regnskap.periode_slutt

    if slutt < start:
        feil.append(
            f"Regnskapsperioden slutter før den starter ({start.isoformat()} til "
            f"{slutt.isoformat()}). Kontroller regnskapsstart og regnskapsslutt."
        )
        return feil  # De øvrige kontrollene er meningsløse på en snudd periode.

    if start.year != slutt.year:
        feil.append(
            f"Regnskapsperioden går over to kalenderår ({start.isoformat()} til "
            f"{slutt.isoformat()}). Wenche støtter ikke forlenget første regnskapsår, fordi "
            "skattemeldingen skal leveres for hvert kalenderår. Bruk et kort første "
            "regnskapsår fra stiftelsesdatoen til 31. desember samme år."
        )

    if (slutt.month, slutt.day) != (12, 31):
        feil.append(
            f"Regnskapsperioden slutter {slutt.isoformat()}, ikke 31. desember. Wenche "
            "støtter bare regnskapsår som avsluttes ved kalenderårets slutt."
        )

    if slutt.year != regnskap.regnskapsaar:
        feil.append(
            f"Regnskapsåret er oppgitt som {regnskap.regnskapsaar}, men perioden avsluttes i "
            f"{slutt.year}. Regnskapsåret skal være året perioden avsluttes."
        )

    return feil


def advarsler(regnskap: Aarsregnskap) -> list[str]:
    """
    Ikke-blokkerende advarsler om forhold som ikke gjør innsendingen ugyldig,
    men som ofte tyder på en feil i tallene. Tom liste betyr ingen advarsler.

    I motsetning til valider() stopper ikke disse innsendingen. De er ment som
    et varsku som brukeren (eller et verktøy som genererer config.yaml) kan lene
    seg på.
    """
    adv = []

    # Utbytte kan bare deles ut av fri egenkapital (aksjeloven § 8-1). Fri
    # egenkapital = overkursfond + annen egenkapital (aksjekapital er bundet).
    # I modellen reduserer utbytte annen_egenkapital, så hvis utdelingen
    # overstiger det utdelbare, blir fri egenkapital negativ etter utdelingen.
    ek = regnskap.balanse.egenkapital_og_gjeld.egenkapital
    fri_egenkapital = ek.overkursfond + ek.annen_egenkapital
    # Både en utbetaling og en avsetning er en utdeling etter § 8-1: avsetningen er allerede
    # trukket fra annen egenkapital, så den kan gjøre fri egenkapital negativ helt alene.
    avsatt_utbytte = regnskap.balanse.egenkapital_og_gjeld.kortsiktig_gjeld.avsatt_utbytte
    if avsatt_utbytte > 0 and fri_egenkapital < -0.01:
        adv.append(
            f"Det er avsatt utbytte ({avsatt_utbytte:,.0f} NOK), men fri egenkapital etter "
            f"avsetningen er negativ ({fri_egenkapital:,.0f} NOK). Utbytte kan bare deles ut "
            "av fri egenkapital (aksjeloven § 8-1). Kontroller avsetningen mot siste "
            "godkjente årsregnskap."
        )
    if regnskap.utbytte_utbetalt > 0 and fri_egenkapital < -0.01:
        adv.append(
            f"Det er utbetalt utbytte ({regnskap.utbytte_utbetalt:,.0f} NOK), men "
            f"fri egenkapital etter utdelingen er negativ ({fri_egenkapital:,.0f} "
            "NOK). Utbytte kan bare deles ut av fri egenkapital (aksjeloven § 8-1). "
            "Kontroller at utbetalingen faktisk er utbytte og ikke f.eks. lån til "
            "aksjonær eller tilbakebetaling av innbetalt kapital."
        )

    # Skattekostnaden i resultatregnskapet har en motpost i balansen: er skatten ikke
    # betalt ved årsslutt (normaltilfellet, den forfaller året etter), skal den stå som
    # betalbar skatt under kortsiktig gjeld. Er den ført som kostnad uten å stå noe sted i
    # balansen, mangler enten gjelden eller en tilsvarende reduksjon i bankinnskuddet.
    # (Ikke-blokkerende: skatten kan være betalt i året, og da er det bankinnskuddet som er
    # redusert. Balansekontrollen i valider() fanger opp om totalene ikke går opp.)
    kg = regnskap.balanse.egenkapital_og_gjeld.kortsiktig_gjeld
    if regnskap.resultatregnskap.skattekostnad > 0.01 and kg.betalbar_skatt < 0.01:
        adv.append(
            f"Det er ført en skattekostnad "
            f"({regnskap.resultatregnskap.skattekostnad:,.0f} NOK), men betalbar skatt "
            "står ikke i balansen. Er skatten ikke betalt ved årsslutt, skal den føres "
            "som «Betalbar skatt» under kortsiktig gjeld (konto 2500)."
        )

    # Et kort første regnskapsår skal starte på stiftelsesdatoen. Avviker de to, er
    # sannsynligvis én av dem feil skrevet inn.
    stiftet = regnskap.selskap.stiftelsesdato
    if stiftet and regnskap.regnskapsstart and regnskap.regnskapsstart != stiftet:
        adv.append(
            f"Regnskapsperioden starter {regnskap.regnskapsstart.isoformat()}, men selskapet "
            f"ble stiftet {stiftet.isoformat()}. Et kort første regnskapsår løper fra "
            "stiftelsesdatoen. Kontroller datoene."
        )

    # Sammenligningstall for fjoråret er påkrevd etter regnskapsloven § 6-6 for
    # selskaper som ikke er nystiftet. Et selskap stiftet før regnskapsåret skal
    # ha et fjorår å sammenligne med; er fjorårstallene helt tomme, mangler de
    # sannsynligvis. (Ikke-blokkerende: et genuint hvilende selskap kan ha hatt
    # reelt null i fjor, så dette er et varsku, ikke en hard feil.)
    stiftelsesaar = regnskap.selskap.stiftelsesaar
    fb = regnskap.foregaaende_aar_balanse
    fjoraar_tomt = abs(fb.eiendeler.sum) < 0.01 and abs(fb.egenkapital_og_gjeld.sum) < 0.01
    if stiftelsesaar and not regnskap.er_foerste_regnskapsaar and fjoraar_tomt:
        adv.append(
            f"Selskapet ble stiftet i {stiftelsesaar}, men det er ikke oppgitt "
            f"sammenligningstall for fjoråret ({regnskap.regnskapsaar - 1}). "
            "Regnskapsloven § 6-6 krever sammenligningstall for selskaper som ikke "
            "er nystiftet. Fyll inn «Fjorårets tall», eller bekreft at fjoråret "
            "faktisk var null hvis selskapet var helt uten aktivitet."
        )

    # Det årsresultat, innskudd og utbytte ikke forklarer av endringen i egenkapitalen, sendes
    # som «annen endring i egenkapital» i skattemeldingen, og Skatteetaten reagerer først etter
    # innsending (N_AVVIK_ÅRSRESULTAT_EGENKAPITALAVSTEMMING). Bruker samme regnestykke som
    # næringsspesifikasjonen, så advarselen og innsendingen ikke kan drifte fra hverandre.
    # Hoppes over når fjorårstallene mangler helt: da er hele egenkapitalen uforklart, og
    # fjorårsadvarselen over sier allerede hva som er galt. (Ikke-blokkerende: en legitim
    # annen endring er sjelden for et passivt holdingselskap, men mulig.)
    if regnskap.er_foerste_regnskapsaar or not fjoraar_tomt:
        _, _, tillegg, fradrag = egenkapitalavstemming(regnskap)
        uforklart = sum(b for k, b in tillegg if k == "annenPositivEndringIEgenkapital") - sum(
            b for k, b in fradrag if k == "annenNegativEndringIEgenkapital"
        )
        if abs(uforklart) > 1:
            retning = "økt" if uforklart > 0 else "falt"
            adv.append(
                f"Egenkapitalen har {retning} {abs(uforklart):,.0f} NOK mer enn årsresultatet, "
                "innskudd og utbytte forklarer. Beløpet sendes som «annen endring i "
                "egenkapital» i skattemeldingen, og Skatteetaten reagerer gjerne på det. "
                "Vanlige årsaker er et resultattall som mangler eller er feil, et utbytte som "
                "ikke er ført, fjorårstall som ikke stemmer med fjorårets årsregnskap, eller "
                "en config med felt denne Wenche-versjonen ikke kjenner (oppgrader da Wenche)."
            )

    # Utbytte fra et selskap selskapet eier under 20 % av, kommer verken fra et datterselskap
    # eller et tilknyttet selskap og skal på egen linje i årsregnskapet. Står utbyttet som
    # utbytte fra datterselskap uten at balansen har aksjer i datterselskap, verken i år eller
    # i fjor, er det sannsynligvis feil linje. Unntaket er et tilknyttet selskap (20 % eller
    # mer): modellen har ingen egen balanselinje for det, så aksjene står under andre aksjer,
    # mens utbyttet med rette står på linjen for datterselskap og tilknyttet selskap.
    # (Ikke-blokkerende: datterselskapet kan være solgt, og skatten blir den samme.)
    fp = regnskap.resultatregnskap.finansposter
    am = regnskap.balanse.eiendeler.anleggsmidler
    fam = regnskap.foregaaende_aar_balanse.eiendeler.anleggsmidler
    if (
        fp.utbytte_fra_datterselskap > 0.01
        and am.aksjer_i_datterselskap < 0.01
        and fam.aksjer_i_datterselskap < 0.01
        and (regnskap.eierandel_for_utbytte is None or regnskap.eierandel_for_utbytte < 20)
    ):
        adv.append(
            f"Det er ført utbytte fra datterselskap "
            f"({fp.utbytte_fra_datterselskap:,.0f} NOK), men balansen har ingen aksjer i "
            "datterselskap, verken i år eller i fjor. Eier selskapet under 20 % av selskapet "
            "som delte ut, er det verken datterselskap eller tilknyttet selskap, og utbyttet "
            "skal føres som «Utbytte fra andre aksjer» (utbytte_fra_andre_aksjer). Er det "
            "et tilknyttet selskap (20 % eller mer), er linjen riktig."
        )

    # Tinginnskuddet hører til stiftelsen. Står det igjen i en config som bæres videre til
    # senere år, blir det stille ignorert, og da skal brukeren få vite det.
    if regnskap.selskap.tinginnskudd_ved_stiftelse > 0 and not regnskap.er_foerste_regnskapsaar:
        adv.append(
            f"Tinginnskudd ved stiftelse "
            f"({regnskap.selskap.tinginnskudd_ved_stiftelse:,.0f} NOK) er oppgitt, men "
            f"{regnskap.regnskapsaar} er ikke selskapets første regnskapsår. Feltet gjelder "
            "bare stiftelsesinnskuddet og påvirker ikke denne innsendingen. Det kan fjernes."
        )

    return adv


log = logging.getLogger(__name__)


def bygg_filer(regnskap: Aarsregnskap) -> dict[str, bytes]:
    """
    XML-dokumentene årsregnskapet består av, med filnavn: hovedskjema (RR-0002) og underskjema
    (RR-0002U). Ren bygging, uten validering, nettverk eller disk; brukes av dry-run i CLI-en
    og av dokument-nedlastingen i begge webgrensesnittene.
    """
    base = f"aarsregnskap_{regnskap.regnskapsaar}_{regnskap.selskap.org_nummer}"
    return {
        f"{base}_hovedskjema.xml": generer_hovedskjema(regnskap),
        f"{base}_underskjema.xml": generer_underskjema(regnskap),
    }


def send_inn(regnskap: Aarsregnskap, klient: AltinnClient) -> str:
    """
    Sender inn årsregnskapet til Brønnøysundregistrene via Altinn.

    Flyten er:
      1. Opprett instans (Altinn oppretter data-elementer automatisk)
      2. PUT Hovedskjema (selskapsinfo, periode, prinsipper)
      3. PUT Underskjema (resultatregnskap og balanse)
      4. process/next (uten action) avanserer til Signering

    Returnerer Altinn-lenken der brukeren må signere med BankID/ID-Porten.
    Signering kan ikke gjøres maskinelt; det er et juridisk krav.

    Kaster ValideringsFeil ved blokkerende feil, før noe sendes. Fremdrift og
    ikke-blokkerende advarsler logges (CLI-en viser dem på stderr).
    """
    feil = valider(regnskap)
    if feil:
        raise ValideringsFeil(feil)
    log.info("Validering OK.")
    for a in advarsler(regnskap):
        log.warning("ADVARSEL: %s", a)

    hovedskjema = generer_hovedskjema(regnskap)
    underskjema = generer_underskjema(regnskap)
    org = regnskap.selskap.org_nummer
    aar = regnskap.regnskapsaar
    log.info(
        "XML generert: Hovedskjema %s bytes, Underskjema %s bytes.",
        f"{len(hovedskjema):,}",
        f"{len(underskjema):,}",
    )

    log.info("Sender årsregnskap til Brønnøysundregistrene via Altinn...")
    instans = klient.opprett_instans("aarsregnskap", org)

    klient.oppdater_data_element(
        "aarsregnskap",
        instans,
        data_type="Hovedskjema",
        data=hovedskjema,
        content_type="application/xml",
    )
    log.info("Hovedskjema lastet opp.")

    klient.oppdater_data_element(
        "aarsregnskap",
        instans,
        data_type="Underskjema",
        data=underskjema,
        content_type="application/xml",
    )
    log.info("Underskjema lastet opp.")

    if regnskap.balanse.eiendeler.anleggsmidler.andre_aksjer > 0:
        vedlegg = generer_aksjenote_vedlegg(regnskap)
        vedlegg_element = klient.last_opp_vedlegg(
            "aarsregnskap",
            instans,
            data=vedlegg,
            content_type="application/pdf",
            filnavn=f"aksjenote_{aar}_{org}.pdf",
        )
        log.info("Aksjenote (Vedlegg) lastet opp. Venter på virusskanning...")
        klient.vent_paa_filskanning("aarsregnskap", instans, vedlegg_element["id"])
        log.info("Virusskanning fullført.")

    inbox_url = klient.fullfoor_instans("aarsregnskap", instans)
    log.info("Årsregnskap lastet opp og klar for signering.")
    log.info("Finn skjemaet i Altinn-innboksen og signer der: %s", inbox_url)
    return inbox_url
