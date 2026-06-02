"""
Les/skriv den lokale config-fila (config.yaml / config.dev.yaml).

Self-hosted lagrer utfyllingen på disk (i motsetning til hostet, der klienten er fasit og
ingenting lagres). Skjemaet i SPA-en laster eksisterende config ved oppstart og skriver den
tilbake ved lagring. Formen på dict-en er identisk med det domenelaget (`les_config`) leser.
"""
from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, Body

from . import miljo

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def hent_config() -> dict:
    """Returner eksisterende config som dict (eller null hvis fila ikke finnes ennå)."""
    fil = miljo.config_fil()
    if not fil.exists():
        return {"config": None, "fil": str(fil.resolve()), "env": miljo.aktiv_env()}
    data = yaml.safe_load(fil.read_text(encoding="utf-8")) or {}
    return {"config": data, "fil": str(fil.resolve()), "env": miljo.aktiv_env()}


@router.put("")
def lagre_config(config: dict[str, Any] = Body(...)) -> dict:
    """Skriv config til aktiv config-fil (config.yaml i prod, config.dev.yaml i test)."""
    fil = miljo.config_fil()
    fil.write_text(
        yaml.dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return {"ok": True, "fil": str(fil.resolve())}
