"""
Systembruker-flyt for Altinn 3.

Altinn 3 krever at sluttbrukersystemer registrerer seg i systemregisteret
og oppretter en systembruker for hver organisasjon de skal handle på vegne av.

Oppsett (kjøres én gang):
  1. wenche registrer-system      registrerer Wenche i Altinns systemregister
  2. wenche opprett-systembruker  sender forespørsel til org om godkjenning
  3. Brukeren godkjenner via confirmUrl i nettleseren

Ved innsending bruker wenche login et systembruker-token fra Maskinporten.
"""

import uuid

import httpx

from wenche import miljoer
from wenche.feil import MyndighetsFeil

_TJENESTE = "altinn"

# Navnet som inngår i system-ID-en (<orgnr>_wenche2). «2» fordi den første registreringen
# måtte gjøres om, og Altinn lar ikke en system-ID gjenbrukes.
_SYSTEM_NAVN = "wenche2"

# Ressurser Wenche-systemet trenger tilgang til.
# BRG årsregnskap: Altinn 3-app, ressurs-ID på format app_{org}_{appnavn}.
# SKD aksjonærregisteroppgave: SKDs eget REST-API, ressurs-ID fra SKDs API-dokumentasjon.


def _app_ressurs(app_key: str) -> dict:
    """Altinn-ressursen for en Altinn 3-app, utledet av app-tabellen så ID-ene ikke kan sprike."""
    org, app = miljoer.ALTINN_APPER[app_key]
    return {"resource": [{"id": "urn:altinn:resource", "value": f"app_{org}_{app}"}]}


SKATTEMELDING_RETT = _app_ressurs("skattemelding")
_SKATTEMELDING_RETT = SKATTEMELDING_RETT  # eldre navn

_RIGHTS = [
    _app_ressurs("aarsregnskap"),
    {
        "resource": [
            {"id": "urn:altinn:resource", "value": "ske-innrapportering-aksjonaerregisteroppgave"}
        ]
    },
    SKATTEMELDING_RETT,
]


def _base() -> str:
    return miljoer.miljo().altinn_platform


def system_id(vendor_orgnr: str) -> str:
    """Returnerer system-ID på formatet <orgnr>_wenche2."""
    return f"{vendor_orgnr}_{_SYSTEM_NAVN}"


def _send(metode: str, url: str, steg: str, token: str, **kw) -> httpx.Response:
    """Ett kall mot Altinn uten statussjekk (kalleren tolker svaret). Nettverksfeil blir MyndighetsFeil."""
    headers = {"Authorization": f"Bearer {token}", **kw.pop("headers", {})}
    fn = getattr(httpx, metode.lower())  # slås opp ved kall, så tester kan patche httpx.get
    try:
        return fn(url, headers=headers, timeout=15, **kw)
    except httpx.RequestError as e:
        raise MyndighetsFeil.fra_nettverksfeil(_TJENESTE, steg, e) from e


def _kall(metode: str, url: str, steg: str, token: str, **kw) -> httpx.Response:
    """Ett kall mot Altinn der alt annet enn 2xx er en feil med steget navngitt."""
    resp = _send(metode, url, steg, token, **kw)
    if not resp.is_success:
        raise MyndighetsFeil.fra_svar(_TJENESTE, steg, resp)
    return resp


def _bygg_system_payload(vendor_orgnr: str, client_id: str) -> dict:
    sid = system_id(vendor_orgnr)
    return {
        "id": sid,
        "vendor": {"authority": "iso6523-actorid-upis", "ID": f"0192:{vendor_orgnr}"},
        "name": {"nb": "Wenche", "nn": "Wenche", "en": "Wenche"},
        "description": {
            "nb": "Enkel innsending av årsregnskap til Brønnøysundregistrene for holdingselskap.",
            "nn": "Enkel innsending av årsrekneskap til Brønnøysundregistra for holdingselskap.",
            "en": "Simple annual accounts submission to the Register of Business Enterprises.",
        },
        "clientId": [client_id],
        "isVisible": True,
        "rights": _RIGHTS,
    }


def registrer_system(maskinporten_token: str, vendor_orgnr: str, client_id: str) -> dict:
    """
    Registrerer eller oppdaterer Wenche i Altinns systemregister.

    Prøver POST først. Hvis systemet allerede finnes, brukes PUT for å oppdatere.
    """
    sid = system_id(vendor_orgnr)
    payload = _bygg_system_payload(vendor_orgnr, client_id)
    steg = "registrering av systemet i Altinn"
    base = f"{_base()}/authentication/api/v1/systemregister/vendor"
    resp = _send("POST", base, steg, maskinporten_token, json=payload)
    if resp.is_success:
        return _normaliser_svar(resp, sid, oppdatert=False)
    # Systemet finnes allerede: oppdater med PUT
    if resp.status_code == 400 and "already exists" in resp.text:
        resp = _kall("PUT", f"{base}/{sid}", steg, maskinporten_token, json=payload)
        return _normaliser_svar(resp, sid, oppdatert=True)
    raise MyndighetsFeil.fra_svar(_TJENESTE, steg, resp)


