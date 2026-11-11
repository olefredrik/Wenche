"""
Altinn 3 API-klient.

Håndterer oppretting, datainnsending og fullføring av instanser for alle tre
innsendingstypene: årsregnskap, skattemelding og aksjonærregisteroppgave.

Alle kall går gjennom `_kall` (wenche.klient), som gjør nettverksfeil og feilstatus om til
`MyndighetsFeil` med steget navngitt, så web-lagene og CLI-en kan vise hvor det stoppet uten å
tolke tekst. Base-URL-er og app-ID-er kommer fra wenche.miljoer.
"""

import logging
import time

from wenche.feil import MyndighetsFeil
from wenche.klient import HttpKlient
from wenche.miljoer import ALTINN_APPER

log = logging.getLogger(__name__)

# Eldre form av app-tabellen ({"org": ..., "app": ...}), beholdt for kallsteder som leser den.
APPS = {navn: {"org": org, "app": app} for navn, (org, app) in ALTINN_APPER.items()}


class AltinnClient(HttpKlient):
    tjeneste = "altinn"

    def __init__(self, altinn_token: str, env: str | None = None):
        super().__init__(altinn_token, env=env, timeout=30)

    def _app_base(self, app_key: str) -> str:
        org, app = ALTINN_APPER[app_key]
        return self.miljo.altinn_app_url(org, app)

    def opprett_instans(self, app_key: str, org_nummer: str) -> dict:
        """Oppretter en ny instans for gitt innsendingstype."""
        url = f"{self._app_base(app_key)}/instances"
        payload = {"instanceOwner": {"organisationNumber": org_nummer}}
        instans = self._kall("POST", url, "oppretting av innsending i Altinn", json=payload).json()
        log.info("Instans opprettet: %s", instans["id"])
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
        return self._kall(
            "PUT",
            url,
            "opplasting av data til Altinn",
            content=data,
            headers={"Content-Type": content_type},
        ).json()

    def _finn_data_element_id(self, instans: dict, data_type: str) -> str:
        """Finner data-element ID for gitt dataType i instansens data-array."""
        for element in instans.get("data", []):
            if element.get("dataType") == data_type:
                return element["id"]
        tilgjengelige = [e.get("dataType") for e in instans.get("data", [])]
        raise MyndighetsFeil(
            self.tjeneste,
            "opplasting av data til Altinn",
            kode="mangler-dataelement",
            beskrivelse=(
                f"Fant ikke data-element med dataType='{data_type}' i instansen. "
                f"Tilgjengelige typer: {tilgjengelige}"
            ),
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
        MyndighetsFeil ved infisert fil eller tidsavbrudd.
        """
        instance_id = instans["id"]
        inst_url = f"{self._app_base(app_key)}/instances/{instance_id}"
        steg = "virusskanning av vedlegg i Altinn"
        for _ in range(maks_forsok):
            data_elementer = self._kall("GET", inst_url, steg).json().get("data", [])
            element = next((el for el in data_elementer if el.get("id") == element_id), None)
            resultat = element.get("fileScanResult") if element else None
            if resultat == "Clean":
                return
            if resultat == "Infected":
                raise MyndighetsFeil(
                    self.tjeneste,
                    steg,
                    kode="infisert",
                    beskrivelse="Vedlegget ble avvist av Altinns virusskanning.",
                )
            # Pending eller None: vent og prøv igjen
            time.sleep(ventetid)
        raise MyndighetsFeil(
            self.tjeneste,
            steg,
            kode="tidsavbrudd",
            beskrivelse=(
                f"Altinns virusskanning av vedlegget ble ikke ferdig etter "
                f"{maks_forsok * ventetid:.0f} sekunder."
            ),
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
        return self._kall(
            "POST",
            url,
            "opplasting av vedlegg til Altinn",
            content=data,
            headers={
                "Content-Type": content_type,
                "Content-Disposition": f'attachment; filename="{filnavn}"',
            },
            params={"datatype": "Vedlegg"},
        ).json()

    def last_opp_skattemelding_data(self, instans: dict, konvolutt: bytes) -> dict:
        """
        Laster opp skattemelding-konvolutten til Altinn3.

        Skattemeldingen krever POST (ikke PUT) med Content-Type: text/xml og
        Content-Disposition uten anførselstegn rundt filnavnet. Dette er
        spesifikt for SKDs formueinntekt-skattemelding-v2-app.
        """
        instance_id = instans["id"]
        url = (
            f"{self._app_base('skattemelding')}/instances/{instance_id}/data"
            "?dataType=skattemeldingOgNaeringsspesifikasjon"
        )
        return self._kall(
            "POST",
            url,
            "opplasting av skattemeldingen til Altinn",
            content=konvolutt,
            headers={
                "Content-Type": "text/xml",
                "Content-Disposition": "attachment; filename=skattemelding.xml",
            },
        ).json()

    def fullfoor_instans(self, app_key: str, instans: dict) -> str:
        """
        Avanserer instansen til signeringssteget og returnerer Altinn-lenken
        der brukeren kan signere med BankID/ID-Porten.

        Signering krever ID-Porten og kan ikke gjøres maskinelt.
        """
        instance_id = instans["id"]
        url = f"{self._app_base(app_key)}/instances/{instance_id}/process/next"
        self._kall("PUT", url, "fullføring av innsendingen i Altinn")
        log.info("Instans klar for signering.")
        return self.miljo.altinn_innboks
