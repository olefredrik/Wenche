"""
Advarsel om felt i config.yaml som Wenche ikke kjenner.

Leserne ignorerte ukjente felt uten varsel, så et beløp i et felt Wenche ikke kjenner,
forsvant fra innsendingen mens valideringen sa OK (#191). Typisk er configen laget for en
nyere Wenche-versjon, eller feltnavnet er feilstavet.

Testene dekker:
  1. Ukjente felt fanges med full sti i alle kontrollerte seksjoner.
  2. Ingen falske treff: skjemaets felt, eksempel-configen og SAF-T-importen er kjente.
  3. Advarselen når brukeren i alle tre valideringene og i CLI-en.
"""

import copy
import re
from pathlib import Path

import yaml
from click.testing import CliRunner

from wenche import innsending as tjeneste
from wenche import saft
from wenche.cli import main
from wenche.configfelt import advarsel_om_ukjente_felt, ukjente_felt

_ROT = Path(__file__).resolve().parent.parent
_EKSEMPEL = yaml.safe_load((_ROT / "config.example.yaml").read_text())


def _med(sti: str, verdi=1) -> dict:
    """Eksempel-configen med en verdi satt på en punktum-separert sti."""
    cfg = copy.deepcopy(_EKSEMPEL)
    node = cfg
    *forelder, blad = sti.split(".")
    for nokkel in forelder:
        node = node.setdefault(nokkel, {})
    node[blad] = verdi
    return cfg


class TestUkjenteFelt:
    def test_eksempel_configen_har_ingen_ukjente_felt(self):
        assert ukjente_felt(_EKSEMPEL) == []

    def test_feilstavet_resultatfelt(self):
        cfg = _med("resultatregnskap.finansposter.utbytte_fra_andre_akjser", 20000)
        assert ukjente_felt(cfg) == ["resultatregnskap.finansposter.utbytte_fra_andre_akjser"]

    def test_ukjent_balansefelt(self):
        cfg = _med("balanse.eiendeler.anleggsmidler.aksjer_i_tilknyttet_selskap", 5000)
        assert ukjente_felt(cfg) == ["balanse.eiendeler.anleggsmidler.aksjer_i_tilknyttet_selskap"]

    def test_ukjent_felt_i_fjoraaret(self):
        cfg = _med("foregaaende_aar.resultatregnskap.finansposter.nytt_felt")
        assert ukjente_felt(cfg) == ["foregaaende_aar.resultatregnskap.finansposter.nytt_felt"]

    def test_ukjent_felt_i_selskap_og_skattemelding(self):
        cfg = _med("selskap.epost", "x")
        cfg["skattemelding"]["eierandel"] = 90
        assert ukjente_felt(cfg) == ["selskap.epost", "skattemelding.eierandel"]

    def test_ukjent_felt_hos_aksjonaer(self):
        cfg = copy.deepcopy(_EKSEMPEL)
        cfg["aksjonaerer"][0]["fnr"] = "x"
        assert ukjente_felt(cfg) == ["aksjonaerer[0].fnr"]

    def test_toppnivaaet_kontrolleres_ogsaa(self):
        # Alle seksjoner er kjente via Konfig, også noter og naeringsspesifikasjon, mens en
        # feilstavet toppnøkkel fanges. Metadata med «_» foran (som _advarsler) er ikke felt.
        cfg = copy.deepcopy(_EKSEMPEL)
        cfg["noter"] = {
            "antall_ansatte": 0,
            "laan_til_naerstaaende": [{"motpart": "X", "saldo": 1}],
        }
        cfg["naeringsspesifikasjon"] = {
            "poster": [{"kategori": "salgsinntekt", "kode": "3000", "beloep": 1}]
        }
        cfg["_advarsler"] = ["x"]
        assert ukjente_felt(cfg) == []
        cfg["regnskapsår"] = 2025
        cfg["noter"]["laan_til_naerstaaende"][0]["rente"] = 2
        assert sorted(ukjente_felt(cfg)) == ["noter.laan_til_naerstaaende[0].rente", "regnskapsår"]

    def test_leser_fil(self, tmp_path):
        fil = tmp_path / "config.yaml"
        fil.write_text(yaml.safe_dump(_med("selskap.epost", "x"), allow_unicode=True))
        assert ukjente_felt(str(fil)) == ["selskap.epost"]