def _normaliser_svar(resp: httpx.Response, sid: str, oppdatert: bool) -> dict:
    """Altinn returnerer noen ganger system-ID-en som rå streng i stedet for dict.
    Normaliser til alltid-dict for konsistent oppstrøms-bruk."""
    if not resp.text.strip():
        return {"id": sid, "oppdatert": oppdatert}
    try:
        data = resp.json()
    except ValueError:
        return {"id": sid, "oppdatert": oppdatert}
    if isinstance(data, dict):
        data.setdefault("id", sid)
        data.setdefault("oppdatert", oppdatert)
        return data
    # Strengt svar (typisk bare system-ID-en)
    return {"id": data if isinstance(data, str) else sid, "oppdatert": oppdatert}


def opprett_forespørsel(maskinporten_token: str, vendor_orgnr: str, org_nummer: str) -> dict:
    """
    Oppretter en systembrukerforespørsel for organisasjonen.

    Returnerer {'id': '<uuid>', 'status': 'New', 'confirmUrl': '...'}.
    Brukeren må gå til confirmUrl og godkjenne i nettleseren. Altinn svarer AUTH-00004
    når org-en alt har en systembruker eller forespørsel for systemet; koden ligger i
    `MyndighetsFeil.kode`.
    """
    payload = {
        "systemId": system_id(vendor_orgnr),
        "partyOrgNo": org_nummer,
        "integrationTitle": "Wenche",
        "rights": _RIGHTS,
    }
    return _kall(
        "POST",
        f"{_base()}/authentication/api/v1/systemuser/request/vendor",
        "oppretting av systembruker-forespørsel i Altinn",
        maskinporten_token,
        json=payload,
    ).json()


def hent_forespørsel_status(maskinporten_token: str, request_id: str) -> dict:
    """Henter status for en systembrukerforespørsel."""
    return _kall(
        "GET",
        f"{_base()}/authentication/api/v1/systemuser/request/vendor/{request_id}",
        "henting av forespørselsstatus fra Altinn",
        maskinporten_token,
    ).json()


def opprett_endringsforespørsel(
    maskinporten_token: str, systembruker_id: str, required_rights: list[dict]
) -> dict:
    """
    Sender en endringsforespørsel for en eksisterende systembruker via vendor-API-et.

    Brukes når systemet har fått nye rettigheter: oppdaterer systembrukeren uten å slette
    den. Returnerer svar med confirmUrl som brukeren må godkjenne.

    API: POST /authentication/api/v1/systemuser/changerequest/vendor
         ?correlation-id={uuid}&system-user-id={systemUserId}
    Body: {"requiredRights": [...], "unwantedRights": []}
    """
    return _kall(
        "POST",
        f"{_base()}/authentication/api/v1/systemuser/changerequest/vendor",
        "endringsforespørsel for systembruker i Altinn",
        maskinporten_token,
        params={"correlation-id": str(uuid.uuid4()), "system-user-id": systembruker_id},
        json={"requiredRights": required_rights, "unwantedRights": []},
    ).json()


def hent_systembrukere(maskinporten_token: str, vendor_orgnr: str) -> list[dict]:
    """
    Henter alle godkjente systembrukere for Wenche-systemet.

    Returnerer en liste med systembruker-objekter fra Altinn. Endepunktet er paginert
    (50 per side, med `links.next` til neste side); vi følger lenkene til alle sidene er
    hentet. Uten dette ble bare de første 50 sett, så kunde nr. 51+ ble usynlig for
    gjenkjennings-sjekken og fikk AUTH-00004 («existing SystemUser tied to System-Id») ved
    ny tilkobling.
    """
    sid = system_id(vendor_orgnr)
    url: str | None = f"{_base()}/authentication/api/v1/systemuser/vendor/bysystem/{sid}"
    alle: list[dict] = []
    while url:
        data = _kall("GET", url, "henting av systembrukere fra Altinn", maskinporten_token).json()
        if not isinstance(data, dict):
            # Uventet flat liste (ingen paginerings-wrapper): returner som den er.
            return data
        alle.extend(data.get("data", []))
        url = (data.get("links") or {}).get("next")
    return alle
