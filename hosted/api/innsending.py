"""
Innsendings-endepunkter for hostet Wenche.

- POST /api/innsending/{type}?dry_run=...   -> config sendes i request-body (klienten er
    fasit), ingen server-side lagring av kundedata mellom kall. Bygger via wenche-domenet.
    dry_run: lokal bygging/validering, ingen nettverk, ingen disk, ingen binding kreves.
    ekte: vendor-creds + godkjent kunde-org; gjenbruker domene + klienter.

Personvern: innsendingsdata (inkl. fødselsnummer) lever kun i minnet i det ene kallet som
behandler det, aldri lagret mellom requester. Robusthet: en sovende/restartende server kan
ikke miste utfyllingen, klienten (re)sender den. Sikkerhet: ekte innsending krever at
data-org == godkjent systembruker-org (kunde_org), så vi aldri sender på vegne av feil org.
"""
import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from wenche import aarsregnskap as ar
from wenche import aksjonaerregister as akr
from wenche import auth as wauth
from wenche import skattemelding as sm
from wenche.altinn_client import AltinnClient
from wenche.auth import SCOPES, SKD_AKSJONAER_SCOPE, SKD_SKATTEMELDING_SCOPE
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skattemelding_xml import generer_skattemelding_fra_konfig, hent_partsnummer
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import (
    SkattemeldingValideringsfeil,
    SkdSkattemeldingClient,
)

from .config import settings
from .deps import krev_kunde_org, krev_invitert, krev_vendor

logger = logging.getLogger("wenche.hosted.innsending")
router = APIRouter(prefix="/api", tags=["innsending"])


def _sjekk_org(cfg: dict, kunde_org: str) -> None:
    """Hindrer innsending på vegne av en annen org enn den med godkjent systembruker."""
    cfg_org = str((cfg.get("selskap") or {}).get("org_nummer", "")).strip()
    if cfg_org != str(kunde_org):
        raise HTTPException(
            status_code=409,
            detail=f"Data-org ({cfg_org or 'tom'}) matcher ikke godkjent systembruker-org ({kunde_org}).",
        )


@router.post("/innsending/aarsregnskap")
def innsending_aarsregnskap(
    request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
) -> dict:
    st = krev_invitert(request)
    cfg = config
    regnskap = ar.les_config(cfg)
    feil = ar.valider(regnskap)
    if dry_run:
        return {"dry_run": True, "ok": not feil, "feil": feil, "advarsler": ar.advarsler(regnskap)}
    if feil:
        raise HTTPException(status_code=422, detail={"feil": feil})
    creds, _ = krev_vendor()
    org = krev_kunde_org(st)
    _sjekk_org(cfg, org)
    s = settings()
    altinn_token = wauth.hent_tokens_for(creds, org, SCOPES, veksle_altinn=True)["altinn_token"]
    with AltinnClient(altinn_token, env=s.env) as klient:
        resultat = ar.send_inn(regnskap, klient)
    return {"sendt": True, "resultat": resultat}


@router.post("/innsending/aksjonaer")
def innsending_aksjonaer(
    request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
) -> dict:
    st = krev_invitert(request)
    cfg = config
    oppgave = akr.les_config(cfg)
    if dry_run:
        return {"dry_run": True, "ok": True, "antall_aksjonaerer": len(oppgave.aksjonaerer)}
    creds, _ = krev_vendor()
    org = krev_kunde_org(st)
    _sjekk_org(cfg, org)
    s = settings()
    token = wauth.hent_tokens_for(creds, org, SKD_AKSJONAER_SCOPE)["maskinporten_token"]
    with SkdAksjonaerClient(token, env=s.env) as klient:
        svar = akr.send_inn(oppgave, klient)
    return {"sendt": True, "resultat": svar}


@router.post("/innsending/skattemelding")
def innsending_skattemelding(
    request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
) -> dict:
    st = krev_invitert(request)
    cfg = config
    regnskap, konfig = sm.les_config(cfg)
    if dry_run:
        # Lokal bygging uten nettverk/partsnummer. SKD-validering skjer server-side ved ekte innsending.
        return {"dry_run": True, "ok": True, "regnskapsaar": regnskap.regnskapsaar}
    creds, _ = krev_vendor()
    org = krev_kunde_org(st)
    _sjekk_org(cfg, org)
    s = settings()
    tokens = wauth.hent_tokens_for(creds, org, SKD_SKATTEMELDING_SCOPE, veksle_altinn=True)
    with SkdSkattemeldingClient(tokens["maskinporten_token"], env=s.env) as skd:
        forhandsutfylt, gjeldende_dokument_id = skd.hent_forhåndsutfylt_med_id(
            regnskap.regnskapsaar, org
        )
        partsnummer = hent_partsnummer(forhandsutfylt)
        skattemelding_xml = generer_skattemelding_fra_konfig(regnskap, konfig, partsnummer)
        naeringsspesifikasjon_xml = generer_naeringsspesifikasjon(regnskap, partsnummer)
        try:
            instans_id = skd.send(
                inntektsaar=regnskap.regnskapsaar,
                orgnr=org,
                skattemelding_xml=skattemelding_xml,
                altinn_token=tokens["altinn_token"],
                naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
                gjeldende_dokument_id=gjeldende_dokument_id,
            )
        except SkattemeldingValideringsfeil as e:
            raise HTTPException(status_code=422, detail={"validering": str(e)})
    return {"sendt": True, "instans_id": instans_id}
