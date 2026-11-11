"""Notegenereringen: note 2 om ansatte bøyes etter antallet (ingen / 1 ansatt / N ansatte)."""

from pathlib import Path

import pytest

from wenche import aarsregnskap, noter
from wenche.models import Noter

_CONFIG = Path(__file__).resolve().parent.parent / "config.example.yaml"


@pytest.mark.parametrize(
    ("antall", "tekst"),
    [
        (0, "Selskapet har ingen ansatte."),
        (1, "Selskapet hadde 1 ansatt i regnskapsåret."),
        (2, "Selskapet hadde 2 ansatte i regnskapsåret."),
    ],
)
def test_note_2_boeyer_ansatt_etter_antall(antall: int, tekst: str) -> None:
    regnskap = aarsregnskap.les_config(str(_CONFIG))
    tekst_ut = noter.generer(regnskap, Noter(antall_ansatte=antall))
    assert tekst in tekst_ut
    if antall:
        assert "Lønnskostnader inkl. arbeidsgiveravgift" in tekst_ut
    else:
        assert "Lønnskostnader" not in tekst_ut
