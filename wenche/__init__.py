"""Wenche — enkel innsending til Altinn for holdingselskaper."""

import tomllib
from contextlib import suppress
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _les_versjon() -> str:
    """
    Finn versjon fra pyproject.toml hvis den ligger ved siden av kildekoden
    (klone-fra-Github eller editable install), og fall tilbake til wheel-
    metadata for installasjoner fra PyPI. Sikrer at brukere som kjører rett
    fra et klonet repo får riktig versjon, og at editable installs ikke viser
    en frosset metadata-versjon fra installasjonstidspunktet.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject.is_file():
        # En ødelagt eller ufullstendig pyproject skal ikke stoppe importen; fall videre.
        with suppress(OSError, KeyError, TypeError, ValueError):
            with pyproject.open("rb") as f:
                return tomllib.load(f)["project"]["version"]
    try:
        return version("wenche")
    except PackageNotFoundError:
        return "ukjent"


__version__ = _les_versjon()
