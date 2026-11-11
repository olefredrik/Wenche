"""
Innsendings-endepunkter for self-hosted Wenche.

Gjenbruker den delte orkestreringen i `wenche.innsending` (samme som hostet og CLI), men med
*lokal* auth: brukerens egen Maskinporten-innlogging (egen RSA-nøkkel), ingen vendor/invite.
Config sendes i request-body, slik at endepunktene er rene og state-løse; utfyllingen lagres
separat via /api/config.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException

from wenche import auth
from wenche import innsending as tjeneste
from wenche.altinn_client import AltinnClient
from wenche.feil import KonfigFeil, MyndighetsFeil, ValideringsFeil, brukermelding, url_fra_unntak
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import SkattemeldingValideringsfeil, SkdSkattemeldingClient

from . import miljo

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/innsending", tags=["innsending"])


def _fra_httpx(e: httpx.HTTPError) -> MyndighetsFeil:
    """Rå httpx-feil som slapp forbi en klient: pakk som MyndighetsFeil uten kjent steg."""
    url = url_fra_unntak(e) or ""
    tjeneste_navn = "skatteetaten" if ("skatteetaten" in url or "sits.no" in url) else "altinn"
    if isinstance(e, httpx.HTTPStatusError):
        return MyndighetsFeil.fra_svar(tjeneste_navn, "", e.response)
    if isinstance(e, httpx.RequestError):
        return MyndighetsFeil.fra_nettverksfeil(tjeneste_navn, "", e)
    return MyndighetsFeil(tjeneste_navn, "", beskrivelse=type(e).__name__)


def _lesbar_502(e: MyndighetsFeil) -> HTTPException:
    """Logg steg, status og kode (svarkroppen bare på DEBUG), og gi en melding som navngir steget."""
    log.warning(
        "Innsending feilet: %s (HTTP %s, kode %s, url %s)",
        e.steg or "ukjent steg",
        e.status,
        e.kode,
        e.url,
    )
    if e.kropp:
        log.debug("Svarkropp: %s", e.kropp[:2000])
    melding = brukermelding(e)
    if e.status == 403 and miljo.er_test():
        melding += (
            " I testmiljø må selskapets org_nummer være Tenor-orgnr-et du har systembruker for."
        )
    return HTTPException(status_code=502, detail=melding)


def _utfor(fn):
    """
    Kjør en innsending og gjør alle feil om til lesbare HTTP-svar, aldri en rå 500.

    `fn` må omslutte hele innsendingen, også token-hentingen, så et avslag fra Maskinporten
    blir en lesbar 502 i stedet for en naken 500. Valideringsfeil og config-feil gir 422;
    alt fra myndighetene gir 502 med steget navngitt.
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
        raise _lesbar_502(e) from e
    except httpx.HTTPError as e:
        raise _lesbar_502(_fra_httpx(e)) from e
    except HTTPException:
        raise
    except RuntimeError as e:
        log.warning("Innsending feilet: %s", e)
        raise HTTPException(status_code=502, detail=str(e).split("\n", 1)[0]) from e


def _orgnr(config: dict) -> str:
    return str((config.get("selskap") or {}).get("org_nummer", "")).strip()


@router.post("/aarsregnskap")
def innsending_aarsregnskap(config: dict[str, Any] = Body(...), dry_run: bool = False) -> dict:
    config = miljo.med_test_org(config)
    if dry_run:
        return _utfor(lambda: {"dry_run": True, **tjeneste.valider_aarsregnskap(config)})

    def _send():
        token = auth.get_altinn_token()
        with AltinnClient(token, env=miljo.aktiv_env()) as klient:
            return tjeneste.send_aarsregnskap(config, klient)

    return _utfor(_send)


@router.post("/aksjonaer")
def innsending_aksjonaer(config: dict[str, Any] = Body(...), dry_run: bool = False) -> dict:
    config = miljo.med_test_org(config)
    if dry_run:
        return _utfor(lambda: {"dry_run": True, **tjeneste.valider_aksjonaer(config)})

    def _send():
        token = auth.get_skd_aksjonaer_token()
        with SkdAksjonaerClient(token, env=miljo.aktiv_env()) as klient:
            return tjeneste.send_aksjonaer(config, klient)

    return _utfor(_send)


@router.post("/skattemelding")
def innsending_skattemelding(
    config: dict[str, Any] = Body(...), dry_run: bool = False, bekreft_klage: bool = False
) -> dict:
    config = miljo.med_test_org(config)
    if dry_run:
        return _utfor(lambda: {"dry_run": True, **tjeneste.valider_skattemelding(config)})
    orgnr = _orgnr(config)

    # Henter alltid live forhåndsutfylt (gir riktig partsnummer + gjeldende dokument-id) for
    # org-en. Bruker bevisst IKKE SKD_TEST_PARTSNUMMER-snarveien: et hardkodet partsnummer som
    # ikke matcher test-org-en gir «tekniskFeil» fra SKDs validator. Samme flyt som prod.
    def _send():
        tokens = auth.get_skd_skattemelding_tokens()
        with SkdSkattemeldingClient(tokens["maskinporten_token"], env=miljo.aktiv_env()) as skd:
            return tjeneste.send_skattemelding(
                config, skd, tokens["altinn_token"], orgnr=orgnr, bekreft_klage=bekreft_klage
            )

    return _utfor(_send)
