"""
Tester for fase «ikke lekk nøkkelsti i feilsvar og stram filrettigheter på config.yaml».

config.yaml kan inneholde fødselsnummer (aksjonærer) og skal være lesbar kun for eier,
samme regel som token-cachen (auth.py). Og feilmeldingen ved manglende privat nøkkel
propagerer til API-klienter via web-backendens 502-svar, så den skal ikke røpe filstien.
"""
import stat

import pytest

from wenche.auth import _les_nokkel
from wenche.web.backend import miljo
from wenche.web.backend.ruter_config import lagre_config


def test_les_nokkel_feilmelding_roper_ikke_filsti(tmp_path):
    sti = tmp_path / "hemmelig-katalog" / "nokkel.pem"
    with pytest.raises(RuntimeError) as ei:
        _les_nokkel(str(sti))
    melding = str(ei.value)
    assert "hemmelig-katalog" not in melding
    assert "MASKINPORTEN_PRIVAT_NOKKEL" in melding


def _modus(fil) -> int:
    return stat.S_IMODE(fil.stat().st_mode)


def test_lagre_config_oppretter_med_0600(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lagre_config(config={"selskap": {"navn": "Test AS"}})
    assert _modus(miljo.config_fil()) == 0o600


def test_lagre_config_strammer_eksisterende_fil(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fil = miljo.config_fil()
    fil.write_text("selskap: {}\n", encoding="utf-8")
    fil.chmod(0o644)  # fil fra før innstrammingen
    lagre_config(config={"selskap": {"navn": "Test AS"}})
    assert _modus(fil) == 0o600
