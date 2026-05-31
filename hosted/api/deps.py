"""Delte FastAPI-vakter/avhengigheter for hosted-appen."""
from fastapi import HTTPException, Request

from wenche import auth as wauth
from wenche.auth import ADMIN_SCOPES, VendorCredentials

from . import session as sesjon
from .config import settings


def krev_sesjon(request: Request) -> sesjon.SessionState:
    sid = request.session.get("sid")
    if not sid or not request.session.get("epost"):
        raise HTTPException(status_code=401, detail="Ikke innlogget.")
    return sesjon.hent(sid)


def krev_vendor() -> tuple[VendorCredentials, str]:
    s = settings()
    creds = s.vendor_credentials()
    if not creds or not s.vendor_orgnr:
        raise HTTPException(status_code=503, detail="Vendor er ikke konfigurert på serveren.")
    return creds, s.vendor_orgnr


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
