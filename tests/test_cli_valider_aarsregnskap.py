"""
Tester for `wenche valider-aarsregnskap` (CLI).

Kommandoen kjører de lokale sjekkene (valider + advarsler) uten å sende inn,
slik at den kan brukes som en gate: exit-kode 1 ved blokkerende feil, 0 ellers
(advarsler alene gir ikke feilkode). Ingenting genereres eller sendes.
"""

import yaml
from click.testing import CliRunner

from wenche.cli import main

_BASE = {
    "selskap": {
        "navn": "Test Holding AS",
        "org_nummer": "123456789",
        "daglig_leder": "Ola Nordmann",
        "styreleder": "Ola Nordmann",
        "forretningsadresse": "Testveien 1, 0001 Oslo",
        "stiftelsesaar": 2020,
        "aksjekapital": 30000,
    },
    "regnskapsaar": 2025,
    "resultatregnskap": {
        "driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
        "driftskostnader": {"loennskostnader": 0, "avskrivninger": 0, "andre_driftskostnader": 0},
        "finansposter": {
            "utbytte_fra_datterselskap": 0,
            "andre_finansinntekter": 0,
            "rentekostnader": 0,
            "andre_finanskostnader": 0,
        },
    },
    "balanse": {
        "eiendeler": {
            "anleggsmidler": {"aksjer_i_datterselskap": 0, "andre_aksjer": 0, "langsiktige_fordringer": 0},
            "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000},
        },
        "egenkapital_og_gjeld": {
            "egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 0},
            "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
            "kortsiktig_gjeld": {
                "leverandoergjeld": 0,
                "skyldige_offentlige_avgifter": 0,
                "annen_kortsiktig_gjeld": 0,
            },
        },
    },
    # Sammenligningstall for fjoråret (selskapet er stiftet 2020, ikke nystiftet).
    "foregaaende_aar": {
        "balanse": {
            "eiendeler": {
                "anleggsmidler": {"aksjer_i_datterselskap": 0, "andre_aksjer": 0, "langsiktige_fordringer": 0},
                "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000},
            },
            "egenkapital_og_gjeld": {
                "egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 0},
                "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
                "kortsiktig_gjeld": {
                    "leverandoergjeld": 0,
                    "skyldige_offentlige_avgifter": 0,
                    "annen_kortsiktig_gjeld": 0,
                },
            },
        },
    },
    "aksjonaerer": [
        {
            "navn": "Kari Nordmann",
            "fodselsnummer": "01010112345",
            "antall_aksjer": 1000,
            "aksjeklasse": "ordinære",
            "utbytte_utbetalt": 0,
            "innbetalt_kapital_per_aksje": 30,
        }
    ],
}


def _skriv(tmp_path, muter=None):
    import copy

    cfg = copy.deepcopy(_BASE)
    if muter:
        muter(cfg)
    fil = tmp_path / "config.yaml"
    fil.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return str(fil)


def test_gyldig_regnskap_gir_exit_0(tmp_path):
    fil = _skriv(tmp_path)
    res = CliRunner().invoke(main, ["valider-aarsregnskap", "--config", fil])
    assert res.exit_code == 0
    assert "Validering OK." in res.output


def test_ubalanse_gir_exit_1(tmp_path):
    def muter(cfg):
        cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = 0  # eiendeler 0, EK 30000

    fil = _skriv(tmp_path, muter)
    res = CliRunner().invoke(main, ["valider-aarsregnskap", "--config", fil])
    assert res.exit_code == 1
    assert "Balansen går ikke opp" in res.output


def test_utbytte_uten_dekning_advarer_men_exit_0(tmp_path):
    def muter(cfg):
        # Balansen holdes gyldig: bank 5000, fri EK negativ (-25000), aksjekapital 30000.
        cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = 5000
        cfg["balanse"]["egenkapital_og_gjeld"]["egenkapital"]["annen_egenkapital"] = -25000
        cfg["aksjonaerer"][0]["utbytte_utbetalt"] = 10000

    fil = _skriv(tmp_path, muter)
    res = CliRunner().invoke(main, ["valider-aarsregnskap", "--config", fil])
    assert res.exit_code == 0
    assert "ADVARSEL" in res.output
    assert "fri egenkapital" in res.output


def test_finner_ikke_config_gir_exit_1(tmp_path):
    res = CliRunner().invoke(
        main, ["valider-aarsregnskap", "--config", str(tmp_path / "mangler.yaml")]
    )
    assert res.exit_code == 1
    assert "finner ikke" in res.output
