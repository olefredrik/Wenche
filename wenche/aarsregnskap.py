"""
Innsending av årsregnskap til Brønnøysundregistrene via Altinn 3.
"""

from datetime import date

import yaml

from wenche.altinn_client import AltinnClient
from wenche.models import (
    Aarsregnskap,
    Anleggsmidler,
    Balanse,
    Driftsinntekter,
    Driftskostnader,
    Eiendeler,
    Egenkapital,
    EgenkapitalOgGjeld,
    Finansposter,
    KortsiktigGjeld,
    LangsiktigGjeld,
    Omloepmidler,
    Resultatregnskap,
    Selskap,
)
from wenche.brg_xml import generer_aksjenote_vedlegg, generer_hovedskjema, generer_underskjema


def _tall(verdi) -> float:
    """Tolererer tomme og manglende tallfelt (None, "", whitespace) som 0.0, ellers float().

    Skjemaet utelater urørte (valgfrie) felt og sender tom streng for blanke. Et passivt
    holdingselskap har legitimt mange slike, særlig i fjorårstallene. Uten dette havnet en ""
    eller None i modellen og fikk summeringen til å kaste TypeError -> naken HTTP 500.
    """
    if verdi is None or (isinstance(verdi, str) and not verdi.strip()):
        return 0.0
    return float(verdi)


def _dato(verdi) -> date | None:
    """Tolererer tomme og manglende datofelt som None, ellers en date.

    YAML tolker en naken YYYY-MM-DD som date, mens skjemaet sender streng. Begge godtas.
    En ugyldig dato blir en lesbar feil, ikke en naken ValueError fra fromisoformat.
    """
    if verdi is None or (isinstance(verdi, str) and not verdi.strip()):
        return None
    if isinstance(verdi, date):
        return verdi
    tekst = str(verdi).strip()
    # En ISO-datetime ("2025-10-24T00:00:00.000Z") er ikke noe skjemaet sender, men den
    # oppstår når et JS Date serialiseres til JSON. Kilden er rettet (SPA-en parser YAML
    # med CORE_SCHEMA), men gamle lagrede configer kan bære formen, og en dato med
    # tidsdel er utvetydig nok til å ta imot i stedet for å avvise med formatfeil.
    if "T" in tekst:
        tekst = tekst.split("T", 1)[0]
    try:
        return date.fromisoformat(tekst)
    except ValueError:
        raise ValueError(f"«{verdi}» er ikke en gyldig dato. Bruk formatet ÅÅÅÅ-MM-DD.")


def _les_resultat(r: dict) -> Resultatregnskap:
    # .get(..., {}) på hver underseksjon: et delvis utfylt år (typisk fjoråret) utelater hele
    # seksjoner brukeren ikke rørte, så et direkte oppslag ville kastet KeyError -> 500.
    di = r.get("driftsinntekter", {})
    dk = r.get("driftskostnader", {})
    fp = r.get("finansposter", {})
    return Resultatregnskap(
        driftsinntekter=Driftsinntekter(
            salgsinntekter=_tall(di.get("salgsinntekter")),
            andre_driftsinntekter=_tall(di.get("andre_driftsinntekter")),
        ),
        driftskostnader=Driftskostnader(
            loennskostnader=_tall(dk.get("loennskostnader")),
            avskrivninger=_tall(dk.get("avskrivninger")),
            andre_driftskostnader=_tall(dk.get("andre_driftskostnader")),
        ),
        finansposter=Finansposter(
            utbytte_fra_datterselskap=_tall(fp.get("utbytte_fra_datterselskap")),
            andre_finansinntekter=_tall(fp.get("andre_finansinntekter")),
            rentekostnader=_tall(fp.get("rentekostnader")),
            andre_finanskostnader=_tall(fp.get("andre_finanskostnader")),
        ),
        skattekostnad=_tall(r.get("skattekostnad")),
    )


