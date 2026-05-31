"""
Invite-only-port + sesjonsstatus for hostet Wenche.

Onboarding-modellen (besluttet): invite-lenke + BankID.
- Invite-lenke: en signert token (uten utløp) du deler ut manuelt. Gyldig token setter
  'invited' i sesjonen. Roteres ved å bytte HOSTED_INVITE_SECRET.
- Selve autentiseringen/autorisasjonen er Altinn systembruker-godkjenning (BankID), se
  systembruker.py. En lekket invite-lenke gir kun tilgang til app-skallet, ikke evnen til
  å sende inn for en org man ikke kontrollerer.

Ingen e-post, ingen passord, ingen database.
"""
import secrets

from fastapi import APIRouter, Request
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel

from . import session as sesjon
from .config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SALT = "invite"
_PAYLOAD = "wenche-invite"


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings().invite_secret, salt=_SALT)


def lag_invite_token() -> str:
    """Lag invite-token (uten utløp). Del ut som {public_url}/?invite=<token>."""
    return _serializer().dumps(_PAYLOAD)


class InviteBody(BaseModel):
    token: str


@router.post("/invite")
def bruk_invite(body: InviteBody, request: Request) -> dict:
    """Løs inn en invite-lenke og marker økten som invitert."""
    try:
        payload = _serializer().loads(body.token)
    except BadSignature:
        return {"invited": False, "feil": "Ugyldig invite-lenke."}
    if payload != _PAYLOAD:
        return {"invited": False, "feil": "Ugyldig invite-lenke."}
    request.session["invited"] = True
    if not request.session.get("sid"):
        request.session["sid"] = secrets.token_urlsafe(16)
    return {"invited": True}


@router.get("/me")
def me(request: Request) -> dict:
    """Sesjonsstatus: er økten invitert, og hvilken kunde-org er evt. bundet."""
    if not request.session.get("invited"):
        return {"invited": False}
    sid = request.session.get("sid")
    st = sesjon.hent(sid) if sid else None
    return {"invited": True, "kunde_org": st.kunde_org if st else None}


@router.post("/logout")
def logout(request: Request) -> dict:
    """Logg ut: slett ephemeral sesjonsdata og tøm cookien."""
    sid = request.session.get("sid")
    if sid:
        sesjon.slett(sid)
    request.session.clear()
    return {"ok": True}
