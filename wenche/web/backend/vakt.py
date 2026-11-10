"""
Vakt mot forespørsler fra andre nettsteder til den lokale serveren.

`wenche` lytter på 127.0.0.1 uten innlogging: alt som når porten, får gjøre alt. Nettleseren er
den eneste veien inn for en fremmed, og et nettsted brukeren besøker kan sende forespørsler til
http://127.0.0.1:8080 uten at brukeren merker det. Uten vakt kunne en slik side opprette
systembruker-forespørsler, skrive over nøkkel og credentials, og (med DNS-rebinding, der
angriperens domene peker på 127.0.0.1) lese config-fila med aksjonærenes fødselsnummer.

Tre sjekker:

- Vert (TrustedHostMiddleware i app.py, med `TILLATTE_VERTER`): Host må være loopback. Det
  stopper DNS-rebinding, der nettleseren tror den snakker med angriperens domene.
- Opprinnelse: en forespørsel som bærer `Origin` fra noe annet enn loopback avvises. Nettleseren
  setter alltid `Origin` på POST/PUT/DELETE, også på skjema-innsendinger og `no-cors`-fetch, så
  dette stopper alle cross-site-kall med sideeffekt. `Sec-Fetch-Site: cross-site` avvises også.
- Klientheader: endringskall må bære `X-Wenche-Klient`, som SPA-en setter på alle kall. En
  egendefinert header gjør kallet til en CORS-forespørsel med preflight, og preflighten besvares
  aldri (ingen CORS-middleware), så en fremmed side kommer ikke engang til selve kallet. Belte og
  bukseseler oppå opprinnelsessjekken.

GET er unntatt klientheaderen, så helsesjekk og /docs virker fra adresselinjen. Lesing er uansett
dekket av same-origin-policyen (uten CORS-middleware kan en fremmed side ikke lese svaret) og av
vertssjekken.
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Verter en Origin-header kan peke på og fortsatt regnes som denne maskinen.
LOKALE_VERTER = frozenset({"127.0.0.1", "localhost", "::1"})
# Host-verdier serveren godtar. Starlettes vertssjekk leser ikke IPv6-form ([::1]), og serveren
# binder uansett bare til 127.0.0.1.
TILLATTE_VERTER = ("127.0.0.1", "localhost")
KLIENT_HEADER = "x-wenche-klient"
_ENDRINGSMETODER = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_FREMMED = "Forespørselen kommer fra et annet nettsted og er avvist."


def er_lokal_origin(origin: str) -> bool:
    """Om en Origin-header peker på denne maskinen (loopback), uansett port og skjema."""
    try:
        vert = urlsplit(origin).hostname
    except ValueError:
        return False
    return vert in LOKALE_VERTER


def avvisningsgrunn(metode: str, headers: Mapping[str, str]) -> str | None:
    """Teksten som forklarer hvorfor forespørselen avvises, eller None når den slipper gjennom."""
    origin = headers.get("origin")
    if origin is not None and not er_lokal_origin(origin):
        return _FREMMED
    if headers.get("sec-fetch-site") == "cross-site":
        return _FREMMED
    if metode.upper() in _ENDRINGSMETODER and KLIENT_HEADER not in headers:
        return f"Mangler headeren {KLIENT_HEADER}. Bruk Wenches eget grensesnitt eller CLI-en."
    return None


class LokalVakt:
    """ASGI-middleware som anvender `avvisningsgrunn` på alle kall under `prefiks`."""

    def __init__(self, app: ASGIApp, prefiks: str = "/api") -> None:
        self.app = app
        self.prefiks = prefiks

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self.prefiks):
            grunn = avvisningsgrunn(scope["method"], Headers(scope=scope))
            if grunn:
                await JSONResponse({"detail": grunn}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)
