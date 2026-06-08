"""
Oppslag mot Brønnøysundregistrenes åpne Enhetsregister-API (gratis, ingen auth).

Brukes til å forhåndsfylle selskapsopplysninger SAF-T ikke bærer: daglig leder, styreleder og
stiftelsesår. Alt er offentlige registerdata, og ingenting lagres. Oppslagene er fail-soft: ved
ukjent org, manglende felt eller transient nettverksfeil returneres tomme verdier, aldri et unntak
som blokkerer flyten. Parsingen er skilt ut som rene funksjoner så den kan gjenbrukes av hostet
sin selvbetjenings-navnematch, som beholder en strengere feilkontrakt (se hosted/api/auth.py).
"""
from __future__ import annotations

import httpx

_BASE = "https://data.brreg.no/enhetsregisteret/api/enheter"


def _fullt_navn(person: dict) -> str:
    n = person.get("navn") or {}
    return " ".join(d for d in (n.get("fornavn"), n.get("mellomnavn"), n.get("etternavn")) if d)


def _rolle_aktiv(rolle: dict) -> bool:
    """En rolle teller bare når personen sitter aktivt (ikke fratrådt, avregistrert eller død)."""
    if rolle.get("fratraadt") or rolle.get("avregistrert"):
        return False
    return not (rolle.get("person") or {}).get("erDoed")


def parse_roller(data: dict) -> dict:
    """
    Plukk aktiv daglig leder og styreleder ut av et /roller-svar, pluss en flat liste med navn på
    alle aktive rolleinnehavere (til navnematch). Tomme verdier der rollen mangler.
    """
    daglig_leder = ""
    styreleder = ""
    alle: list[str] = []
    for gruppe in data.get("rollegrupper", []):
        gruppetype = (gruppe.get("type") or {}).get("kode")
        for rolle in gruppe.get("roller", []):
            if not _rolle_aktiv(rolle):
                continue
            navn = _fullt_navn(rolle.get("person") or {})
            if not navn:
                continue
            alle.append(navn)
            rolletype = (rolle.get("type") or {}).get("kode")
            if gruppetype == "DAGL" and not daglig_leder:
                daglig_leder = navn
            elif gruppetype == "STYR" and rolletype == "LEDE" and not styreleder:
                styreleder = navn
    return {"daglig_leder": daglig_leder, "styreleder": styreleder, "alle": alle}


def parse_stiftelsesaar(data: dict) -> int:
    """Årstallet fra `stiftelsesdato` (YYYY-MM-DD) i et enhets-svar. 0 om ukjent eller ugyldig."""
    stiftelsesdato = data.get("stiftelsesdato")
    if not stiftelsesdato or len(stiftelsesdato) < 4:
        return 0
    try:
        return int(stiftelsesdato[:4])
    except ValueError:
        return 0


def _hent_json(url: str, timeout: float) -> dict | None:
    try:
        resp = httpx.get(url, headers={"Accept": "application/json"}, timeout=timeout)
    except httpx.HTTPError:
        return None
    if not resp.is_success:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def hent_roller(orgnr: str, *, timeout: float = 5.0) -> dict:
    """Aktiv daglig leder og styreleder for orgnr fra Enhetsregisteret. Fail-soft (tomt ved feil)."""
    data = _hent_json(f"{_BASE}/{orgnr}/roller", timeout)
    return parse_roller(data) if data else {"daglig_leder": "", "styreleder": "", "alle": []}


def hent_stiftelsesaar(orgnr: str, *, timeout: float = 5.0) -> int:
    """Stiftelsesår for orgnr fra Enhetsregisteret. Fail-soft (0 ved feil eller ukjent org)."""
    data = _hent_json(f"{_BASE}/{orgnr}", timeout)
    return parse_stiftelsesaar(data) if data else 0
