"""
config.example.yaml er utgangspunktet brukere kopierer, så den skal validere i alle tre
innsendingene. Den gjorde ikke det: balansen gikk ikke opp, fødselsnummeret hadde ugyldige
kontrollsifre, og kontakt-e-post og selskapsrepresentant manglet. Ingen test leste fila, så
feilen ble stående.
"""

from pathlib import Path

import yaml

from wenche import innsending as tjeneste

_CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "config.example.yaml").read_text()
)


def test_aarsregnskapet_validerer_uten_advarsler():
    svar = tjeneste.valider_aarsregnskap(_CONFIG)
    assert svar["feil"] == []
    assert svar["advarsler"] == []


def test_aksjonaerregisteroppgaven_validerer():
    assert tjeneste.valider_aksjonaer(_CONFIG)["feil"] == []


def test_skattemeldingen_validerer():
    assert tjeneste.valider_skattemelding(_CONFIG)["feil"] == []
