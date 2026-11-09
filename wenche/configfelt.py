"""
Varsel om felt i config.yaml som Wenche ikke kjenner.

Leserne henter bare feltene de kjenner og ignorerer resten uten varsel. Et beløp i et felt
Wenche ikke kjenner, forsvinner derfor fra innsendingen mens valideringen sier OK. Typisk
er configen laget for en nyere Wenche-versjon, eller feltnavnet er feilstavet (#191).

De gyldige nøklene utledes fra dataklassene i models.py, der config-nøklene og feltnavnene
er like, så listen ikke kan drifte fra modellen. Toppnivået kontrolleres ikke: der ligger
seksjoner uten egen dataklasse (noter, naeringsspesifikasjon, utbytte_vedtaksdato).

Modulen har bare modeller som avhengighet, så den kan importeres fra alle kallsteder.
"""

from dataclasses import fields, is_dataclass
from typing import get_type_hints

import yaml

from wenche.models import (
    Aksjonaer,
    Balanse,
    Resultatregnskap,
    Selskap,
    SkattemeldingKonfig,
)


def _nokler(klasse) -> dict:
    """Gyldige nøkler for en dataklasse. Et nestet felt gir et undertre, et blad gir None."""
    typer = get_type_hints(klasse)
    return {
        f.name: _nokler(typer[f.name]) if is_dataclass(typer[f.name]) else None
        for f in fields(klasse)
    }


_SKATTEMELDING = _nokler(SkattemeldingKonfig)
# Postene leses fra toppnivået (naeringsspesifikasjon.poster), ikke fra skattemelding-seksjonen.
del _SKATTEMELDING["naeringsspesifikasjonsposter"]

_KJENTE = {
    "selskap": _nokler(Selskap),
    "resultatregnskap": _nokler(Resultatregnskap),
    "balanse": _nokler(Balanse),
    "foregaaende_aar": {
        "resultatregnskap": _nokler(Resultatregnskap),
        "balanse": _nokler(Balanse),
    },
    "skattemelding": _SKATTEMELDING,
}
_AKSJONAER = _nokler(Aksjonaer)


def _ukjente(verdi: dict, kjente: dict, sti: str) -> list[str]:
    ukjente = []
    for nokkel, under in verdi.items():
        full = f"{sti}.{nokkel}"
        if nokkel not in kjente:
            ukjente.append(full)
        elif isinstance(kjente[nokkel], dict) and isinstance(under, dict):
            ukjente.extend(_ukjente(under, kjente[nokkel], full))
    return ukjente


def ukjente_felt(config: str | dict) -> list[str]:
    """Stiene til feltene i config-en som Wenche ikke kjenner, f.eks. `balanse.eiendeler.x`."""
    if isinstance(config, dict):
        raw = config
    else:
        with open(config, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    ukjente = []
    for seksjon, kjente in _KJENTE.items():
        if isinstance(raw.get(seksjon), dict):
            ukjente.extend(_ukjente(raw[seksjon], kjente, seksjon))
    for i, aksjonaer in enumerate(raw.get("aksjonaerer") or []):
        if isinstance(aksjonaer, dict):
            ukjente.extend(_ukjente(aksjonaer, _AKSJONAER, f"aksjonaerer[{i}]"))
    return ukjente


def advarsel_om_ukjente_felt(config: str | dict) -> list[str]:
    """Én advarsel som lister de ukjente feltene, eller en tom liste."""
    ukjente = ukjente_felt(config)
    if not ukjente:
        return []
    return [
        f"Wenche kjenner ikke {'disse feltene' if len(ukjente) > 1 else 'feltet'} i configen, "
        f"og ignorerer {'dem' if len(ukjente) > 1 else 'det'}: {', '.join(ukjente)}. "
        "Står det et beløp der, kommer det ikke med i innsendingen. Kontroller stavemåten, "
        "eller oppgrader Wenche hvis configen er laget for en nyere versjon."
    ]
