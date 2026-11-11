"""
Autentisering mot Maskinporten via JWT grant (RFC 7523).

Wenche identifiserer seg som konsument med et selvgenerert RSA-nøkkelpar.
Ingen nettleserinnlogging nødvendig.

Flyt:
  1. Lag et JWT signert med din private RSA-nøkkel
  2. Send til Maskinporten og motta access token
  3. Veksle Maskinporten-token mot Altinn-token

To innganger: `hent_tokens_for` tar credentials eksplisitt (hostet: vendor-creds fra
server-config), `hent_tokens` leser dem fra miljøvariabler for gitt miljø (self-hosted og CLI; .env-filene er
lastet av inngangen, se wenche.miljoer). De eldre
`login`/`get_*_token`-funksjonene er tynne innpakninger rundt `hent_tokens`, beholdt fordi
web-backenden og testene kaller dem.
"""

import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from joserfc import jwt
from joserfc.jwk import RSAKey

from wenche import miljoer
from wenche.feil import AuthFeil, KonfigFeil, MyndighetsFeil
from wenche.filer import skriv_privat

log = logging.getLogger(__name__)

# Credentials leses fra miljøvariabler. .env-filene (~/.wenche/.env og .env i arbeidsmappen)
# lastes av inngangene (CLI-en, den lokale webserveren) via `miljoer.last_env_filer`, ikke ved
# import av biblioteket. Miljø-spesifikke URL-er slås opp ved hvert kall, så et miljøbytte i
# prosessen virker straks.


def _gjeldende_env() -> str:
    return miljoer.gjeldende_navn()


def _maskinporten_token_url(env: str | None = None) -> str:
    return miljoer.miljo(env).maskinporten_tokenendepunkt


def _maskinporten_aud(env: str | None = None) -> str:
    return miljoer.miljo(env).maskinporten_aud


def _altinn_exchange_url(env: str | None = None) -> str:
    return miljoer.miljo(env).altinn_veksling_url


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
    "skatteetaten:formueinntekt/skattemelding altinn:instances.read altinn:instances.write"
)

# Scope for lesestatus fra SKDs skattemelding-API (ingen Altinn-instanser)
SKD_SKATTEMELDING_LESE_SCOPE = "skatteetaten:formueinntekt/skattemelding"


@dataclass
class VendorCredentials:
    """
    Maskinporten-credentials for én leverandør (vendor).

    Self-hosted bygger disse fra .env (se `hent_tokens`). En hostet tjeneste bygger dem fra
    server-config/KMS og sender dem eksplisitt til hent_tokens_for(), uten å lese .env eller
    skrive token-cache.
    """

    client_id: str
    kid: str
    # repr=False: nøkkelen skal aldri bli med hvis objektet havner i en logg eller feilmelding.
    private_key_pem: bytes = field(repr=False)


def _token_file(env: str | None = None) -> Path:
    """
    Sti til token-cachen for gitt miljø.

    Prod og test holdes i hver sin fil slik at et test-token (tt02) aldri kan
    gjenbrukes i produksjon. Speiler config-splittingen (config.yaml /
    config.dev.yaml) fra PR #96; token-cachen ble den gang oversett og forble
    delt, noe som ga 401 ved miljøbytte.
    """
    if env is None:
        env = _gjeldende_env()
    navn = "token.dev.json" if env == "test" else "token.json"
    return Path.home() / ".wenche" / navn


def _env_fra_iss(iss: str) -> str:
    """Avleder miljø fra Altinn-tokenets utsteder (iss). tt02 => test."""
    return "test" if "tt02" in (iss or "") else "prod"


