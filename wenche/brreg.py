"""
Oppslag mot Brønnøysundregistrenes åpne Enhetsregister-API (gratis, ingen auth).

Brukes til å forhåndsfylle selskapsopplysninger SAF-T ikke bærer: daglig leder, styreleder og
stiftelsesår. Alt er offentlige registerdata, og ingenting lagres. Oppslagene er fail-soft: ved
ukjent org, manglende felt eller transient nettverksfeil returneres tomme verdier, aldri et unntak
som blokkerer flyten. Parsingen er skilt ut som rene funksjoner så den kan gjenbrukes av hostet
sin selvbetjenings-navnematch, som beholder en strengere feilkontrakt (se hosted/api/auth.py).
"""

from __future__ import annotations

from datetime import date

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
    Plukk aktiv daglig leder og styreleder ut av et /roller-svar, pluss to flate navnelister:
    `ledelse` (aktiv daglig leder og styreleder, til navnematchen i hostet) og `alle` (hver aktiv
    rolleinnehaver, også styremedlemmer, varamedlemmer, revisor og regnskapsfører). Tomme verdier
    der rollen mangler.
    """
    daglig_leder = ""
    styreleder = ""
    ledelse: list[str] = []
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
            er_daglig_leder = gruppetype == "DAGL"
            er_styreleder = gruppetype == "STYR" and rolletype == "LEDE"
            if er_daglig_leder or er_styreleder:
                ledelse.append(navn)
            if er_daglig_leder and not daglig_leder:
                daglig_leder = navn
            elif er_styreleder and not styreleder:
                styreleder = navn
    return {
        "daglig_leder": daglig_leder,
        "styreleder": styreleder,
        "ledelse": ledelse,
        "alle": alle,
    }


def parse_stiftelsesaar(data: dict) -> int:
    """Årstallet fra `stiftelsesdato` (YYYY-MM-DD) i et enhets-svar. 0 om ukjent eller ugyldig."""
    stiftelsesdato = data.get("stiftelsesdato")
    if not stiftelsesdato or len(stiftelsesdato) < 4:
        return 0
    try:
        return int(stiftelsesdato[:4])
    except ValueError:
        return 0


def parse_stiftelsesdato(data: dict) -> str:
    """
    Hele `stiftelsesdato` (YYYY-MM-DD) fra et enhets-svar. Tom streng om ukjent eller ugyldig.

    Årstallet alene er ikke nok: aksjonærregisteroppgaven oppgir stiftelsesdato, og et
    kort første regnskapsår starter på stiftelsesdatoen. Begge ble før satt til 1. januar
    fordi oppslaget kastet bort dag og måned.
    """
    stiftelsesdato = (data.get("stiftelsesdato") or "").strip()
    try:
        return date.fromisoformat(stiftelsesdato).isoformat()
    except ValueError:
        return ""


def _format_adresse(adr: dict) -> str:
    """Sett sammen brregs strukturerte forretningsadresse til én linje, f.eks.
    «Kong Carls gate 29, 4010 STAVANGER». Tom streng om adressen mangler."""
    if not adr:
        return ""
    gate = ", ".join(linje for linje in (adr.get("adresse") or []) if linje)
    poststed = " ".join(d for d in (adr.get("postnummer"), adr.get("poststed")) if d)
    return ", ".join(d for d in (gate, poststed) if d)


def parse_enhet(data: dict) -> dict:
    """Navn, forretningsadresse og stiftelsesår fra et enhets-svar. Tomme verdier der noe mangler."""
    return {
        "navn": data.get("navn") or "",
        "forretningsadresse": _format_adresse(data.get("forretningsadresse") or {}),
        "stiftelsesaar": parse_stiftelsesaar(data),
        "stiftelsesdato": parse_stiftelsesdato(data),
    }


def _hent(url: str, timeout: float) -> tuple[int | None, dict | None]:
    """(HTTP-status, JSON-objekt). (None, None) ved nettverksfeil, (status, None) uten JSON-objekt."""
    try:
        resp = httpx.get(url, headers={"Accept": "application/json"}, timeout=timeout)
    except httpx.HTTPError:
        return None, None
    try:
        data = resp.json()
    except ValueError:
        return resp.status_code, None
    return resp.status_code, data if isinstance(data, dict) else None


def _hent_json(url: str, timeout: float) -> dict | None:
    status, data = _hent(url, timeout)
    if status is None or not 200 <= status < 300:
        return None
    return data


def hent_enhet_svar(orgnr: str, *, timeout: float = 5.0) -> tuple[int | None, dict | None]:
    """
    Rått enhets-oppslag: (HTTP-status, JSON). Lar kalleren skille «fant ikke orgnr» (404) fra
    «fikk ikke kontakt» (None), der `hent_enhet` svarer tomt for begge.
    """
    return _hent(f"{_BASE}/{orgnr}", timeout)


def hent_roller(orgnr: str, *, timeout: float = 5.0) -> dict:
    """Aktiv daglig leder og styreleder for orgnr fra Enhetsregisteret. Fail-soft (tomt ved feil)."""
    data = _hent_json(f"{_BASE}/{orgnr}/roller", timeout)
    if not data:
        return {"daglig_leder": "", "styreleder": "", "ledelse": [], "alle": []}
    return parse_roller(data)


def hent_enhet(orgnr: str, *, timeout: float = 5.0) -> dict:
    """Navn, forretningsadresse og stiftelsesår for orgnr fra Enhetsregisteret. Fail-soft (tomt ved feil)."""
    data = _hent_json(f"{_BASE}/{orgnr}", timeout)
    if not data:
        return {"navn": "", "forretningsadresse": "", "stiftelsesaar": 0, "stiftelsesdato": ""}
    return parse_enhet(data)
