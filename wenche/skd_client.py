"""
SKD API-klient for aksjonærregisteroppgave (RF-1086).

Skatteetaten har eget REST-API for innrapportering — uavhengig av Altinn-instansflyt.
Autentisering skjer med Maskinporten-token direkte (ikke vekslet mot Altinn).

Innsendingsflyt:
  1. POST /{år}/1086H        — send Hovedskjema, få tilbake hovedskjemaId
  2. POST /{år}/{id}/1086U   — send Underskjema for hver aksjonær
  3. POST /{år}/{id}/bekreft — bekreft at alle underskjema er innsendt

Merk: prod-URL er ikke publisert i åpen dokumentasjon. Verifiser mot SwaggerHub
(https://app.swaggerhub.com/apis/skatteetaten/innrapportering-aksjonaerregister-api/)
eller ta kontakt med Skatteetaten.
"""

import uuid

import httpx

_BASES = {
    "test": "https://api-test.sits.no/api/aksjonaerregister/v1",
    "prod": "https://api.sits.no/api/aksjonaerregister/v1",  # TODO: verifiser prod-URL
}


class SkdAksjonaerClient:
    def __init__(self, maskinporten_token: str, env: str = "prod"):
        if env not in _BASES:
            raise ValueError(f"Ugyldig env: {env!r}. Bruk 'prod' eller 'test'.")
        self._base = _BASES[env]
        self._token = maskinporten_token
        self._http = httpx.Client(timeout=30)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/xml",
            "Accept": "application/json",
            "idempotencyKey": str(uuid.uuid4()),
        }

    def send_hovedskjema(self, regnskapsaar: int, xml: bytes) -> str:
        """
        Sender Hovedskjema (RF-1086) til SKD.

        Returnerer hovedskjemaId (UUID) som brukes i påfølgende kall.
        """
        resp = self._http.post(
            f"{self._base}/{regnskapsaar}/1086H",
            content=xml,
            headers=self._headers(),
        )
        if not resp.is_success:
            raise RuntimeError(
                f"Feil ved innsending av Hovedskjema: {resp.status_code}\n{resp.text}"
            )
        data = resp.json()
        if "hovedskjemaId" not in data:
            raise RuntimeError(
                f"Uventet respons fra SKD (mangler 'hovedskjemaId'):\n{data}"
            )
        return data["hovedskjemaId"]

    def send_underskjema(
        self, regnskapsaar: int, hovedskjemaId: str, xml: bytes
    ) -> None:
        """Sender Underskjema (RF-1086-U) for én aksjonær."""
        resp = self._http.post(
            f"{self._base}/{regnskapsaar}/{hovedskjemaId}/1086U",
            content=xml,
            headers=self._headers(),
        )
        if not resp.is_success:
            raise RuntimeError(
                f"Feil ved innsending av Underskjema: {resp.status_code}\n{resp.text}"
            )

    def bekreft(self, regnskapsaar: int, hovedskjemaId: str, antall_underskjema: int) -> dict:
        """
        Bekrefter at alle underskjema er innsendt.

        Returnerer forsendelse-ID og dialog-ID fra SKD.
        """
        headers = {k: v for k, v in self._headers().items() if k != "Content-Type"}
        resp = self._http.post(
            f"{self._base}/{regnskapsaar}/{hovedskjemaId}/bekreft",
            params={"antall_underskjema": antall_underskjema},
            headers=headers,
        )
        if not resp.is_success:
            raise RuntimeError(
                f"Feil ved bekreftelse: {resp.status_code}\n{resp.text}"
            )
        return resp.json()

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
