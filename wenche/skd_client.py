"""
SKD API-klient for aksjonærregisteroppgave (RF-1086).

Skatteetaten har eget REST-API for innrapportering, uavhengig av Altinn-instansflyt.
Autentisering skjer med Maskinporten-token direkte (ikke vekslet mot Altinn).

Innsendingsflyt:
  1. POST /{år}/1086H        send Hovedskjema, få tilbake hovedskjemaId
  2. POST /{år}/{id}/1086U   send Underskjema for hver aksjonær
  3. POST /{år}/{id}/bekreft bekreft at alle underskjema er innsendt

Prod-URL (api.skatteetaten.no) er verifisert med vellykket innsending 2026-05-04.
"""

import uuid

import httpx

from wenche.feil import MyndighetsFeil

_TJENESTE = "skatteetaten"

_BASES = {
    "test": "https://api-test.sits.no/api/aksjonaerregister/v1",
    "prod": "https://api.skatteetaten.no/api/aksjonaerregister/v1",
}


class SkdAksjonaerClient:
    def __init__(self, maskinporten_token: str, env: str = "prod"):
        if env not in _BASES:
            raise ValueError(f"Ugyldig env: {env!r}. Bruk 'prod' eller 'test'.")
        self._base = _BASES[env]
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {maskinporten_token}", "Accept": "application/json"},
            timeout=30,
        )

    def _kall(self, url: str, steg: str, **kw) -> httpx.Response:
        """Ett POST-kall. Hvert kall får sin egen idempotencyKey, som SKDs API krever."""
        headers = {"idempotencyKey": str(uuid.uuid4()), **kw.pop("headers", {})}
        try:
            resp = self._http.post(url, headers=headers, **kw)
        except httpx.RequestError as e:
            raise MyndighetsFeil.fra_nettverksfeil(_TJENESTE, steg, e) from e
        if not resp.is_success:
            raise MyndighetsFeil.fra_svar(_TJENESTE, steg, resp)
        return resp

    def send_hovedskjema(self, regnskapsaar: int, xml: bytes) -> str:
        """Sender Hovedskjema (RF-1086) til SKD. Returnerer hovedskjemaId (UUID) for neste kall."""
        steg = "innsending av hovedskjemaet (RF-1086)"
        resp = self._kall(
            f"{self._base}/{regnskapsaar}/1086H",
            steg,
            content=xml,
            headers={"Content-Type": "application/xml"},
        )
        data = resp.json()
        if "hovedskjemaId" not in data:
            raise MyndighetsFeil.fra_svar(
                _TJENESTE, steg, resp, beskrivelse="Uventet svar: mangler 'hovedskjemaId'."
            )
        return data["hovedskjemaId"]

    def send_underskjema(self, regnskapsaar: int, hovedskjemaId: str, xml: bytes) -> None:
        """Sender Underskjema (RF-1086-U) for én aksjonær."""
        self._kall(
            f"{self._base}/{regnskapsaar}/{hovedskjemaId}/1086U",
            "innsending av underskjemaet (RF-1086-U)",
            content=xml,
            headers={"Content-Type": "application/xml"},
        )

    def bekreft(self, regnskapsaar: int, hovedskjemaId: str, antall_underskjema: int) -> dict:
        """Bekrefter at alle underskjema er innsendt. Returnerer forsendelse-ID og dialog-ID."""
        return self._kall(
            f"{self._base}/{regnskapsaar}/{hovedskjemaId}/bekreft",
            "bekreftelse av aksjonærregisteroppgaven",
            params={"antall_underskjema": antall_underskjema},
        ).json()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "SkdAksjonaerClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
