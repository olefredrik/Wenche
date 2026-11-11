"""
Ett skjema for config.yaml, utledet fra dataklassene i wenche.models (`Konfig` og `Dok`).

Fra samme kilde lages JSON Schema (`wenche skjema`), TypeScript-typen SPA-ene bruker
(packages/ui/src/config.generert.ts), referansetabellene i docs/referanse.md og nøkkeltreet
wenche.configfelt varsler om ukjente felt fra. Feltnavn, typer, standardverdier og tekster kan
dermed ikke drifte fra hverandre: endres modellen, må de genererte filene regenereres
(scripts/generer_skjema.py), og testene sier fra hvis de ikke er det.
"""

from __future__ import annotations

import re
import types
import typing
from dataclasses import MISSING, dataclass, fields, is_dataclass
from datetime import date
from typing import Annotated, Any, get_args, get_origin, get_type_hints

from wenche.models import Dok, IkkeIConfig, Konfig

_SKALARER: dict[Any, str] = {str: "str", int: "int", float: "float", bool: "bool", date: "date"}
_JSON_TYPER = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
_TS_TYPER = {
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "date": "string",
}
# Typenavnene i referansen. Beløp er float i modellen (desimaler fra SAF-T), men oppgis i hele
# kroner; felt som faktisk tar desimaler sier det selv med Dok(typenavn=...).
_REFERANSE_TYPER = {
    "str": "tekst",
    "int": "heltall",
    "float": "heltall",
    "bool": "boolsk",
    "date": "dato",
    "list": "liste",
}


def _er_dataklasse(t: Any) -> bool:
    """Som dataclasses.is_dataclass for typer, men uten TypeGuard-snevring (mypy)."""
    return isinstance(t, type) and is_dataclass(t)


@dataclass(frozen=True)
class Felt:
    navn: str
    type: Any  # typen uten Annotated
    dok: Dok | None
    paakrevd: bool  # må stå i config.yaml
    standard: Any  # MISSING når feltet ikke har en enkel standardverdi


def felter(klasse: type) -> list[Felt]:
    """Feltene i en dataklasse slik de står i config.yaml (IkkeIConfig-felt er utelatt)."""
    hints = get_type_hints(klasse, include_extras=True)
    ut = []
    for f in fields(klasse):
        hint = hints[f.name]
        dok = None
        ren = hint
        skjult = False
        if get_origin(hint) is Annotated:
            ren, *meta = get_args(hint)
            for m in meta:
                if isinstance(m, Dok):
                    dok = m
                elif isinstance(m, IkkeIConfig):
                    skjult = True
        if skjult:
            continue
        har_standard = f.default is not MISSING or f.default_factory is not MISSING
        paakrevd = dok.paakrevd == "ja" if dok and dok.paakrevd is not None else not har_standard
        standard = f.default if f.default is not MISSING else MISSING
        ut.append(Felt(f.name, ren, dok, paakrevd, standard))
    return ut


def analyser(t: Any) -> tuple[str, Any, bool]:
    """(slag, elementtype, nullbar) for en felttype. Slag: str/int/float/bool/date/list/dataclass."""
    nullbar = False
    if get_origin(t) in (typing.Union, types.UnionType):
        args = [a for a in get_args(t) if a is not type(None)]
        if len(args) != 1:
            raise TypeError(f"Skjemaet støtter bare `X | None`, ikke {t}")
        nullbar = True
        t = args[0]
    if get_origin(t) in (list, tuple):
        return "list", get_args(t)[0], nullbar
    if _er_dataklasse(t):
        return "dataclass", t, nullbar
    if t not in _SKALARER:
        raise TypeError(f"Skjemaet kjenner ikke typen {t}")
    return _SKALARER[t], None, nullbar


def klasser() -> list[type]:
    """Alle dataklasser Konfig bruker, med avhengighetene først, og Konfig sist."""
    rekkefolge: list[type] = []

    def besok(klasse: type) -> None:
        if klasse in rekkefolge:
            return
        for f in felter(klasse):
            slag, indre, _ = analyser(f.type)
            if slag == "dataclass":
                besok(indre)
            elif slag == "list" and _er_dataklasse(indre):
                besok(indre)
        rekkefolge.append(klasse)

    besok(Konfig)
    return rekkefolge


# ---------------------------------------------------------------------------
# Nøkkeltre (for configfelt)
# ---------------------------------------------------------------------------


def nokkeltre(klasse: type = Konfig) -> dict:
    """Nøklene config.yaml kan ha: blad gir None, objekt gir dict, liste av objekter gir [dict]."""
    tre: dict = {}
    for f in felter(klasse):
        slag, indre, _ = analyser(f.type)
        if slag == "dataclass":
            tre[f.navn] = nokkeltre(indre)
        elif slag == "list":
            tre[f.navn] = [nokkeltre(indre)] if _er_dataklasse(indre) else []
        else:
            tre[f.navn] = None
    return tre


def bladstier(klasse: type = Konfig, prefiks: str = "") -> list[str]:
    """Punkt-stiene til alle skalarfelt, lister skrevet som `aksjonaerer[].navn`."""
    stier = []
    for f in felter(klasse):
        sti = f"{prefiks}{f.navn}"
        slag, indre, _ = analyser(f.type)
        if slag == "dataclass":
            stier.extend(bladstier(indre, f"{sti}."))
        elif slag == "list" and _er_dataklasse(indre):
            stier.extend(bladstier(indre, f"{sti}[]."))
        else:
            stier.append(sti)
    return stier


# ---------------------------------------------------------------------------
# JSON Schema
# ---------------------------------------------------------------------------


