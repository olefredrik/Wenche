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
from typing import Any

import httpx

from wenche.feil import MyndighetsFeil
from wenche.klient import HttpKlient


class SkdAksjonaerClient(HttpKlient):
    tjeneste = "skatteetaten"

    def __init__(self, maskinporten_token: str, env: str | None = None):
        super().__init__(maskinporten_token, env=env, timeout=30)
        self._base = self.miljo.skd_aksjonaer_api

    def _post(self, url: str, steg: str, **kw: Any) -> httpx.Response:
        """Ett POST-kall. Hvert kall får sin egen idempotencyKey, som SKDs API krever."""
        headers = {"idempotencyKey": str(uuid.uuid4()), **kw.pop("headers", {})}
        return self._kall("POST", url, steg, headers=headers, **kw)

    def send_hovedskjema(self, regnskapsaar: int, xml: bytes) -> str:
        """Sender Hovedskjema (RF-1086) til SKD. Returnerer hovedskjemaId (UUID) for neste kall."""
        steg = "innsending av hovedskjemaet (RF-1086)"
        resp = self._post(
            f"{self._base}/{regnskapsaar}/1086H",
            steg,
            content=xml,
            headers={"Content-Type": "application/xml"},
        )
        data = resp.json()
        if "hovedskjemaId" not in data:
            raise MyndighetsFeil.fra_svar(
                self.tjeneste, steg, resp, beskrivelse="Uventet svar: mangler 'hovedskjemaId'."
            )
        return data["hovedskjemaId"]

    def send_underskjema(self, regnskapsaar: int, hovedskjemaId: str, xml: bytes) -> None:
        """Sender Underskjema (RF-1086-U) for én aksjonær."""
        self._post(
            f"{self._base}/{regnskapsaar}/{hovedskjemaId}/1086U",
            "innsending av underskjemaet (RF-1086-U)",
            content=xml,
            headers={"Content-Type": "application/xml"},
        )

    def bekreft(self, regnskapsaar: int, hovedskjemaId: str, antall_underskjema: int) -> dict:
        """Bekrefter at alle underskjema er innsendt. Returnerer forsendelse-ID og dialog-ID."""
        return self._post(
            f"{self._base}/{regnskapsaar}/{hovedskjemaId}/bekreft",
            "bekreftelse av aksjonærregisteroppgaven",
            params={"antall_underskjema": antall_underskjema},
        ).json()
