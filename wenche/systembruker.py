"""
Systembruker-flyt for Altinn 3.

Altinn 3 krever at sluttbrukersystemer registrerer seg i systemregisteret
og oppretter en systembruker for hver organisasjon de skal handle på vegne av.

Oppsett (kjøres én gang):
  1. wenche registrer-system   — registrerer Wenche i Altinns systemregister
  2. wenche opprett-systembruker — sender forespørsel til org om godkjenning
  3. Brukeren godkjenner via confirmUrl i nettleseren

Ved innsending bruker wenche login et systembruker-token fra Maskinporten.
"""

import os
import uuid

import httpx

_BASES = {
    "test": "https://platform.tt02.altinn.no",
    "prod": "https://platform.altinn.no",
}

_SYSTEM_NAVN = "wenche2"

# Ressurser Wenche-systemet trenger tilgang til.
# BRG årsregnskap: Altinn 3-app, ressurs-ID på format app_{org}_{appnavn}.
# SKD aksjonærregisteroppgave: SKDs eget REST-API, ressurs-ID fra SKDs API-dokumentasjon.
_SKATTEMELDING_RETT = {
    "resource": [
        {"id": "urn:altinn:resource", "value": "app_skd_formueinntekt-skattemelding-v2"}
    ]
}

_RIGHTS = [
    {
        "resource": [
            {"id": "urn:altinn:resource", "value": "app_brg_aarsregnskap-vanlig-202406"}
        ]
    },
    {
        "resource": [
            {"id": "urn:altinn:resource", "value": "ske-innrapportering-aksjonaerregisteroppgave"}
        ]
    },
    _SKATTEMELDING_RETT,
]


def _base() -> str:
    env = os.getenv("WENCHE_ENV", "prod")
    return _BASES[env]


def system_id(vendor_orgnr: str) -> str:
    """Returnerer system-ID på formatet <orgnr>_wenche."""
    return f"{vendor_orgnr}_{_SYSTEM_NAVN}"


def _bygg_system_payload(vendor_orgnr: str, client_id: str) -> dict:
    sid = system_id(vendor_orgnr)
    return {
        "id": sid,
        "vendor": {
            "authority": "iso6523-actorid-upis",
            "ID": f"0192:{vendor_orgnr}",
        },
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
    headers = {
        "Authorization": f"Bearer {maskinporten_token}",
        "Content-Type": "application/json",
    }

    resp = httpx.post(
        f"{_base()}/authentication/api/v1/systemregister/vendor",
        json=payload,
        headers=headers,
        timeout=15,
    )
    if resp.is_success:
        return _normaliser_svar(resp, sid, oppdatert=False)

    # Systemet finnes allerede — oppdater med PUT
    if resp.status_code == 400 and "already exists" in resp.text:
        resp = httpx.put(
            f"{_base()}/authentication/api/v1/systemregister/vendor/{sid}",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if not resp.is_success:
            raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")
        return _normaliser_svar(resp, sid, oppdatert=True)

    raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")


def _normaliser_svar(resp, sid: str, oppdatert: bool) -> dict:
    """Altinn returnerer noen ganger system-ID-en som rå streng i stedet for dict.
    Normaliser til alltid-dict for konsistent oppstrøms-bruk."""
    if not resp.text.strip():
        return {"id": sid, "oppdatert": oppdatert}
    try:
        data = resp.json()
    except Exception:
        return {"id": sid, "oppdatert": oppdatert}
    if isinstance(data, dict):
        data.setdefault("id", sid)
        data.setdefault("oppdatert", oppdatert)
        return data
    # Strengt svar (typisk bare system-ID-en)
    return {"id": data if isinstance(data, str) else sid, "oppdatert": oppdatert}


def opprett_forespørsel(
    maskinporten_token: str, vendor_orgnr: str, org_nummer: str
) -> dict:
    """
    Oppretter en systembrukerforespørsel for organisasjonen.

    Returnerer {'id': '<uuid>', 'status': 'New', 'confirmUrl': '...'}.
    Brukeren må gå til confirmUrl og godkjenne i nettleseren.
    """
    sid = system_id(vendor_orgnr)
    payload = {
        "systemId": sid,
        "partyOrgNo": org_nummer,
        "integrationTitle": "Wenche",
        "rights": _RIGHTS,
    }
    resp = httpx.post(
        f"{_base()}/authentication/api/v1/systemuser/request/vendor",
        json=payload,
        headers={
            "Authorization": f"Bearer {maskinporten_token}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    if not resp.is_success:
        raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")
    return resp.json()


def hent_forespørsel_status(maskinporten_token: str, request_id: str) -> dict:
    """Henter status for en systembrukerforespørsel."""
    resp = httpx.get(
        f"{_base()}/authentication/api/v1/systemuser/request/vendor/{request_id}",
        headers={"Authorization": f"Bearer {maskinporten_token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def opprett_endringsforespørsel(
    maskinporten_token: str, systembruker_id: str, required_rights: list[dict]
) -> dict:
    """
    Sender en endringsforespørsel for en eksisterende systembruker via vendor-API-et.

    Brukes når systemet har fått nye rettigheter — oppdaterer systembrukeren
    uten å slette den. Returnerer svar med confirmUrl som brukeren må godkjenne.

    API: POST /authentication/api/v1/systemuser/changerequest/vendor
         ?correlation-id={uuid}&system-user-id={systemUserId}
    Body: {"requiredRights": [...], "unwantedRights": []}

    Args:
        systembruker_id:  UUID-en til systembrukeren (fra hent_systembrukere).
        required_rights:  Liste med rettigheter som skal legges til (samme format som _RIGHTS).
    """
    payload = {
        "requiredRights": required_rights,
        "unwantedRights": [],
    }
    resp = httpx.post(
        f"{_base()}/authentication/api/v1/systemuser/changerequest/vendor",
        params={
            "correlation-id": str(uuid.uuid4()),
            "system-user-id": systembruker_id,
        },
        json=payload,
        headers={
            "Authorization": f"Bearer {maskinporten_token}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    if not resp.is_success:
        raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")
    return resp.json()


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
    url = f"{_base()}/authentication/api/v1/systemuser/vendor/bysystem/{sid}"
    headers = {"Authorization": f"Bearer {maskinporten_token}"}
    alle: list[dict] = []
    while url:
        resp = httpx.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            # Uventet flat liste (ingen paginerings-wrapper): returner som den er.
            return data
        alle.extend(data.get("data", []))
        url = (data.get("links") or {}).get("next")
    return alle


