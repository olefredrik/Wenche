"""
Frist- og statusoversikt for self-hosted Wenche (porten fra Hjem-fanen i `wenche/ui.py`).

Statussjekk mot myndighetene gjøres mot PROD for din egen virksomhet (ORG_NUMMER), uavhengig
av aktivt miljø — test-API-ene kjenner kun syntetiske Tenor-orgnumre. Derfor er statussjekk
aktiv kun i prod-modus med et reelt konfigurert orgnr. Aksjonærregisteret har ingen automatisk
sjekk.
"""
from __future__ import annotations

import dataclasses

from fastapi import APIRouter

from wenche import fristsjekk

from . import miljo

router = APIRouter(prefix="/api/frister", tags=["frister"])

_FRISTER = [
    {
        "key": "skattemelding",
        "tittel": "Skattemelding",
        "undertittel": "Skattemelding og næringsspesifikasjon",
        "maaned": 5,
        "dag": 31,
        "beskrivelse": "Beregnes og sendes digitalt via Altinn.",
        "auto_sjekk": True,
    },
    {
        "key": "aarsregnskap",
        "tittel": "Årsregnskap",
        "undertittel": "Brønnøysundregistrene",
        "maaned": 7,
        "dag": 31,
        "beskrivelse": "Sendes via Altinn, signeres med BankID.",
        "auto_sjekk": True,
    },
    {
        "key": "aksjonaerregister",
        "tittel": "Aksjonærregisteroppgave",
        "undertittel": "RF-1086, Skatteetaten",
        "maaned": 1,
        "dag": 31,
        "beskrivelse": "Sendes maskinelt, ingen signering.",
        "auto_sjekk": False,
    },
]

_SJEKK_FN = {
    "skattemelding": fristsjekk.sjekk_skattemelding,
    "aarsregnskap": fristsjekk.sjekk_aarsregnskap,
}


def _statussjekk_aktiv() -> tuple[bool, str]:
    """(aktiv, prod_orgnr). Aktiv kun i prod med et reelt orgnr (ikke placeholder)."""
    import os

    prod_orgnr = os.getenv("ORG_NUMMER", "").strip()
    orgnr_konfigurert = bool(prod_orgnr) and prod_orgnr != "123456789"
    return (orgnr_konfigurert and miljo.aktiv_env() == "prod", prod_orgnr)


@router.get("")
def frister() -> dict:
    """Statisk frist-info + flagg. Live status hentes separat (POST /sjekk) så lasting er rask."""
    aktiv, _orgnr = _statussjekk_aktiv()
    out = []
    for f in _FRISTER:
        neste = fristsjekk.neste_frist(f["maaned"], f["dag"])
        out.append({**f, "neste_frist": neste.isoformat()})
    return {
        "env": miljo.aktiv_env(),
        "statussjekk_aktiv": aktiv,
        "frister": out,
    }


@router.post("/sjekk")
def sjekk() -> dict:
    """Kjør live statussjekk mot myndighetene for de fristene som støtter det."""
    aktiv, orgnr = _statussjekk_aktiv()
    if not aktiv:
        return {"statuser": {}}
    statuser: dict[str, dict] = {}
    for f in _FRISTER:
        if not f["auto_sjekk"]:
            continue
        aar = fristsjekk.regnskapsaar_for_frist(f["maaned"], f["dag"])
        try:
            resultat = _SJEKK_FN[f["key"]](orgnr, aar)
            statuser[f["key"]] = dataclasses.asdict(resultat)
        except Exception as e:
            statuser[f["key"]] = {"innfridd": False, "beskrivelse": f"Kunne ikke sjekke ({type(e).__name__})"}
    return {"statuser": statuser}
