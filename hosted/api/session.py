"""
Ephemeral per-sesjon-tilstand, i minne. Ingen database, ingenting på disk.

«Invitert»-status og en sesjon-ID bæres i en signert cookie (se main.py). Selve
innsendingsdataene (regnskap, fødselsnummer m.m.) holdes server-side i minne kun for
den aktive sesjonen, nøklet på sesjon-ID-en, og slettes ved utlogging eller etter
innsending. Dette er GDPR-dataminimeringen i praksis.

Merknad: in-memory dict forutsetter én prosess (én uvicorn-worker / én maskin), som er
tilstrekkelig for invite-only. Multi-worker/multi-maskin ville krevd delt, kortlevd lager.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    kunde_org: str | None = None          # org med godkjent systembruker for denne brukeren
    request_id: str | None = None         # aktiv systembruker-forespørsel (venter på godkjenning)
    pending_org: str | None = None        # org det er bedt om systembruker for
    data: dict[str, Any] = field(default_factory=dict)  # ephemeral innsendingsdata


_store: dict[str, SessionState] = {}


def hent(sid: str) -> SessionState:
    """Hent (eller opprett) sesjonstilstand for en sesjon-ID."""
    return _store.setdefault(sid, SessionState())


def slett(sid: str) -> None:
    """Slett all sesjonstilstand (ved utlogging/innsending)."""
    _store.pop(sid, None)
