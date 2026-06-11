"""
Dokumentgenerering for forhåndsvisning/nedlasting i hostet Wenche.

Genererer lokalt fra config-en i request-body (akkurat som innsending dry-run): ingen nettverk,
ingenting lagres mellom kall. Krever kun gyldig invite (`krev_invitert`), ikke vendor/kunde-org,
siden ingenting sendes inn. Notene sendes heller ikke inn, men kan lastes ned for signering og
arkivering hos selskapet. Gjenbruker domene-genereringen, samme kode som self-hosted bruker.
"""
import base64
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from wenche import aarsregnskap as ar
from wenche import aksjonaerregister as akr
from wenche import noter as noter_modul
from wenche import skattemelding as sm
from wenche.aksjonaerregister import generer_hovedskjema_xml, generer_underskjema_xml
from wenche.brg_xml import generer_hovedskjema, generer_underskjema
from wenche.models import LaanTilNaerstaaende, Noter

from .deps import krev_invitert

router = APIRouter(prefix="/api/dokumenter", tags=["dokumenter"])


def _fil(filnavn: str, innhold: bytes, mime: str) -> dict:
    return {"filnavn": filnavn, "mime": mime, "base64": base64.b64encode(innhold).decode("ascii")}


# Lesbare navn på config-seksjonene les_config slår opp direkte. Et ufullstendig Tall-steg
# (typisk tomt resultatregnskap eller balanse) får les_config til å kaste KeyError på det
# manglende nøkkeloppslaget; uten _les_eller_422 ble det en naken HTTP 500. Aksjonærregisteret
# rører ikke resultatregnskap/balanse, så det er det eneste dokumentet som lar seg generere før
# tallene er fylt inn, derav den forvirrende delvise feilen.
_SEKSJON_TEKST = {
    "resultatregnskap": "Resultatregnskapet",
    "balanse": "Balansen",
    "regnskapsaar": "Regnskapsåret",
    "selskap": "Selskapsopplysningene",
    "aksjonaerer": "Aksjonærene",
}


def _les_eller_422(les, config: dict):
    """Kjør en les_config og gjør en manglende config-seksjon om til en forklarende 422.

    Samme ånd som skattemelding.valider_selskap: en påregnelig, ufullstendig brukertilstand skal
    bli et avvik brukeren kan rette, ikke en uhåndtert serverfeil.
    """
    try:
        return les(config)
    except KeyError as e:
        felt = str(e.args[0]) if e.args else ""
        navn = _SEKSJON_TEKST.get(felt, f"Feltet «{felt}»" if felt else "Et påkrevd felt")
        raise HTTPException(
            status_code=422,
            detail={
                "feil": [
                    f"{navn} mangler. Fyll inn opplysningene i Tall-steget før du genererer "
                    "dette dokumentet."
                ]
            },
        ) from e


def _bygg_noter(config: dict) -> Noter:
    noter_cfg = config.get("noter") or {}
    return Noter(
        antall_ansatte=int(noter_cfg.get("antall_ansatte", 0)),
        laan_til_naerstaaende=[
            LaanTilNaerstaaende(
                motpart=l.get("motpart", l.get("mottaker", "")),
                saldo=float(l.get("saldo", l.get("beloep", 0))),
                retning=l.get("retning", "långiver"),
                rente_prosent=float(l.get("rente_prosent", 0.0)),
                sikkerhet=l.get("sikkerhet", ""),
            )
            for l in noter_cfg.get("laan_til_naerstaaende", [])
        ],
    )


@router.post("/skattemelding")
def dok_skattemelding(request: Request, config: dict[str, Any] = Body(...)) -> dict:
    krev_invitert(request)
    feil = sm.valider_selskap(config)
    if feil:
        raise HTTPException(status_code=422, detail={"feil": feil})
    regnskap, konfig = _les_eller_422(sm.les_config, config)
    tekst = sm.generer(regnskap, konfig)
    navn = f"skattemelding_{regnskap.regnskapsaar}_{regnskap.selskap.org_nummer}.txt"
    return {"filer": [_fil(navn, tekst.encode("utf-8"), "text/plain; charset=utf-8")]}


@router.post("/aarsregnskap")
def dok_aarsregnskap(request: Request, config: dict[str, Any] = Body(...)) -> dict:
    krev_invitert(request)
    regnskap = _les_eller_422(ar.les_config, config)
    feil = ar.valider(regnskap)
    if feil:
        raise HTTPException(status_code=422, detail={"feil": feil})
    base = f"aarsregnskap_{regnskap.regnskapsaar}_{regnskap.selskap.org_nummer}"
    return {
        "filer": [
            _fil(f"{base}_hovedskjema.xml", generer_hovedskjema(regnskap), "application/xml"),
            _fil(f"{base}_underskjema.xml", generer_underskjema(regnskap), "application/xml"),
        ]
    }


@router.post("/aksjonaer")
def dok_aksjonaer(request: Request, config: dict[str, Any] = Body(...)) -> dict:
    krev_invitert(request)
    oppgave = _les_eller_422(akr.les_config, config)
    feil = akr.valider(oppgave)
    if feil:
        raise HTTPException(status_code=422, detail={"feil": feil})
    base = f"aksjonaerregister_{oppgave.regnskapsaar}_{oppgave.selskap.org_nummer}"
    filer = [_fil(f"{base}_hovedskjema.xml", generer_hovedskjema_xml(oppgave), "application/xml")]
    for i, aksjonaer in enumerate(oppgave.aksjonaerer, 1):
        filer.append(
            _fil(
                f"{base}_underskjema_{i}.xml",
                generer_underskjema_xml(aksjonaer, oppgave),
                "application/xml",
            )
        )
    return {"filer": filer}


@router.post("/noter")
def dok_noter(request: Request, config: dict[str, Any] = Body(...)) -> dict:
    krev_invitert(request)
    regnskap = _les_eller_422(ar.les_config, config)
    tekst = noter_modul.generer(regnskap, _bygg_noter(config))
    navn = f"noter_{regnskap.regnskapsaar}_{regnskap.selskap.org_nummer}.txt"
    return {"filer": [_fil(navn, tekst.encode("utf-8"), "text/plain; charset=utf-8")]}