def _les_balanse(b: dict) -> Balanse:
    eiendeler = b.get("eiendeler", {})
    am = eiendeler.get("anleggsmidler", {})
    om = eiendeler.get("omloepmidler", {})
    ekg = b.get("egenkapital_og_gjeld", {})
    ek = ekg.get("egenkapital", {})
    lg = ekg.get("langsiktig_gjeld", {})
    kg = ekg.get("kortsiktig_gjeld", {})
    return Balanse(
        eiendeler=Eiendeler(
            anleggsmidler=Anleggsmidler(
                aksjer_i_datterselskap=_tall(am.get("aksjer_i_datterselskap")),
                andre_aksjer=_tall(am.get("andre_aksjer")),
                langsiktige_fordringer=_tall(am.get("langsiktige_fordringer")),
            ),
            omloepmidler=Omloepmidler(
                kortsiktige_fordringer=_tall(om.get("kortsiktige_fordringer")),
                bankinnskudd=_tall(om.get("bankinnskudd")),
            ),
        ),
        egenkapital_og_gjeld=EgenkapitalOgGjeld(
            egenkapital=Egenkapital(
                aksjekapital=_tall(ek.get("aksjekapital")),
                overkursfond=_tall(ek.get("overkursfond")),
                annen_egenkapital=_tall(ek.get("annen_egenkapital")),
            ),
            langsiktig_gjeld=LangsiktigGjeld(
                laan_fra_aksjonaer=_tall(lg.get("laan_fra_aksjonaer")),
                andre_langsiktige_laan=_tall(lg.get("andre_langsiktige_laan")),
            ),
            kortsiktig_gjeld=KortsiktigGjeld(
                leverandoergjeld=_tall(kg.get("leverandoergjeld")),
                betalbar_skatt=_tall(kg.get("betalbar_skatt")),
                skyldige_offentlige_avgifter=_tall(kg.get("skyldige_offentlige_avgifter")),
                avsatt_utbytte=_tall(kg.get("avsatt_utbytte")),
                annen_kortsiktig_gjeld=_tall(kg.get("annen_kortsiktig_gjeld")),
            ),
        ),
    )


def les_config(config_fil: str | dict) -> Aarsregnskap:
    """Leser config (filsti eller allerede parset dict) og returnerer et Aarsregnskap-objekt."""
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
        stiftelsesdato=_dato(s.get("stiftelsesdato")),
        tinginnskudd_ved_stiftelse=_tall(s.get("tinginnskudd_ved_stiftelse")),
    )

    resultat = _les_resultat(cfg["resultatregnskap"])
    balanse = _les_balanse(cfg["balanse"])

    fa = cfg.get("foregaaende_aar", {})
    foregaaende_resultat = _les_resultat(fa["resultatregnskap"]) if "resultatregnskap" in fa else Resultatregnskap()
    foregaaende_balanse = _les_balanse(fa["balanse"]) if "balanse" in fa else Balanse()

    utbytte_utbetalt = sum(
        float(a.get("utbytte_utbetalt", 0)) for a in cfg.get("aksjonaerer", [])
    )

    return Aarsregnskap(
        selskap=selskap,
        regnskapsaar=cfg["regnskapsaar"],
        resultatregnskap=resultat,
        balanse=balanse,
        foregaaende_aar_resultat=foregaaende_resultat,
        foregaaende_aar_balanse=foregaaende_balanse,
        utbytte_utbetalt=utbytte_utbetalt,
        regnskapsstart=_dato(cfg.get("regnskapsstart")),
        regnskapsslutt=_dato(cfg.get("regnskapsslutt")),
    )


