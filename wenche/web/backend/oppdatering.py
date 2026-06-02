"""Versjonssjekk mot PyPI for self-hosted Wenche (porten fra `wenche/ui.py`)."""
from __future__ import annotations

import os
from pathlib import Path

import httpx


def parse_versjon(v: str) -> tuple[int, ...]:
    """Parser semver-strenger som "0.25.0" til tupler av ints. Klipper ikke-numeriske suffikser."""
    deler: list[int] = []
    for ledd in v.split("."):
        siffer = ""
        for ch in ledd:
            if ch.isdigit():
                siffer += ch
            else:
                break
        if siffer:
            deler.append(int(siffer))
    return tuple(deler)


def er_nyere_versjon(siste: str, naavaerende: str) -> bool:
    """True hvis `siste` er strengt nyere enn `naavaerende`."""
    return parse_versjon(siste) > parse_versjon(naavaerende)


def hent_nyeste_pypi_versjon() -> str | None:
    """
    Spør PyPI om siste publiserte Wenche-versjon. Returnerer None ved nettverks-/parse-feil,
    slik at UI faller stille tilbake til kun installert versjon.

    WENCHE_FAKE_NY_VERSJON kan settes for å verifisere oppdaterings-badgen uten en ekte utgivelse.
    """
    fake = os.environ.get("WENCHE_FAKE_NY_VERSJON")
    if fake:
        return fake
    try:
        resp = httpx.get("https://pypi.org/pypi/wenche/json", timeout=3.0)
        resp.raise_for_status()
        return resp.json()["info"]["version"]
    except Exception:
        return None


def kjorer_fra_git_klone() -> bool:
    """True hvis Wenche kjøres fra et git-arbeidstre (klone/fork), False hvis pip-installert."""
    return (Path(__file__).resolve().parents[3] / ".git").exists()
