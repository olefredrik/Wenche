"""
Forhåndsfyll-endepunkt for den hostede tjenesten.

Henter selskapsopplysninger Enhetsregisteret kjenner (daglig leder, styreleder, stiftelsesår)
for den koblede orgen, slik at klienten kan forhåndsfylle skjemaet. SAF-T bærer ikke disse
feltene, så uten dette må brukeren skrive dem manuelt etter import (se issue #130).

Nøkles på den signerte øktbindingen (kunde_org, ev. invite_org), aldri brukerinput, så oppslaget
ikke kan misbrukes til å enumerere registeret. Kun offentlige data, ingenting lagres. Fail-soft:
er registeret nede, returneres tomme felter og skjemaet forblir tomt (samme oppførsel som før).
"""
from fastapi import APIRouter, HTTPException, Request

from wenche import brreg

from .deps import krev_invitert

router = APIRouter(prefix="/api/selskap", tags=["selskap"])


@router.get("")
def hent_selskap(request: Request) -> dict:
    krev_invitert(request)
    org = request.session.get("kunde_org") or request.session.get("invite_org")
    if not org:
        raise HTTPException(status_code=409, detail="Ingen koblet org å hente opplysninger for.")
    org = str(org).strip()
    roller = brreg.hent_roller(org)
    return {
        "org_nummer": org,
        "daglig_leder": roller["daglig_leder"],
        "styreleder": roller["styreleder"],
        "stiftelsesaar": brreg.hent_stiftelsesaar(org),
    }
