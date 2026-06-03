"""
Innsendings-endepunkter for hostet Wenche.

- POST /api/innsending/{type}?dry_run=...   -> config sendes i request-body (klienten er
    fasit), ingen server-side lagring av kundedata mellom kall. Bygger via wenche-domenet.
    dry_run: lokal bygging/validering, ingen nettverk, ingen disk, ingen binding kreves.
    ekte: vendor-creds + godkjent kunde-org; gjenbruker domene + klienter.

Orkestreringen (bygg → valider → send) ligger i `wenche.innsending` og deles med CLI-en og
self-hosted-appen. Denne modulen legger kun hostet-auth (invite + vendor + kunde-org) oppå.

Personvern: innsendingsdata (inkl. fødselsnummer) lever kun i minnet i det ene kallet som
behandler det, aldri lagret mellom requester. Robusthet: en sovende/restartende server kan
ikke miste utfyllingen, klienten (re)sender den. Sikkerhet: ekte innsending krever at
data-org == godkjent systembruker-org (kunde_org), så vi aldri sender på vegne av feil org.
"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException, Request

from wenche import auth as wauth
from wenche import innsending as tjeneste
from wenche.altinn_client import AltinnClient
from wenche.auth import SCOPES, SKD_AKSJONAER_SCOPE, SKD_SKATTEMELDING_SCOPE
from wenche.innsending import InnsendingValideringsfeil
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import (
    SkattemeldingValideringsfeil,
    SkdSkattemeldingClient,
)

from .config import settings
from .deps import krev_invitert, krev_kunde_org, krev_vendor

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


def _tolk_http_feil(e: httpx.HTTPStatusError) -> HTTPException:
    """Gjør en rå HTTP-feil fra Altinn/Skatteetaten om til en lesbar 502 (unngår 500 + stacktrace)."""
    kode = e.response.status_code
    if kode == 403:
        melding = (
            "Altinn avslo tilgangen (HTTP 403). Vanligste årsak: systembrukeren er ikke lenger "
            "godkjent for selskapet, eller tjenesten mangler nødvendig rettighet."
        )
    elif kode == 401:
        melding = "Altinn avviste tokenet (HTTP 401). Prøv igjen, eller koble systembrukeren på nytt."
    elif kode >= 500:
        melding = (
            f"Altinn/Skatteetaten svarte med en serverfeil (HTTP {kode}). Dette er som regel "
            "midlertidig hos myndighetene. Ingenting er sendt inn. Prøv igjen om litt."
        )
    else:
        detalj = (e.response.text or "").strip()[:200]
        melding = f"Altinn/Skatteetaten svarte med HTTP {kode}." + (f" {detalj}" if detalj else "")
    return HTTPException(status_code=502, detail=melding)


def _utfor(fn):
    """
    Kjør en innsending og gjør alle feil om til lesbare HTTP-svar, aldri en rå 500.

    Domeneklientene melder feil på to måter: rå `httpx.HTTPStatusError` (Altinn) og
    `RuntimeError` med ferdig melding (SKD-klienten). Valideringsfeil gir 422; alt annet 502.
    """
    try:
        return fn()
    except InnsendingValideringsfeil as e:
        raise HTTPException(status_code=422, detail={"feil": e.feil})
    except SkattemeldingValideringsfeil as e:  # subklasse av RuntimeError — fanges først
        raise HTTPException(status_code=422, detail={"validering": str(e)})
    except httpx.HTTPStatusError as e:
        raise _tolk_http_feil(e)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/innsending/aarsregnskap")
def innsending_aarsregnskap(
    request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
) -> dict:
    krev_invitert(request)
    if dry_run:
        return {"dry_run": True, **tjeneste.valider_aarsregnskap(config)}
    creds, _ = krev_vendor()
    org = krev_kunde_org(request)
    _sjekk_org(config, org)
    s = settings()
    altinn_token = wauth.hent_tokens_for(creds, org, SCOPES, veksle_altinn=True)["altinn_token"]

    def _send():
        with AltinnClient(altinn_token, env=s.env) as klient:
            return tjeneste.send_aarsregnskap(config, klient)

    return _utfor(_send)


@router.post("/innsending/aksjonaer")
def innsending_aksjonaer(
    request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
) -> dict:
    krev_invitert(request)
    if dry_run:
        return {"dry_run": True, **tjeneste.valider_aksjonaer(config)}
    creds, _ = krev_vendor()
    org = krev_kunde_org(request)
    _sjekk_org(config, org)
    s = settings()
    token = wauth.hent_tokens_for(creds, org, SKD_AKSJONAER_SCOPE)["maskinporten_token"]

    def _send():
        with SkdAksjonaerClient(token, env=s.env) as klient:
            return tjeneste.send_aksjonaer(config, klient)

    return _utfor(_send)


@router.post("/innsending/skattemelding")
def innsending_skattemelding(
    request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
) -> dict:
    krev_invitert(request)
    if dry_run:
        return {"dry_run": True, **tjeneste.valider_skattemelding(config)}
    creds, _ = krev_vendor()
    org = krev_kunde_org(request)
    _sjekk_org(config, org)
    s = settings()
    tokens = wauth.hent_tokens_for(creds, org, SKD_SKATTEMELDING_SCOPE, veksle_altinn=True)

    def _send():
        with SkdSkattemeldingClient(tokens["maskinporten_token"], env=s.env) as skd:
            return tjeneste.send_skattemelding(config, skd, tokens["altinn_token"], orgnr=org)

    return _utfor(_send)
