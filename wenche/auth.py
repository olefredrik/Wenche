"""
Autentisering mot Maskinporten via JWT grant (RFC 7523).

Wenche identifiserer seg som konsument med et selvgenerert RSA-nøkkelpar.
Ingen nettleserinnlogging nødvendig.

Flyt:
  1. Lag et JWT signert med din private RSA-nøkkel
  2. Send til Maskinporten og motta access token
  3. Veksle Maskinporten-token mot Altinn-token
"""

import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from authlib.jose import jwt
from dotenv import load_dotenv

# Last credentials fra ~/.wenche/.env (fast lokasjon, brukerbundet, utenfor
# cwd og git-trees). Faller tilbake til cwd/.env for bakoverkompatibilitet
# med oppsett gjort i tidligere versjoner av Wenche.
_BRUKER_ENV_FIL = Path.home() / ".wenche" / ".env"
if _BRUKER_ENV_FIL.is_file():
    load_dotenv(_BRUKER_ENV_FIL)
load_dotenv()

# Miljø-spesifikke URL-er evalueres ved hvert kall (ikke ved modulinnlastning),
# slik at brukeren kan bytte miljø i UI-et og få umiddelbar effekt uten å
# starte Wenche på nytt.

def _gjeldende_env() -> str:
    return os.getenv("WENCHE_ENV", "prod")


def _maskinporten_token_url() -> str:
    return (
        "https://test.maskinporten.no/token"
        if _gjeldende_env() == "test"
        else "https://maskinporten.no/token"
    )


def _maskinporten_aud() -> str:
    return (
        "https://test.maskinporten.no/"
        if _gjeldende_env() == "test"
        else "https://maskinporten.no/"
    )


def _altinn_exchange_url() -> str:
    return (
        "https://platform.tt02.altinn.no/authentication/api/v1/exchange/maskinporten"
        if _gjeldende_env() == "test"
        else "https://platform.altinn.no/authentication/api/v1/exchange/maskinporten"
    )


# Bakoverkompatibel modul-tilgang for ekstern kode (bruk funksjonene over for
# kall som skal respektere endring av WENCHE_ENV ved kjøretid).
MASKINPORTEN_TOKEN_URL = _maskinporten_token_url()
MASKINPORTEN_AUD = _maskinporten_aud()
ALTINN_EXCHANGE_URL = _altinn_exchange_url()

# Scopes for innsending av instanser via Altinn
SCOPES = "altinn:instances.read altinn:instances.write"

# Scopes for administrasjon av systemregister og systembruker
ADMIN_SCOPES = (
    "altinn:authentication/systemregister.write "
    "altinn:authentication/systemuser.request.read "
    "altinn:authentication/systemuser.request.write"
)

# Scope for innsending av aksjonærregisteroppgave direkte til SKDs API
SKD_AKSJONAER_SCOPE = "skatteetaten:innrapporteringaksjonaerregisteroppgave"

# Scopes for skattemelding: direkte mot SKDs API + Altinn3-instanser
SKD_SKATTEMELDING_SCOPE = (
    "skatteetaten:formueinntekt/skattemelding "
    "altinn:instances.read altinn:instances.write"
)

# Scope for lesestatus fra SKDs skattemelding-API (ingen Altinn-instanser)
SKD_SKATTEMELDING_LESE_SCOPE = "skatteetaten:formueinntekt/skattemelding"


@dataclass
class VendorCredentials:
    """
    Maskinporten-credentials for én leverandør (vendor).

    Self-hosted bygger disse implisitt fra env (se login/get_*_token). En hostet
    tjeneste bygger dem fra server-config/KMS og sender dem eksplisitt til
    hent_tokens_for(), uten å lese .env eller skrive token-cache.
    """
    client_id: str
    kid: str
    private_key_pem: bytes


