"""
Innsending av årsregnskap til Brønnøysundregistrene via Altinn 3.
"""

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
                skyldige_offentlige_avgifter=_tall(kg.get("skyldige_offentlige_avgifter")),
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

    # Sammenligningstall for fjoråret er påkrevd etter regnskapsloven § 6-6 for
    # selskaper som ikke er nystiftet. Et selskap stiftet før regnskapsåret skal
    # ha et fjorår å sammenligne med; er fjorårstallene helt tomme, mangler de
    # sannsynligvis. (Ikke-blokkerende: et genuint hvilende selskap kan ha hatt
    # reelt null i fjor, så dette er et varsku, ikke en hard feil.)
    stiftelsesaar = regnskap.selskap.stiftelsesaar
    fb = regnskap.foregaaende_aar_balanse
    fjoraar_tomt = abs(fb.eiendeler.sum) < 0.01 and abs(fb.egenkapital_og_gjeld.sum) < 0.01
    if stiftelsesaar and stiftelsesaar < regnskap.regnskapsaar and fjoraar_tomt:
        adv.append(
            f"Selskapet ble stiftet i {stiftelsesaar}, men det er ikke oppgitt "
            f"sammenligningstall for fjoråret ({regnskap.regnskapsaar - 1}). "
            "Regnskapsloven § 6-6 krever sammenligningstall for selskaper som ikke "
            "er nystiftet. Fyll inn «Fjorårets tall», eller bekreft at fjoråret "
            "faktisk var null hvis selskapet var helt uten aktivitet."
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
