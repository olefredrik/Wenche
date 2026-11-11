"""
Myndighetsmiljøene Wenche kan treffe: prod og test (Altinn tt02 og Skatteetatens testmiljø).

Én plass for alle base-URL-er, Maskinporten-utstedere og Altinn-app-ID-er. `gjeldende_navn()`
leser WENCHE_ENV (standard prod) og validerer verdien, så ingen klient trenger sin egen tabell.
Alt som ikke var «test» ble før stille behandlet som prod i deler av koden; nå er en ukjent
verdi en KonfigFeil.

Her bor også `last_env_filer()`: inngangene (CLI-en og den lokale webserveren) laster
`~/.wenche/.env` og en eventuell `.env` i arbeidsmappen ved oppstart. Biblioteket gjør det ikke
lenger ved import, så en import av `wenche.auth` muterer ikke prosessens miljø.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from wenche.feil import KonfigFeil


@dataclass(frozen=True)
class Miljo:
    navn: str
    maskinporten_tokenendepunkt: str
    maskinporten_aud: str
    altinn_platform: str
    altinn_apper: str  # mal med {org}, f.eks. https://brg.apps.altinn.no
    altinn_web: str
    altinn_innboks: str
    skd_api: str

    @property
    def er_test(self) -> bool:
        return self.navn == "test"

    @property
    def altinn_veksling_url(self) -> str:
        """Veksling av Maskinporten-token mot Altinn-token."""
        return f"{self.altinn_platform}/authentication/api/v1/exchange/maskinporten"

    @property
    def skd_aksjonaer_api(self) -> str:
        """Skatteetatens REST-API for aksjonærregisteroppgaven (RF-1086)."""
        return f"{self.skd_api}/api/aksjonaerregister/v1"

    def altinn_app_url(self, org: str, app: str) -> str:
        """Basis-URL for en Altinn 3-app: https://{org}.apps.../{org}/{app}."""
        return self.altinn_apper.format(org=org) + f"/{org}/{app}"


PROD = Miljo(
    navn="prod",
    maskinporten_tokenendepunkt="https://maskinporten.no/token",
    maskinporten_aud="https://maskinporten.no/",
    altinn_platform="https://platform.altinn.no",
    altinn_apper="https://{org}.apps.altinn.no",
    altinn_web="https://altinn.no",
    altinn_innboks="https://af.altinn.no/inbox",
    skd_api="https://api.skatteetaten.no",
)

TEST = Miljo(
    navn="test",
    maskinporten_tokenendepunkt="https://test.maskinporten.no/token",
    maskinporten_aud="https://test.maskinporten.no/",
    altinn_platform="https://platform.tt02.altinn.no",
    altinn_apper="https://{org}.apps.tt02.altinn.no",
    altinn_web="https://tt02.altinn.no",
    altinn_innboks="https://af.tt02.altinn.no/inbox",
    skd_api="https://api-test.sits.no",
)

MILJOER = {PROD.navn: PROD, TEST.navn: TEST}

# Altinn 3-appene for hver innsendingstype, som (org, app). Org er etaten som eier appen, app er
# appnavnet i Altinn Studio. Like i begge miljøer. Systembruker-rettighetene (systembruker.py)
# utledes av samme tabell, så app-ID-ene ikke kan sprike.
ALTINN_APPER = {
    "aarsregnskap": ("brg", "aarsregnskap-vanlig-202406"),  # RR-0002, sist oppdatert 2025-09
    "aksjonaerregister": ("skd", "a2-1051-241111"),  # RF-1086, opprettet 2025-11
    "skattemelding": ("skd", "formueinntekt-skattemelding-v2"),
}


def gjeldende_navn() -> str:
    """Miljønavnet fra WENCHE_ENV (standard prod). En ukjent verdi er en feil, ikke stille prod."""
    navn = os.getenv("WENCHE_ENV", "prod")
    if navn not in MILJOER:
        raise KonfigFeil(
            f"Ugyldig WENCHE_ENV: {navn!r}. Bruk 'prod' eller 'test'.", felt="WENCHE_ENV"
        )
    return navn


def miljo(navn: str | None = None) -> Miljo:
    """Miljøet med gitt navn, eller det gjeldende (WENCHE_ENV) når navnet ikke er oppgitt."""
    if not navn:
        navn = gjeldende_navn()
    if navn not in MILJOER:
        raise KonfigFeil(f"Ugyldig miljø: {navn!r}. Bruk 'prod' eller 'test'.", felt="WENCHE_ENV")
    return MILJOER[navn]


# Credentials bor i ~/.wenche/.env (fast lokasjon, brukerbundet, utenfor git-trær). En .env i
# arbeidsmappen (eller over den) leses også, for oppsett gjort i tidligere versjoner av Wenche.
BRUKER_ENV_FIL = Path.home() / ".wenche" / ".env"


def last_env_filer() -> None:
    """Last ~/.wenche/.env først, deretter .env fra arbeidsmappen. Setter aldri over en variabel
    som alt er satt i prosessen, så kommandolinjen og Fly-secrets vinner."""
    if BRUKER_ENV_FIL.is_file():
        load_dotenv(BRUKER_ENV_FIL)
    cwd_env = find_dotenv(usecwd=True)
    if cwd_env:
        load_dotenv(cwd_env)
