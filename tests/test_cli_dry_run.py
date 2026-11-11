"""
Dry-run i CLI-en: filene skrives av CLI-en selv (domenelaget rører ikke disk), i `--ut-mappe`,
med 0600 siden aksjonærregisteroppgaven inneholder fødselsnummer. Feil Wenche selv melder
blir en lesbar melding og exit-kode 1, ikke en traceback.
"""

import stat

import yaml
from click.testing import CliRunner

from tests.test_selfhosted_innsending import _gyldig_config
from wenche.cli import main


def _skriv_config(tmp_path, cfg=None) -> str:
    fil = tmp_path / "config.yaml"
    fil.write_text(yaml.safe_dump(cfg or _gyldig_config(), allow_unicode=True), encoding="utf-8")
    return str(fil)


def test_send_aarsregnskap_dry_run_skriver_filer_med_0600(tmp_path, monkeypatch):
    monkeypatch.delenv("WENCHE_ENV", raising=False)
    ut = tmp_path / "ut"
    res = CliRunner().invoke(
        main,
        [
            "send-aarsregnskap",
            "--config",
            _skriv_config(tmp_path),
            "--dry-run",
            "--ut-mappe",
            str(ut),
        ],
    )
    assert res.exit_code == 0, res.output
    assert sorted(p.name for p in ut.iterdir()) == [
        "aarsregnskap_2024_310137715_hovedskjema.xml",
        "aarsregnskap_2024_310137715_underskjema.xml",
    ]
    for p in ut.iterdir():
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
    assert "Ingenting sendt" in res.output


def test_send_aksjonaerregister_dry_run(tmp_path, monkeypatch):
    monkeypatch.delenv("WENCHE_ENV", raising=False)
    ut = tmp_path / "ut"
    res = CliRunner().invoke(
        main,
        [
            "send-aksjonaerregister",
            "--config",
            _skriv_config(tmp_path),
            "--dry-run",
            "--ut-mappe",
            str(ut),
        ],
    )
    assert res.exit_code == 0, res.output
    assert sorted(p.name for p in ut.iterdir()) == [
        "aksjonaerregister_2024_310137715_hovedskjema.xml",
        "aksjonaerregister_2024_310137715_underskjema_1.xml",
    ]


def test_dry_run_med_valideringsfeil_gir_exit_1_og_ingen_filer(tmp_path, monkeypatch):
    monkeypatch.delenv("WENCHE_ENV", raising=False)
    cfg = _gyldig_config()
    cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = 999  # balansen går ikke opp
    ut = tmp_path / "ut"
    res = CliRunner().invoke(
        main,
        [
            "send-aarsregnskap",
            "--config",
            _skriv_config(tmp_path, cfg),
            "--dry-run",
            "--ut-mappe",
            str(ut),
        ],
    )
    assert res.exit_code == 1
    assert "Validering mislyktes" in res.output
    assert not ut.exists()


def test_wenchefeil_gir_lesbar_melding_ikke_traceback(tmp_path, monkeypatch):
    """Manglende credentials (KonfigFeil) under innlogging: «Feil: ...» og exit 1."""
    import wenche.auth as auth_mod
    from wenche.feil import KonfigFeil

    monkeypatch.delenv("WENCHE_ENV", raising=False)

    def mangler():
        raise KonfigFeil("MASKINPORTEN_CLIENT_ID mangler.")

    monkeypatch.setattr(auth_mod, "get_altinn_token", mangler)
    res = CliRunner().invoke(main, ["send-aarsregnskap", "--config", _skriv_config(tmp_path)])
    assert res.exit_code == 1
    assert "Feil: MASKINPORTEN_CLIENT_ID mangler." in res.output
    assert "Traceback" not in res.output
