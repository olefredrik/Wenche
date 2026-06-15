"""
ID-porten-innlogging (OIDC authorization_code + PKCE) for hostet Wenche.

Primær onboarding-port i prod: brukeren logger inn med BankID via ID-porten, og vi får et
verifisert navn (+ fødselsnummer som transient `pid`-claim). Det verifiserte navnet erstatter
det tidligere fritt innskrevne navnet i rollesjekken mot Enhetsregisteret (se auth.velg_org),
så onboardingen ikke lenger hviler på et upåvist navn. Fødselsnummeret lagres aldri; kun det
verifiserte navnet legges i den signerte sesjonscookien.

ID-porten gir identitet, ikke innsendingsrett. Den reelle fullmakten til å sende inn ligger
fortsatt i Altinn systembruker-godkjenningen (systembruker.py). ID-porten er person-porten foran.

Flyt:
  GET /api/auth/idporten/login         -> bygg autorisasjons-URL (PKCE S256), redirect til ID-porten.
  GET /api/auth/idporten/callback      -> valider state, veksle code mot tokens (private_key_jwt),
                                          valider id_token, legg verifisert navn i sesjonen.
  GET /api/auth/idporten/organisasjoner -> veksle access_token mot Altinn-token, hent autoriserte
                                           parter (orger personen kan handle for).
  POST /api/auth/idporten/velg-org     -> bind sesjonen til valgt org (Altinn-verifisert).

Klient-assertion signeres med operatørens egne ID-porten-nøkkel (ikke Maskinporten-vendor-
nøkkelen). Endepunkter og JWKS hentes fra ID-portens well-known-dokument (cachet i minnet, én
worker), så vi slipper å hardkode stier som kan endres.
"""
import base64
import hashlib
import logging
import secrets
import time
import uuid
from urllib.parse import urlencode

import httpx
from authlib.jose import JsonWebKey, jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .config import settings

router = APIRouter(prefix="/api/auth/idporten", tags=["idporten"])
_log = logging.getLogger("wenche.idporten")

# Tillatt klokkeskjev ved id_token-validering.
_LEEWAY = 60


def _scope() -> str:
    """
    OIDC-scope for innloggingen.

    `altinn:reportees` («se hvem du kan representere») kreves for å (a) la Altinn godta
    token-vekslingen (exchange/id-porten avviser tokens uten en altinn:-scope, jf. Altinns
    HasAltinnScope) og (b) hente autoriserte parter. Men scopet må være tildelt klienten i
    Samarbeidsportalen, ellers avviser ID-porten HELE innloggingen (invalid_scope). Derfor ber
    vi om det kun når operatøren har skrudd på flagget; ellers logger man inn med bare
    openid+profile og velger selskap manuelt.
    """
    return "openid profile altinn:reportees" if settings().idporten_reportees else "openid profile"

# Well-known-metadata og JWKS per miljø (test/prod), cachet i minnet.
_metadata_cache: dict[str, dict] = {}
_jwks_cache: dict[str, object] = {}


def _issuer(env: str) -> str:
    """ID-portens utsteder for miljøet. test ⇒ test.idporten.no, ellers prod."""
    return "https://test.idporten.no" if env == "test" else "https://idporten.no"


def _metadata(env: str) -> dict:
    md = _metadata_cache.get(env)
    if md is None:
        resp = httpx.get(f"{_issuer(env)}/.well-known/openid-configuration", timeout=10)
        resp.raise_for_status()
        md = resp.json()
        _metadata_cache[env] = md
    return md


def _jwks(env: str):
    jwks = _jwks_cache.get(env)
    if jwks is None:
        resp = httpx.get(_metadata(env)["jwks_uri"], timeout=10)
        resp.raise_for_status()
        jwks = JsonWebKey.import_key_set(resp.json())
        _jwks_cache[env] = jwks
    return jwks


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _client_assertion(audience: str) -> str:
    """Signert private_key_jwt for token-endepunktet (iss=sub=client_id, aud=utsteder)."""
    s = settings()
    now = int(time.time())
    claims = {
        "iss": s.idporten_client_id,
        "sub": s.idporten_client_id,
        "aud": audience,
        "iat": now,
        "exp": now + 60,
        "jti": str(uuid.uuid4()),
    }
    header = {"alg": "RS256", "kid": s.idporten_kid}
    token = jwt.encode(header, claims, s.idporten_key())
    return token.decode() if isinstance(token, bytes) else token


def _navn_fra_claims(claims: dict) -> str:
    """Verifisert navn: `name` om satt, ellers satt sammen av given_name/family_name."""
    navn = (claims.get("name") or "").strip()
    if navn:
        return navn
    deler = [claims.get("given_name"), claims.get("family_name")]
    return " ".join(d for d in deler if d).strip()


def _altinn_exchange_url(env: str) -> str:
    return (
        "https://platform.tt02.altinn.no/authentication/api/v1/exchange/id-porten"
        if env == "test"
        else "https://platform.altinn.no/authentication/api/v1/exchange/id-porten"
    )


