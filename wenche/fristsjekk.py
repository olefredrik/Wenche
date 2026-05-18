"""
Sjekk innsendingsstatus mot offentlige API-er.

Brukes av Wenche UI for å vise om frister er innfridd:
  - Skattemelding: Skatteetatens API (krever Maskinporten-token)
  - Årsregnskap:   Brønnøysundregistrenes åpne Regnskapsregister-API
  - Aksjonærregisteroppgave: Ingen offentlig status-API tilgjengelig

Skattemelding-sjekken bruker endepunktet GET /api/skattemelding/v2/{aar}/{orgnr}
som returnerer en XML-wrapper med <type>-element. Verdiene er definert i
Skatteetatens offisielle XSD-skjema (Dokumenttype):
  - skattemeldingUpersonligUtkast    → forhåndsutfylt, ikke innsendt
  - skattemeldingUpersonligFastsatt  → innsendt og fastsatt

Kilde: https://github.com/Skatteetaten/skattemeldingen/blob/master/src/resources/
       xsd/skattemeldingognaeringsspesifikasjonforespoerselresponse_v2_kompakt.xsd
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from xml.etree import ElementTree as ET

import httpx
from dotenv import load_dotenv

load_dotenv()


def neste_frist(maaned: int, dag: int) -> date:
    """Neste forekomst av (maaned, dag) fra og med i dag."""
    today = date.today()
    frist = date(today.year, maaned, dag)
    if frist < today:
        frist = date(today.year + 1, maaned, dag)
    return frist


def regnskapsaar_for_frist(maaned: int, dag: int) -> int:
    """
    Regnskapsåret som neste frist gjelder for.

    Frister leveres i året etter regnskapsårets slutt, så regnskapsår = frist.year - 1.
    F.eks. frist 31. juli 2026 → regnskapsår 2025.
    """
    return neste_frist(maaned, dag).year - 1

# Basis-URL-er for Skatteetatens API — samme som i skd_skattemelding_client.py.
_SKD_BASES = {
    "test": "https://api-test.sits.no",
    "prod": "https://api.skatteetaten.no",
}

# Brønnøysundregistrenes Regnskapsregister-API.
# Åpent API uten autentisering.
# Dokumentasjon: https://data.brreg.no/regnskapsregisteret/openapi/index.html
_BRG_REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap"


@dataclass
class FristStatus:
    innfridd: bool = False
    tidspunkt: str | None = None
    beskrivelse: str = ""
    brukertekst: str = ""
    lenke: str | None = None


def sjekk_skattemelding(orgnr: str, aar: int) -> FristStatus:
    """Sjekk om skattemelding er fastsatt via Skatteetatens API."""
    try:
        from wenche.auth import get_skd_skattemelding_maskinporten_token

        token = get_skd_skattemelding_maskinporten_token()
    except RuntimeError:
        return FristStatus(beskrivelse="Maskinporten ikke konfigurert")

    env = os.getenv("WENCHE_ENV", "prod")
    base = _SKD_BASES.get(env, _SKD_BASES["prod"])

    try:
        resp = httpx.get(
            f"{base}/api/skattemelding/v2/{aar}/{orgnr}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/xml",
            },
            timeout=30,
        )
    except httpx.HTTPError:
        return FristStatus(beskrivelse="Kunne ikke kontakte Skatteetaten")

    if not resp.is_success:
        return FristStatus(beskrivelse=f"Skatteetaten svarte med HTTP {resp.status_code}")

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return FristStatus(beskrivelse="Ugyldig svar fra Skatteetaten")

    # <type>-elementet i wrapper-XML-en angir dokumentstatus.
    # "Fastsatt" i verdien betyr at skattemeldingen er innsendt og godkjent.
    # Ref: Dokumenttype-enum i XSD (se modul-docstring).
    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "type" and elem.text and "Fastsatt" in elem.text:
            return FristStatus(
                innfridd=True,
                brukertekst=f"Skattemeldingen for {aar} er sendt inn og godkjent.",
                lenke=f"https://af.altinn.no/?party=urn%3Aaltinn%3Aorganization%3Aidentifier-no%3A{orgnr}",
            )

    return FristStatus(
        beskrivelse="Ikke innsendt",
        brukertekst=f"Skattemeldingen for {aar} er ikke innsendt ennå.",
    )


def sjekk_aarsregnskap(orgnr: str, aar: int) -> FristStatus:
    """Sjekk om årsregnskap er levert via Brønnøysundregistrenes API."""
    try:
        resp = httpx.get(
            f"{_BRG_REGNSKAP_URL}/{orgnr}",
            headers={"Accept": "application/json"},
            timeout=15,
        )
    except httpx.HTTPError:
        return FristStatus(beskrivelse="Kunne ikke kontakte Regnskapsregisteret")

    if not resp.is_success:
        return FristStatus(beskrivelse="Kunne ikke kontakte Regnskapsregisteret")

    try:
        data = resp.json()
    except ValueError:
        return FristStatus(beskrivelse="Uventet svar fra Regnskapsregisteret")

    if not isinstance(data, list):
        return FristStatus(beskrivelse="Uventet svar fra Regnskapsregisteret")

    for regnskap in data:
        periode = regnskap.get("regnskapsperiode", {})
        fra = periode.get("fraDato", "")
        if fra.startswith(str(aar)):
            mottatt = regnskap.get("mottaksdag")
            return FristStatus(
                innfridd=True,
                tidspunkt=mottatt,
                brukertekst=f"Brønnøysundregistrene har mottatt årsregnskapet for {aar}.",
            )

    return FristStatus(
        beskrivelse="Ikke levert",
        brukertekst=f"Brønnøysundregistrene har ikke mottatt årsregnskapet for {aar} ennå.",
    )


def sjekk_aksjonaerregister(orgnr: str, aar: int) -> FristStatus:
    """Aksjonærregister — ingen offentlig status-API tilgjengelig."""
    return FristStatus(
        beskrivelse="Ingen automatisk sjekk tilgjengelig",
        brukertekst="Sjekk status manuelt hos Skatteetaten.",
    )
