"""
SAF-T Financial-importer for Wenche.

Leser en SAF-T Financial XML-fil (v1.20 / v1.30,
namespace: urn:StandardAuditFile-Taxation-Financial:NO) og returnerer en dict
klar til å lagres som config.yaml.

Støtter alle SAF-T-kompatible regnskapssystemer (Fiken, Tripletex, Visma,
Uni Micro, PowerOffice Go, etc.) da GroupingCategory og GroupingCode er
sentralt standardisert av Skatteetaten.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

_NS = "urn:StandardAuditFile-Taxation-Financial:NO"
_T = f"{{{_NS}}}"


def _tag(name: str) -> str:
    return f"{_T}{name}"


def _tekst(el: ET.Element, tag: str, default: str = "") -> str:
    child = el.find(_tag(tag))
    return child.text.strip() if child is not None and child.text else default


def _tall(el: ET.Element, tag: str) -> float:
    child = el.find(_tag(tag))
    if child is None or not child.text:
        return 0.0
    try:
        return float(child.text.strip())
    except ValueError:
        return 0.0


def _netto(account: ET.Element) -> float:
    """Netto saldo (debet minus kredit). Positiv = debet-saldo."""
    return _tall(account, "ClosingDebitBalance") - _tall(account, "ClosingCreditBalance")


def _aapning_netto(account: ET.Element) -> float:
    """Åpningssaldo (= foregående års sluttsaldo): debet minus kredit."""
    return _tall(account, "OpeningDebitBalance") - _tall(account, "OpeningCreditBalance")


def _er_offentlig_avgift(code: str) -> bool:
    """
    True for GroupingCode som tilsvarer skyldige offentlige avgifter:
    2500–2599 (betalbar skatt, forskuddsskatt) og 2700–2799 (MVA, aga, skattetrekk).
    """
    try:
        c = int(code)
        return 2500 <= c <= 2599 or 2700 <= c <= 2799
    except ValueError:
        return False


def _tom_akkumulator() -> dict:
    return {
        "salgsinntekter": 0.0,
        "andre_driftsinntekter": 0.0,
        "loennskostnader": 0.0,
        "avskrivninger": 0.0,
        "andre_driftskostnader": 0.0,
        "utbytte_fra_datterselskap": 0.0,
        "andre_finansinntekter": 0.0,
        "rentekostnader": 0.0,
        "andre_finanskostnader": 0.0,
        "aksjer_i_datterselskap": 0.0,
        "andre_aksjer": 0.0,
        "langsiktige_fordringer": 0.0,
        "kortsiktige_fordringer": 0.0,
        "bankinnskudd": 0.0,
        "aksjekapital_balanse": 0.0,
        "overkursfond": 0.0,
        "annen_egenkapital": 0.0,
        "laan_fra_aksjonaer": 0.0,
        "andre_langsiktige_laan": 0.0,
        "leverandoergjeld": 0.0,
        "skyldige_offentlige_avgifter": 0.0,
        "annen_kortsiktig_gjeld": 0.0,
    }


def _akkumuler(acc: dict, account: ET.Element, netto: float) -> None:
    """Legger konto-saldo til riktig felt i akkumulatoren."""
    cat = _tekst(account, "GroupingCategory")
    code = _tekst(account, "GroupingCode")
    if cat == "NA":
        return

    if cat == "salgsinntekt":
        acc["salgsinntekter"] += -netto

    elif cat == "annenDriftsinntekt":
        acc["andre_driftsinntekter"] += -netto

    elif cat == "loennskostnad":
        acc["loennskostnader"] += netto

    elif cat == "annenDriftskostnad":
        if code == "6000":
            acc["avskrivninger"] += netto
        else:
            acc["andre_driftskostnader"] += netto

    elif cat == "finansinntekt":
        # GroupingCode 8040 = utbytte fra datterselskap/tilknyttede selskaper
        if code == "8040":
            acc["utbytte_fra_datterselskap"] += -netto
        else:
            acc["andre_finansinntekter"] += -netto

    elif cat == "finanskostnad":
        # GroupingCode 8150 = rentekostnader
        if code == "8150":
            acc["rentekostnader"] += netto
        else:
            acc["andre_finanskostnader"] += netto

    elif cat == "balanseverdiForAnleggsmiddel":
        # 1300 = aksjer i heleide datterselskaper, 1320 = tilknyttede selskaper
        if code in ("1300", "1320"):
            acc["aksjer_i_datterselskap"] += netto
        elif code == "1350":
            acc["andre_aksjer"] += netto
        else:
            # 1370 (lån til eiere/konsern), 1390 (andre langsiktige fordringer),
            # 1105/1205/1280 (driftsmidler) — samles i langsiktige_fordringer
            acc["langsiktige_fordringer"] += netto

    elif cat == "balanseverdiForOmloepsmiddel":
        # 1920/1950 = bankinnskudd (inkl. skattetrekkskonto)
        if code in ("1920", "1950"):
            acc["bankinnskudd"] += netto
        else:
            acc["kortsiktige_fordringer"] += netto

    elif cat == "egenkapital":
        # Egenkapital er kredit-normal: positivt netto = underskudd
        if code == "2000":
            acc["aksjekapital_balanse"] += -netto
        elif code == "2030":
            acc["overkursfond"] += -netto
        else:
            # 2045 (fond), 2050 (annen EK), 2080 (udekket tap = debet = negativt)
            acc["annen_egenkapital"] += -netto

    elif cat == "langsiktigGjeld":
        # 2250 = gjeld til eiere/styremedlemmer = lån fra aksjonær
        if code == "2250":
            acc["laan_fra_aksjonaer"] += -netto
        else:
            acc["andre_langsiktige_laan"] += -netto

    elif cat == "kortsiktigGjeld":
        if code == "2400":
            acc["leverandoergjeld"] += -netto
        elif _er_offentlig_avgift(code):
            acc["skyldige_offentlige_avgifter"] += -netto
        else:
            acc["annen_kortsiktig_gjeld"] += -netto


def _bygg_resultat(acc: dict) -> dict:
    return {
        "driftsinntekter": {
            "salgsinntekter": acc["salgsinntekter"],
            "andre_driftsinntekter": acc["andre_driftsinntekter"],
        },
        "driftskostnader": {
            "loennskostnader": acc["loennskostnader"],
            "avskrivninger": acc["avskrivninger"],
            "andre_driftskostnader": acc["andre_driftskostnader"],
        },
        "finansposter": {
            "utbytte_fra_datterselskap": acc["utbytte_fra_datterselskap"],
            "andre_finansinntekter": acc["andre_finansinntekter"],
            "rentekostnader": acc["rentekostnader"],
            "andre_finanskostnader": acc["andre_finanskostnader"],
        },
    }


def _bygg_balanse(acc: dict) -> dict:
    return {
        "eiendeler": {
            "anleggsmidler": {
                "aksjer_i_datterselskap": acc["aksjer_i_datterselskap"],
                "andre_aksjer": acc["andre_aksjer"],
                "langsiktige_fordringer": acc["langsiktige_fordringer"],
            },
            "omloepmidler": {
                "kortsiktige_fordringer": acc["kortsiktige_fordringer"],
                "bankinnskudd": acc["bankinnskudd"],
            },
        },
        "egenkapital_og_gjeld": {
            "egenkapital": {
                "aksjekapital": acc["aksjekapital_balanse"],
                "overkursfond": acc["overkursfond"],
                "annen_egenkapital": acc["annen_egenkapital"],
            },
            "langsiktig_gjeld": {
                "laan_fra_aksjonaer": acc["laan_fra_aksjonaer"],
                "andre_langsiktige_laan": acc["andre_langsiktige_laan"],
            },
            "kortsiktig_gjeld": {
                "leverandoergjeld": acc["leverandoergjeld"],
                "skyldige_offentlige_avgifter": acc["skyldige_offentlige_avgifter"],
                "annen_kortsiktig_gjeld": acc["annen_kortsiktig_gjeld"],
            },
        },
    }


def importer(saft_fil: str | Path) -> dict:
    """
    Leser en SAF-T Financial XML-fil og returnerer en dict
    kompatibel med config.yaml-formatet til Wenche.

    Feltene daglig_leder, styreleder, stiftelsesaar og aksjonaerer
    er ikke tilgjengelig i SAF-T og må fylles inn manuelt etterpå.

    Foregående års resultatregnskap er ikke tilgjengelig i SAF-T
    (P&L-kontoer nullstilles ved årsavslutning) og settes til 0.
    Foregående års balanse hentes fra åpningssaldoene.
    """
    tree = ET.parse(str(saft_fil))
    root = tree.getroot()

    header = root.find(_tag("Header"))
    if header is None:
        raise ValueError("Finner ingen Header i SAF-T-filen.")

    company = header.find(_tag("Company"))
    if company is None:
        raise ValueError("Finner ingen Company-seksjon i SAF-T-filen.")

    org_nummer = _tekst(company, "RegistrationNumber")
    navn = _tekst(company, "Name")

    adresse = ""
    adresse_el = company.find(_tag("Address"))
    if adresse_el is not None:
        gate = _tekst(adresse_el, "StreetName")
        postnr = _tekst(adresse_el, "PostalCode")
        by = _tekst(adresse_el, "City")
        deler = [d for d in [gate, f"{postnr} {by}".strip()] if d]
        adresse = ", ".join(deler)

    sel_crit = header.find(_tag("SelectionCriteria"))
    regnskapsaar = int(_tekst(sel_crit, "PeriodStartYear", "0")) if sel_crit is not None else 0

    gl = root.find(f".//{_tag('GeneralLedgerAccounts')}")
    if gl is None:
        raise ValueError("Finner ingen GeneralLedgerAccounts i SAF-T-filen.")

    nar = _tom_akkumulator()      # nåværende år (closing balances)
    fjor_b = _tom_akkumulator()   # foregående år balanse (opening balances)

    for account in gl.findall(_tag("Account")):
        _akkumuler(nar, account, _netto(account))
        _akkumuler(fjor_b, account, _aapning_netto(account))

    aksjekapital = nar["aksjekapital_balanse"]

    return {
        "selskap": {
            "navn": navn,
            "org_nummer": org_nummer,
            "daglig_leder": "",
            "styreleder": "",
            "forretningsadresse": adresse,
            "stiftelsesaar": 0,
            "aksjekapital": aksjekapital,
            "kontakt_epost": "",
        },
        "regnskapsaar": regnskapsaar,
        "resultatregnskap": _bygg_resultat(nar),
        "balanse": _bygg_balanse(nar),
        "foregaaende_aar": {
            # Resultatregnskap for foregående år er ikke tilgjengelig i SAF-T
            # (P&L-kontoer nullstilles ved årsavslutning) — fyll inn manuelt.
            "resultatregnskap": _bygg_resultat(_tom_akkumulator()),
            "balanse": _bygg_balanse(fjor_b),
        },
        "skattemelding": {
            "underskudd_til_fremfoering": 0.0,
            "anvend_fritaksmetoden": False,
            "eierandel_datterselskap": 100,
        },
        "aksjonaerer": [],
        "noter": {
            "antall_ansatte": 0,
            "laan_til_naerstaaende": [],
        },
    }
