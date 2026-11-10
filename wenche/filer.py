"""
Filskriving for hemmeligheter og personopplysninger.

Token-cache, privat nøkkel, config med fødselsnummer og systembruker-tilstand skal bare kunne
leses av eieren. `write_text` fulgt av `chmod` gir et lite vindu der fila har umask-rettigheter,
og lar en avbrutt skriving etterlate en halv fil. Her opprettes fila med 0600 fra første byte
og byttes inn atomisk, så andre prosesser ser enten den gamle eller den nye versjonen.
"""
from __future__ import annotations

import os
from pathlib import Path


def sikre_privat_mappe(mappe: Path) -> None:
    """Opprett mappen (og foreldre) med rettigheter bare for eieren. No-op hvis den finnes."""
    Path(mappe).mkdir(mode=0o700, parents=True, exist_ok=True)


def skriv_privat(sti: Path, data: bytes | str) -> None:
    """
    Skriv `data` til `sti` som en fil bare eieren kan lese (0600), atomisk.

    Fila opprettes som en midlertidig søsterfil med 0600 (rettighetene settes i selve
    open-kallet, ikke etterpå), fylles, og byttes så inn med `os.replace`. En fil som alt
    finnes med videre rettigheter erstattes av den nye, strammere fila.
    """
    sti = Path(sti)
    sikre_privat_mappe(sti.parent)
    if isinstance(data, str):
        data = data.encode("utf-8")
    tmp = sti.with_name(f".{sti.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, sti)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
