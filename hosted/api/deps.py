"""
Delte FastAPI-vakter/avhengigheter for hosted-appen.

Sesjonsmodell: all per-bruker-tilstand bæres i den signerte session-cookien (Starlette
SessionMiddleware, se main.py), ingenting i serverminnet mellom requester og ingenting på
disk. Cookien holder kun ikke-sensitiv binding (invite-port, org-numre og en forespørsels-
UUID); selve innsendingsdataene (regnskap, fødselsnummer) sender klienten i request-body i
det ene kallet som behandler dem, og lagres aldri. At bindingen ligger i cookien og ikke i
prosessminnet er nettopp det som lar en sovende/restartende maskin (Fly scale-to-zero,
deploy) slippe å låse brukeren ute av en alt etablert tilkobling.
"""
from fastapi import HTTPException, Request

from wenche import auth as wauth
from wenche.auth import ADMIN_SCOPES, VendorCredentials

from .config import settings


def krev_invitert(request: Request) -> None:
    """Krev at økten har løst inn en gyldig invite-lenke."""
    if not request.session.get("invited"):
        raise HTTPException(status_code=401, detail="Wenche er kun for inviterte.")


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


def krev_kunde_org(request: Request) -> str:
    """Org-en med godkjent systembruker for denne økten, fra den signerte cookien."""
    org = request.session.get("kunde_org")
    if not org:
        raise HTTPException(
            status_code=409,
            detail="Ingen godkjent systembruker. Fullfør systembruker-onboarding først.",
        )
    return str(org)


def admin_token(creds: VendorCredentials) -> str:
    """Maskinporten-token med admin-scopes (systemregister/systembruker), uten systembruker-claim."""
    return wauth.hent_tokens_for(creds, scopes=ADMIN_SCOPES)["maskinporten_token"]