def _altinn_parter_url(env: str) -> str:
    # Endepunktet henter den autentiserte brukeren fra tokenet selv (ingen party-id i stien).
    base = "https://platform.tt02.altinn.no" if env == "test" else "https://platform.altinn.no"
    return f"{base}/accessmanagement/api/v1/authorizedparties?includeAltinn2=true"


def _veksle_til_altinn_token(access_token: str, env: str) -> str:
    """Veksle ID-porten access_token mot Altinn brukertoken."""
    resp = httpx.get(
        _altinn_exchange_url(env),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        _log.warning("Altinn exchange/id-porten svarte %s: %s", resp.status_code, resp.text[:500])
    resp.raise_for_status()
    return resp.text.strip().strip('"')


def _hent_altinn_parter(altinn_token: str, env: str) -> list:
    """Hent autoriserte parter (orger) for brukeren fra Altinn Access Management."""
    resp = httpx.get(
        _altinn_parter_url(env),
        headers={"Authorization": f"Bearer {altinn_token}", "Accept": "application/json"},
        timeout=15,
    )
    if resp.status_code != 200:
        _log.warning(
            "Altinn authorizedparties svarte %s: %s", resp.status_code, resp.text[:500],
        )
    resp.raise_for_status()
    return resp.json()


def _orger_fra_parter(parter: list) -> list[dict]:
    """
    Filtrer Altinn autoriserte parter til organisasjoner brukeren har reell tilgang til.

    Felt fra Altinns AuthorizedPartyExternal (camelCase): `type` (JsonStringEnum: Person/
    Organization/SelfIdentified), `organizationNumber`, `name`, `isDeleted`,
    `onlyHierarchyElementWithNoAccess` (hierarki-node uten faktisk tilgang).
    """
    return [
        {"orgnr": p["organizationNumber"], "navn": p.get("name") or p["organizationNumber"]}
        for p in parter
        if (
            p.get("type") == "Organization"
            and p.get("organizationNumber")
            and not p.get("isDeleted")
            and not p.get("onlyHierarchyElementWithNoAccess")
        )
    ]


def _krev_aktivert() -> None:
    if not settings().idporten_aktivert:
        raise HTTPException(status_code=404, detail="ID-porten-innlogging er ikke konfigurert.")


@router.get("/login")
def login(request: Request) -> RedirectResponse:
    """Start ID-porten-innlogging: lagre state/nonce/PKCE i sesjonen og redirect til ID-porten."""
    _krev_aktivert()
    s = settings()
    md = _metadata(s.env)

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())

    request.session["idp_state"] = state
    request.session["idp_nonce"] = nonce
    request.session["idp_verifier"] = verifier

    params = {
        "response_type": "code",
        "client_id": s.idporten_client_id,
        "redirect_uri": s.idporten_redirect_uri,
        "scope": _scope(),
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(md["authorization_endpoint"] + "?" + urlencode(params))


def _tilbake(feil: str | None = None) -> RedirectResponse:
    """Redirect tilbake til SPA-en, ev. med en lesbar feil SPA-en viser som banner."""
    base = settings().public_url.rstrip("/") + "/"
    if feil:
        base += "?" + urlencode({"idp_feil": feil})
    return RedirectResponse(base)


@router.get("/callback")
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> RedirectResponse:
    """Løs inn autorisasjonskoden, valider id_token, og bind den verifiserte identiteten til økten."""
    _krev_aktivert()
    s = settings()

    forventet_state = request.session.pop("idp_state", None)
    nonce = request.session.pop("idp_nonce", None)
    verifier = request.session.pop("idp_verifier", None)

    if error:
        # Brukeren avbrøt eller ID-porten avviste. error_description er teknisk, vis en rolig tekst.
        return _tilbake("Innloggingen ble avbrutt. Prøv igjen.")
    if not code or not state or state != forventet_state or not verifier:
        return _tilbake("Innloggingen kunne ikke fullføres. Prøv igjen.")

    md = _metadata(s.env)
    try:
        token_resp = httpx.post(
            md["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": s.idporten_redirect_uri,
                "code_verifier": verifier,
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": _client_assertion(md["issuer"]),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        token_resp.raise_for_status()
        id_token = token_resp.json()["id_token"]
        claims = _valider_id_token(id_token, md, nonce)
    except (httpx.HTTPError, KeyError, ValueError):
        return _tilbake("Innloggingen kunne ikke fullføres. Prøv igjen.")

    navn = _navn_fra_claims(claims)
    if not navn:
        # Uten et verifisert navn kan vi ikke gjøre rollesjekken mot Enhetsregisteret.
        return _tilbake("Fikk ikke navnet ditt fra ID-porten. Ta kontakt for manuell tilgang.")

    # Bind den verifiserte identiteten til økten. Fødselsnummeret (`pid`) lagres aldri; kun
    # navnet, som rollesjekken (velg_org) bruker. `via_idporten` skiller en ID-porten-økt fra
    # en invite-innløst økt, så SPA-en vet at den skal vise velg-org-steget.
    request.session["invited"] = True
    request.session["via_idporten"] = True
    request.session["idporten_navn"] = navn

    # access_token lagres KUN når selskapslista fra Altinn er på (reportees): da skal det veksles
    # mot et Altinn-token for å hente autoriserte parter, og slettes straks selskap er valgt. Er
    # lista av, har tokenet ingen funksjon, så vi lagrer det ikke (datasparsommelighet, og
    # sesjonscookien er signert men ikke kryptert). Fødselsnummeret lagres uansett aldri.
    if s.idporten_reportees:
        access_token = token_resp.json().get("access_token", "")
        if access_token:
            request.session["idporten_access_token"] = access_token

    return _tilbake()


class VelgOrgBody(BaseModel):
    org: str


@router.get("/organisasjoner")
def hent_organisasjoner(request: Request) -> dict:
    """
    Hent listen av orger brukeren kan handle for, via Altinn autoriserte parter.

    Veksler ID-porten access_token (lagret i sesjonen etter /callback) mot et Altinn brukertoken,
    og henter organisasjonslisten for den innloggede personen. Returnerer alltid en dict med
    'organisasjoner'-liste – tom liste + 'feil' ved feil, slik at SPA-en kan falle tilbake til
    manuell orgnr-input uten å kaste.
    """
    _krev_aktivert()
    if not request.session.get("via_idporten"):
        raise HTTPException(status_code=401, detail="Logg inn med ID-porten først.")
    s = settings()
    if not s.idporten_reportees:
        # Scopet altinn:reportees er ikke tildelt, så vi har ikke tilgang til parter-lista.
        # Tom liste uten feil: SPA-en viser manuell orgnr-inntasting (som den skal når flagget er av).
        return {"organisasjoner": []}
    access_token = request.session.get("idporten_access_token", "")
    if not access_token:
        return {
            "organisasjoner": [],
            "feil": "Sesjonen er utløpt. Logg inn med ID-porten på nytt.",
        }

    try:
        altinn_token = _veksle_til_altinn_token(access_token, s.env)
        parter = _hent_altinn_parter(altinn_token, s.env)
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        _log.exception("Kunne ikke hente autoriserte parter fra Altinn")
        return {
            "organisasjoner": [],
            "feil": "Kunne ikke hente selskapslisten fra Altinn. Skriv inn organisasjonsnummeret manuelt.",
        }

    return {"organisasjoner": _orger_fra_parter(parter)}


@router.post("/velg-org")
def velg_org_altinn(body: VelgOrgBody, request: Request) -> dict:
    """
    Bind sesjonen til orgnr valgt fra Altinn autoriserte parter-listen.

    Altinn er autoritativ kilde: re-verifiserer at orgnr er i den godkjente listen for å hindre
    at en manipulert request binder en vilkårlig org. Ingen brreg-sjekk nødvendig – Altinn er
    allerede sterkere enn brreg-navnematchen. access_token slettes fra sesjonen etter binding.
    """
    _krev_aktivert()
    if not request.session.get("via_idporten"):
        raise HTTPException(status_code=401, detail="Logg inn med ID-porten først.")
    access_token = request.session.get("idporten_access_token", "")
    if not access_token:
        s = settings()
        return {
            "ok": False,
            "feil": "Sesjonen er utløpt. Logg inn med ID-porten på nytt.",
            "kontakt": s.kontakt,
        }

    s = settings()
    orgnr = "".join(c for c in body.org if c.isdigit())
    if len(orgnr) != 9:
        return {"ok": False, "feil": "Ugyldig organisasjonsnummer.", "kontakt": s.kontakt}

    try:
        altinn_token = _veksle_til_altinn_token(access_token, s.env)
        parter = _hent_altinn_parter(altinn_token, s.env)
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        return {
            "ok": False,
            "feil": "Kunne ikke bekrefte tilgang mot Altinn. Prøv igjen.",
            "kontakt": s.kontakt,
        }

    godkjente = {o["orgnr"] for o in _orger_fra_parter(parter)}

    if orgnr not in godkjente:
        return {
            "ok": False,
            "feil": "Du har ikke registrert tilgang for dette selskapet i Altinn.",
            "kontakt": s.kontakt,
        }

    # Org bekreftet av Altinn – bind sesjonen og rydd access_token
    request.session["invited"] = True
    request.session["invite_org"] = orgnr
    request.session.pop("idporten_access_token", None)
    return {"ok": True, "invite_org": orgnr}


def _valider_id_token(id_token: str, md: dict, nonce: str | None) -> dict:
    """Valider signatur (JWKS), utsteder, mottaker og nonce. Kaster ved avvik."""
    claims = jwt.decode(
        id_token,
        _jwks(settings().env),
        claims_options={
            "iss": {"essential": True, "value": md["issuer"]},
            "aud": {"essential": True, "value": settings().idporten_client_id},
        },
    )
    claims.validate(now=int(time.time()), leeway=_LEEWAY)
    if not nonce or claims.get("nonce") != nonce:
        raise ValueError("nonce-avvik i id_token")
    return claims
