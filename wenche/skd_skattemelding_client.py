"""
Skatteetaten API-klient for skattemelding (upersonlig/AS).

Innsendingsflyt for AS via Maskinporten:
  1. GET  /api/skattemelding/v2/{år}/{orgnr}          — hent forhåndsutfylt melding
  2. POST /api/skattemelding/v2/valider/{år}/{orgnr}  — valider konvolutten
  3. POST Altinn3: opprett instans
  4. POST Altinn3: last opp konvolutt (text/xml, ingen anførselstegn i Content-Disposition)
  5. PUT  Altinn3: /process/next  (→ Bekreftelse)
  6. PUT  Altinn3: /process/next  (→ Tilbakemelding)
  7. GET  Altinn3: hent kvittering

Merk: krever at tilgang er innvilget av Skatteetaten (søknad sendt 2026-03-26).
      Kontakt: https://eksternjira.sits.no/servicedesk/customer/user/login

Autentisering: Maskinporten-token veksles mot Altinn-token for Altinn3-kallene.
Scope: skatteetaten:formueinntekt/skattemelding, altinn:instances.read/write
"""

from __future__ import annotations

import httpx

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

        Returnerer rå XML-bytes som kan brukes som utgangspunkt for innsending.
        Skatteetaten fyller inn myndighetsfastsatte felt — disse kan ikke overskrives.

        Krever API-tilgang fra Skatteetaten.
        """
        raise NotImplementedError(
            "Krever API-tilgang fra Skatteetaten. "
            "Søknad sendt 2026-03-26 via https://eksternjira.sits.no"
        )

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

        Krever API-tilgang fra Skatteetaten.
        """
        raise NotImplementedError(
            "Krever API-tilgang fra Skatteetaten. "
            "Søknad sendt 2026-03-26 via https://eksternjira.sits.no"
        )

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
          4. Kjør to prosesssteg (Bekreftelse + Tilbakemelding)
          5. Hent og returner forsendelse-ID

        Krever API-tilgang fra Skatteetaten og gyldig Altinn-token.
        """
        raise NotImplementedError(
            "Krever API-tilgang fra Skatteetaten. "
            "Søknad sendt 2026-03-26 via https://eksternjira.sits.no"
        )

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
