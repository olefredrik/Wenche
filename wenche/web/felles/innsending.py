"""
Innsending, delt av hostet og self-hosted.

Orkestreringen (bygg, valider, send) ligger i `wenche.innsending` og deles også med CLI-en.
Her ligger det web-laget legger oppå: config i request-body (klienten er fasit, ingenting lagres
mellom kall), dry-run uten nettverk, og én feilfelle (`kjoer`) som gjør alt domeneklientene
melder om til lesbare HTTP-svar, aldri en rå 500.

Appene skiller seg bare i hvordan de autentiserer og hvilken org de sender for, og
`lag_router` tar det som parametre: hostet gir vendor-creds med den økt-bundne kunde-orgen som
systembruker-claim, self-hosted gir brukerens egen Maskinporten-innlogging.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request

from wenche import innsending as tjeneste
from wenche.altinn_client import AltinnClient
from wenche.feil import KonfigFeil, MyndighetsFeil, ValideringsFeil, brukermelding, url_fra_unntak
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import SkattemeldingValideringsfeil, SkdSkattemeldingClient

from .svar import InnsendingSvar, ValideringSvar

log = logging.getLogger("wenche.web.innsending")

# Hintet self-hosted legger til ved 403 i testmiljø: der er årsaken nesten alltid at config-orgen
# ikke er Tenor-orgen systembrukeren er godkjent for.
TENOR_HINT = " I testmiljø må selskapets org_nummer være Tenor-orgnr-et du har systembruker for."


class TokenKilde(Protocol):
    """
    Tokens for en innsending på vegne av `org`. Kalles inne i feilfellen, så et avslag fra
    Maskinporten eller en feilet Altinn-veksling blir en lesbar 502, ikke en naken 500.
    """

    def altinn(self, org: str) -> str: ...

    def skd_aksjonaer(self, org: str) -> str: ...

    def skd_skattemelding(self, org: str) -> tuple[str, str]:
        """(maskinporten_token, altinn_token)."""
        ...


# ---------------------------------------------------------------------------
# Feilfellen
# ---------------------------------------------------------------------------


def steg_av_url(url: str) -> str | None:
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


def fra_httpx(e: httpx.HTTPError) -> MyndighetsFeil:
    """Rå httpx-feil som slapp forbi en klient: pakk som MyndighetsFeil med steg utledet av URL-en."""
    url = url_fra_unntak(e) or ""
    tjeneste_navn = "skatteetaten" if ("skatteetaten" in url or "sits.no" in url) else "altinn"
    steg = steg_av_url(url) or ""
    if isinstance(e, httpx.HTTPStatusError):
        return MyndighetsFeil.fra_svar(tjeneste_navn, steg, e.response)
    if isinstance(e, httpx.RequestError):
        return MyndighetsFeil.fra_nettverksfeil(tjeneste_navn, steg, e)
    return MyndighetsFeil(tjeneste_navn, steg, beskrivelse=type(e).__name__)


def lesbar_502(
    e: MyndighetsFeil, *, org: str | None = None, hint_403: str | None = None
) -> HTTPException:
    """
    Logg feilen server-side (steg, status, kode, URL; svarkroppen bare på DEBUG, den kan
    inneholde interne detaljer) og gi brukeren en melding som navngir steget og koden.
    `org` logges (ikke kundedata) så en operatør kan knytte feilen til riktig selskap.
    """
    log.warning(
        "Innsending feilet%s: %s (HTTP %s, kode %s, url %s)",
        f" for org {org}" if org else "",
        e.steg or "ukjent steg",
        e.status,
        e.kode,
        e.url,
    )
    if e.kropp:
        log.debug("Svarkropp: %s", e.kropp[:2000])
    melding = brukermelding(e)
    if e.status == 403 and hint_403:
        melding += hint_403
    return HTTPException(status_code=502, detail=melding)


def kjoer(fn: Callable[[], Any], *, org: str | None = None, hint_403: str | None = None) -> Any:
    """
    Kjør en innsending og gjør alle feil om til lesbare HTTP-svar, aldri en rå 500.

    `fn` må omslutte HELE innsendingen, inkludert token-hentingen: et avslag fra Maskinporten
    (f.eks. systembruker mangler en rettighet) eller en feilet Altinn-veksling kaster ellers
    utenfor denne fellen og blir en naken 500 hos brukeren.

    Valideringsfeil og config-feil gir 422; alt fra myndighetene (MyndighetsFeil fra klientene,
    eller rå httpx-feil som reserve) gir 502 med steget navngitt. Bevisst reist HTTPException
    slipper gjennom uendret. Alt annet blir en kontrollert 500 med melding (og traceback i
    loggen), aldri en stacktrace hos brukeren.
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
        raise lesbar_502(e, org=org, hint_403=hint_403) from e
    except httpx.HTTPError as e:
        raise lesbar_502(fra_httpx(e), org=org, hint_403=hint_403) from e
    except HTTPException:
        raise  # alt bevisst reist (f.eks. org-vakten sin 409) skal slippe gjennom uendret
    except RuntimeError as e:
        # Eldre feil med ferdig melding. Bare første linje til klienten (en eventuell
        # svarkropp etter linjeskift logges, vises ikke).
        log.warning("Innsending feilet%s: %s", f" for org {org}" if org else "", e)
        raise HTTPException(status_code=502, detail=str(e).split("\n", 1)[0]) from e
    except Exception:
        log.exception("Uventet feil under innsending%s", f" for org {org}" if org else "")
        raise HTTPException(
            status_code=500,
            detail="Uventet feil under innsending. Feilen er logget. Prøv igjen, eller ta kontakt.",
        ) from None


