"""
Tester for hjelpefunksjoner i wenche.ui som ikke krever NiceGUI-runtime.
"""

from datetime import date
from unittest.mock import patch

from wenche.ui import _neste_frist, _regnskapsaar_for_frist


def _freeze_today(d: date):
    """Lag en `date`-subklasse med today() frosset til gitt dato."""
    klass = type("FrozenDate", (date,), {})
    klass.today = classmethod(lambda cls: d)
    return klass


class TestRegnskapsaarForFrist:

    def test_skattemelding_frist_31_mai_etter_idag(self):
        """18. mai 2026: neste 31. mai er 2026 → regnskapsår 2025."""
        with patch("wenche.ui.date", _freeze_today(date(2026, 5, 18))):
            assert _regnskapsaar_for_frist(5, 31) == 2025

    def test_aarsregnskap_frist_31_juli(self):
        """18. mai 2026: neste 31. juli er 2026 → regnskapsår 2025."""
        with patch("wenche.ui.date", _freeze_today(date(2026, 5, 18))):
            assert _regnskapsaar_for_frist(7, 31) == 2025

    def test_aksjonaerregister_frist_31_januar_etter_passert(self):
        """18. mai 2026: 31. jan 2026 er passert, neste er 2027 → regnskapsår 2026."""
        with patch("wenche.ui.date", _freeze_today(date(2026, 5, 18))):
            assert _regnskapsaar_for_frist(1, 31) == 2026

    def test_frist_idag_telles_som_aktiv(self):
        """Dagens dato er fristen → frist.year - 1 = forrige år."""
        with patch("wenche.ui.date", _freeze_today(date(2026, 5, 31))):
            assert _regnskapsaar_for_frist(5, 31) == 2025

    def test_dagen_etter_frist_ruller_til_neste_aar(self):
        """1. juni 2026: 31. mai er passert, neste er 2027 → regnskapsår 2026."""
        with patch("wenche.ui.date", _freeze_today(date(2026, 6, 1))):
            assert _regnskapsaar_for_frist(5, 31) == 2026


class TestNesteFrist:

    def test_frist_i_fremtiden_samme_aar(self):
        with patch("wenche.ui.date", _freeze_today(date(2026, 5, 18))):
            assert _neste_frist(7, 31) == date(2026, 7, 31)

    def test_frist_passert_ruller_til_neste_aar(self):
        with patch("wenche.ui.date", _freeze_today(date(2026, 5, 18))):
            assert _neste_frist(1, 31) == date(2027, 1, 31)
