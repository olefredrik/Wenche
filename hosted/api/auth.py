"""
Magic-link-innlogging + invite-allowlist for hostet Wenche (Fase 3).

Flyt:
  1. POST /api/auth/request-link {epost}  -> hvis invitert, lag signert engangstoken
     og "send" lenke. Dev: lenken logges (og returneres som dev_lenke for testing).
  2. GET  /api/auth/verify?token=...      -> valider token + allowlist, sett sesjonsidentitet.
  3. GET  /api/auth/me                     -> gjeldende identitet.
  4. POST /api/auth/logout                 -> nullstill sesjon + slett ephemeral data.

Identitet bæres i en signert sesjonscookie, ingen brukerdatabase. Kunde-org bindes
senere (Fase 4, systembruker-godkjenning).
"""
import logging
import secrets

from fastapi import APIRouter, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from . import session as sesjon
from .config import settings

logger = logging.getLogger("wenche.hosted.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

_SALT = "magic-link"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings().session_secret, salt=_SALT)


def _send_magic_link(epost: str, lenke: str) -> None:
    """
    Pluggbar sender. Dev: logg lenken. Prod (senere): ekte e-postleverandør
    (Postmark/Resend/SMTP). Holdt bak denne ene funksjonen så bytte er trivielt.
    """
    logger.info("Magic-link til %s: %s", epost, lenke)


class LinkForespoersel(BaseModel):
    epost: str


@router.post("/request-link")
def request_link(body: LinkForespoersel) -> dict:
    """Be om innloggingslenke. Svarer generisk uansett, for å hindre e-post-enumerering."""
    s = settings()
    epost = body.epost.strip().lower()
    svar: dict = {"sendt": True}
    if epost in s.allowlist:
        token = _serializer().dumps(epost)
        lenke = f"{s.public_url}/api/auth/verify?token={token}"
        _send_magic_link(epost, lenke)
        if s.expose_dev_link:
            svar["dev_lenke"] = lenke
    return svar


@router.get("/verify")
def verify(token: str, request: Request) -> dict:
    """Valider engangslenken og etabler sesjonsidentitet."""
    s = settings()
    try:
        epost = _serializer().loads(token, max_age=s.link_max_age_sec)
    except SignatureExpired:
        return {"ok": False, "feil": "Lenken er utløpt."}
    except BadSignature:
        return {"ok": False, "feil": "Ugyldig lenke."}
    if epost.lower() not in s.allowlist:
        return {"ok": False, "feil": "Ikke invitert."}
    sid = secrets.token_urlsafe(16)
    request.session["sid"] = sid
    request.session["epost"] = epost.lower()
    sesjon.hent(sid).epost = epost.lower()
    return {"ok": True, "epost": epost.lower()}


@router.get("/me")
def me(request: Request) -> dict:
    """Gjeldende sesjonsidentitet (og kunde-org når den er bundet i Fase 4)."""
    epost = request.session.get("epost")
    if not epost:
        return {"innlogget": False}
    sid = request.session.get("sid")
    st = sesjon.hent(sid) if sid else None
    return {
        "innlogget": True,
        "epost": epost,
        "kunde_org": st.kunde_org if st else None,
    }


@router.post("/logout")
def logout(request: Request) -> dict:
    """Logg ut: slett ephemeral sesjonsdata og tøm cookien."""
    sid = request.session.get("sid")
    if sid:
        sesjon.slett(sid)
    request.session.clear()
    return {"ok": True}
