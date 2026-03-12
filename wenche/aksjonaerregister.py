"""
Innsending av aksjonærregisteroppgave (RF-1086) via Altinn.

Fristen er 31. januar året etter regnskapsåret.
Oppgaven rapporterer aksjonærer, beholdninger og eventuelle
utbytter og transaksjoner i løpet av året.
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom

import yaml

from wenche.altinn_client import AltinnClient
from wenche.models import Aksjonaer, Aksjonaerregisteroppgave, Selskap


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


def generer_xml(oppgave: Aksjonaerregisteroppgave) -> bytes:
    """
    Genererer RF-1086 XML-melding.

    XML-skjemaet er basert på Skatteetatens spesifikasjon for
    aksjonærregisteroppgaven. Verifiser mot gjeldende XSD-skjema:
    https://www.skatteetaten.no/bedrift-og-organisasjon/starte-og-drive/aksjeselskap/aksjonarregisteret/
    """
    rot = ET.Element("Skjema")
    rot.set("xmlns", "urn:ske:fastsetting:formueinntekt:aksjerekopp:v2")
    rot.set("skjemanummer", "RF-1086")
    rot.set("innsendingstype", "ordinaer")

    # Innsenderinfo
    innsender = ET.SubElement(rot, "Innsender")
    ET.SubElement(innsender, "Organisasjonsnummer").text = oppgave.selskap.org_nummer
    ET.SubElement(innsender, "Navn").text = oppgave.selskap.navn

    # Regnskapsår
    ET.SubElement(rot, "Inntektsaar").text = str(oppgave.regnskapsaar)

    # Selskapsopplysninger
    selskap_el = ET.SubElement(rot, "Selskap")
    ET.SubElement(selskap_el, "Organisasjonsnummer").text = oppgave.selskap.org_nummer
    ET.SubElement(selskap_el, "Navn").text = oppgave.selskap.navn
    ET.SubElement(selskap_el, "AntallAksjer").text = str(oppgave.totalt_antall_aksjer)
    ET.SubElement(selskap_el, "Aksjekapital").text = str(oppgave.selskap.aksjekapital)

    # Aksjonærer
    for a in oppgave.aksjonaerer:
        a_el = ET.SubElement(rot, "Aksjonaer")
        ET.SubElement(a_el, "Fodselsnummer").text = a.fodselsnummer
        ET.SubElement(a_el, "Navn").text = a.navn
        behold = ET.SubElement(a_el, "Beholdning")
        ET.SubElement(behold, "Aksjeklasse").text = a.aksjeklasse
        ET.SubElement(behold, "AntallAksjerUltimo").text = str(a.antall_aksjer)
        ET.SubElement(behold, "InnbetaltKapitalPerAksje").text = str(
            a.innbetalt_kapital_per_aksje
        )
        if a.utbytte_utbetalt > 0:
            utbytte = ET.SubElement(a_el, "Utbytte")
            ET.SubElement(utbytte, "UtbytteBelop").text = str(a.utbytte_utbetalt)

    # Pretty-print XML
    raa = ET.tostring(rot, encoding="unicode")
    pent = minidom.parseString(raa).toprettyxml(indent="  ", encoding="UTF-8")
    return pent


def valider(oppgave: Aksjonaerregisteroppgave) -> list[str]:
    feil = []

    if not oppgave.aksjonaerer:
        feil.append("Minst én aksjonær må være registrert.")

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
    klient: AltinnClient,
    dry_run: bool = False,
) -> str | None:
    """
    Sender inn aksjonærregisteroppgaven via Altinn.

    dry_run=True genererer XML uten å sende til Altinn.
    Returnerer Altinn-lenke for signering, eller None ved dry_run.
    """
    feil = valider(oppgave)
    if feil:
        print("\nValidering mislyktes:")
        for f in feil:
            print(f"  - {f}")
        raise SystemExit(1)

    print("Validering OK.")

    xml_data = generer_xml(oppgave)
    print(f"RF-1086 XML generert ({len(xml_data):,} bytes).")

    if dry_run:
        utfil = f"aksjonaerregister_{oppgave.regnskapsaar}_{oppgave.selskap.org_nummer}.xml"
        with open(utfil, "wb") as f:
            f.write(xml_data)
        print(f"Dry-run: XML lagret til {utfil} — ingenting sendt til Altinn.")
        return None

    print("Sender aksjonærregisteroppgave til Altinn...")
    instans = klient.opprett_instans("aksjonaerregister", oppgave.selskap.org_nummer)
    klient.oppdater_data_element(
        "aksjonaerregister",
        instans,
        data_type="rf1086",
        data=xml_data,
        content_type="application/xml",
    )
    sign_url = klient.fullfoor_instans("aksjonaerregister", instans)

    print(f"Aksjonærregisteroppgave lastet opp og klar for signering.")
    print(f"Signer i Altinn: {sign_url}")
    return sign_url
