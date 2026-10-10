"""
SAF-T Financial-importer for Wenche.

Leser en SAF-T Financial XML-fil (v1.10 til v1.40, alle med samme
namespace: urn:StandardAuditFile-Taxation-Financial:NO) og returnerer en dict
klar til å lagres som config.yaml.

Støtter alle SAF-T-kompatible regnskapssystemer (Fiken, Tripletex, Visma,
Uni Micro, PowerOffice Go, etc.) da GroupingCategory og GroupingCode er
sentralt standardisert av Skatteetaten. Kontoene plasseres ut fra disse to
feltene alene, så en fil uten grupperingskoder kan ikke importeres. Eldre filer
(v1.10/v1.20) har ofte bare StandardAccountID.

Versjon 1.40 (påkrevd fra regnskapsår som starter 1. januar 2027) er
bakoverkompatibel med 1.30: endringene gjelder eiere, valutabeløp og MVA i NOK
på transaksjonsnivå, som importen ikke leser.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

# Parse-inngangene går via defusedxml: SAF-T-filer kommer fra brukeropplasting, og stdlib-ET
# er sårbar for entitetsekspansjon (billion laughs). defusedxml returnerer vanlige
# stdlib-Element-objekter, så resten av modulen (ET.Element-typehints m.m.) er uendret.
from defusedxml.ElementTree import fromstring as _safe_fromstring
from defusedxml.ElementTree import parse as _safe_parse

_NS = "urn:StandardAuditFile-Taxation-Financial:NO"
_T = f"{{{_NS}}}"

# AuditFileVersion-verdiene importen er laget for. Alle bruker samme namespace og samme
# kontostruktur (GeneralLedgerAccounts/Account), så forskjellen ligger utenfor det som leses.
_KJENTE_VERSJONER = ("1.10", "1.20", "1.30", "1.40")

# Kategorier som med vilje ikke gir noen regnskapslinje: NA og resultatDisponeringForSAF-T
# (8800) er begge disponering av årsresultatet, som Skatteetaten ber om å mappe til den ene
# eller den andre. Motposten står allerede i egenkapitalen.
_IKKE_REGNSKAPSLINJE = frozenset({"NA", "resultatDisponeringForSAF-T"})

# Hvor mange konto-ID-er en advarsel lister opp før resten oppsummeres som et antall.
_MAKS_KONTOER_I_ADVARSEL = 10


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


def _er_betalbar_skatt(code: str) -> bool:
    """
    True for GroupingCode som tilsvarer betalbar selskapsskatt: 2500 (ikke fastsatt) og
    2510 (fastsatt), med underkontoer. Egen linje i balansen fordi den er motposten til
    skattekostnaden i resultatregnskapet; tidligere havnet den i skyldige offentlige avgifter.
    """
    try:
        return 2500 <= int(code) <= 2519
    except ValueError:
        return False


def _er_offentlig_avgift(code: str) -> bool:
    """
    True for GroupingCode som tilsvarer skyldige offentlige avgifter:
    2520–2599 (forskuddsskatt o.l.) og 2700–2799 (MVA, aga, skattetrekk).
    Betalbar selskapsskatt (2500–2519) har egen linje, se _er_betalbar_skatt.
    """
    try:
        c = int(code)
        return 2520 <= c <= 2599 or 2700 <= c <= 2799
    except ValueError:
        return False


# Finansielle anleggsmidler uten egen linje i modellen: investeringer i datter- og
# konsernselskap med deltakerfastsetting (1312), i tilknyttede selskap (1331, 1332) og
# obligasjoner (1360).
_UKLASSIFISERTE_INVESTERINGER = frozenset({"1312", "1331", "1332", "1360"})


def _er_uklassifisert_anleggsmiddel(code: str) -> bool:
    """Om grupperingskoden er et anleggsmiddel Wenche ikke har en egen linje for."""
    if code in _UKLASSIFISERTE_INVESTERINGER:
        return True
    try:
        return int(code) < 1300
    except ValueError:
        return False


def _advarsler_om_uklassifiserte(acc: dict) -> list[str]:
    """
    Advarsler om anleggsmidler som er importert inn i en grovere linje enn de hører til.

    Wenche har ingen linje for immaterielle eiendeler, varige driftsmidler, investeringer i
    tilknyttede selskap eller deltakerlignede datterselskap, eller obligasjoner, verken i
    årsregnskapet eller i næringsspesifikasjonen. Kontoene havner derfor i langsiktige
    fordringer og rapporteres som kode 1390. Det er en uriktig opplysning, og brukeren er
    den eneste som kan avgjøre hva beløpet skal gjøre.
    """
    uklassifiserte = acc["uklassifiserte_anleggsmidler"]
    if not uklassifiserte:
        return []

    koder = ", ".join(sorted(uklassifiserte))
    sum_beloep = sum(uklassifiserte.values())
    return [
        f"SAF-T-filen har {sum_beloep:,.0f} NOK på anleggsmiddelkontoer Wenche ikke har en "
        f"egen linje for (grupperingskode {koder}), typisk immaterielle eiendeler, varige "
        "driftsmidler, investeringer i tilknyttede selskap eller obligasjoner. Beløpet er lagt inn under «Langsiktige fordringer» og blir "
        "rapportert som «andre langsiktige fordringer» (kode 1390). Kontroller at det er "
        "riktig for selskapet, og rett tallene selv hvis det ikke er det."
    ]


def _konto_id(account: ET.Element) -> str:
    """Kontoens ID slik brukeren kjenner den igjen fra regnskapssystemet."""
    return (
        _tekst(account, "AccountID")
        or _tekst(account, "StandardAccountID")
        or "(uten konto-ID)"
    )


def _har_gruppering(account: ET.Element) -> bool:
    return bool(_tekst(account, "GroupingCategory") or _tekst(account, "GroupingCode"))


def _kontoliste(kontoer) -> str:
    """Kommaseparert liste med konto-ID-er, kortet ned når den blir lang."""
    kontoer = sorted(kontoer)
    vist = ", ".join(kontoer[:_MAKS_KONTOER_I_ADVARSEL])
    resten = len(kontoer) - _MAKS_KONTOER_I_ADVARSEL
    return f"{vist} og {resten} til" if resten > 0 else vist


def _advarsler_om_versjon(versjon: str) -> list[str]:
    """
    Advarsel når filen oppgir en AuditFileVersion importen ikke er laget for.

    Filen leses likevel: en ny versjon med samme namespace er som regel bakoverkompatibel,
    slik 1.40 er. Manglende versjon gir ingen advarsel, siden feltet ikke endrer hvordan
    kontoene leses.
    """
    if not versjon:
        return []
    try:
        normalisert = f"{float(versjon):.2f}"
    except ValueError:
        normalisert = versjon
    if normalisert in _KJENTE_VERSJONER:
        return []
    return [
        f"SAF-T-filen oppgir versjon {versjon}, som Wenche ikke kjenner. Importen er laget "
        f"for versjon {', '.join(_KJENTE_VERSJONER)}. Jeg har lest filen på samme måte, men "
        "kontroller tallene mot regnskapet før du sender inn."
    ]


def _advarsler_om_ufordelte(nar: dict, fjor: dict) -> list[str]:
    """
    Sumkontroll: advarsel når saldo på kontoer ikke ble fordelt på noen regnskapslinje.

    En konto med en kategori importen ikke håndterer, eller uten grupperingskode, faller
    ellers ut av tallene uten at noen merker det. I verste fall blir resultatet et
    nullregnskap. Beløpene legges ikke noe sted, siden det bare er brukeren som vet hvor de
    hører hjemme.
    """
    ufordelte = {**fjor["ufordelte_kontoer"], **nar["ufordelte_kontoer"]}
    if not ufordelte:
        return []

    sum_ub = sum(abs(b) for b in nar["ufordelte_kontoer"].values())
    sum_ib = sum(abs(b) for b in fjor["ufordelte_kontoer"].values())
    beloep = []
    if sum_ub:
        beloep.append(f"{sum_ub:,.0f} NOK i utgående saldo")
    if sum_ib:
        beloep.append(f"{sum_ib:,.0f} NOK i inngående saldo (fjorårets balanse)")

    tekst = (
        f"SAF-T-filen har saldo på {len(ufordelte)} konto(er) som importen ikke fant noen "
        f"linje for i regnskapet (konto {_kontoliste(ufordelte)}). Til sammen "
        f"{' og '.join(beloep)} er derfor ikke med i tallene."
    )
    uten_gruppering = nar["uten_gruppering"] | fjor["uten_gruppering"]
    if uten_gruppering:
        tekst += (
            f" Konto {_kontoliste(uten_gruppering)} mangler GroupingCategory og "
            "GroupingCode, som Wenche bruker til å plassere kontoene."
        )
    tekst += (
        " Kontroller grupperingen i regnskapssystemet, eller legg inn beløpene selv der "
        "de hører hjemme."
    )
    return [tekst]


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
        "skattekostnad": 0.0,
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
        "betalbar_skatt": 0.0,
        "skyldige_offentlige_avgifter": 0.0,
        "avsatt_utbytte": 0.0,
        "annen_kortsiktig_gjeld": 0.0,
        # Anleggsmiddelkontoer som samles i langsiktige_fordringer fordi modellen ikke har
        # noen egen linje for dem: {grupperingskode: beløp}. Brukes bare til å advare, aldri
        # til beløp, jf. _advarsler_om_uklassifiserte.
        "uklassifiserte_anleggsmidler": {},
        # Kontoer med saldo som ikke havnet på noen linje: {konto-ID: beløp}, og hvilke av
        # dem som mangler grupperingskode. Brukes bare til sumkontrollen i
        # _advarsler_om_ufordelte, aldri til beløp.
        "ufordelte_kontoer": {},
        "uten_gruppering": set(),
    }


def _akkumuler(acc: dict, account: ET.Element, netto: float) -> None:
    """Legger konto-saldo til riktig felt i akkumulatoren."""
    cat = _tekst(account, "GroupingCategory")
    code = _tekst(account, "GroupingCode")
    if cat in _IKKE_REGNSKAPSLINJE:
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
        # GroupingCode 8090 = inntekt av andre investeringer/utbytte, samme kode som
        # næringsspesifikasjonen bruker for utbytte_fra_datterselskap
        if code == "8090":
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
        # 1313 = investeringer i andre datter- og konsernselskap
        if code == "1313":
            acc["aksjer_i_datterselskap"] += netto
        elif code == "1350":
            acc["andre_aksjer"] += netto
        else:
            # 1320 (lån til foretak i samme konsern), 1370 (fordringer på eiere),
            # 1390 (andre langsiktige fordringer),
            # 1105/1205/1280 (driftsmidler) — samles i langsiktige_fordringer
            acc["langsiktige_fordringer"] += netto
            # Fordringskodene hører hjemme her, resten gjør det ikke: alt under 1300 er
            # immaterielle eiendeler (10xx) eller varige driftsmidler (11xx/12xx), og
            # 1312/1331/1332/1360 er investeringer. De rapporteres da som «andre langsiktige
            # fordringer» (1390). Beløpet blir liggende
            # der, men brukeren skal få vite det i stedet for at det skjer i stillhet.
            if netto and _er_uklassifisert_anleggsmiddel(code):
                acc["uklassifiserte_anleggsmidler"][code] = (
                    acc["uklassifiserte_anleggsmidler"].get(code, 0.0) + netto
                )

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
        elif code in ("2020", "2030"):
            # 2020 = overkurs. 2030 (annen innskutt egenkapital) har ingen egen linje og
            # er innskutt, ikke opptjent, så den følger overkursen.
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
        elif _er_betalbar_skatt(code):
            acc["betalbar_skatt"] += -netto
        elif _er_offentlig_avgift(code):
            acc["skyldige_offentlige_avgifter"] += -netto
        elif code == "2800":
            # Avsatt utbytte har egen linje i årsregnskapet og egen kode (2800) i
            # næringsspesifikasjonen. Før havnet den i annen kortsiktig gjeld og ble
            # rapportert som 2990.
            acc["avsatt_utbytte"] += -netto
        else:
            acc["annen_kortsiktig_gjeld"] += -netto

    # Skattekostnad: 8300 (betalbar skatt på ordinært resultat) og 8321–8324 (utsatt skatt,
    # avvik fra tidligere år). Kategorinavnet følger næringsspesifikasjonens elementnavn, som
    # de øvrige kategoriene her. 83-serien tas også på kode alene, siden hele serien i
    # kodelisten er skatt: uten dette forsvant skattekostnaden stille i importen, og balansen
    # gikk ikke opp for et selskap med skattepliktig inntekt. Står sist, så en eksplisitt
    # kategori over alltid vinner.
    elif cat == "skattekostnad" or code.startswith("83"):
        acc["skattekostnad"] += netto

    # Alt annet (ukjent kategori, eller ingen grupperingskode) får ingen linje. Før forsvant
    # saldoen her i stillhet; nå noteres den, så importen kan si fra.
    elif netto:
        konto = _konto_id(account)
        acc["ufordelte_kontoer"][konto] = acc["ufordelte_kontoer"].get(konto, 0.0) + netto
        if not _har_gruppering(account):
            acc["uten_gruppering"].add(konto)


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
        "skattekostnad": acc["skattekostnad"],
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
                "betalbar_skatt": acc["betalbar_skatt"],
                "skyldige_offentlige_avgifter": acc["skyldige_offentlige_avgifter"],
                "avsatt_utbytte": acc["avsatt_utbytte"],
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
    kontakt_epost hentes fra Company/Contact/Email hvis SAF-T-fila
    inneholder det, ellers tom streng.

    Foregående års resultatregnskap er ikke tilgjengelig i SAF-T
    (P&L-kontoer nullstilles ved årsavslutning) og settes til 0.
    Foregående års balanse hentes fra åpningssaldoene.

    Lån fra aksjonær (konto 2250) gir en stub-noteoppføring i
    noter.laan_til_naerstaaende med saldoen ferdig utfylt. Motpart,
    rentesats og sikkerhet finnes ikke i SAF-T og må fylles inn manuelt.

    Fremførbart underskudd (skattemelding.underskudd_til_fremfoering)
    estimeres fra åpningssaldoen på konto 2080 (udekket tap). For
    selskaper med ikke-fradragsberettigede kostnader vil regnskapsmessig
    underskudd avvike fra det skattemessige; verifiser mot fjorårets
    RF-1028 hvis det er aktuelt.
    """
    tree = _safe_parse(str(saft_fil))
    return _fra_root(tree.getroot())


