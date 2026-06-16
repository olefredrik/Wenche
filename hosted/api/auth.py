"""
Onboarding-porter + sesjonsstatus for hostet Wenche.

To porter binder en økt til et selskap. Begge setter 'invited' (gate passert) og til slutt
'invite_org' (org bundet til økten); navnene er historiske, men dekker nå begge portene:

- ID-porten-innlogging (primær i prod, se idporten.py): brukeren logger inn med BankID, vi får
  et VERIFISERT navn, og velg_org bekrefter at navnet står som aktiv daglig leder/styreleder for
  det oppgitte orgnr i Enhetsregisteret før økten bindes. Det verifiserte navnet erstatter det
  tidligere fritt innskrevne, så onboardingen ikke lenger hviler på et upåvist navn.
- Invite-lenke (operatør-fallback): en signert token som bærer ETT orgnr, delt ut manuelt til en
  kjent, verifisert person. Org er ikke brukerinput. Brukes når ID-porten-rollesjekken ikke kan
  treffe (skjermet person, selskap uten registrert rolleinnehaver). Roteres via HOSTED_INVITE_SECRET.

Den reelle fullmakten til å sende inn er uansett Altinn systembruker-godkjenning (BankID), se
systembruker.py. Portene her er forporten som hindrer at noen trigger en systembruker-forespørsel
mot et vilkårlig selskap; ID-porten gjør den forporten sterk (verifisert identitet).

Fortsett på en annen enhet (handoff): sesjonen lever per nettleser (signert cookie, ingen DB),
så en ny enhet har ingen binding. En alt fullført økt (bundet kunde_org) kan lage en kortvarig,
signert overføringslenke som den nye enheten åpner for å arve samme binding, uten ny BankID.
Lenken er ferskvare (HANDOFF_MAKS_ALDER), ikke engangsbruk.

ID-porten gir oss et transient fødselsnummer (`pid`) ved innlogging; det lagres aldri. Ellers:
ingen e-post, ingen passord, ingen database.
"""
import time
from collections import defaultdict, deque

import httpx
from fastapi import APIRouter, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer
from pydantic import BaseModel

from wenche import brreg

from .config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SALT = "invite"
_HANDOFF_SALT = "handoff"
# Overføringslenken er ferskvare: kort nok til at den i praksis må brukes med en gang (skann
# QR-en på den andre enheten), så et avlyttet/etterlatt token ikke kan løses inn senere.
_HANDOFF_MAKS_ALDER = 300  # sekunder

# Enhetsregisterets åpne rolle-endepunkt (gratis, ingen auth). Gir navn på daglig leder og
# styre som offentlig data, slik at vi kan bekrefte at den ID-porten-verifiserte personen
# står som rolleinnehaver for orgnummeret uten å samle inn eller lagre noe.
_BRREG_ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{org}/roller"

# Lett, in-memory rate-limit (én worker med vilje, så et dict holder). Demper enumerering av
# registeret via velg-org-steget; nullstilles ved restart, helt greit for formålet.
_RATE: dict[str, deque] = defaultdict(deque)
_RATE_VINDU = 600.0  # sekunder
_RATE_MAKS = 20

# MOD11-vekter for organisasjonsnummerets kontrollsiffer.
_MOD11_VEKTER = (3, 2, 7, 6, 5, 4, 3, 2)


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings().invite_secret, salt=_SALT)


def _handoff_serializer() -> URLSafeTimedSerializer:
    # Egen salt på sesjons-secret-en: overføringslenken er en sesjonsforlengelse, ikke en
    # operatør-utdelt invitasjon, og kan dermed ikke forveksles med (eller forfalskes fra)
    # invite-tokens eller selve cookien.
    return URLSafeTimedSerializer(settings().session_secret, salt=_HANDOFF_SALT)


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
    """
    Navn på aktive daglig leder/styre fra Enhetsregisteret, til navnematch i velg_org.
    Beholder en streng feilkontrakt med vilje: 404 gir tom liste, men nettverks- og serverfeil
    propageres (raise_for_status), så velg_org kan skille «fant ikke navnet» fra «fikk ikke
    kontakt med registeret». Selve parsingen deles med wenche.brreg (forhåndsfyll-stien).
    """
    resp = httpx.get(
        _BRREG_ROLLER_URL.format(org=orgnr),
        headers={"Accept": "application/json"},
        timeout=10,
    )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return brreg.parse_roller(resp.json())["alle"]


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
    _grant(request, str(org).strip())
    return {"invited": True, "invite_org": str(org).strip()}


def _grant(request: Request, orgnr: str) -> None:
    """Bind sesjonen til orgnr: marker gate passert ('invited') og sett bundet org ('invite_org')."""
    request.session["invited"] = True
    request.session["invite_org"] = orgnr


