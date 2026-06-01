"""Delte FastAPI-vakter/avhengigheter for hosted-appen."""
import secrets

from fastapi import HTTPException, Request

from wenche import auth as wauth
from wenche.auth import ADMIN_SCOPES, VendorCredentials

from . import session as sesjon
from .config import settings


def krev_invitert(request: Request) -> sesjon.SessionState:
    """Krev at økten har løst inn en gyldig invite-lenke. Sikrer også en sesjon-ID."""
    if not request.session.get("invited"):
        raise HTTPException(status_code=401, detail="Wenche er kun for inviterte.")
    sid = request.session.get("sid")
    if not sid:
        sid = secrets.token_urlsafe(16)
        request.session["sid"] = sid
    return sesjon.hent(sid)


def krev_vendor() -> tuple[VendorCredentials, str]:
    s = settings()
    creds = s.vendor_credentials()
    if not creds or not s.vendor_orgnr:
        raise HTTPException(status_code=503, detail="Vendor er ikke konfigurert på serveren.")
    return creds, s.vendor_orgnr


def krev_invite_org(request: Request) -> str:
    """Org-en invitasjonen gjelder, autoritativt fra den signerte invite-lenken (ikke brukerinput)."""
    org = request.session.get("invite_org")
    if not org:
        raise HTTPException(
            status_code=409,
            detail="Invite-lenken er ikke knyttet til et selskap. Be om en ny lenke.",
        )
    return str(org).strip()


def krev_kunde_org(st: sesjon.SessionState) -> str:
    if not st.kunde_org:
        raise HTTPException(
            status_code=409,
            detail="Ingen godkjent systembruker. Fullfør systembruker-onboarding først.",
        )
    return st.kunde_org


def admin_token(creds: VendorCredentials) -> str:
    """Maskinporten-token med admin-scopes (systemregister/systembruker), uten systembruker-claim."""
    return wauth.hent_tokens_for(creds, scopes=ADMIN_SCOPES)["maskinporten_token"]
