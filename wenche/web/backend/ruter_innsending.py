"""
Innsendings-endepunkter for self-hosted Wenche.

Gjenbruker den delte orkestreringen i `wenche.innsending` (samme som hostet og CLI), men med
*lokal* auth: brukerens egen Maskinporten-innlogging (egen RSA-nøkkel), ingen vendor/invite.
Config sendes i request-body, slik at endepunktene er rene og state-løse — utfyllingen lagres
separat via /api/config.
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Body, HTTPException

from wenche import auth
from wenche import innsending as tjeneste
from wenche.altinn_client import AltinnClient
from wenche.innsending import InnsendingValideringsfeil
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import SkattemeldingValideringsfeil, SkdSkattemeldingClient

from . import miljo

router = APIRouter(prefix="/api/innsending", tags=["innsending"])


def _tolk_http_feil(e: httpx.HTTPStatusError) -> HTTPException:
    """Gjør en rå HTTP-feil fra Altinn/Skatteetaten om til en lesbar 502 (unngår 500 + stacktrace)."""
    kode = e.response.status_code
    if kode == 403:
        melding = (
            "Altinn avslo tilgangen (HTTP 403). Vanligste årsak: systembrukeren er ikke godkjent "
            "for dette selskapet eller tjenesten, eller organisasjonsnummeret i skjemaet matcher "
            "ikke org-en systembrukeren er godkjent for"
            + (" (i testmiljø må selskapets org_nummer være Tenor-orgnr du har systembruker for)." if miljo.er_test() else ".")
        )
    elif kode == 401:
        melding = "Altinn avviste tokenet (HTTP 401). Sjekk at klienten har riktige scopes og rettigheter."
    else:
        detalj = (e.response.text or "").strip()[:200]
        melding = f"Altinn/Skatteetaten svarte med HTTP {kode}." + (f" {detalj}" if detalj else "")
    return HTTPException(status_code=502, detail=melding)


def _orgnr(config: dict) -> str:
    return str((config.get("selskap") or {}).get("org_nummer", "")).strip()


def _utfor(fn):
    """
    Kjør en innsending og gjør alle feil om til lesbare HTTP-svar, aldri en rå 500.

    Domeneklientene melder feil på to måter: rå `httpx.HTTPStatusError` (Altinn) og
    `RuntimeError` med en ferdig melding (SKD-klienten pakker HTTP-feil slik). Begge fanges.
    Valideringsfeil (blokkerende avvik) gir 422; alt annet fra Altinn/Skatteetaten gir 502.
    """
    try:
        return fn()
    except InnsendingValideringsfeil as e:
        raise HTTPException(status_code=422, detail={"feil": e.feil})
    except SkattemeldingValideringsfeil as e:  # subklasse av RuntimeError — må fanges først
        raise HTTPException(status_code=422, detail={"validering": str(e)})
    except httpx.HTTPStatusError as e:
        raise _tolk_http_feil(e)
    except httpx.RequestError:
        # Tidsavbrudd/tilkoblingsfeil (ikke et HTTP-svar). Søsken av HTTPStatusError, så den
        # må fanges eksplisitt — ellers blir den en naken 500. Samme hull som hostet tettet
        # i PR #131.
        raise HTTPException(
            status_code=502,
            detail=(
                "Fikk ikke fullført forespørselen mot Altinn/Skatteetaten (nettverksfeil eller "
                "tidsavbrudd). Det er som regel midlertidig. Sjekk i Altinn eller hos Skatteetaten "
                "før du prøver på nytt, i tilfelle forespørselen likevel gikk gjennom."
            ),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/aarsregnskap")
def innsending_aarsregnskap(config: dict[str, Any] = Body(...), dry_run: bool = False) -> dict:
    config = miljo.med_test_org(config)
    if dry_run:
        return {"dry_run": True, **tjeneste.valider_aarsregnskap(config)}
    token = auth.get_altinn_token()

    def _send():
        with AltinnClient(token, env=miljo.aktiv_env()) as klient:
            return tjeneste.send_aarsregnskap(config, klient)

    return _utfor(_send)


@router.post("/aksjonaer")
def innsending_aksjonaer(config: dict[str, Any] = Body(...), dry_run: bool = False) -> dict:
    config = miljo.med_test_org(config)
    if dry_run:
        return {"dry_run": True, **tjeneste.valider_aksjonaer(config)}
    token = auth.get_skd_aksjonaer_token()

    def _send():
        with SkdAksjonaerClient(token, env=miljo.aktiv_env()) as klient:
            return tjeneste.send_aksjonaer(config, klient)

    return _utfor(_send)


@router.post("/skattemelding")
def innsending_skattemelding(config: dict[str, Any] = Body(...), dry_run: bool = False) -> dict:
    config = miljo.med_test_org(config)
    if dry_run:
        return {"dry_run": True, **tjeneste.valider_skattemelding(config)}
    tokens = auth.get_skd_skattemelding_tokens()
    orgnr = _orgnr(config)
    # Henter alltid live forhåndsutfylt (gir riktig partsnummer + gjeldende dokument-id) for org-en.
    # Bruker bevisst IKKE SKD_TEST_PARTSNUMMER-snarveien: et hardkodet partsnummer som ikke matcher
    # test-org-en gir «tekniskFeil» fra SKDs validator. Samme flyt som prod.
    def _send():
        with SkdSkattemeldingClient(tokens["maskinporten_token"], env=miljo.aktiv_env()) as skd:
            return tjeneste.send_skattemelding(config, skd, tokens["altinn_token"], orgnr=orgnr)

    return _utfor(_send)
