"""
Små hjelpere XML-byggerne og XML-leserne deler.

Avrunding: myndighetene vil ha hele kroner, og Wenche bruker Pythons `round` (halv til nærmeste
partall) overalt. Det er bevisst holdt uendret her, så XML-en blir byte for byte lik den var da
hver bygger hadde sin egen kopi av regnestykket.
"""

from __future__ import annotations

from typing import Any


def heltall(verdi: float) -> int:
    """Beløp i hele kroner."""
    return round(verdi)


def heltall_tekst(verdi: float) -> str:
    """Beløp i hele kroner, som tekst til et XML-element."""
    return str(int(round(verdi)))


def beloep_tekst(verdi: float) -> str:
    """Hele kroner med to desimaler («123.00»), slik næringsspesifikasjonens beløpstype vil ha det."""
    return f"{round(verdi):.2f}"


def desimaltall(verdi: float, desimaler: int, *, kompakt: bool = False) -> str:
    """
    Tall med inntil `desimaler` desimaler og punktum som skilletegn, uten tusenskille: hele tall
    uten desimaler («300»), ellers med fast antall desimaler («10000.50»), eller uten etterstilte
    nuller når `kompakt` («0.1»). RF-1086 bruker begge formene.
    """
    rundet = round(float(verdi), desimaler)
    if rundet.is_integer():
        return str(int(rundet))
    tekst = f"{rundet:.{desimaler}f}"
    return tekst.rstrip("0").rstrip(".") if kompakt else tekst


def lokalnavn(tag: str) -> str:
    """Elementnavnet uten namespace: «{urn:...}type» blir «type»."""
    return tag.rsplit("}", 1)[-1]


def finn_tekst(el: Any, tag: str) -> str | None:
    """Teksten i barneelementet `tag`, uansett namespace. None når det mangler eller er tomt."""
    funnet = el.findtext(f"{{*}}{tag}")
    return funnet.strip() if funnet else None
