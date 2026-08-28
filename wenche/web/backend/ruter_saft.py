"""
SAF-T Financial-import for self-hosted Wenche.

Tar imot en opplastet SAF-T XML som rå request-body, parser den i minnet (wenche.saft) og
returnerer en config-dict som SPA-en forhåndsfyller skjemaet med. Ingenting skrives til disk
eller lagres: bytene leses inn i minnet, parses og forkastes. Brukeren ser over og lagrer selv.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from wenche.saft import importer_bytes

router = APIRouter(prefix="/api/saft", tags=["saft"])

# Romslig tak. En SAF-T for et passivt holdingselskap er noen få kB; grensen hindrer at en stor
# opplasting spiller over til en temp-fil på disk og holder behandlingen i minnet.
_MAKS_BYTES = 1_000_000


def _les_med_grense(data: bytes) -> dict:
    if not data:
        raise HTTPException(status_code=400, detail="Tom forespørsel: last opp en SAF-T-fil.")
    if len(data) > _MAKS_BYTES:
        raise HTTPException(status_code=413, detail="SAF-T-filen er for stor (maks 1 MB).")
    try:
        return importer_bytes(data)
    except HTTPException:
        raise
    except Exception as e:  # ugyldig/uventet XML
        raise HTTPException(status_code=422, detail=f"Kunne ikke lese SAF-T-filen: {e}")


@router.post("/import")
async def importer_saft(request: Request, foregaaende: bool = Query(False)) -> dict:
    lengde = request.headers.get("content-length")
    if lengde and lengde.isdigit() and int(lengde) > _MAKS_BYTES:
        raise HTTPException(status_code=413, detail="SAF-T-filen er for stor (maks 1 MB).")
    config = _les_med_grense(await request.body())
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
