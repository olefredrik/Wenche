"""
Altinn 3 API-klient.

Håndterer oppretting, datainnsending og fullføring av instanser
for alle tre innsendingstyper: årsregnskap, skattemelding og
aksjonærregisteroppgave.
"""

import os
import time

import httpx

_BASES = {
    "test": {
        "platform": "https://platform.tt02.altinn.no",
        "apps": "https://{org}.apps.tt02.altinn.no",
        "web": "https://tt02.altinn.no",
        "inbox": "https://af.tt02.altinn.no/inbox",
    },
    "prod": {
        "platform": "https://platform.altinn.no",
        "apps": "https://{org}.apps.altinn.no",
        "web": "https://altinn.no",
        "inbox": "https://af.altinn.no/inbox",
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
        "app": "formueinntekt-skattemelding-v2",
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
        self._altinn_web = _BASES[env]["web"]
        self._altinn_inbox = _BASES[env]["inbox"]
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

    def vent_paa_filskanning(
        self,
        app_key: str,
        instans: dict,
        element_id: str,
        maks_forsok: int = 10,
        ventetid: float = 2.0,
    ) -> None:
        """
        Venter til Altinns virusskanning av et data-element er fullført.

        Altinn skanner alle opplastede filer asynkront. process/next feiler med
        DataElementFileScanPending hvis skanningen ikke er ferdig. Denne metoden
        poller data-elementet inntil fileScanResult == 'Clean', eller kaster
        RuntimeError ved infisert fil eller tidsavbrudd.
        """
        instance_id = instans["id"]
        inst_url = f"{self._app_base(app_key)}/instances/{instance_id}"
        for forsok in range(maks_forsok):
            resp = self._http.get(inst_url)
            resp.raise_for_status()
            data_elementer = resp.json().get("data", [])
            element = next((el for el in data_elementer if el.get("id") == element_id), None)
            resultat = element.get("fileScanResult") if element else None
            if resultat == "Clean":
                return
            if resultat == "Infected":
                raise RuntimeError("Vedlegg ble avvist av Altinns virusskanning.")
            # Pending eller None — vent og prøv igjen
            time.sleep(ventetid)
        raise RuntimeError(
            f"Altinns virusskanning av Vedlegg ble ikke ferdig etter "
            f"{maks_forsok * ventetid:.0f} sekunder."
        )

    def last_opp_vedlegg(
        self,
        app_key: str,
        instans: dict,
        data: bytes,
        content_type: str,
        filnavn: str,
    ) -> dict:
        """
        Laster opp et nytt Vedlegg-element til instansen via POST.

        Altinn oppretter ikke Vedlegg automatisk ved instansoppretting,
        så vi bruker POST for å legge til et nytt data-element.
        """
        instance_id = instans["id"]
        url = f"{self._app_base(app_key)}/instances/{instance_id}/data"
        params = {"datatype": "Vedlegg"}
        resp = self._http.post(
            url,
            content=data,
            headers={
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{filnavn}"',
            },
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def last_opp_skattemelding_data(
        self,
        instans: dict,
        konvolutt: bytes,
    ) -> dict:
        """
        Laster opp skattemelding-konvolutten til Altinn3.

        Skattemeldingen krever POST (ikke PUT) med Content-Type: text/xml og
        Content-Disposition uten anførselstegn rundt filnavnet — dette er
        spesifikt for SKDs formueinntekt-skattemelding-v2-app.
        """
        instance_id = instans["id"]
        url = (
            f"{self._app_base('skattemelding')}/instances/{instance_id}/data"
            "?dataType=skattemeldingOgNaeringsspesifikasjon"
        )
        resp = self._http.post(
            url,
            content=konvolutt,
            headers={
                "Content-Type": "text/xml",
                "Content-Disposition": "attachment; filename=skattemelding.xml",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def neste_prosesssteg(self, app_key: str, instans: dict) -> dict:
        """Avanserer instansen ett prosesssteg (PUT /process/next)."""
        instance_id = instans["id"]
        url = f"{self._app_base(app_key)}/instances/{instance_id}/process/next"
        resp = self._http.put(url)
        if not resp.is_success:
            raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")
        return resp.json()

    def fullfoor_instans(self, app_key: str, instans: dict) -> str:
        """
        Avanserer instansen til signeringssteget og returnerer Altinn-lenken
        der brukeren kan signere med BankID/ID-Porten.

        Signering krever ID-Porten og kan ikke gjøres maskinelt.
        """
        instance_id = instans["id"]
        url = f"{self._app_base(app_key)}/instances/{instance_id}/process/next"
        resp = self._http.put(url)
        if not resp.is_success:
            raise RuntimeError(f"{resp.status_code} {resp.reason_phrase}:\n{resp.text}")
        print("Instans klar for signering.")

        return self._altinn_inbox

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
