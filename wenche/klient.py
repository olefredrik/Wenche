"""
Felles grunnlag for HTTP-klientene mot Altinn og Skatteetaten.

Hver klient hadde sin egen kopi av miljøoppslaget, httpx.Client med Bearer-token og timeout,
kontekst-håndtering og «ett kall gir MyndighetsFeil med steget navngitt». Det bor her én gang;
klientene legger bare til URL-ene og flyten sin.
"""

from __future__ import annotations

from typing import Any, Self

import httpx

from wenche import miljoer
from wenche.feil import MyndighetsFeil


class HttpKlient:
    # Navnet brukeren ser i feilmeldinger: "altinn" eller "skatteetaten".
    tjeneste = ""

    def __init__(
        self,
        token: str,
        *,
        env: str | None = None,
        timeout: float = 30,
        accept: str = "application/json",
    ) -> None:
        self.miljo = miljoer.miljo(env)
        self._http = httpx.Client(
            headers={"Authorization": f"Bearer {token}", "Accept": accept}, timeout=timeout
        )

    def _kall(self, metode: str, url: str, steg: str, **kw: Any) -> httpx.Response:
        """Ett kall. Nettverksfeil og alt annet enn 2xx blir MyndighetsFeil med steget navngitt."""
        try:
            resp = self._http.request(metode, url, **kw)
        except httpx.RequestError as e:
            raise MyndighetsFeil.fra_nettverksfeil(self.tjeneste, steg, e) from e
        if not resp.is_success:
            raise MyndighetsFeil.fra_svar(self.tjeneste, steg, resp)
        return resp

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
