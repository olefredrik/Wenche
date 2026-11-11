"""
Ett skjema for config.yaml: dataklassene i wenche.models (Konfig + Dok) er den ene kilden, og
JSON Schema, TypeScript-typen, referansetabellene og nøkkeltreet i configfelt kommer derfra.

Testene sikrer at kilden er komplett (alle felt dokumentert), at skjemaet er gyldig og strengt,
at eksempel-configen validerer, og at de genererte filene i repoet er à jour med modellen.
"""

import copy
import json
import re
from pathlib import Path

import jsonschema
import pytest
import yaml
from click.testing import CliRunner

from wenche import skjema
from wenche.cli import main
from wenche.models import Konfig

_ROT = Path(__file__).resolve().parent.parent
_SKJEMA = skjema.json_schema()
_EKSEMPEL = yaml.safe_load((_ROT / "config.example.yaml").read_text(encoding="utf-8"))


def _json_klar(obj):
    """YAML gir datoer som date-objekter; i JSON er de tekst."""
    return json.loads(json.dumps(obj, default=lambda o: o.isoformat()))


def _valider(cfg: dict) -> None:
    jsonschema.validate(_json_klar(cfg), _SKJEMA, format_checker=jsonschema.FormatChecker())


class TestKilden:
    def test_alle_bladfelt_har_dok(self):
        for klasse in skjema.klasser():
            for f in skjema.felter(klasse):
                slag, _, _ = skjema.analyser(f.type)
                if slag == "dataclass" and klasse is not Konfig:
                    continue  # underseksjoner dokumenteres av sine egne felt
                assert f.dok is not None and f.dok.tekst.strip(), (
                    f"{klasse.__name__}.{f.navn} mangler Dok"
                )

    def test_dok_tekstene_foelger_skrivereglene(self):
        # Tekstene er brukerrettet dokumentasjon: ingen tankestrek (prosjektregel).
        for klasse in skjema.klasser():
            for f in skjema.felter(klasse):
                if f.dok:
                    assert "—" not in f.dok.tekst and "–" not in f.dok.tekst, f.navn

    def test_bladstiene_dekker_skjemaet_i_webappene(self):
        # Vakt mot drift mellom skjemaet i SPA-ene og modellen: hvert felt skjemaet kan
        # skrive, skal finnes i config-skjemaet.
        stier = set(skjema.bladstier())
        tekst = (_ROT / "packages/ui/src/felter.ts").read_text(encoding="utf-8")
        nokler = set(re.findall(r'key: "([a-z_.]+)"', tekst))
        assert len(nokler) > 40  # fanger at mønsteret slutter å treffe
        assert nokler <= stier, nokler - stier


class TestJsonSchema:
    def test_skjemaet_er_gyldig_og_strengt(self):
        jsonschema.Draft202012Validator.check_schema(_SKJEMA)
        assert _SKJEMA["required"] == ["selskap", "regnskapsaar", "resultatregnskap", "balanse"]
        assert _SKJEMA["additionalProperties"] is False
        assert all(d["additionalProperties"] is False for d in _SKJEMA["$defs"].values())

    def test_typer_standardverdier_og_lovlige_verdier(self):
        defs = _SKJEMA["$defs"]
        assert defs["Selskap"]["properties"]["stiftelsesdato"]["anyOf"][0] == {
            "type": "string",
            "format": "date",
        }
        assert defs["LaanTilNaerstaaende"]["properties"]["retning"]["enum"] == [
            "långiver",
            "låntaker",
        ]
        assert defs["SkattemeldingKonfig"]["properties"]["anvend_fritaksmetoden"]["default"] is True
        assert "naeringsspesifikasjonsposter" not in defs["SkattemeldingKonfig"]["properties"]
        # Leses med 0 som standard, så valgfri i fila selv om modellen krever den.
        assert "utbytte_utbetalt" not in defs["Aksjonaer"]["required"]
        assert defs["Aksjonaer"]["required"] == [
            "navn",
            "fodselsnummer",
            "antall_aksjer",
            "aksjeklasse",
        ]

    def test_eksempel_configen_validerer(self):
        _valider(_EKSEMPEL)

    def test_config_med_noter_laan_og_naeringsspesifikasjon_validerer(self):
        cfg = copy.deepcopy(_EKSEMPEL)
        cfg["noter"] = {
            "antall_ansatte": 0,
            "laan_til_naerstaaende": [
                {"motpart": "Kari Eier", "saldo": 50000, "retning": "låntaker"}
            ],
        }
        cfg["naeringsspesifikasjon"] = {
            "poster": [{"kategori": "salgsinntekt", "kode": "3000", "beloep": 1}]
        }
        cfg["utbytte_vedtaksdato"] = "2025-06-01"
        _valider(cfg)

    def test_ukjent_felt_og_ugyldig_verdi_avvises(self):
        cfg = copy.deepcopy(_EKSEMPEL)
        cfg["balanse"]["eiendeler"]["anleggsmidler"]["aksjer_i_tilknyttet_selskap"] = 1
        with pytest.raises(jsonschema.ValidationError, match="aksjer_i_tilknyttet_selskap"):
            _valider(cfg)
        cfg = copy.deepcopy(_EKSEMPEL)
        cfg["noter"] = {
            "laan_til_naerstaaende": [{"motpart": "X", "saldo": 1, "retning": "garantist"}]
        }
        with pytest.raises(jsonschema.ValidationError, match="garantist"):
            _valider(cfg)

    def test_cli_skjema_skriver_json(self, tmp_path):
        resultat = CliRunner().invoke(main, ["skjema"])
        assert resultat.exit_code == 0, resultat.output
        assert json.loads(resultat.output)["title"] == "Wenche config.yaml"
        ut = tmp_path / "skjema.json"
        resultat = CliRunner().invoke(main, ["skjema", "--ut", str(ut)])
        assert resultat.exit_code == 0
        assert json.loads(ut.read_text(encoding="utf-8")) == _SKJEMA


class TestGenererteFiler:
    def test_typescript_typen_er_a_jour(self):
        fil = _ROT / "packages/ui/src/config.generert.ts"
        assert fil.read_text(encoding="utf-8") == skjema.typescript(), (
            "Kjør scripts/generer_skjema.py"
        )

    def test_referansen_er_a_jour(self):
        tekst = (_ROT / "docs/referanse.md").read_text(encoding="utf-8")
        assert tekst.count("<!-- skjema:") >= 15
        assert skjema.oppdater_referanse(tekst) == tekst, "Kjør scripts/generer_skjema.py"

    def test_referansen_dokumenterer_hvert_felt(self):
        tekst = (_ROT / "docs/referanse.md").read_text(encoding="utf-8")
        for sti in skjema.bladstier():
            navn = sti.rsplit(".", 1)[-1]
            assert f"| `{navn}` |" in tekst, sti
