"""
Størrelsesgrense på request-kropper, for begge webgrensesnittene.

FastAPI leser og parser JSON-kroppen før vakter og avhengigheter kjører, så uten en grense kunne
hvem som helst (i hostet: uten invite) få serveren til å parse vilkårlig store dokumenter.
Config-ene appene tar imot er noen få kB, SAF-T-filer noen hundre kB.

Middlewaren avviser med 413 på to måter: en `Content-Length` over grensen avvises før noe er
lest, og en kropp uten (eller med løgnaktig) lengde leses inn bundet av grensen og avvises idet
den passerer. Kroppen som slapp gjennom spilles av igjen for appen, som ikke merker noe.
"""

from __future__ import annotations

from collections.abc import Mapping

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

STANDARD_MAKS_BYTES = 2_000_000


def melding(grense: int) -> str:
    return f"Forespørselen er for stor (maks {grense / 1_000_000:g} MB)."


class Kroppsgrense:
    """ASGI-middleware: 413 når kroppen er større enn grensen for stien (ellers standard)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        maks_bytes: int = STANDARD_MAKS_BYTES,
        per_sti: Mapping[str, int] | None = None,
    ) -> None:
        self.app = app
        self.maks_bytes = maks_bytes
        self.per_sti = dict(per_sti or {})

    def grense_for(self, sti: str) -> int:
        return self.per_sti.get(sti, self.maks_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        grense = self.grense_for(scope["path"])
        lengde = Headers(scope=scope).get("content-length")
        if lengde and lengde.isdigit() and int(lengde) > grense:
            await _avvis(grense, scope, receive, send)
            return

        # Les kroppen inn, bundet av grensen, og spill den av igjen for appen. Dekker både
        # chunked overføring (ingen Content-Length) og en Content-Length som lyver.
        meldinger: list[Message] = []
        total = 0
        while True:
            m = await receive()
            meldinger.append(m)
            if m["type"] != "http.request":
                break  # http.disconnect: appen får den som vanlig
            total += len(m.get("body", b""))
            if total > grense:
                await _avvis(grense, scope, receive, send)
                return
            if not m.get("more_body", False):
                break

        async def avspilling() -> Message:
            if meldinger:
                return meldinger.pop(0)
            return await receive()

        await self.app(scope, avspilling, send)


async def _avvis(grense: int, scope: Scope, receive: Receive, send: Send) -> None:
    await JSONResponse({"detail": melding(grense)}, status_code=413)(scope, receive, send)
