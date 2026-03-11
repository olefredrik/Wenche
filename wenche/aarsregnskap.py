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
from wenche.brg_xml import generer_hovedskjema, generer_underskjema


def _les_resultat(r: dict) -> Resultatregnskap:
    return Resultatregnskap(
        driftsinntekter=Driftsinntekter(
            salgsinntekter=r["driftsinntekter"].get("salgsinntekter", 0),
            andre_driftsinntekter=r["driftsinntekter"].get("andre_driftsinntekter", 0),
        ),
        driftskostnader=Driftskostnader(
            loennskostnader=r["driftskostnader"].get("loennskostnader", 0),
            avskrivninger=r["driftskostnader"].get("avskrivninger", 0),
            andre_driftskostnader=r["driftskostnader"].get("andre_driftskostnader", 0),
        ),
        finansposter=Finansposter(
            utbytte_fra_datterselskap=r["finansposter"].get("utbytte_fra_datterselskap", 0),
            andre_finansinntekter=r["finansposter"].get("andre_finansinntekter", 0),
            rentekostnader=r["finansposter"].get("rentekostnader", 0),
            andre_finanskostnader=r["finansposter"].get("andre_finanskostnader", 0),
        ),
    )


def _les_balanse(b: dict) -> Balanse:
    return Balanse(
        eiendeler=Eiendeler(
            anleggsmidler=Anleggsmidler(
                aksjer_i_datterselskap=b["eiendeler"]["anleggsmidler"].get("aksjer_i_datterselskap", 0),
                andre_aksjer=b["eiendeler"]["anleggsmidler"].get("andre_aksjer", 0),
                langsiktige_fordringer=b["eiendeler"]["anleggsmidler"].get("langsiktige_fordringer", 0),
            ),
            omloepmidler=Omloepmidler(
                kortsiktige_fordringer=b["eiendeler"]["omloepmidler"].get("kortsiktige_fordringer", 0),
                bankinnskudd=b["eiendeler"]["omloepmidler"].get("bankinnskudd", 0),
            ),
        ),
        egenkapital_og_gjeld=EgenkapitalOgGjeld(
            egenkapital=Egenkapital(
                aksjekapital=b["egenkapital_og_gjeld"]["egenkapital"].get("aksjekapital", 0),
                overkursfond=b["egenkapital_og_gjeld"]["egenkapital"].get("overkursfond", 0),
                annen_egenkapital=b["egenkapital_og_gjeld"]["egenkapital"].get("annen_egenkapital", 0),
            ),
            langsiktig_gjeld=LangsiktigGjeld(
                laan_fra_aksjonaer=b["egenkapital_og_gjeld"]["langsiktig_gjeld"].get("laan_fra_aksjonaer", 0),
                andre_langsiktige_laan=b["egenkapital_og_gjeld"]["langsiktig_gjeld"].get("andre_langsiktige_laan", 0),
            ),
            kortsiktig_gjeld=KortsiktigGjeld(
                leverandoergjeld=b["egenkapital_og_gjeld"]["kortsiktig_gjeld"].get("leverandoergjeld", 0),
                skyldige_offentlige_avgifter=b["egenkapital_og_gjeld"]["kortsiktig_gjeld"].get("skyldige_offentlige_avgifter", 0),
                annen_kortsiktig_gjeld=b["egenkapital_og_gjeld"]["kortsiktig_gjeld"].get("annen_kortsiktig_gjeld", 0),
            ),
        ),
    )


def les_config(config_fil: str) -> Aarsregnskap:
    """Leser config.yaml og returnerer et Aarsregnskap-objekt."""
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

    return Aarsregnskap(
        selskap=selskap,
        regnskapsaar=cfg["regnskapsaar"],
        resultatregnskap=resultat,
        balanse=balanse,
        foregaaende_aar_resultat=foregaaende_resultat,
        foregaaende_aar_balanse=foregaaende_balanse,
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
            f"avviker med {diff:+,} NOK."
        )

    if len(regnskap.selskap.org_nummer.replace(" ", "")) != 9:
        feil.append("Organisasjonsnummeret må være 9 siffer.")

    return feil


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

    sign_url = klient.fullfoor_instans("aarsregnskap", instans)

    print(f"Årsregnskap lastet opp og klar for signering.")
    print(f"Signer i Altinn: {sign_url}")
    return sign_url
