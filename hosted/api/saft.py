"""
SAF-T Financial-import for hostet Wenche.

Tar imot en opplastet SAF-T XML som rå request-body, parser den i minnet (wenche.saft) og
returnerer en config-dict som klienten forhåndsfyller skjemaet med. Krever gyldig invite, ikke
vendor/kunde-org, siden ingenting sendes inn. Personvern: bytene leses inn i minnet, parses og
forkastes. Ingenting skrives til disk eller lagres (sesjonen er fasit). Behandlingen skjer i
EØS (Fly arn/Stockholm). Org-låsen i klienten gjør at SAF-T-ens org ikke endrer kundeidentitet.
"""
from fastapi import APIRouter, HTTPException, Query, Request

from wenche.saft import importer_bytes

from .deps import krev_invitert

router = APIRouter(prefix="/api/saft", tags=["saft"])

# Romslig tak. En SAF-T for et passivt holdingselskap er noen få kB; grensen hindrer at en stor
# opplasting spiller over til en temp-fil på disk og holder behandlingen i minnet.
_MAKS_BYTES = 1_000_000


@router.post("/import")
async def importer_saft(request: Request, foregaaende: bool = Query(False)) -> dict:
    krev_invitert(request)
    lengde = request.headers.get("content-length")
    if lengde and lengde.isdigit() and int(lengde) > _MAKS_BYTES:
        raise HTTPException(status_code=413, detail="SAF-T-filen er for stor (maks 1 MB).")
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Tom forespørsel: last opp en SAF-T-fil.")
    if len(data) > _MAKS_BYTES:
        raise HTTPException(status_code=413, detail="SAF-T-filen er for stor (maks 1 MB).")
    try:
        config = importer_bytes(data)
    except Exception as e:  # ugyldig/uventet XML
        raise HTTPException(status_code=422, detail=f"Kunne ikke lese SAF-T-filen: {e}")
    if foregaaende:
        # Fjorårets SAF-T: dens sluttsaldoer er fjorårets resultat og balanse (sammenligningstall).
        return {
            "regnskapsaar": config.get("regnskapsaar"),
            "foregaaende_aar": {
                "resultatregnskap": config["resultatregnskap"],
                "balanse": config["balanse"],
            },
        }
    return config
