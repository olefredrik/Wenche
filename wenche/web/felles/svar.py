"""
Svar-modeller for API-ene begge webgrensesnittene deler (dokumenter og innsending).

Modellene er kontrakten mot SPA-ene: FastAPI validerer svaret mot dem og legger dem i
OpenAPI-skjemaet, så en feltendring synes ett sted. Felt som er None utelates
(`response_model_exclude_none` på rutene), så JSON-en er uendret for de kallene som ikke
bruker dem.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Fil(BaseModel):
    """Én generert fil, base64-kodet så SPA-en kan tilby den som nedlasting."""

    filnavn: str
    mime: str
    base64: str


class FilerSvar(BaseModel):
    filer: list[Fil]


class SkatteberegningSvar(BaseModel):
    """Forslag til skattekostnad-feltet, beregnet av kjernen (samme tall som visningen)."""

    beregnet_skatt: int
    skattepliktig_inntekt: int
    foert_skattekostnad: int


class ValideringSvar(BaseModel):
    """Dry-run: lokal validering uten nettverk. `feil` er blokkerende, `advarsler` ikke."""

    dry_run: bool = True
    ok: bool
    feil: list[str]
    advarsler: list[str]
    antall_aksjonaerer: int | None = None
    regnskapsaar: int | None = None


class InnsendingSvar(BaseModel):
    """
    Ekte innsending. `resultat` er signeringslenken (årsregnskap og skattemelding, som
    signeres i Altinn) eller kvitteringen fra Skatteetaten (aksjonærregisteroppgaven).
    `krever_bekreftelse` settes når ingenting ble sendt fordi brukeren må bekrefte først
    (klage på skjønnsfastsetting); `melding` forklarer da hvorfor.
    """

    sendt: bool
    resultat: Any = None
    klage: bool | None = None
    krever_bekreftelse: str | None = None
    melding: str | None = None