def _token_file(env: str | None = None) -> Path:
    """
    Sti til token-cachen for gitt miljø.

    Prod og test holdes i hver sin fil slik at et test-token (tt02) aldri kan
    gjenbrukes i produksjon. Speiler config-splittingen (config.yaml /
    config.dev.yaml) fra PR #96 — token-cachen ble den gang oversett og forble
    delt, noe som ga 401 ved miljøbytte.
    """
    if env is None:
        env = _gjeldende_env()
    navn = "token.dev.json" if env == "test" else "token.json"
    return Path.home() / ".wenche" / navn


def _env_fra_iss(iss: str) -> str:
    """Avleder miljø fra Altinn-tokenets utsteder (iss). tt02 ⇒ test."""
    return "test" if "tt02" in (iss or "") else "prod"


def _altinn_token_gyldig(altinn_token: str, env: str, margin_sek: int = 60) -> bool:
    """
    Om et cachet Altinn-token trygt kan gjenbrukes i gitt miljø.

    Returnerer False (⇒ re-autentisering) hvis tokenet er utløpt eller utløper
    innen margin_sek, tilhører feil miljø (iss), eller ikke lar seg dekode.
    Defensiv: enhver tvil gir False.
    """
    try:
        deler = altinn_token.split(".")
        if len(deler) < 2:
            return False
        pad = deler[1] + "=" * (-len(deler[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(pad))
    except Exception:
        return False
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or exp <= time.time() + margin_sek:
        return False
    return _env_fra_iss(payload.get("iss", "")) == env


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
        "aud": _maskinporten_aud(),
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
        _maskinporten_token_url(),
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


def veksle_til_altinn_token(maskinporten_token: str) -> str:
    """Veksler et Maskinporten-token mot et Altinn-token for gjeldende miljø."""
    resp = httpx.get(
        _altinn_exchange_url(),
        headers={"Authorization": f"Bearer {maskinporten_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.text.strip().strip('"')


def hent_tokens_for(
    creds: VendorCredentials,
    org_nummer: str | None = None,
    scopes: str = SCOPES,
    *,
    veksle_altinn: bool = False,
) -> dict:
    """
    Henter token(s) for en vendor som handler på vegne av org_nummer.

    Env-fri og fil-fri: leser ikke .env og skriver ikke token-cache. Brukt av en
    hostet tjeneste der vendor-creds kommer fra server-config/KMS og kunde-org fra
    sesjonen. Self-hosted bruker fortsatt login()/get_*_token(). Miljø (prod/test)
    styres av WENCHE_ENV i prosessen som vanlig.

    org_nummer=None gir et token uten systembruker-authorization_details, brukt for
    admin-scopes (systemregister/systembruker) der vendor opptrer som seg selv.
    """
    maskinporten_token = _hent_maskinporten_token(
        creds.client_id, creds.private_key_pem, creds.kid,
        scopes=scopes, org_nummer=org_nummer,
    )
    tokens = {"maskinporten_token": maskinporten_token}
    if veksle_altinn:
        tokens["altinn_token"] = veksle_til_altinn_token(maskinporten_token)
    return tokens


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


def _les_miljo_env(
    navn: str,
    env: str,
    hjelpetekst: str | None = None,
    paakrevd: bool = True,
    default: str | None = None,
) -> str | None:
    """
    Les en credential-variabel som potensielt er miljø-spesifikk.

    Sjekker først `{navn}_{ENV}` (f.eks. MASKINPORTEN_CLIENT_ID_TEST),
    deretter `{navn}` som fallback. Brukere som bare har én klient kan
    fortsette å bruke det generiske navnet. Brukere som har separate
    test- og prod-klienter kan ha begge sett samtidig i .env og la
    WENCHE_ENV velge riktig sett.
    """
    suffix = env.upper()
    verdi = os.getenv(f"{navn}_{suffix}") or os.getenv(navn)
    if verdi:
        return verdi
    if paakrevd:
        raise RuntimeError(
            f"{navn}_{suffix} (eller {navn} som fallback) mangler.\n"
            f"{hjelpetekst or ''}"
        )
    return default


def login(lagre_token: bool = True) -> dict:
    """
    Autentiserer mot Maskinporten med systembruker-token og veksler mot Altinn-token.

    Krever ORG_NUMMER i .env. Returnerer {'maskinporten_token': str, 'altinn_token': str}.

    Hvis lagre_token=False, skrives ikke tokenet til disk. Brukes ved
    tilkoblingstest der vi ikke vil overskrive et eksisterende aktivt token
    eller forstyrre annen miljø-konfigurasjon.
    """
    env = os.getenv("WENCHE_ENV", "prod")
    client_id = _les_miljo_env(
        "MASKINPORTEN_CLIENT_ID", env,
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_miljo_env(
        "MASKINPORTEN_KID", env,
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    vendor_orgnr = _les_påkrevd_env(
        "ORG_NUMMER",
        "Legg til ORG_NUMMER=<ditt organisasjonsnummer> i .env.",
    )
    # I testmiljø skal Maskinporten-JWT-en hevde at vi handler på vegne av
    # den syntetiske Tenor-orgen (kunden i test), ikke vår egen leverandør-org.
    # Systembrukeren i tt02-Altinn er knyttet til Tenor-orgen, så uten denne
    # mappingen får vi 403 på instance-opprettelse selv om credentials er ok.
    org_nummer = (
        os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr
    )
    nokkel_sti = _les_miljo_env(
        "MASKINPORTEN_PRIVAT_NOKKEL", env, paakrevd=False, default="maskinporten_privat.pem",
    )
    private_key_pem = _les_nokkel(nokkel_sti)

    print("Autentiserer mot Maskinporten (systembruker)...")
    maskinporten_token = _hent_maskinporten_token(
        client_id, private_key_pem, kid, org_nummer=org_nummer
    )

    print("Maskinporten-token mottatt. Henter Altinn-token...")
    altinn_token = veksle_til_altinn_token(maskinporten_token)

    tokens = {
        "maskinporten_token": maskinporten_token,
        "altinn_token": altinn_token,
    }

    if not lagre_token:
        print("Autentisering vellykket (token ikke lagret).\n")
        return tokens

    fil = _token_file(env)
    fil.parent.mkdir(parents=True, exist_ok=True)
    fil.write_text(json.dumps(tokens))
    fil.chmod(0o600)

    print("Autentisering vellykket.\n")
    return tokens


def login_admin() -> str:
    """
    Henter et Maskinporten-token med admin-scopes for systemregister og systembruker.

    Returnerer rått Maskinporten access token (ikke vekslet mot Altinn).
    """
    env = os.getenv("WENCHE_ENV", "prod")
    client_id = _les_miljo_env(
        "MASKINPORTEN_CLIENT_ID", env,
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_miljo_env(
        "MASKINPORTEN_KID", env,
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    nokkel_sti = _les_miljo_env(
        "MASKINPORTEN_PRIVAT_NOKKEL", env, paakrevd=False, default="maskinporten_privat.pem",
    )
    private_key_pem = _les_nokkel(nokkel_sti)

    return _hent_maskinporten_token(client_id, private_key_pem, kid, scopes=ADMIN_SCOPES)


def get_altinn_token() -> str:
    """
    Returnerer et gyldig Altinn-token for aktivt miljø.

    Gjenbruker cachet token kun hvis det ikke er utløpt og tilhører riktig
    miljø; ellers re-autentiseres det. Hindrer 401 ved miljøbytte og utløpt
    cache (tidligere ble cachet token returnert ukritisk).
    """
    env = _gjeldende_env()
    fil = _token_file(env)
    if fil.exists():
        try:
            tokens = json.loads(fil.read_text())
        except (json.JSONDecodeError, OSError):
            tokens = None
        if tokens and _altinn_token_gyldig(tokens.get("altinn_token", ""), env):
            return tokens["altinn_token"]
    return login()["altinn_token"]


def get_skd_aksjonaer_token() -> str:
    """
    Henter et Maskinporten-token med SKD aksjonærregister-scope og systembruker.

    SKDs API bruker Maskinporten-token direkte (ingen Altinn-veksling).
    Krever at scope 'skatteetaten:innrapporteringaksjonaerregisteroppgave'
    er innvilget av Skatteetaten for klienten.
    """
    env = os.getenv("WENCHE_ENV", "prod")
    client_id = _les_miljo_env(
        "MASKINPORTEN_CLIENT_ID", env,
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_miljo_env(
        "MASKINPORTEN_KID", env,
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    vendor_orgnr = _les_påkrevd_env(
        "ORG_NUMMER",
        "Legg til ORG_NUMMER=<ditt organisasjonsnummer> i .env.",
    )
    # I SKDs testmiljø må systembrukeren tilhøre et syntetisk Tenor-org, ikke produksjonsorg.
    org_nummer = os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr
    nokkel_sti = _les_miljo_env(
        "MASKINPORTEN_PRIVAT_NOKKEL", env, paakrevd=False, default="maskinporten_privat.pem",
    )
    private_key_pem = _les_nokkel(nokkel_sti)

    return _hent_maskinporten_token(
        client_id, private_key_pem, kid, scopes=SKD_AKSJONAER_SCOPE, org_nummer=org_nummer
    )


def get_skd_skattemelding_maskinporten_token() -> str:
    """
    Henter et Maskinporten-token med skattemelding-scope (kun lesestatus).

    Brukes for read-only sjekk av fastsettingsstatus mot SKDs API.
    Ingen Altinn-veksling — krever ikke at brukeren har Altinn-rettigheter.
    """
    env = os.getenv("WENCHE_ENV", "prod")
    client_id = _les_miljo_env(
        "MASKINPORTEN_CLIENT_ID", env,
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_miljo_env(
        "MASKINPORTEN_KID", env,
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    vendor_orgnr = _les_påkrevd_env(
        "ORG_NUMMER",
        "Legg til ORG_NUMMER=<ditt organisasjonsnummer> i .env.",
    )
    org_nummer = os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr
    nokkel_sti = _les_miljo_env(
        "MASKINPORTEN_PRIVAT_NOKKEL", env, paakrevd=False, default="maskinporten_privat.pem",
    )
    private_key_pem = _les_nokkel(nokkel_sti)

    return _hent_maskinporten_token(
        client_id, private_key_pem, kid,
        scopes=SKD_SKATTEMELDING_LESE_SCOPE,
        org_nummer=org_nummer,
    )


def get_skd_skattemelding_tokens() -> dict:
    """
    Henter tokens for skattemelding-API.

    Returnerer {'maskinporten_token': str, 'altinn_token': str}.
    Maskinporten-token brukes direkte mot SKDs forhåndsutfylt- og valider-API.
    Altinn-token brukes for Altinn3-instansoperasjoner.

    I testmiljø brukes SKD_TEST_ORG_NUMMER som systembruker-org.
    """
    env = os.getenv("WENCHE_ENV", "prod")
    client_id = _les_miljo_env(
        "MASKINPORTEN_CLIENT_ID", env,
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_miljo_env(
        "MASKINPORTEN_KID", env,
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    vendor_orgnr = _les_påkrevd_env(
        "ORG_NUMMER",
        "Legg til ORG_NUMMER=<ditt organisasjonsnummer> i .env.",
    )
    org_nummer = os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr
    nokkel_sti = _les_miljo_env(
        "MASKINPORTEN_PRIVAT_NOKKEL", env, paakrevd=False, default="maskinporten_privat.pem",
    )
    private_key_pem = _les_nokkel(nokkel_sti)

    maskinporten_token = _hent_maskinporten_token(
        client_id, private_key_pem, kid,
        scopes=SKD_SKATTEMELDING_SCOPE,
        org_nummer=org_nummer,
    )

    altinn_token = veksle_til_altinn_token(maskinporten_token)

    return {
        "maskinporten_token": maskinporten_token,
        "altinn_token": altinn_token,
    }


def logout():
    """Sletter lagret token for aktivt miljø."""
    fil = _token_file()
    if fil.exists():
        fil.unlink()
        print("Token slettet.")
    else:
        print("Ingen aktiv sesjon å logge ut fra.")
