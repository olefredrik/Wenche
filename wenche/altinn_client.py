"""
Altinn 3 API-klient.

Håndterer oppretting, datainnsending og fullføring av instanser
for alle tre innsendingstyper: årsregnskap, skattemelding og
aksjonærregisteroppgave.
"""

import os

import httpx

_BASES = {
    "test": {
        "platform": "https://platform.tt02.altinn.no",
        "apps": "https://{org}.apps.tt02.altinn.no",
    },
    "prod": {
        "platform": "https://platform.altinn.no",
        "apps": "https://{org}.apps.altinn.no",
    },
}

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
    def __init__(self, altinn_token: str, env: str | None = None):
        if env is None:
            env = os.getenv("WENCHE_ENV", "prod")
        if env not in _BASES:
            raise ValueError(f"Ugyldig env: {env!r}. Bruk 'prod' eller 'test'.")
        self._env = env
        self._apps_base = _BASES[env]["apps"]
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
        return self._apps_base.format(org=cfg["org"]) + f"/{cfg['org']}/{cfg['app']}"

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

    def oppdater_data_element(
        self,
        app_key: str,
        instans: dict,
        data_type: str,
        data: bytes,
        content_type: str,
    ) -> dict:
        """
        Oppdaterer et eksisterende data-element i instansen med PUT.
        Altinn oppretter data-elementene automatisk ved instansoppretting;
        vi finner riktig element via dataType og erstatter innholdet.
        """
        instance_id = instans["id"]
        element_id = self._finn_data_element_id(instans, data_type)
        url = f"{self._app_base(app_key)}/instances/{instance_id}/data/{element_id}"
        resp = self._http.put(
            url,
            content=data,
            headers={"Content-Type": content_type},
        )
        resp.raise_for_status()
        return resp.json()

    def _finn_data_element_id(self, instans: dict, data_type: str) -> str:
        """Finner data-element ID for gitt dataType i instansens data-array."""
        for element in instans.get("data", []):
            if element.get("dataType") == data_type:
                return element["id"]
        raise ValueError(
            f"Fant ikke data-element med dataType='{data_type}' i instansen. "
            f"Tilgjengelige typer: {[e.get('dataType') for e in instans.get('data', [])]}"
        )

    def fullfoor_instans(self, app_key: str, instans: dict) -> None:
        """
        Fullfører innsending i to steg:
          1. confirm — bekrefter og flytter instansen til signeringssteg
          2. sign    — signerer og sender inn
        """
        instance_id = instans["id"]
        url = f"{self._app_base(app_key)}/instances/{instance_id}/process/next"

        resp = self._http.put(url, json={"action": "confirm"})
        if not resp.is_success:
            raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")
        print("Instans bekreftet (confirm).")

        resp = self._http.put(url, json={"action": "sign"})
        if not resp.is_success:
            raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")
        print("Innsending signert og fullfort.")

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