# ---------------------------------------------------------------------------
# Ruteren
# ---------------------------------------------------------------------------


def org_fra_config(request: Request, config: dict) -> str:
    """Standard `forbered`: send for selskapet i config-en (self-hosted)."""
    return str((config.get("selskap") or {}).get("org_nummer", "")).strip()


def lag_router(
    *,
    tokens: TokenKilde,
    env: Callable[[], str],
    vakt: Callable[..., Any] | None = None,
    transform: Callable[[dict], dict] = lambda config: config,
    forbered: Callable[[Request, dict], str] = org_fra_config,
    hint_403: Callable[[], str | None] = lambda: None,
) -> APIRouter:
    """
    Ruteren /api/innsending/* for én app.

    - `vakt`: FastAPI-avhengighet før hvert kall (hostet: krev_invitert).
    - `transform`: kjøres på config-en først (self-hosted: miljo.med_test_org).
    - `forbered(request, config)`: kjøres før en EKTE innsending (ikke dry-run) og gir org-en
      det sendes for. Hostet krever her vendor-config og økt-bundet kunde-org lik data-org, og
      reiser 409/503 selv; self-hosted bruker config-orgen.
    - `tokens`: TokenKilde, kalt inne i feilfellen.
    - `env`: aktivt myndighetsmiljø for klientene, lest per kall.
    - `hint_403`: tillegg til meldingen ved 403, lest per kall (self-hosted: Tenor-hintet i test).

    dry_run gir lokal validering uten nettverk og uten binding; svaret er ValideringSvar.
    """
    router = APIRouter(
        prefix="/api/innsending",
        tags=["innsending"],
        dependencies=[Depends(vakt)] if vakt else [],
    )
    svar_modell = ValideringSvar | InnsendingSvar

    @router.post("/aarsregnskap", response_model=svar_modell, response_model_exclude_none=True)
    def innsending_aarsregnskap(
        request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
    ) -> dict:
        config = transform(config)
        if dry_run:
            return kjoer(lambda: {"dry_run": True, **tjeneste.valider_aarsregnskap(config)})
        org = forbered(request, config)

        def _send() -> dict:
            with AltinnClient(tokens.altinn(org), env=env()) as klient:
                return tjeneste.send_aarsregnskap(config, klient)

        return kjoer(_send, org=org, hint_403=hint_403())

    @router.post("/aksjonaer", response_model=svar_modell, response_model_exclude_none=True)
    def innsending_aksjonaer(
        request: Request, config: dict[str, Any] = Body(...), dry_run: bool = False
    ) -> dict:
        config = transform(config)
        if dry_run:
            return kjoer(lambda: {"dry_run": True, **tjeneste.valider_aksjonaer(config)})
        org = forbered(request, config)

        def _send() -> dict:
            with SkdAksjonaerClient(tokens.skd_aksjonaer(org), env=env()) as klient:
                return tjeneste.send_aksjonaer(config, klient)

        return kjoer(_send, org=org, hint_403=hint_403())

    @router.post("/skattemelding", response_model=svar_modell, response_model_exclude_none=True)
    def innsending_skattemelding(
        request: Request,
        config: dict[str, Any] = Body(...),
        dry_run: bool = False,
        bekreft_klage: bool = False,
    ) -> dict:
        config = transform(config)
        if dry_run:
            return kjoer(lambda: {"dry_run": True, **tjeneste.valider_skattemelding(config)})
        org = forbered(request, config)

        # Henter alltid live forhåndsutfylt (riktig partsnummer + gjeldende dokument-id) for
        # org-en, aldri SKD_TEST_PARTSNUMMER-snarveien: et hardkodet partsnummer som ikke matcher
        # org-en gir «tekniskFeil» fra SKDs validator. Samme flyt som prod.
        def _send() -> dict:
            maskinporten_token, altinn_token = tokens.skd_skattemelding(org)
            with SkdSkattemeldingClient(maskinporten_token, env=env()) as skd:
                return tjeneste.send_skattemelding(
                    config, skd, altinn_token, orgnr=org, bekreft_klage=bekreft_klage
                )

        return kjoer(_send, org=org, hint_403=hint_403())

    return router