class TestIngenFalskeTreff:
    def test_alle_skjemafelt_er_kjente(self):
        # Vakt mot drift mellom skjemaet og modellen: hvert felt skjemaet kan skrive, skal
        # Wenche kjenne. Feiler denne, har skjemaet fått et felt modellen ikke leser.
        skjema = (_ROT / "packages/ui/src/felter.ts").read_text()
        nokler = set(re.findall(r'key: "([a-z_.]+)"', skjema))
        assert len(nokler) > 40  # Fanger at mønsteret slutter å treffe.
        for sti in sorted(nokler):
            assert ukjente_felt(_med(sti)) == [], sti

    def test_saft_importen_gir_ingen_ukjente_felt(self):
        cfg = saft.importer(str(Path(__file__).parent / "fixtures" / "saft_financial_v140.xml"))
        cfg.pop("_advarsler", None)
        assert ukjente_felt(cfg) == []


class TestAdvarselen:
    def test_ingen_advarsel_uten_ukjente_felt(self):
        assert advarsel_om_ukjente_felt(_EKSEMPEL) == []

    def test_ett_felt(self):
        adv = advarsel_om_ukjente_felt(_med("selskap.epost", "x"))
        assert len(adv) == 1
        assert "feltet i configen, og ignorerer det: selskap.epost" in adv[0]
        assert "oppgrader Wenche" in adv[0]

    def test_flere_felt_i_samme_advarsel(self):
        cfg = _med("selskap.epost", "x")
        cfg["skattemelding"]["eierandel"] = 90
        adv = advarsel_om_ukjente_felt(cfg)
        assert len(adv) == 1
        assert "disse feltene" in adv[0]
        assert "selskap.epost, skattemelding.eierandel" in adv[0]


class TestKallsteder:
    _CFG = _med("resultatregnskap.finansposter.utbytte_fra_andre_akjser", 20000)

    def test_aarsregnskapets_validering(self):
        svar = tjeneste.valider_aarsregnskap(copy.deepcopy(self._CFG))
        assert any("utbytte_fra_andre_akjser" in a for a in svar["advarsler"])

    def test_aksjonaerregisterets_validering(self):
        svar = tjeneste.valider_aksjonaer(copy.deepcopy(self._CFG))
        assert any("utbytte_fra_andre_akjser" in a for a in svar["advarsler"])

    def test_skattemeldingens_validering(self):
        svar = tjeneste.valider_skattemelding(copy.deepcopy(self._CFG))
        assert any("utbytte_fra_andre_akjser" in a for a in svar["advarsler"])

    def test_skattemeldingens_feilsvar_har_ogsaa_advarselen(self):
        # Et feilstavet felt kan være grunnen til at et påkrevd felt mangler.
        cfg = copy.deepcopy(_EKSEMPEL)
        cfg["selskap"]["dagliglder"] = cfg["selskap"].pop("daglig_leder")
        cfg["selskap"]["styreleder"] = ""
        svar = tjeneste.valider_skattemelding(cfg)
        assert not svar["ok"]
        assert any("selskap.dagliglder" in a for a in svar["advarsler"])

    def test_cli_valider_aarsregnskap(self, tmp_path):
        fil = tmp_path / "config.yaml"
        fil.write_text(yaml.safe_dump(self._CFG, allow_unicode=True))
        result = CliRunner().invoke(main, ["valider-aarsregnskap", "--config", str(fil)])
        assert result.exit_code == 0
        assert "ADVARSEL" in result.output and "utbytte_fra_andre_akjser" in result.output

    def test_cli_generer_skattemelding_holder_stdout_ren(self, tmp_path):
        fil = tmp_path / "config.yaml"
        fil.write_text(yaml.safe_dump(self._CFG, allow_unicode=True))
        result = CliRunner().invoke(main, ["generer-skattemelding", "--config", str(fil)])
        assert result.exit_code == 0
        assert "utbytte_fra_andre_akjser" in result.stderr
        assert "utbytte_fra_andre_akjser" not in result.stdout
