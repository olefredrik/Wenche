"""
Autentisering mot Maskinporten via JWT grant (RFC 7523).

Wenche identifiserer seg som konsument med et selvgenerert RSA-nøkkelpar.
Ingen nettleserinnlogging nødvendig.

Flyt:
  1. Lag et JWT signert med din private RSA-nøkkel
  2. Send til Maskinporten og motta access token
  3. Veksle Maskinporten-token mot Altinn-token
"""

import json
import os
import time
import uuid
from pathlib import Path

import httpx
from authlib.jose import jwt
from dotenv import load_dotenv

load_dotenv()

_ENV = os.getenv("WENCHE_ENV", "prod")

if _ENV == "test":
    MASKINPORTEN_TOKEN_URL = "https://test.maskinporten.no/token"
    MASKINPORTEN_AUD = "https://test.maskinporten.no/"
    ALTINN_EXCHANGE_URL = (
        "https://platform.tt02.altinn.no/authentication/api/v1/exchange/maskinporten"
    )
else:
    MASKINPORTEN_TOKEN_URL = "https://maskinporten.no/token"
    MASKINPORTEN_AUD = "https://maskinporten.no/"
    ALTINN_EXCHANGE_URL = (
        "https://platform.altinn.no/authentication/api/v1/exchange/maskinporten"
    )

# Scopes for innsending av instanser
SCOPES = "altinn:instances.read altinn:instances.write"

# Scopes for administrasjon av systemregister og systembruker
ADMIN_SCOPES = (
    "altinn:authentication/systemregister.write "
    "altinn:authentication/systemuser.request.read "
    "altinn:authentication/systemuser.request.write"
)
TOKEN_FILE = Path.home() / ".wenche" / "token.json"


def _lag_jwt(
    client_id: str,
    private_key_pem: bytes,
    kid: str,
    scopes: str = SCOPES,
    org_nummer: str | None = None,
) -> str:
    """
    Lager et signert JWT for Maskinporten JWT grant-flyten.

    Hvis org_nummer er oppgitt, legges authorization_details til i JWT-et
    for å hente et systembruker-token.
    """
    now = int(time.time())
    claims = {
        "iss": client_id,
        "sub": client_id,
        "aud": MASKINPORTEN_AUD,
        "scope": scopes,
        "iat": now,
        "exp": now + 119,  # Maskinporten tillater maks 120 sekunder
        "jti": str(uuid.uuid4()),
    }
    if org_nummer:
        claims["authorization_details"] = [
            {
                "type": "urn:altinn:systemuser",
                "systemuser_org": {
                    "authority": "iso6523-actorid-upis",
                    "ID": f"0192:{org_nummer}",
                },
            }
        ]
    header = {"alg": "RS256", "kid": kid}
    token = jwt.encode(header, claims, private_key_pem)
    return token.decode() if isinstance(token, bytes) else token


def _hent_maskinporten_token(
    client_id: str,
    private_key_pem: bytes,
    kid: str,
    scopes: str = SCOPES,
    org_nummer: str | None = None,
) -> str:
    """Henter et Maskinporten access token."""
    assertion = _lag_jwt(client_id, private_key_pem, kid, scopes=scopes, org_nummer=org_nummer)
    resp = httpx.post(
        MASKINPORTEN_TOKEN_URL,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Maskinporten svarte {resp.status_code}:\n{resp.text}")
    return resp.json()["access_token"]


def _les_nokkel(nokkel_sti: str) -> bytes:
    try:
        return Path(nokkel_sti).read_bytes()
    except FileNotFoundError:
        raise RuntimeError(
            f"Finner ikke privat nøkkel: {nokkel_sti}\n"
            "Generer nøkkelpar med:\n"
            "  openssl genrsa -out maskinporten_privat.pem 2048\n"
            "  openssl rsa -in maskinporten_privat.pem -pubout -out maskinporten_offentlig.pem"
        )


def _les_påkrevd_env(navn: str, hjelpetekst: str) -> str:
    verdi = os.getenv(navn)
    if not verdi:
        raise RuntimeError(f"{navn} mangler.\n{hjelpetekst}")
    return verdi


def login() -> dict:
    """
    Autentiserer mot Maskinporten med systembruker-token og veksler mot Altinn-token.

    Krever ORG_NUMMER i .env. Returnerer {'maskinporten_token': str, 'altinn_token': str}.
    """
    client_id = _les_påkrevd_env(
        "MASKINPORTEN_CLIENT_ID",
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_påkrevd_env(
        "MASKINPORTEN_KID",
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    org_nummer = _les_påkrevd_env(
        "ORG_NUMMER",
        "Legg til ORG_NUMMER=<ditt organisasjonsnummer> i .env.",
    )
    nokkel_sti = os.getenv("MASKINPORTEN_PRIVAT_NOKKEL", "maskinporten_privat.pem")
    private_key_pem = _les_nokkel(nokkel_sti)

    print("Autentiserer mot Maskinporten (systembruker)...")
    maskinporten_token = _hent_maskinporten_token(
        client_id, private_key_pem, kid, org_nummer=org_nummer
    )

    print("Maskinporten-token mottatt. Henter Altinn-token...")
    altinn_resp = httpx.get(
        ALTINN_EXCHANGE_URL,
        headers={"Authorization": f"Bearer {maskinporten_token}"},
        timeout=15,
    )
    altinn_resp.raise_for_status()
    altinn_token = altinn_resp.text.strip().strip('"')

    tokens = {
        "maskinporten_token": maskinporten_token,
        "altinn_token": altinn_token,
    }

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens))
    TOKEN_FILE.chmod(0o600)

    print("Autentisering vellykket.\n")
    return tokens


def login_admin() -> str:
    """
    Henter et Maskinporten-token med admin-scopes for systemregister og systembruker.

    Returnerer rått Maskinporten access token (ikke vekslet mot Altinn).
    """
    client_id = _les_påkrevd_env(
        "MASKINPORTEN_CLIENT_ID",
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_påkrevd_env(
        "MASKINPORTEN_KID",
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    nokkel_sti = os.getenv("MASKINPORTEN_PRIVAT_NOKKEL", "maskinporten_privat.pem")
    private_key_pem = _les_nokkel(nokkel_sti)

    return _hent_maskinporten_token(client_id, private_key_pem, kid, scopes=ADMIN_SCOPES)


def get_altinn_token() -> str:
    """Returnerer gjeldende Altinn-token, eller henter nytt."""
    if TOKEN_FILE.exists():
        tokens = json.loads(TOKEN_FILE.read_text())
        return tokens["altinn_token"]
    return login()["altinn_token"]


def logout():
    """Sletter lagret token."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        print("Token slettet.")
    else:
        print("Ingen aktiv sesjon å logge ut fra.")
