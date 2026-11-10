"""
Innsendings-endepunkter for hostet Wenche.

- POST /api/innsending/{type}?dry_run=...   -> config sendes i request-body (klienten er
    fasit), ingen server-side lagring av kundedata mellom kall. Bygger via wenche-domenet.
    dry_run: lokal bygging/validering, ingen nettverk, ingen disk, ingen binding kreves.
    ekte: vendor-creds + godkjent kunde-org; gjenbruker domene + klienter.

Orkestreringen (bygg, valider, send) ligger i `wenche.innsending` og deles med CLI-en og
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
from wenche.feil import KonfigFeil, MyndighetsFeil, ValideringsFeil, brukermelding, url_fra_unntak
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


def _url_fra_feil(e: Exception) -> str:
    """Oppstrøms-URL-en fra en httpx-feil, trygt (tom streng når den ikke er satt)."""
    return url_fra_unntak(e) or ""


def _steg_av_url(url: str) -> str | None:
    """Utled et lesbart navn på innsendingssteget fra oppstrøms-URL-en.

    Reserveløsning for rå httpx-feil som ikke gikk gjennom en av Wenches klienter (de navngir
    steget selv). Rekkefølgen er bevisst: de mest spesifikke mønstrene først, siden f.eks.
    valider- og data-URL-ene også inneholder de generiske bitene. Returnerer None når URL-en
    ikke kjennes igjen, så meldingen faller tilbake på en generisk formulering.
    """
    u = (url or "").lower()
    if "skattemelding/v2/valider" in u:
        return "validering av skattemeldingen hos Skatteetaten"
    if "skattemelding/v2" in u:
        return "henting av forhåndsutfylt skattemelding fra Skatteetaten"
    if "/process/next" in u:
        return "fullføring av innsendingen i Altinn"
    if "/instances" in u and "/data" in u:
        return "opplasting av data til Altinn"
    if "/instances" in u:
        return "oppretting av innsending i Altinn"
    if "altinn" in u:
        return "kommunikasjon med Altinn"
    if "skatteetaten" in u:
        return "kommunikasjon med Skatteetaten"
    return None


def _fra_httpx(e: httpx.HTTPError) -> MyndighetsFeil:
    """Rå httpx-feil som slapp forbi en klient: pakk som MyndighetsFeil med steg utledet av URL-en."""
    url = _url_fra_feil(e)
    tjeneste_navn = "skatteetaten" if ("skatteetaten" in url or "sits.no" in url) else "altinn"
    steg = _steg_av_url(url) or ""
    if isinstance(e, httpx.HTTPStatusError):
        return MyndighetsFeil.fra_svar(tjeneste_navn, steg, e.response)
    if isinstance(e, httpx.RequestError):
        return MyndighetsFeil.fra_nettverksfeil(tjeneste_navn, steg, e)
    return MyndighetsFeil(tjeneste_navn, steg, beskrivelse=type(e).__name__)


def _lesbar_502(e: MyndighetsFeil, kunde_org: str | None) -> HTTPException:
    """
    Logg feilen server-side (steg, status, kode, URL; svarkroppen bare på DEBUG, den kan
    inneholde interne detaljer) og gi brukeren en melding som navngir steget og koden.
    `kunde_org` logges (ikke kundedata) så en operatør kan knytte feilen til riktig org.
    """
    logger.warning(
        "Innsending feilet for org %s: %s (HTTP %s, kode %s, url %s)",
        kunde_org,
        e.steg or "ukjent steg",
        e.status,
        e.kode,
        e.url,
    )
    if e.kropp:
        logger.debug("Svarkropp: %s", e.kropp[:2000])
    return HTTPException(status_code=502, detail=brukermelding(e))


def _utfor(fn, kunde_org: str | None = None):
    """
    Kjør en innsending og gjør alle feil om til lesbare HTTP-svar, aldri en rå 500.

    `fn` må omslutte HELE innsendingen, inkludert token-hentingen: et avslag fra
    Maskinporten (f.eks. systembruker mangler en rettighet) eller en feilet Altinn-veksling
    kaster ellers utenfor denne fellen og blir en naken 500 hos brukeren.

    Valideringsfeil og config-feil gir 422; alt fra myndighetene (MyndighetsFeil fra klientene,
    eller rå httpx-feil som reserve) gir 502 med steget navngitt. Bevisst reist HTTPException
    slipper gjennom uendret.
    """
    try:
        return fn()
    except ValideringsFeil as e:
        raise HTTPException(status_code=422, detail={"feil": e.feil}) from e
    except SkattemeldingValideringsfeil as e:
        raise HTTPException(status_code=422, detail={"validering": str(e)}) from e
    except KonfigFeil as e:
        raise HTTPException(status_code=422, detail={"feil": [str(e)]}) from e
    except MyndighetsFeil as e:
        raise _lesbar_502(e, kunde_org) from e
    except httpx.HTTPError as e:
        raise _lesbar_502(_fra_httpx(e), kunde_org) from e
    except HTTPException:
        raise  # alt bevisst reist (f.eks. _sjekk_org 409) skal slippe gjennom uendret
    except RuntimeError as e:
        # Eldre feil med ferdig melding. Bare første linje til klienten (en eventuell
        # svarkropp etter linjeskift logges, vises ikke).
        logger.warning("Innsending feilet for org %s: %s", kunde_org, e)
        raise HTTPException(status_code=502, detail=str(e).split("\n", 1)[0]) from e
    except Exception:
        # Siste skanse: en uventet feiltype skal aldri bli en naken stacktrace-500 hos
        # brukeren. Logg med traceback + org så den blir attribuerbar, og gi et rent svar.
        logger.exception("Uventet feil under innsending for org %s", kunde_org)
        raise HTTPException(
            status_code=500,
            detail="Uventet feil under innsending. Feilen er logget. Prøv igjen, eller ta kontakt.",
        ) from None


@router.post("/innsending/aarsregnskap")
def innsending_aarsregnskap(
    request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
) -> dict:
    krev_invitert(request)
    if dry_run:
        return _utfor(lambda: {"dry_run": True, **tjeneste.valider_aarsregnskap(config)})
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
        return _utfor(lambda: {"dry_run": True, **tjeneste.valider_aksjonaer(config)})
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
    request: Request,
    config: dict[str, Any] = Body(...),
    dry_run: bool = False,
    bekreft_klage: bool = False,
) -> dict:
    krev_invitert(request)
    if dry_run:
        return _utfor(lambda: {"dry_run": True, **tjeneste.valider_skattemelding(config)})
    creds, _ = krev_vendor()
    org = krev_kunde_org(request)
    _sjekk_org(config, org)
    s = settings()

    def _send():
        tokens = wauth.hent_tokens_for(creds, org, SKD_SKATTEMELDING_SCOPE, veksle_altinn=True)
        with SkdSkattemeldingClient(tokens["maskinporten_token"], env=s.env) as skd:
            return tjeneste.send_skattemelding(
                config, skd, tokens["altinn_token"], orgnr=org, bekreft_klage=bekreft_klage
            )

    return _utfor(_send, org)
