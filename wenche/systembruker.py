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

import httpx

_BASES = {
    "test": "https://platform.tt02.altinn.no",
    "prod": "https://platform.altinn.no",
}

_SYSTEM_NAVN = "wenche"

# Ressurs-ID for BRG årsregnskap-appen i Altinns ressursregister.
# Altinn 3-apper får ressurs-ID på formatet app_{org}_{appnavn}.
_BRG_RESSURS = "app_brg_aarsregnskap-vanlig-202406"

_RIGHTS = [
    {
        "resource": [
            {"id": "urn:altinn:resource", "value": _BRG_RESSURS}
        ]
    }
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
        return resp.json()

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
        return resp.json() if resp.text.strip() else {"id": sid, "oppdatert": True}

    raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")


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
        "integrationTitle": "Wenche årsregnskap",
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