def _altinn_token_gyldig(altinn_token: str, env: str, margin_sek: int = 60) -> bool:
    """
    Om et cachet Altinn-token trygt kan gjenbrukes i gitt miljø.

    Returnerer False (=> re-autentisering) hvis tokenet er utløpt eller utløper
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
    if not isinstance(exp, int | float) or exp <= time.time() + margin_sek:
        return False
    return _env_fra_iss(payload.get("iss", "")) == env


def _lag_jwt(
    client_id: str,
    private_key_pem: bytes,
    kid: str,
    scopes: str = SCOPES,
    org_nummer: str | None = None,
    env: str | None = None,
) -> str:
    """
    Lager et signert JWT for Maskinporten JWT grant-flyten.

    Hvis org_nummer er oppgitt, legges authorization_details til i JWT-et
    for å hente et systembruker-token. `env` overstyrer WENCHE_ENV for
    kall som eksplisitt skal treffe et bestemt miljø (se fristsjekk).
    """
    now = int(time.time())
    claims: dict = {
        "iss": client_id,
        "sub": client_id,
        "aud": _maskinporten_aud(env),
        "scope": scopes,
        "iat": now,
        "exp": now + 119,  # Maskinporten tillater maks 120 sekunder
        "jti": str(uuid.uuid4()),
    }
    if org_nummer:
        claims["authorization_details"] = [
            {
                "type": "urn:altinn:systemuser",
                "systemuser_org": {"authority": "iso6523-actorid-upis", "ID": f"0192:{org_nummer}"},
            }
        ]
    header = {"alg": "RS256", "kid": kid}
    return jwt.encode(header, claims, RSAKey.import_key(private_key_pem), algorithms=["RS256"])


def _hent_maskinporten_token(
    client_id: str,
    private_key_pem: bytes,
    kid: str,
    scopes: str = SCOPES,
    org_nummer: str | None = None,
    env: str | None = None,
) -> str:
    """Henter et Maskinporten access token. `env` overstyrer WENCHE_ENV (default: les den)."""
    assertion = _lag_jwt(
        client_id, private_key_pem, kid, scopes=scopes, org_nummer=org_nummer, env=env
    )
    steg = "henting av token fra Maskinporten"
    try:
        resp = httpx.post(
            _maskinporten_token_url(env),
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
    except httpx.RequestError as e:
        raise MyndighetsFeil.fra_nettverksfeil("maskinporten", steg, e) from e
    if resp.status_code != 200:
        raise AuthFeil.fra_maskinporten_svar(resp)
    return resp.json()["access_token"]


def veksle_til_altinn_token(maskinporten_token: str, env: str | None = None) -> str:
    """Veksler et Maskinporten-token mot et Altinn-token for gitt miljø (default: gjeldende)."""
    steg = "veksling av Maskinporten-token mot Altinn-token"
    try:
        resp = httpx.get(
            _altinn_exchange_url(env),
            headers={"Authorization": f"Bearer {maskinporten_token}"},
            timeout=15,
        )
    except httpx.RequestError as e:
        raise MyndighetsFeil.fra_nettverksfeil("altinn", steg, e) from e
    if not resp.is_success:
        raise MyndighetsFeil.fra_svar("altinn", steg, resp)
    return resp.text.strip().strip('"')


def hent_tokens_for(
    creds: VendorCredentials,
    org_nummer: str | None = None,
    scopes: str = SCOPES,
    *,
    veksle_altinn: bool = False,
    env: str | None = None,
) -> dict:
    """
    Henter token(s) for en vendor som handler på vegne av org_nummer.

    Env-fri og fil-fri: leser ikke .env og skriver ikke token-cache. Brukt av en
    hostet tjeneste der vendor-creds kommer fra server-config/KMS og kunde-org fra
    sesjonen. Self-hosted bruker `hent_tokens`. Miljø (prod/test) er `env`, eller
    WENCHE_ENV i prosessen når den ikke er oppgitt.

    org_nummer=None gir et token uten systembruker-authorization_details, brukt for
    admin-scopes (systemregister/systembruker) der vendor opptrer som seg selv.
    """
    maskinporten_token = _hent_maskinporten_token(
        creds.client_id,
        creds.private_key_pem,
        creds.kid,
        scopes=scopes,
        org_nummer=org_nummer,
        env=env,
    )
    tokens = {"maskinporten_token": maskinporten_token}
    if veksle_altinn:
        tokens["altinn_token"] = veksle_til_altinn_token(maskinporten_token, env)
    return tokens


def _les_nokkel(nokkel_sti: str) -> bytes:
    try:
        return Path(nokkel_sti).read_bytes()
    except FileNotFoundError:
        # Ikke ta med filstien i meldingen: den propagerer til API-klienter via web-backendens
        # 502-svar, og plasseringen av den private nøkkelen er ikke noe en klient skal se.
        raise KonfigFeil(
            "Finner ikke privat nøkkel for Maskinporten. "
            "Sjekk at MASKINPORTEN_PRIVAT_NOKKEL i .env peker på riktig fil.\n"
            "Generer nøkkelpar med:\n"
            "  openssl genrsa -out maskinporten_privat.pem 2048\n"
            "  openssl rsa -in maskinporten_privat.pem -pubout -out maskinporten_offentlig.pem",
            felt="MASKINPORTEN_PRIVAT_NOKKEL",
        ) from None


def _les_paakrevd_env(navn: str, hjelpetekst: str) -> str:
    verdi = os.getenv(navn)
    if not verdi:
        raise KonfigFeil(f"{navn} mangler.\n{hjelpetekst}", felt=navn)
    return verdi


def _les_miljo_env(
    navn: str,
    env: str,
    hjelpetekst: str | None = None,
    paakrevd: bool = True,
    default: str = "",
) -> str:
    """
    Les en credential-variabel som potensielt er miljø-spesifikk.

    Sjekker først `{navn}_{ENV}` (f.eks. MASKINPORTEN_CLIENT_ID_TEST), deretter `{navn}` som
    fallback. Brukere som bare har én klient kan fortsette å bruke det generiske navnet.
    Brukere som har separate test- og prod-klienter kan ha begge sett samtidig i .env og la
    WENCHE_ENV velge riktig sett. Påkrevde variabler gir KonfigFeil når de mangler; valgfrie
    gir `default`.
    """
    suffix = env.upper()
    verdi = os.getenv(f"{navn}_{suffix}") or os.getenv(navn)
    if verdi:
        return verdi
    if paakrevd:
        raise KonfigFeil(
            f"{navn}_{suffix} (eller {navn} som fallback) mangler.\n{hjelpetekst or ''}",
            felt=navn,
        )
    return default


def les_cli_credentials(env: str) -> VendorCredentials:
    """
    Les Maskinporten-credentials (klient-ID, nøkkel-ID, privat nøkkel) fra .env for gitt miljø.

    Felles for alle self-hosted innloggingsfunksjonene; hostet bygger i stedet
    VendorCredentials eksplisitt fra server-config (se hent_tokens_for).
    """
    client_id = _les_miljo_env(
        "MASKINPORTEN_CLIENT_ID",
        env,
        "Kopier .env.example til .env og fyll inn din klient-ID fra Digdirs selvbetjeningsportal.",
    )
    kid = _les_miljo_env(
        "MASKINPORTEN_KID",
        env,
        "Finn nøkkel-ID (UUID) i Digdirs selvbetjeningsportal under klientens nøkler og legg den i .env.",
    )
    nokkel_sti = _les_miljo_env(
        "MASKINPORTEN_PRIVAT_NOKKEL",
        env,
        paakrevd=False,
        default="maskinporten_privat.pem",
    )
    return VendorCredentials(client_id=client_id, kid=kid, private_key_pem=_les_nokkel(nokkel_sti))


_les_cli_credentials = les_cli_credentials  # eldre navn, brukt av tester og driftsskript


def les_vendor_orgnr() -> str:
    """Ditt eget organisasjonsnummer (ORG_NUMMER), som er vendor i Altinn uansett miljø."""
    return _les_paakrevd_env("ORG_NUMMER", "Legg til ORG_NUMMER=<ditt organisasjonsnummer> i .env.")


def _les_systembruker_org(env: str) -> str:
    """
    Org-en systembruker-claimet skal gjelde.

    I testmiljø skal Maskinporten-JWT-en hevde at vi handler på vegne av den
    syntetiske Tenor-orgen (kunden i test), ikke vår egen leverandør-org.
    Systembrukeren i tt02-Altinn er knyttet til Tenor-orgen, så uten denne
    mappingen får vi 403 på instance-opprettelse selv om credentials er ok.
    """
    vendor_orgnr = les_vendor_orgnr()
    return os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr


def hent_tokens(
    scopes: str = SCOPES,
    *,
    med_systembruker: bool = True,
    veksle_altinn: bool = False,
    env: str | None = None,
) -> dict:
    """
    Tokens for self-hosted og CLI: credentials fra .env for gitt miljø (standard: WENCHE_ENV).

    `med_systembruker=False` gir et token uten systembruker-claim (admin-scopes, der vendor
    opptrer som seg selv). `veksle_altinn=True` legger ved et Altinn-token.
    Returnerer {'maskinporten_token': str[, 'altinn_token': str]}.
    """
    env = env or _gjeldende_env()
    creds = les_cli_credentials(env)
    org = _les_systembruker_org(env) if med_systembruker else None
    return hent_tokens_for(creds, org, scopes, veksle_altinn=veksle_altinn, env=env)


def login(lagre_token: bool = True) -> dict:
    """
    Autentiserer mot Maskinporten med systembruker-token og veksler mot Altinn-token.

    Krever ORG_NUMMER i .env. Returnerer {'maskinporten_token': str, 'altinn_token': str}.

    Hvis lagre_token=False, skrives ikke tokenet til disk. Brukes ved
    tilkoblingstest der vi ikke vil overskrive et eksisterende aktivt token
    eller forstyrre annen miljø-konfigurasjon.
    """
    env = _gjeldende_env()
    log.info("Autentiserer mot Maskinporten (systembruker)...")
    tokens = hent_tokens(SCOPES, veksle_altinn=True, env=env)
    if not lagre_token:
        log.info("Autentisering vellykket (token ikke lagret).")
        return tokens
    # 0600 fra første byte og atomisk innbytting: tokenene gir tilgang til å sende inn.
    skriv_privat(_token_file(env), json.dumps(tokens))
    log.info("Autentisering vellykket.")
    return tokens


def login_admin() -> str:
    """Maskinporten-token med admin-scopes for systemregister og systembruker (ikke vekslet)."""
    return hent_tokens(ADMIN_SCOPES, med_systembruker=False)["maskinporten_token"]


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
    Maskinporten-token med SKD aksjonærregister-scope og systembruker.

    SKDs API bruker Maskinporten-token direkte (ingen Altinn-veksling). Krever at scope
    'skatteetaten:innrapporteringaksjonaerregisteroppgave' er innvilget for klienten.
    """
    return hent_tokens(SKD_AKSJONAER_SCOPE)["maskinporten_token"]


def get_skd_skattemelding_maskinporten_token(env: str | None = None) -> str:
    """
    Maskinporten-token med skattemelding-scope (kun lesestatus), uten Altinn-veksling.

    `env` overstyrer WENCHE_ENV for kall som eksplisitt skal treffe et bestemt miljø
    (fristsjekk spør alltid prod), uten å mutere prosessens miljø.
    """
    return hent_tokens(SKD_SKATTEMELDING_LESE_SCOPE, env=env)["maskinporten_token"]


def get_skd_skattemelding_tokens() -> dict:
    """
    Tokens for skattemelding-API: {'maskinporten_token': str, 'altinn_token': str}.

    Maskinporten-token brukes direkte mot SKDs forhåndsutfylt- og valider-API, Altinn-token
    for Altinn3-instansoperasjonene. I testmiljø brukes SKD_TEST_ORG_NUMMER som systembruker-org.
    """
    return hent_tokens(SKD_SKATTEMELDING_SCOPE, veksle_altinn=True)


def logout() -> None:
    """Sletter lagret token for aktivt miljø."""
    fil = _token_file()
    if fil.exists():
        fil.unlink()
        log.info("Token slettet.")
    else:
        log.info("Ingen aktiv sesjon å logge ut fra.")
