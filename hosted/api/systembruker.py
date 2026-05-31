"""
Systembruker-onboarding for hostet Wenche (Fase 4).

Operatøren (vendor) registrerer sluttbrukersystemet i Altinn én gang. Per kunde:
  1. POST /api/systembruker/request {org}  -> opprett forespørsel, returner confirmUrl.
  2. Kunden godkjenner i Altinn med BankID (daglig leder/styreleder).
  3. POST /api/systembruker/status         -> sjekk status; ved 'Accepted' bindes
                                              sesjonens kunde-org.

Gjenbruker `wenche.systembruker` (samme kode som self-hosted). Vendor-creds og
vendor-orgnr kommer fra server-config; request-id holdes i sesjonen, ikke i filer.
"""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from wenche import auth as wauth
from wenche import systembruker as wsb
from wenche.auth import ADMIN_SCOPES, VendorCredentials

from . import session as sesjon
from .config import settings

logger = logging.getLogger("wenche.hosted.systembruker")
router = APIRouter(prefix="/api/systembruker", tags=["systembruker"])


def _krev_sesjon(request: Request) -> sesjon.SessionState:
    sid = request.session.get("sid")
    if not sid or not request.session.get("epost"):
        raise HTTPException(status_code=401, detail="Ikke innlogget.")
    return sesjon.hent(sid)


def _krev_vendor() -> tuple[VendorCredentials, str]:
    s = settings()
    creds = s.vendor_credentials()
    if not creds or not s.vendor_orgnr:
        raise HTTPException(status_code=503, detail="Vendor er ikke konfigurert på serveren.")
    return creds, s.vendor_orgnr


def _admin_token(creds: VendorCredentials) -> str:
    """Maskinporten-token med admin-scopes (systemregister/systembruker), uten systembruker_org."""
    return wauth.hent_tokens_for(creds, scopes=ADMIN_SCOPES)["maskinporten_token"]


class OrgForespoersel(BaseModel):
    org: str


@router.post("/request")
def request_systembruker(body: OrgForespoersel, request: Request) -> dict:
    """Opprett en systembruker-forespørsel for kundens org og returner godkjenningslenke."""
    st = _krev_sesjon(request)
    creds, vendor_orgnr = _krev_vendor()
    org = body.org.strip()
    token = _admin_token(creds)
    # Sikre at systemet er registrert (idempotent), så opprett forespørselen.
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
    """Sjekk status på forespørselen; ved 'Accepted' bindes kunde-org til sesjonen."""
    st = _krev_sesjon(request)
    creds, _ = _krev_vendor()
    if not st.request_id:
        raise HTTPException(status_code=400, detail="Ingen aktiv systembruker-forespørsel.")
    token = _admin_token(creds)
    svar = wsb.hent_forespørsel_status(token, st.request_id)
    status = svar.get("status")
    godkjent = status == "Accepted"
    if godkjent and st.pending_org:
        st.kunde_org = st.pending_org
    return {"status": status, "godkjent": godkjent, "kunde_org": st.kunde_org}
