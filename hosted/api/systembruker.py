"""
Systembruker-onboarding for hostet Wenche.

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

from wenche import systembruker as wsb

from .config import settings
from .deps import admin_token, krev_invite_org, krev_invitert, krev_vendor

logger = logging.getLogger("wenche.hosted.systembruker")
router = APIRouter(prefix="/api/systembruker", tags=["systembruker"])


@router.post("/request")
def request_systembruker(request: Request) -> dict:
    """
    Start systembruker-onboarding for selskapet i invitasjonen.

    Org-en kommer fra den signerte invite-lenken (krev_invite_org), ikke fra brukerinput,
    så ingen kan be om eller bindes til et selskap de ikke er invitert for.

    Gjenkommende kunde: har org allerede en godkjent systembruker for vårt system,
    bindes kunde-org direkte (ingen ny BankID-godkjenning). Ny kunde: opprett
    forespørsel og returner godkjenningslenke.

    Unntak for selvbetjente økter: AlreadyApproved-snarveien hopper over BankID, og
    selvbetjent tilgang er bare et navneoppslag mot offentlige data (ikke identitetsbevis).
    Å honorere snarveien der ville latt en som kjenner et offentlig styremedlemsnavn sende
    inn for et alt-onboardet selskap. Slike krever derfor manuell invitasjon.
    """
    st = krev_invitert(request)
    org = krev_invite_org(request)
    creds, vendor_orgnr = krev_vendor()
    token = admin_token(creds)
    eksisterende = wsb.hent_systembrukere(token, vendor_orgnr)
    if any(b.get("reporteeOrgNo") == org for b in eksisterende):
        if request.session.get("via_selvbetjening"):
            raise HTTPException(
                status_code=409,
                detail="Dette selskapet er allerede satt opp i Wenche. Av sikkerhetsgrunner "
                "kobles slike bare via en invitasjon. Ta kontakt: " + settings().kontakt + ".",
            )
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
    st = krev_invitert(request)
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
