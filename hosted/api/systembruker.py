"""
Systembruker-onboarding for hostet Wenche (Fase 4).

Operatøren (vendor) registrerer sluttbrukersystemet i Altinn én gang. Per kunde:
  1. POST /api/systembruker/request {org}  -> opprett forespørsel, returner confirmUrl.
  2. Kunden godkjenner i Altinn med BankID (daglig leder/styreleder).
  3. POST /api/systembruker/status         -> sjekk status; ved 'Accepted' bindes
                                              sesjonens kunde-org.

Gjenbruker `wenche.systembruker` (samme kode som self-hosted). Request-id holdes i
sesjonen, ikke i filer.
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from wenche import systembruker as wsb

from .deps import admin_token, krev_sesjon, krev_vendor

logger = logging.getLogger("wenche.hosted.systembruker")
router = APIRouter(prefix="/api/systembruker", tags=["systembruker"])


class OrgForespoersel(BaseModel):
    org: str


@router.post("/request")
def request_systembruker(body: OrgForespoersel, request: Request) -> dict:
    """
    Start systembruker-onboarding for kundens org.

    Gjenkommende kunde: har org allerede en godkjent systembruker for vårt system,
    bindes kunde-org direkte (ingen ny BankID-godkjenning). Ny kunde: opprett
    forespørsel og returner godkjenningslenke.
    """
    st = krev_sesjon(request)
    creds, vendor_orgnr = krev_vendor()
    org = body.org.strip()
    token = admin_token(creds)
    eksisterende = wsb.hent_systembrukere(token, vendor_orgnr)
    if any(b.get("reporteeOrgNo") == org for b in eksisterende):
        st.kunde_org = org
        st.pending_org = None
        st.request_id = None
        return {"status": "AlreadyApproved", "godkjent": True, "kunde_org": org}
    # Ny kunde: sikre at systemet er registrert (idempotent), så opprett forespørselen.
    wsb.registrer_system(token, vendor_orgnr, creds.client_id)
    svar = wsb.opprett_forespørsel(token, vendor_orgnr, org)
    st.request_id = svar.get("id")
    st.pending_org = org
    return {
        "request_id": st.request_id,
        "status": svar.get("status"),
        "confirm_url": svar.get("confirmUrl"),
    }


@router.post("/status")
def status_systembruker(request: Request) -> dict:
    """Sjekk status; ved 'Accepted' bindes kunde-org til sesjonen."""
    st = krev_sesjon(request)
    creds, _ = krev_vendor()
    if not st.request_id:
        raise HTTPException(status_code=400, detail="Ingen aktiv systembruker-forespørsel.")
    token = admin_token(creds)
    svar = wsb.hent_forespørsel_status(token, st.request_id)
    status = svar.get("status")
    godkjent = status == "Accepted"
    if godkjent and st.pending_org:
        st.kunde_org = st.pending_org
    return {"status": status, "godkjent": godkjent, "kunde_org": st.kunde_org}
