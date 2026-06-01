"""
Invite-only-port + sesjonsstatus for hostet Wenche.

Onboarding-modellen (besluttet): per-org invite-lenke + BankID.
- Invite-lenke: en signert token som bærer ETT bestemt organisasjonsnummer, du deler den
  ut manuelt til en kjent, verifisert person. Gyldig token setter 'invited' og binder
  sesjonen til org-en i tokenet. Org er altså ikke fritt brukerinput. Roteres ved å bytte
  HOSTED_INVITE_SECRET (ugyldiggjør alle utdelte lenker).
- Selve autentiseringen/autorisasjonen er Altinn systembruker-godkjenning (BankID), se
  systembruker.py. En lekket invite-lenke er avgrenset til det ene selskapet i tokenet
  (og kan tilbakekalles ved rotasjon), ikke evnen til å sende inn for en vilkårlig org.

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


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings().invite_secret, salt=_SALT)


def lag_invite_token(org: str) -> str:
    """Lag invite-token for ETT bestemt selskap. Del ut som {public_url}/?invite=<token>."""
    return _serializer().dumps({"org": str(org).strip()})


class InviteBody(BaseModel):
    token: str


@router.post("/invite")
def bruk_invite(body: InviteBody, request: Request) -> dict:
    """Løs inn en per-org invite-lenke og bind økten til selskapet i tokenet."""
    try:
        payload = _serializer().loads(body.token)
    except BadSignature:
        return {"invited": False, "feil": "Ugyldig invite-lenke."}
    org = payload.get("org") if isinstance(payload, dict) else None
    if not org:
        return {"invited": False, "feil": "Ugyldig invite-lenke."}
    request.session["invited"] = True
    request.session["invite_org"] = str(org).strip()
    if not request.session.get("sid"):
        request.session["sid"] = secrets.token_urlsafe(16)
    return {"invited": True, "invite_org": str(org).strip()}


@router.get("/me")
def me(request: Request) -> dict:
    """Sesjonsstatus: invitert?, hvilket selskap invitasjonen gjelder, og evt. bundet kunde-org."""
    if not request.session.get("invited"):
        return {"invited": False}
    sid = request.session.get("sid")
    st = sesjon.hent(sid) if sid else None
    return {
        "invited": True,
        "invite_org": request.session.get("invite_org"),
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