def valider(regnskap: Aarsregnskap) -> list[str]:
    """
    Validerer regnskapet og returnerer en liste med feilmeldinger.
    Tom liste betyr OK.
    """
    feil = []

    if not regnskap.balanse.er_i_balanse():
        diff = regnskap.balanse.differanse()
        feil.append(
            f"Balansen går ikke opp: eiendeler og egenkapital+gjeld "
            f"avviker med {diff:+,.2f} NOK."
        )

    if len(regnskap.selskap.org_nummer.replace(" ", "")) != 9:
        feil.append("Organisasjonsnummeret må være 9 siffer.")

    feil.extend(_valider_periode(regnskap))
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
        return [
            f"Tinginnskudd ved stiftelse kan ikke være negativt "
            f"({tinginnskudd:,.2f} NOK)."
        ]

    if not regnskap.er_foerste_regnskapsaar:
        # Ikke en feil: en config som bæres videre fra år til år (typisk fra Bodil) tar
        # feltet med seg, og da skal innsendingen gå. Advarselen forklarer at det ignoreres.
        return []

    ek = regnskap.balanse.egenkapital_og_gjeld.egenkapital
    fek = regnskap.foregaaende_aar_balanse.egenkapital_og_gjeld.egenkapital
    innskudd = (ek.aksjekapital + ek.overkursfond) - (
        fek.aksjekapital + fek.overkursfond
    )
    if tinginnskudd > innskudd + 0.01:
        return [
            f"Tinginnskudd ved stiftelse ({tinginnskudd:,.2f} NOK) er større enn økningen "
            f"i innskutt egenkapital ({innskudd:,.2f} NOK). Tinginnskuddet er den delen av "
            "aksjekapital og overkursfond som ble skutt inn som ting, ikke et beløp i "
            "tillegg til den."
        ]

    return []


