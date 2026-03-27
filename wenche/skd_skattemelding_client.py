"""
Skatteetaten API-klient for skattemelding (upersonlig/AS).

Innsendingsflyt for AS via Maskinporten:
  1. GET  /api/skattemelding/v2/{år}/{orgnr}          — hent forhåndsutfylt melding
  2. POST /api/skattemelding/v2/valider/{år}/{orgnr}  — valider konvolutten (valgfritt)
  3. POST Altinn3: opprett instans
  4. POST Altinn3: last opp konvolutt (text/xml, ingen anførselstegn i Content-Disposition)
  5. PUT  Altinn3: /process/next  (→ Bekreftelse)
  6. PUT  Altinn3: /process/next  (→ Tilbakemelding)
  7. Returner instans-ID

Autentisering: Maskinporten-token veksles mot Altinn-token for Altinn3-kallene.
Scope: skatteetaten:formueinntekt/skattemelding, altinn:instances.read/write
"""

from __future__ import annotations

import httpx
import json

from wenche.altinn_client import AltinnClient
from wenche.skattemelding_konvolutt import generer_konvolutt

_BASES = {
    "test": "https://api-test.sits.no",
    "prod": "https://api.skatteetaten.no",
}


class SkdSkattemeldingClient:
    """
    Klient for Skatteetatens skattemelding-API (upersonlig/AS).

    Instansieres med et gyldig Maskinporten-token. For Altinn3-operasjoner
    trengs i tillegg et Altinn-token (oppnås via auth.veksle_til_altinn_token).
    """

    def __init__(self, maskinporten_token: str, env: str = "prod"):
        if env not in _BASES:
            raise ValueError(f"Ugyldig env: {env!r}. Bruk 'prod' eller 'test'.")
        self._base = _BASES[env]
        self._env = env
        self._token = maskinporten_token
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {maskinporten_token}",
                "Accept": "application/json",
            },
            timeout=60,
        )

    def hent_forhåndsutfylt(self, inntektsaar: int, orgnr: str) -> bytes:
        """
        Henter forhåndsutfylt skattemelding fra Skatteetaten.

        Returnerer rå XML-bytes (skattemeldingUpersonlig v5).
        Inneholder partsnummer som trengs for innsending — bruk
        skattemelding_xml.hent_partsnummer() for å hente det ut.
        """
        url = f"{self._base}/api/skattemelding/v2/{inntektsaar}/{orgnr}"
        resp = self._http.get(url, headers={"Accept": "application/xml"})
        if not resp.is_success:
            raise RuntimeError(
                f"Feil ved henting av forhåndsutfylt skattemelding: "
                f"{resp.status_code}\n{resp.text}"
            )
        return resp.content

    def valider(
        self,
        inntektsaar: int,
        orgnr: str,
        konvolutt: bytes,
    ) -> dict:
        """
        Validerer skattemelding-konvolutten mot Skatteetatens API.

        Returnerer valideringsresultat med eventuelle avvik og veiledning.
        Validering lagrer ikke data hos Skatteetaten — det er ikke en innsending.
        """
        url = f"{self._base}/api/skattemelding/v2/valider/{inntektsaar}/{orgnr}"
        resp = self._http.post(
            url,
            content=konvolutt,
            headers={"Content-Type": "application/xml"},
        )
        if not resp.is_success:
            raise RuntimeError(
                f"Valideringsfeil: {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def send(
        self,
        inntektsaar: int,
        orgnr: str,
        skattemelding_xml: bytes,
        altinn_token: str,
        naeringsspesifikasjon_xml: bytes | None = None,
    ) -> str:
        """
        Sender skattemeldingen til Skatteetaten via Altinn3.

        Flyt:
          1. Generer konvolutt
          2. Opprett Altinn3-instans
          3. Last opp konvolutt
          4. Bekreftelse (process/next)
          5. Tilbakemelding (process/next)
          6. Returner instans-ID

        Args:
            skattemelding_xml:        XML fra generer_skattemelding_upersonlig().
            altinn_token:             Token fra auth.get_skd_skattemelding_tokens().
            naeringsspesifikasjon_xml: Valgfri næringsoppgave-XML.

        Returns:
            Altinn3 instans-ID for innsendt skattemelding.
        """
        konvolutt = generer_konvolutt(
            skattemelding_xml=skattemelding_xml,
            inntektsaar=inntektsaar,
            orgnr=orgnr,
            naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
        )

        with AltinnClient(altinn_token, env=self._env) as altinn:
            print("Oppretter Altinn3-instans...")
            instans = altinn.opprett_instans("skattemelding", orgnr)

            print("Setter inntektsaar i Skattemeldingsapp_v2-modellen...")
            altinn.oppdater_data_element(
                "skattemelding",
                instans,
                "Skattemeldingsapp_v2",
                json.dumps({"inntektsaar": inntektsaar}).encode(),
                "application/json",
            )

            print("Laster opp skattemelding-konvolutt...")
            altinn.last_opp_skattemelding_data(instans, konvolutt)

            print("Bekreftelse...")
            altinn.neste_prosesssteg("skattemelding", instans)

            print("Tilbakemelding...")
            altinn.neste_prosesssteg("skattemelding", instans)

        return instans["id"]

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def bygg_og_valider_konvolutt(
    skattemelding_xml: bytes,
    inntektsaar: int,
    orgnr: str,
    naeringsspesifikasjon_xml: bytes | None = None,
) -> bytes:
    """
    Hjelpefunksjon: bygger konvolutten uten å sende den.

    Nyttig for lokal testing og for å inspisere XML-strukturen
    før API-tilgang er på plass.
    """
    return generer_konvolutt(
        skattemelding_xml=skattemelding_xml,
        inntektsaar=inntektsaar,
        orgnr=orgnr,
        naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
    )
