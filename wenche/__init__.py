"""Wenche — enkel innsending til Altinn for holdingselskaper."""

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
        try:
            try:
                import tomllib
            except ModuleNotFoundError:
                import tomli as tomllib  # type: ignore[no-redef]
            with pyproject.open("rb") as f:
                return tomllib.load(f)["project"]["version"]
        except Exception:
            pass
    try:
        return version("wenche")
    except PackageNotFoundError:
        return "ukjent"


__version__ = _les_versjon()
