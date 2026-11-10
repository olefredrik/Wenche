"""skriv_privat: filer med hemmeligheter får 0600 fra første byte og byttes inn atomisk."""
import stat

from wenche.filer import sikre_privat_mappe, skriv_privat


def _modus(sti):
    return stat.S_IMODE(sti.stat().st_mode)


def test_skriver_innhold_med_0600_i_privat_mappe(tmp_path):
    fil = tmp_path / "ny" / "token.json"
    skriv_privat(fil, '{"a": 1}')
    assert fil.read_text(encoding="utf-8") == '{"a": 1}'
    assert _modus(fil) == 0o600
    assert _modus(fil.parent) == 0o700


def test_strammer_eksisterende_fil_med_videre_rettigheter(tmp_path):
    fil = tmp_path / "nokkel.pem"
    fil.write_text("gammel", encoding="utf-8")
    fil.chmod(0o644)
    skriv_privat(fil, b"ny")
    assert fil.read_bytes() == b"ny"
    assert _modus(fil) == 0o600


def test_etterlater_ingen_midlertidig_fil(tmp_path):
    fil = tmp_path / "config.yaml"
    skriv_privat(fil, "x: 1\n")
    assert [p.name for p in tmp_path.iterdir()] == ["config.yaml"]


def test_sikre_privat_mappe_er_idempotent(tmp_path):
    mappe = tmp_path / ".wenche"
    sikre_privat_mappe(mappe)
    sikre_privat_mappe(mappe)
    assert mappe.is_dir()
    assert _modus(mappe) == 0o700