def _valider_periode(regnskap: Aarsregnskap) -> list[str]:
    """
    Kontrollerer regnskapsperioden. Tom liste betyr OK.

    Perioden er normalt kalenderåret (rskl. § 1-7 første ledd). Andre ledd åpner for et
    forlenget første regnskapsår på inntil 18 måneder ved oppstart, og da må start- og
    sluttdato oppgis. Reglene her er de som må holde for at både Brønnøysund og
    Skatteetaten skal kunne tolke perioden entydig.
    """
    feil = []
    start, slutt = regnskap.periode_start, regnskap.periode_slutt

    if slutt < start:
        feil.append(
            f"Regnskapsperioden slutter før den starter ({start.isoformat()} til "
            f"{slutt.isoformat()}). Kontroller regnskapsstart og regnskapsslutt."
        )
        return feil  # De øvrige kontrollene er meningsløse på en snudd periode.

    if regnskap.periode_maaneder > 18:
        feil.append(
            f"Regnskapsperioden er {regnskap.periode_maaneder} måneder "
            f"({start.isoformat()} til {slutt.isoformat()}). Regnskapsloven § 1-7 tillater "
            "inntil 18 måneder, og bare for det første regnskapsåret."
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

    # Et forlenget første regnskapsår skal starte på stiftelsesdatoen (rskl. § 1-7 andre
    # ledd). Avviker de to, er sannsynligvis én av dem feil skrevet inn.
    stiftet = regnskap.selskap.stiftelsesdato
    if stiftet and regnskap.regnskapsstart and regnskap.regnskapsstart != stiftet:
        adv.append(
            f"Regnskapsperioden starter {regnskap.regnskapsstart.isoformat()}, men selskapet "
            f"ble stiftet {stiftet.isoformat()}. Et forlenget første regnskapsår løper fra "
            "stiftelsesdatoen. Kontroller datoene."
        )

    # En periode over 12 måneder er lovlig for det første regnskapsåret, og Skatteetaten
    # godtar den (validertOK mot tt02 2026-08-05 for en 14-måneders periode, med inntektsår
    # lik året perioden avsluttes). Advarselen står likevel: dette er et sjeldent tilfelle,
    # og hele perioden fastsettes da i ett inntektsår.
    if regnskap.periode_maaneder > 12:
        adv.append(
            f"Regnskapsperioden er {regnskap.periode_maaneder} måneder "
            f"({regnskap.periode_start.isoformat()} til {regnskap.periode_slutt.isoformat()}), "
            f"altså et forlenget første regnskapsår. Hele perioden fastsettes i inntektsår "
            f"{regnskap.regnskapsaar}. Kontroller at det stemmer med det selskapet har avtalt "
            "med Skatteetaten."
        )

    # Sammenligningstall for fjoråret er påkrevd etter regnskapsloven § 6-6 for
    # selskaper som ikke er nystiftet. Et selskap stiftet før regnskapsåret skal
    # ha et fjorår å sammenligne med; er fjorårstallene helt tomme, mangler de
    # sannsynligvis. (Ikke-blokkerende: et genuint hvilende selskap kan ha hatt
    # reelt null i fjor, så dette er et varsku, ikke en hard feil.)
    #
    # Unntaket er et forlenget første regnskapsår: det spenner over to kalenderår, så
    # stiftelsesåret er lavere enn regnskapsåret selv om dette ER det første regnskapsåret og
    # det ikke finnes noe fjorår å sammenligne med. Uten unntaket ba Wenche om
    # sammenligningstall som ikke eksisterer.
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


def send_inn(regnskap: Aarsregnskap, klient: AltinnClient, dry_run: bool = False) -> str | None:
    """
    Sender inn årsregnskapet til Brønnøysundregistrene via Altinn.

    Flyten er:
      1. Opprett instans → Altinn oppretter data-elementer automatisk
      2. PUT Hovedskjema (selskapsinfo, periode, prinsipper)
      3. PUT Underskjema (resultatregnskap og balanse)
      4. process/next (uten action) → avanserer til Signering

    Returnerer Altinn-lenken der brukeren må signere med BankID/ID-Porten.
    Signering kan ikke gjøres maskinelt — dette er et juridisk krav.

    dry_run=True skriver XML-filene lokalt uten å sende til Altinn.
    """
    feil = valider(regnskap)
    if feil:
        print("\nValidering mislyktes:")
        for f in feil:
            print(f"  - {f}")
        raise SystemExit(1)

    print("Validering OK.")

    for a in advarsler(regnskap):
        print(f"  ADVARSEL: {a}")

    hovedskjema = generer_hovedskjema(regnskap)
    underskjema = generer_underskjema(regnskap)
    org = regnskap.selskap.org_nummer
    aar = regnskap.regnskapsaar
    print(f"XML generert: Hovedskjema {len(hovedskjema):,} bytes, Underskjema {len(underskjema):,} bytes.")

    if dry_run:
        hoved_fil = f"aarsregnskap_{aar}_{org}_hovedskjema.xml"
        under_fil = f"aarsregnskap_{aar}_{org}_underskjema.xml"
        with open(hoved_fil, "wb") as f:
            f.write(hovedskjema)
        with open(under_fil, "wb") as f:
            f.write(underskjema)
        print(f"Dry-run: filer lagret til {hoved_fil} og {under_fil} — ingenting sendt til Altinn.")
        return

    print("Sender årsregnskap til Brønnøysundregistrene via Altinn...")
    instans = klient.opprett_instans("aarsregnskap", org)

    klient.oppdater_data_element(
        "aarsregnskap", instans,
        data_type="Hovedskjema",
        data=hovedskjema,
        content_type="application/xml",
    )
    print("Hovedskjema lastet opp.")

    klient.oppdater_data_element(
        "aarsregnskap", instans,
        data_type="Underskjema",
        data=underskjema,
        content_type="application/xml",
    )
    print("Underskjema lastet opp.")

    if regnskap.balanse.eiendeler.anleggsmidler.andre_aksjer > 0:
        vedlegg = generer_aksjenote_vedlegg(regnskap)
        vedlegg_element = klient.last_opp_vedlegg(
            "aarsregnskap", instans,
            data=vedlegg,
            content_type="application/pdf",
            filnavn=f"aksjenote_{aar}_{org}.pdf",
        )
        print("Aksjenote (Vedlegg) lastet opp. Venter på virusskanning...")
        klient.vent_paa_filskanning("aarsregnskap", instans, vedlegg_element["id"])
        print("Virusskanning fullført.")

    inbox_url = klient.fullfoor_instans("aarsregnskap", instans)

    print(f"Årsregnskap lastet opp og klar for signering.")
    print(f"Finn skjemaet i Altinn-innboksen og signer der: {inbox_url}")
    return inbox_url
