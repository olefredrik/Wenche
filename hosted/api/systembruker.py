"""
Systembruker-onboarding for hostet Wenche.

Operatøren (vendor) registrerer sluttbrukersystemet i Altinn én gang. Per kunde:
  1. POST /api/systembruker/request {org}  -> opprett forespørsel, returner confirmUrl.
  2. Kunden godkjenner i Altinn med BankID (daglig leder/styreleder).
  3. POST /api/systembruker/status         -> sjekk status; ved 'Accepted' bindes
                                              sesjonens kunde-org.

Gjenbruker `wenche.systembruker` (samme kode som self-hosted). Forespørsels-id og binding
holdes i den signerte session-cookien, ikke i serverminnet eller filer, så en sovende/
restartende maskin ikke mister en alt etablert tilkobling.
"""
import logging

from fastapi import APIRouter, HTTPException, Request

from wenche import systembruker as wsb

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

    AlreadyApproved-snarveien (binding uten ny BankID) er trygg fordi begge portene foran er
    sterke: invite-lenken er operatør-attestert, og ID-porten-stien har bevist identiteten med
    BankID + bekreftet rolle for orgnr i Enhetsregisteret (se auth.velg_org). En som bare kjenner
    et offentlig styremedlemsnavn kommer ikke forbi porten i utgangspunktet.
    """
    krev_invitert(request)
    org = krev_invite_org(request)
    creds, vendor_orgnr = krev_vendor()
    token = admin_token(creds)
    eksisterende = wsb.hent_systembrukere(token, vendor_orgnr)
    if any(b.get("reporteeOrgNo") == org for b in eksisterende):
        request.session["kunde_org"] = org
        request.session.pop("pending_org", None)
        request.session.pop("request_id", None)
        return {"status": "AlreadyApproved", "godkjent": True, "kunde_org": org}
    # Ny kunde: sikre at systemet er registrert (idempotent), så opprett forespørselen.
    wsb.registrer_system(token, vendor_orgnr, creds.client_id)
    svar = wsb.opprett_forespørsel(token, vendor_orgnr, org)
    request.session["request_id"] = svar.get("id")
    request.session["pending_org"] = org
    return {
        "request_id": svar.get("id"),
        "status": svar.get("status"),
        "confirm_url": svar.get("confirmUrl"),
    }


@router.post("/status")
def status_systembruker(request: Request) -> dict:
    """Sjekk status; ved 'Accepted' bindes kunde-org til sesjonen."""
    krev_invitert(request)
    creds, _ = krev_vendor()
    request_id = request.session.get("request_id")
    if not request_id:
        raise HTTPException(status_code=400, detail="Ingen aktiv systembruker-forespørsel.")
    token = admin_token(creds)
    svar = wsb.hent_forespørsel_status(token, request_id)
    status = svar.get("status")
    godkjent = status == "Accepted"
    if godkjent and request.session.get("pending_org"):
        request.session["kunde_org"] = request.session["pending_org"]
    return {"status": status, "godkjent": godkjent, "kunde_org": request.session.get("kunde_org")}