def importer_bytes(data: bytes) -> dict:
    """
    Som importer(), men leser SAF-T fra rå bytes i minnet i stedet for en
    diskfil. Brukt av web-UI-ene (hostet + self-hosted) slik at en opplastet
    SAF-T-fil aldri skrives til disk: den parses i minnet og forkastes.
    """
    return _fra_root(_safe_fromstring(data))


def _fra_root(root: ET.Element) -> dict:
    """Felles kjerne: bygg config-dict fra et parset SAF-T-rotelement."""
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

    # SAF-T Company/Contact er valgfri; bruk første Email hvis tilgjengelig.
    kontakt_epost = ""
    contact_el = company.find(_tag("Contact"))
    if contact_el is not None:
        email_el = contact_el.find(_tag("Email"))
        if email_el is not None and email_el.text:
            kontakt_epost = email_el.text.strip()

    sel_crit = header.find(_tag("SelectionCriteria"))
    regnskapsaar = int(_tekst(sel_crit, "PeriodStartYear", "0")) if sel_crit is not None else 0

    gl = root.find(f".//{_tag('GeneralLedgerAccounts')}")
    if gl is None:
        raise ValueError("Finner ingen GeneralLedgerAccounts i SAF-T-filen.")

    kontoer = gl.findall(_tag("Account"))
    if kontoer and not any(_har_gruppering(a) for a in kontoer):
        # Uten grupperingskoder havner hver konto utenfor regnskapet, og resultatet blir et
        # nullregnskap. Det er bedre å stoppe her enn å gi en config med bare nuller.
        raise ValueError(
            "SAF-T-filen har ingen grupperingskoder (GroupingCategory og GroupingCode) på "
            "kontoene. Wenche bruker dem til å plassere kontoene i regnskapet, og kan ikke "
            "lese filen uten dem. Eldre SAF-T-filer (versjon 1.10 og 1.20) har ofte bare "
            "StandardAccountID. Eksporter filen på nytt med grupperingskoder fra "
            "Skatteetatens kodeliste for næringsspesifikasjonen, typisk som versjon 1.30 "
            "eller nyere."
        )

    nar = _tom_akkumulator()      # nåværende år (closing balances)
    fjor_b = _tom_akkumulator()   # foregående år balanse (opening balances)

    for account in kontoer:
        _akkumuler(nar, account, _netto(account))
        _akkumuler(fjor_b, account, _aapning_netto(account))

    aksjekapital = nar["aksjekapital_balanse"]

    # Fremførbart underskudd (estimat): åpningssaldoen på konto 2080
    # representerer akkumulert udekket tap inn i regnskapsåret. Tallet
    # er regnskapsmessig og kan avvike fra det skattemessige fremførbare
    # underskuddet i fjorårets RF-1028; brukeren bør verifisere.
    underskudd_aapning = 0.0
    for account in kontoer:
        if _tekst(account, "GroupingCode") == "2080":
            underskudd_aapning += _aapning_netto(account)

    # Stub-noteoppføring for lån fra aksjonær: saldoen hentes fra konto 2250,
    # men motpart, rentesats og sikkerhet finnes ikke i SAF-T og må fylles
    # inn manuelt av brukeren. retning="låntaker" fordi selskapet er den som
    # har lånt penger fra eieren (nærstående part er långiver).
    laan_til_naerstaaende: list[dict] = []
    if nar["laan_fra_aksjonaer"] > 0:
        laan_til_naerstaaende.append({
            "motpart": "",
            "saldo": nar["laan_fra_aksjonaer"],
            "retning": "låntaker",
            "rente_prosent": 0.0,
            "sikkerhet": "",
        })

    advarsler = (
        _advarsler_om_versjon(_tekst(header, "AuditFileVersion"))
        + _advarsler_om_ufordelte(nar, fjor_b)
        + _advarsler_om_uklassifiserte(nar)
    )

    return {
        "selskap": {
            "navn": navn,
            "org_nummer": org_nummer,
            "daglig_leder": "",
            "styreleder": "",
            "forretningsadresse": adresse,
            "stiftelsesaar": 0,
            "aksjekapital": aksjekapital,
            "kontakt_epost": kontakt_epost,
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
            "underskudd_til_fremfoering": underskudd_aapning,
            "anvend_fritaksmetoden": False,
        },
        "aksjonaerer": [],
        "noter": {
            "antall_ansatte": 0,
            "laan_til_naerstaaende": laan_til_naerstaaende,
        },
        # Underscore-prefikset markerer at dette ikke er et config-felt: nøkkelen bæres bare
        # fra importen til brukeren, og skal aldri skrives til config.yaml. Utelates helt når
        # det ikke er noe å advare om, slik at en vanlig import gir samme config som før.
        **({"_advarsler": advarsler} if advarsler else {}),
    }