@router.post("/velg-org")
def velg_org(body: TilgangBody, request: Request) -> dict:
    """
    ID-porten-rollesjekk: bekreft at den innloggede personens VERIFISERTE navn (fra ID-porten,
    i sesjonen) står som aktiv daglig leder/styremedlem for orgnr i Enhetsregisteret, og bind i
    så fall økten. Navnet kommer fra innloggingen, ikke fra request-body, så det er bevist.
    Ved bom returneres en kontaktvei for manuelle tilfeller (skjermet person, manglende rolle).
    """
    s = settings()
    navn = request.session.get("idporten_navn")
    if not request.session.get("via_idporten") or not navn:
        raise HTTPException(status_code=401, detail="Logg inn med ID-porten først.")

    klient_ip = request.headers.get("fly-client-ip") or (request.client.host if request.client else "ukjent")
    if not _rate_ok(klient_ip):
        return {"ok": False, "feil": "For mange forsøk. Vent litt og prøv igjen.", "kontakt": s.kontakt}

    orgnr = _normaliser_orgnr(body.org)
    if not _gyldig_orgnr(orgnr):
        return {"ok": False, "feil": "Ugyldig organisasjonsnummer.", "kontakt": s.kontakt}

    try:
        rolleinnehavere = _hent_rolleinnehavere(orgnr)
    except httpx.HTTPError:
        return {
            "ok": False,
            "feil": "Fikk ikke kontakt med Enhetsregisteret. Prøv igjen om litt.",
            "kontakt": s.kontakt,
        }

    if not _navn_matcher(navn, rolleinnehavere):
        return {
            "ok": False,
            "feil": "Wenche kunne ikke finne deg som registrert daglig leder eller styreleder for "
            "dette selskapet.",
            "kontakt": s.kontakt,
        }

    _grant(request, orgnr)
    return {"ok": True, "invite_org": orgnr}


class HandoffBody(BaseModel):
    token: str


@router.post("/handoff/create")
def lag_handoff(request: Request) -> dict:
    """
    Lag en kortvarig overføringslenke for å fortsette på en annen enhet.

    Krever en alt fullført økt: kunde_org er kun satt etter en innløst invitasjon mot et
    onboardet selskap eller en gjennomført BankID-godkjenning, så bare en enhet som er
    forbi den reelle porten kan lage lenken. Den nye enheten arver nøyaktig samme binding.
    """
    org = request.session.get("kunde_org")
    if not org:
        raise HTTPException(
            status_code=409,
            detail="Koble selskapet på denne enheten først, så kan du fortsette på en annen.",
        )
    token = _handoff_serializer().dumps({"org": str(org)})
    return {
        "lenke": f"{settings().public_url}/?handoff={token}",
        "gyldig_sekunder": _HANDOFF_MAKS_ALDER,
    }


@router.post("/handoff/use")
def bruk_handoff(body: HandoffBody, request: Request) -> dict:
    """Løs inn en overføringslenke på en ny enhet og arv selskapsbindingen direkte."""
    try:
        payload = _handoff_serializer().loads(body.token, max_age=_HANDOFF_MAKS_ALDER)
    except SignatureExpired:
        return {"invited": False, "feil": "Overføringslenken er utløpt. Lag en ny på den andre enheten."}
    except BadSignature:
        return {"invited": False, "feil": "Ugyldig overføringslenke."}
    org = payload.get("org") if isinstance(payload, dict) else None
    if not org:
        return {"invited": False, "feil": "Ugyldig overføringslenke."}
    org = str(org).strip()
    # Forankret i en alt verifisert økt, så bindingen arves uten ny BankID.
    _grant(request, org)
    request.session["kunde_org"] = org
    return {"invited": True, "invite_org": org, "kunde_org": org}


@router.get("/me")
def me(request: Request) -> dict:
    """Sesjonsstatus: gate passert?, bundet org, evt. kunde-org, og hvilken port som er åpen."""
    s = settings()
    if not request.session.get("invited"):
        # Gatesiden trenger å vite om ID-porten-innlogging er tilgjengelig (prod) eller om den
        # skal vise invite/kontakt-fallback (demo). Begge er ikke-sensitiv config.
        return {"invited": False, "idporten": s.idporten_aktivert, "kontakt": s.kontakt}
    return {
        "invited": True,
        "via_idporten": request.session.get("via_idporten", False),
        # reportees styrer om SPA-en henter selskapslista fra Altinn (krever altinn:accessmanagement/authorizedparties-scopet)
        # eller går rett til manuell orgnr-inntasting.
        "reportees": s.idporten_reportees,
        "navn": request.session.get("idporten_navn"),
        "invite_org": request.session.get("invite_org"),
        "kunde_org": request.session.get("kunde_org"),
        "env": s.env,
        "demo": s.demo_mode,
        "kontakt": s.kontakt,
    }


@router.post("/logout")
def logout(request: Request) -> dict:
    """Logg ut: tøm sesjonscookien (ingen server-side tilstand å rydde)."""
    request.session.clear()
    return {"ok": True}
