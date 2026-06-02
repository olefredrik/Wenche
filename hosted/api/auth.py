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

Selvbetjent tilgang (be_om_tilgang): når operatøren har skrudd på HOSTED_SELVBETJENING kan en
som står som aktiv daglig leder eller styremedlem i Enhetsregisteret for et orgnr få tilgang
med en gang, uten manuell utdeling. Verifiseringen er en proporsjonal støydempingssjekk, ikke
en festning: den hindrer at noen trigger en Altinn-systembruker-forespørsel mot et vilkårlig
selskap de ikke har noe med å gjøre, mens BankID-godkjenningen i Altinn forblir den reelle
porten. Navnet brukes kun transient til matching mot åpne registerdata og lagres aldri.

Ingen e-post, ingen passord, ingen database.
"""
import secrets
import time
from collections import defaultdict, deque

import httpx
from fastapi import APIRouter, Request
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel

from . import session as sesjon
from .config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SALT = "invite"

# Enhetsregisterets åpne rolle-endepunkt (gratis, ingen auth). Gir navn på daglig leder og
# styre som offentlig data, slik at vi kan bekrefte at forespørgeren plausibelt hører til
# orgnummeret uten å samle inn eller lagre noe.
_BRREG_ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{org}/roller"

# Lett, in-memory rate-limit (én worker med vilje, så et dict holder). Demper enumerering av
# registeret via tilgangsskjemaet; nullstilles ved restart, helt greit for formålet.
_RATE: dict[str, deque] = defaultdict(deque)
_RATE_VINDU = 600.0  # sekunder
_RATE_MAKS = 20

# MOD11-vekter for organisasjonsnummerets kontrollsiffer.
_MOD11_VEKTER = (3, 2, 7, 6, 5, 4, 3, 2)


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings().invite_secret, salt=_SALT)


def lag_invite_token(org: str) -> str:
    """Lag invite-token for ETT bestemt selskap. Del ut som {public_url}/?invite=<token>."""
    return _serializer().dumps({"org": str(org).strip()})


def _normaliser_orgnr(raa: str) -> str:
    return "".join(c for c in raa if c.isdigit())


def _gyldig_orgnr(orgnr: str) -> bool:
    """Ni siffer med gyldig MOD11-kontrollsiffer. Avviser åpenbart ugyldige før registeroppslag."""
    if len(orgnr) != 9 or not orgnr.isdigit():
        return False
    sum_ = sum(int(orgnr[i]) * _MOD11_VEKTER[i] for i in range(8))
    rest = sum_ % 11
    kontroll = 0 if rest == 0 else 11 - rest
    return kontroll != 10 and kontroll == int(orgnr[8])


def _tokens(navn: str) -> set[str]:
    return {t for t in navn.lower().replace("-", " ").split() if t}


def _navn_matcher(innsendt: str, kandidater: list[str]) -> bool:
    """
    Tolerant navnematch: den minste navnemengden må være en delmengde av den andre, og begge
    må ha minst to ledd. Håndterer utelatt/ekstra mellomnavn begge veier (f.eks. «Ole Lie» mot
    «Ole Fredrik Lie»), uten å matche på et enkelt vanlig navneledd alene.
    """
    inn = _tokens(innsendt)
    if len(inn) < 2:
        return False
    for kand in kandidater:
        k = _tokens(kand)
        if len(k) < 2:
            continue
        liten, stor = (inn, k) if len(inn) <= len(k) else (k, inn)
        if liten <= stor:
            return True
    return False


def _hent_rolleinnehavere(orgnr: str) -> list[str]:
    """Navn på aktive daglig leder/styre fra Enhetsregisteret. Tom liste om selskapet/rollen mangler."""
    resp = httpx.get(
        _BRREG_ROLLER_URL.format(org=orgnr),
        headers={"Accept": "application/json"},
        timeout=10,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    navn: list[str] = []
    for gruppe in resp.json().get("rollegrupper", []):
        for rolle in gruppe.get("roller", []):
            if rolle.get("fratraadt") or rolle.get("avregistrert"):
                continue
            person = rolle.get("person") or {}
            if person.get("erDoed"):
                continue
            n = person.get("navn") or {}
            fullt = " ".join(d for d in (n.get("fornavn"), n.get("mellomnavn"), n.get("etternavn")) if d)
            if fullt:
                navn.append(fullt)
    return navn


def _rate_ok(nokkel: str) -> bool:
    naa = time.monotonic()
    q = _RATE[nokkel]
    while q and naa - q[0] > _RATE_VINDU:
        q.popleft()
    if len(q) >= _RATE_MAKS:
        return False
    q.append(naa)
    return True


class InviteBody(BaseModel):
    token: str


class TilgangBody(BaseModel):
    navn: str
    org: str


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
    _grant(request, str(org).strip(), via_selvbetjening=False)
    return {"invited": True, "invite_org": str(org).strip()}


def _grant(request: Request, orgnr: str, *, via_selvbetjening: bool) -> None:
    """
    Bind sesjonen til orgnr, samme effekt som en innløst invite-lenke.

    via_selvbetjening skiller tillitsanker: en operatør-myntet invite-lenke (False) er en
    manuell, verifisert utdeling, mens selvbetjening (True) bare er et navneoppslag mot
    offentlige data. Skillet brukes til å nekte AlreadyApproved-snarveien for selvbetjente
    økter (se systembruker.request_systembruker), så BankID forblir reell port der.
    """
    request.session["invited"] = True
    request.session["invite_org"] = orgnr
    request.session["via_selvbetjening"] = via_selvbetjening
    if not request.session.get("sid"):
        request.session["sid"] = secrets.token_urlsafe(16)


@router.post("/be-om-tilgang")
def be_om_tilgang(body: TilgangBody, request: Request) -> dict:
    """
    Selvbetjent tilgang: bekreft at navnet står som aktiv daglig leder/styremedlem for orgnr
    i Enhetsregisteret, og gi i så fall tilgang med en gang (ingen e-post, ingenting lagret).
    Ved bom returneres en kontaktvei for manuelle tilfeller.
    """
    s = settings()
    if not s.selvbetjening:
        return {"invited": False, "feil": "Selvbetjent tilgang er ikke åpen ennå.", "kontakt": s.kontakt}

    klient_ip = request.headers.get("fly-client-ip") or (request.client.host if request.client else "ukjent")
    if not _rate_ok(klient_ip):
        return {"invited": False, "feil": "For mange forsøk. Vent litt og prøv igjen.", "kontakt": s.kontakt}

    orgnr = _normaliser_orgnr(body.org)
    if not _gyldig_orgnr(orgnr):
        return {"invited": False, "feil": "Ugyldig organisasjonsnummer.", "kontakt": s.kontakt}
    if len(_tokens(body.navn)) < 2:
        return {"invited": False, "feil": "Skriv inn fullt navn (fornavn og etternavn).", "kontakt": s.kontakt}

    try:
        rolleinnehavere = _hent_rolleinnehavere(orgnr)
    except httpx.HTTPError:
        return {
            "invited": False,
            "feil": "Fikk ikke kontakt med Enhetsregisteret. Prøv igjen om litt.",
            "kontakt": s.kontakt,
        }

    if not _navn_matcher(body.navn, rolleinnehavere):
        return {
            "invited": False,
            "feil": "Jeg fant ikke navnet ditt som registrert daglig leder eller styremedlem "
            "for dette selskapet.",
            "kontakt": s.kontakt,
        }

    _grant(request, orgnr, via_selvbetjening=True)
    return {"invited": True, "invite_org": orgnr}


@router.get("/me")
def me(request: Request) -> dict:
    """Sesjonsstatus: invitert?, hvilket selskap invitasjonen gjelder, og evt. bundet kunde-org."""
    s = settings()
    if not request.session.get("invited"):
        # Gatesiden trenger å vite om den skal vise selvbetjeningsskjemaet og hvor man ellers
        # tar kontakt. Begge er ikke-sensitiv config.
        return {"invited": False, "selvbetjening": s.selvbetjening, "kontakt": s.kontakt}
    sid = request.session.get("sid")
    st = sesjon.hent(sid) if sid else None
    return {
        "invited": True,
        "invite_org": request.session.get("invite_org"),
        "kunde_org": st.kunde_org if st else None,
        "env": s.env,
        "demo": s.demo_mode,
    }


@router.post("/logout")
def logout(request: Request) -> dict:
    """Logg ut: slett ephemeral sesjonsdata og tøm cookien."""
    sid = request.session.get("sid")
    if sid:
        sesjon.slett(sid)
    request.session.clear()
    return {"ok": True}
