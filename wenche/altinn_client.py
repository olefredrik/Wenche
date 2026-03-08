"""
Altinn 3 API-klient.

Håndterer oppretting, datainnsending og fullføring av instanser
for alle tre innsendingstyper: årsregnskap, skattemelding og
aksjonærregisteroppgave.
"""

import os

import httpx

_ENV = os.getenv("WENCHE_ENV", "prod")

if _ENV == "test":
    _BASE = "https://platform.tt02.altinn.no"
    _APPS_BASE = "https://{org}.apps.tt02.altinn.no"
else:
    _BASE = "https://platform.altinn.no"
    _APPS_BASE = "https://{org}.apps.altinn.no"

# Altinn 3-apper for hver innsendingstype
# Org er etaten som eier appen, app er appnavnet i Altinn Studio.
# Disse må verifiseres mot Altinn sin app-katalog.
APPS = {
    "aarsregnskap": {
        "org": "brg",
        "app": "aarsregnskap-vanlig-202406",          # RR-0002, sist oppdatert 2025-09
    },
    "aksjonaerregister": {
        "org": "skd",
        "app": "a2-1051-241111",                      # RF-1086, opprettet 2025-11
    },
    "skattemelding": {
        "org": "skd",
        "app": "formueinntekt-selskapsmelding",       # TODO: verifiser eksakt appnavn
    },
}


class AltinnClient:
    def __init__(self, altinn_token: str):
        self._token = altinn_token
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {altinn_token}",
                "Accept": "application/json",
            },
            timeout=30,
        )

    def _app_base(self, app_key: str) -> str:
        cfg = APPS[app_key]
        return _APPS_BASE.format(org=cfg["org"]) + f"/{cfg['org']}/{cfg['app']}"

    def opprett_instans(self, app_key: str, org_nummer: str) -> dict:
        """Oppretter en ny instans for gitt innsendingstype."""
        url = f"{self._app_base(app_key)}/instances"
        payload = {
            "instanceOwner": {"organisationNumber": org_nummer},
        }
        resp = self._http.post(url, json=payload)
        resp.raise_for_status()
        instans = resp.json()
        print(f"Instans opprettet: {instans['id']}")
        return instans

    def last_opp_data(
        self,
        app_key: str,
        instans: dict,
        data: bytes,
        content_type: str,
        data_type: str = "default",
    ) -> dict:
        """Laster opp skjemadata til en eksisterende instans."""
        instance_id = instans["id"]          # format: partyId/instanceGuid
        url = (
            f"{self._app_base(app_key)}/instances/{instance_id}"
            f"/data?dataType={data_type}"
        )
        resp = self._http.post(
            url,
            content=data,
            headers={"Content-Type": content_type},
        )
        resp.raise_for_status()
        return resp.json()

    def fullfoor_instans(self, app_key: str, instans: dict) -> None:
        """Sender inn instansen (setter prosess til neste steg — 'submit')."""
        instance_id = instans["id"]
        url = f"{self._app_base(app_key)}/instances/{instance_id}/process/next"
        resp = self._http.put(url)
        resp.raise_for_status()
        print("Innsending fullfort.")

    def hent_status(self, app_key: str, instans: dict) -> dict:
        """Henter status for en instans."""
        instance_id = instans["id"]
        url = f"{self._app_base(app_key)}/instances/{instance_id}"
        resp = self._http.get(url)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
