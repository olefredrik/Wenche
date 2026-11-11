"""
SAF-T Financial-import, delt av hostet og self-hosted.

Tar imot en opplastet SAF-T XML som rå request-body, parser den i minnet (wenche.saft) og
returnerer en config-dict som SPA-en forhåndsfyller skjemaet med. Ingenting skrives til disk
eller lagres: bytene leses inn i minnet, parses og forkastes. Brukeren ser over og lagrer selv.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from wenche.saft import importer_bytes

# Romslig tak. En SAF-T for et passivt holdingselskap er noen få kB; grensen holder behandlingen
# i minnet. Den håndheves også av Kroppsgrense-middlewaren før kroppen leses (se kropp.py, appene
# registrerer STI med denne grensen); sjekkene her er belte og bukseseler.
MAKS_BYTES = 1_000_000
STI = "/api/saft/import"
_FOR_STOR = "SAF-T-filen er for stor (maks 1 MB)."


def importer(data: bytes, *, foregaaende: bool = False) -> dict:
    """Config-dict fra SAF-T-bytene. 400 tom, 413 for stor, 422 når XML-en ikke lar seg lese."""
    if not data:
        raise HTTPException(status_code=400, detail="Tom forespørsel: last opp en SAF-T-fil.")
    if len(data) > MAKS_BYTES:
        raise HTTPException(status_code=413, detail=_FOR_STOR)
    try:
        config = importer_bytes(data)
    except Exception as e:  # ugyldig/uventet XML
        raise HTTPException(status_code=422, detail=f"Kunne ikke lese SAF-T-filen: {e}") from e
    if foregaaende:
        # Brukeren lastet opp fjorårets SAF-T. Dens sluttsaldoer er fjorårets resultat og
        # balanse, altså nettopp sammenligningstallene. Klienten merger kun dette inn.
        return {
            "regnskapsaar": config.get("regnskapsaar"),
            "foregaaende_aar": {
                "resultatregnskap": config["resultatregnskap"],
                "balanse": config["balanse"],
            },
            # Advarsler gjelder tallene som importeres, også når bare fjoråret hentes.
            **({"_advarsler": config["_advarsler"]} if "_advarsler" in config else {}),
        }
    return config


def lag_router(*, vakt: Callable[..., Any] | None = None) -> APIRouter:
    """Ruteren POST /api/saft/import for én app; `vakt` kjøres som avhengighet før kallet."""
    router = APIRouter(
        prefix="/api/saft", tags=["saft"], dependencies=[Depends(vakt)] if vakt else []
    )

    @router.post("/import")
    async def importer_saft(request: Request, foregaaende: bool = Query(False)) -> dict:
        lengde = request.headers.get("content-length")
        if lengde and lengde.isdigit() and int(lengde) > MAKS_BYTES:
            raise HTTPException(status_code=413, detail=_FOR_STOR)
        return importer(await request.body(), foregaaende=foregaaende)

    return router