def json_schema() -> dict:
    """JSON Schema (draft 2020-12) for config.yaml. Ukjente nøkler avvises."""
    defs: dict[str, Any] = {}

    def typeskjema(t: Any) -> dict:
        slag, indre, nullbar = analyser(t)
        if slag == "dataclass":
            if indre.__name__ not in defs:
                defs[indre.__name__] = {}  # reservér navnet før rekursjonen
                defs[indre.__name__] = objekt(indre)
            s: dict = {"$ref": f"#/$defs/{indre.__name__}"}
        elif slag == "list":
            s = {"type": "array", "items": typeskjema(indre)}
        elif slag == "date":
            s = {"type": "string", "format": "date"}
        else:
            s = {"type": _JSON_TYPER[slag]}
        return {"anyOf": [s, {"type": "null"}]} if nullbar else s

    def objekt(klasse: type) -> dict:
        egenskaper: dict[str, Any] = {}
        paakrevde = []
        for f in felter(klasse):
            s = typeskjema(f.type)
            if f.dok:
                s = {"description": f.dok.tekst, **s}
                if f.dok.valg:
                    s["enum"] = list(f.dok.valg)
            if f.standard is not MISSING and f.standard is not None:
                s["default"] = f.standard
            egenskaper[f.navn] = s
            if f.paakrevd:
                paakrevde.append(f.navn)
        ut: dict = {"type": "object", "properties": egenskaper, "additionalProperties": False}
        if paakrevde:
            ut["required"] = paakrevde
        return ut

    rot = objekt(Konfig)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Wenche config.yaml",
        "description": "Selskapsopplysninger, regnskapstall og aksjonærer slik Wenche leser dem. "
        "Beløp i hele kroner. Felt som ikke står her kjenner Wenche ikke, og de kommer ikke "
        "med i innsendingen.",
        **rot,
        "$defs": defs,
    }


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------

_TS_NAVN = {"Konfig": "WencheConfig"}


def typescript() -> str:
    """TypeScript-grensesnitt for config.yaml (packages/ui/src/config.generert.ts)."""

    def ts_type(t: Any) -> str:
        slag, indre, nullbar = analyser(t)
        if slag == "dataclass":
            s = _TS_NAVN.get(indre.__name__, indre.__name__)
        elif slag == "list":
            s = f"{ts_type(indre)}[]"
        else:
            s = _TS_TYPER[slag]
        return f"{s} | null" if nullbar else s

    linjer = [
        "// GENERERT av scripts/generer_skjema.py fra dataklassene i wenche/models.py. Ikke rediger",
        "// for hånd: endre modellen og kjør skriptet. tests/test_skjema.py sjekker at fila er à jour.",
        "",
    ]
    for klasse in klasser():
        navn = _TS_NAVN.get(klasse.__name__, klasse.__name__)
        linjer.append(f"export interface {navn} {{")
        for f in felter(klasse):
            if f.dok:
                linjer.append(f"  /** {f.dok.tekst} */")
            t = (
                " | ".join(f'"{v}"' for v in f.dok.valg)
                if f.dok and f.dok.valg
                else ts_type(f.type)
            )
            linjer.append(f"  {f.navn}{'' if f.paakrevd else '?'}: {t};")
        linjer.append("}")
        linjer.append("")
    return "\n".join(linjer)


# ---------------------------------------------------------------------------
# Referansetabeller i docs/referanse.md
# ---------------------------------------------------------------------------


def _klasse_paa_sti(sti: str) -> type:
    klasse: type = Konfig
    for ledd in [d for d in sti.split(".") if d]:
        treff = [f for f in felter(klasse) if f.navn == ledd]
        if not treff:
            raise KeyError(f"Konfig har ikke feltet {sti!r} ({ledd!r} mangler)")
        slag, indre, _ = analyser(treff[0].type)
        if slag not in ("dataclass", "list") or not _er_dataklasse(indre):
            raise KeyError(f"{sti!r} er ikke en seksjon")
        klasse = indre
    return klasse


def referanse_tabell(sti: str, kun: list[str] | None = None) -> str:
    """
    Markdown-tabell for feltene på en sti i config.yaml ("" er toppnivået). Underseksjoner
    har egne tabeller og utelates, med mindre `kun` lister feltene som skal med.
    """
    klasse = _klasse_paa_sti(sti)
    rader = ["| Felt | Type | Påkrevd | Beskrivelse |", "|---|---|---|---|"]
    for f in felter(klasse):
        slag, indre, _ = analyser(f.type)
        if kun is not None and f.navn not in kun:
            continue
        if kun is None and slag == "dataclass":
            continue
        if f.dok is None:
            raise ValueError(f"{sti}.{f.navn} mangler Dok")
        typenavn = f.dok.typenavn or _REFERANSE_TYPER[slag]
        if f.dok.valg:
            verdier = [f"`{v}`" for v in f.dok.valg]
            typenavn += (
                " ("
                + (" eller ".join(verdier) if len(verdier) == 2 else "én av " + ", ".join(verdier))
                + ")"
            )
        paakrevd = f.dok.paakrevd or ("ja" if f.paakrevd else "nei")
        rader.append(f"| `{f.navn}` | {typenavn} | {paakrevd} | {f.dok.tekst} |")
    return "\n".join(rader)


_MARKOER = re.compile(r"<!-- skjema: ([^\n]*?) -->\n.*?<!-- /skjema -->", re.S)


def oppdater_referanse(tekst: str) -> str:
    """Bytt ut hver tabell mellom `<!-- skjema: STI [FELT ...] -->` og `<!-- /skjema -->`."""

    def erstatt(m: re.Match) -> str:
        sti, *kun = m.group(1).split()
        sti = "" if sti == "." else sti
        return (
            f"<!-- skjema: {m.group(1)} -->\n{referanse_tabell(sti, kun or None)}\n<!-- /skjema -->"
        )

    return _MARKOER.sub(erstatt, tekst)
