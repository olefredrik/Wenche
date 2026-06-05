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


def _utfor(fn, kunde_org: str | None = None):
    """
    Kjør en innsending og gjør alle feil om til lesbare HTTP-svar, aldri en rå 500.

    `fn` må omslutte HELE innsendingen, inkludert token-hentingen: et avslag fra
    Maskinporten (f.eks. systembruker mangler en rettighet) eller en feilet Altinn-veksling
    kaster ellers utenfor denne fellen og blir en naken 500 hos brukeren.

    Domeneklientene melder feil på to måter: rå `httpx.HTTPStatusError` (Altinn) og
    `RuntimeError` med ferdig melding (SKD-klienten / token-henting). Valideringsfeil gir
    422; alt annet 502. `kunde_org` logges (ikke kundedata) så en operatør kan knytte en
    feil til riktig org i loggene uten å vente på at brukeren melder fra.
    """
    try:
        return fn()
    except InnsendingValideringsfeil as e:
        raise HTTPException(status_code=422, detail={"feil": e.feil})
    except SkattemeldingValideringsfeil as e:  # subklasse av RuntimeError — fanges først
        raise HTTPException(status_code=422, detail={"validering": str(e)})
    except httpx.HTTPStatusError as e:
        logger.warning(
            "Innsending feilet for org %s: HTTP %s fra %s",
            kunde_org, e.response.status_code, e.request.url,
        )
        raise _tolk_http_feil(e)
    except httpx.RequestError as e:
        # Tidsavbrudd/tilkoblingsfeil (ikke et HTTP-svar). Søsken av HTTPStatusError, så den
        # må fanges eksplisitt — ellers blir den en naken 500. Skattemelding gjør flere
        # oppstrøms-kall enn aksjonær og er derfor mer utsatt for et forbigående avbrudd.
        url = e.request.url if e.request else "?"
        logger.warning("Innsending feilet for org %s: nettverksfeil mot %s: %s", kunde_org, url, e)
        raise HTTPException(
            status_code=502,
            detail=(
                "Fikk ikke fullført forespørselen mot Altinn/Skatteetaten (nettverksfeil eller "
                "tidsavbrudd). Det er som regel midlertidig. Sjekk Altinn-innboksen din før du "
                "prøver på nytt, i tilfelle forespørselen likevel gikk gjennom."
            ),
        )
    except RuntimeError as e:
        logger.warning("Innsending feilet for org %s: %s", kunde_org, e)
        raise HTTPException(status_code=502, detail=str(e))
    except HTTPException:
        raise  # alt bevisst reist (f.eks. _sjekk_org 409) skal slippe gjennom uendret
    except Exception:
        # Siste skanse: en uventet feiltype skal aldri bli en naken stacktrace-500 hos
        # brukeren. Logg med traceback + org så den blir attribuerbar, og gi et rent svar.
        logger.exception("Uventet feil under innsending for org %s", kunde_org)
        raise HTTPException(
            status_code=500,
            detail="Uventet feil under innsending. Feilen er logget. Prøv igjen, eller ta kontakt.",
        )


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

    def _send():
        altinn_token = wauth.hent_tokens_for(creds, org, SCOPES, veksle_altinn=True)["altinn_token"]
        with AltinnClient(altinn_token, env=s.env) as klient:
            return tjeneste.send_aarsregnskap(config, klient)

    return _utfor(_send, org)


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

    def _send():
        token = wauth.hent_tokens_for(creds, org, SKD_AKSJONAER_SCOPE)["maskinporten_token"]
        with SkdAksjonaerClient(token, env=s.env) as klient:
            return tjeneste.send_aksjonaer(config, klient)

    return _utfor(_send, org)


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

    def _send():
        tokens = wauth.hent_tokens_for(creds, org, SKD_SKATTEMELDING_SCOPE, veksle_altinn=True)
        with SkdSkattemeldingClient(tokens["maskinporten_token"], env=s.env) as skd:
            return tjeneste.send_skattemelding(config, skd, tokens["altinn_token"], orgnr=org)

    return _utfor(_send, org)
