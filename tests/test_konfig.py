"""
Den delte config-leseren (wenche/konfig.py): alle tre innsendingene leser likt, manglende
seksjoner og ugyldige verdier blir KonfigFeil med feltsti, og tomme felt fra skjemaet tåles.
"""

import copy

import pytest
import yaml

from tests.test_selfhosted_innsending import _gyldig_config
from wenche import aarsregnskap, aksjonaerregister, konfig, skattemelding
from wenche.feil import KonfigFeil


def test_les_raa_tar_dict_fil_og_tom_fil(tmp_path):
    cfg = _gyldig_config()
    assert konfig.les_raa(cfg) is cfg
    fil = tmp_path / "config.yaml"
    fil.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    assert konfig.les_raa(str(fil))["selskap"]["org_nummer"] == cfg["selskap"]["org_nummer"]
    (tmp_path / "tom.yaml").write_text("", encoding="utf-8")
    assert konfig.les_raa(str(tmp_path / "tom.yaml")) == {}
    (tmp_path / "liste.yaml").write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(KonfigFeil, match="inneholder ikke en config"):
        konfig.les_raa(str(tmp_path / "liste.yaml"))


@pytest.mark.parametrize(
    "seksjon,navn", [("balanse", "Balansen"), ("resultatregnskap", "Resultatregnskapet")]
)
def test_manglende_seksjon_gir_konfigfeil_med_felt(seksjon, navn):
    cfg = _gyldig_config()
    del cfg[seksjon]
    with pytest.raises(KonfigFeil) as ei:
        aarsregnskap.les_config(cfg)
    assert ei.value.felt == seksjon
    assert f"{navn} mangler" in str(ei.value)
    # En seksjon som står tom i YAML (`balanse:`) teller også som manglende, ikke som krasj.
    cfg[seksjon] = None
    with pytest.raises(KonfigFeil) as ei:
        aarsregnskap.les_config(cfg)
    assert ei.value.felt == seksjon


def test_tom_fil_gir_lesbar_feil_om_selskap():
    with pytest.raises(KonfigFeil, match="Selskapsopplysningene mangler"):
        aarsregnskap.les_config({})


def test_tomme_tallfelt_fra_skjemaet_leses_som_null():
    cfg = _gyldig_config()
    cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = ""
    cfg["resultatregnskap"]["skattekostnad"] = None
    regnskap = aarsregnskap.les_config(cfg)
    assert regnskap.balanse.eiendeler.omloepmidler.bankinnskudd == 0.0
    assert regnskap.resultatregnskap.skattekostnad == 0.0


def test_ugyldig_tall_gir_konfigfeil_med_feltsti():
    cfg = _gyldig_config()
    cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = "tretti tusen"
    with pytest.raises(KonfigFeil) as ei:
        aarsregnskap.les_config(cfg)
    assert ei.value.felt == "balanse.eiendeler.omloepmidler.bankinnskudd"
    assert "må være et tall" in str(ei.value)


@pytest.mark.parametrize("leser", [aarsregnskap.les_config, aksjonaerregister.les_config])
def test_stiftelsesaar_maa_finnes_som_tall_i_alle_leserne(leser):
    cfg = _gyldig_config()
    cfg["selskap"]["stiftelsesaar"] = ""
    with pytest.raises(KonfigFeil, match="Stiftelsesår mangler") as ei:
        leser(cfg)
    assert ei.value.felt == "selskap.stiftelsesaar"
    cfg["selskap"]["stiftelsesaar"] = "nitten"
    with pytest.raises(KonfigFeil, match="Stiftelsesår må være et tall"):
        leser(cfg)
    cfg["selskap"]["stiftelsesaar"] = "2018"
    assert leser(cfg).selskap.stiftelsesaar == 2018
    cfg["selskap"]["stiftelsesaar"] = 2018.0
    assert leser(cfg).selskap.stiftelsesaar == 2018


def test_org_nummer_og_regnskapsaar_tvinges_likt():
    cfg = _gyldig_config()
    cfg["selskap"]["org_nummer"] = 310137715  # uten anførselstegn i YAML blir det et tall
    cfg["regnskapsaar"] = "2024"
    for leser in (aarsregnskap.les_config, aksjonaerregister.les_config):
        lest = leser(cfg)
        assert lest.selskap.org_nummer == "310137715"
        assert lest.regnskapsaar == 2024
    regnskap, _ = skattemelding.les_config(cfg)
    assert regnskap.selskap.org_nummer == "310137715" and regnskap.regnskapsaar == 2024


def test_ugyldig_dato_er_konfigfeil_og_valueerror():
    cfg = _gyldig_config()
    cfg["regnskapsstart"] = "01.01.2024"
    with pytest.raises(KonfigFeil, match="ÅÅÅÅ-MM-DD") as ei:
        aarsregnskap.les_config(cfg)
    assert ei.value.felt == "regnskapsstart"
    assert isinstance(ei.value, ValueError)  # eldre kallsteder fanger ValueError


def test_aksjonaer_antall_som_tekst_og_tomme_felt():
    cfg = _gyldig_config()
    cfg["aksjonaerer"][0]["antall_aksjer"] = "300"
    cfg["aksjonaerer"][0]["utbytte_utbetalt"] = ""
    oppgave = aksjonaerregister.les_config(cfg)
    assert oppgave.aksjonaerer[0].antall_aksjer == 300
    assert oppgave.aksjonaerer[0].utbytte_utbetalt == 0.0
    cfg["aksjonaerer"][0]["antall_aksjer"] = "300.5"
    with pytest.raises(KonfigFeil) as ei:
        aksjonaerregister.les_config(cfg)
    assert ei.value.felt == "aksjonaerer[1].antall_aksjer"


def test_manglende_aksjeklasse_navngir_aksjonaeren():
    cfg = _gyldig_config()
    del cfg["aksjonaerer"][0]["aksjeklasse"]
    with pytest.raises(KonfigFeil) as ei:
        aksjonaerregister.les_config(cfg)
    assert ei.value.felt == "aksjonaerer[1].aksjeklasse"


def test_uten_aksjonaerer_leses_tomt_og_valideringen_sier_fra():
    cfg = _gyldig_config()
    del cfg["aksjonaerer"]
    oppgave = aksjonaerregister.les_config(cfg)
    assert oppgave.aksjonaerer == []
    assert any("Minst én aksjonær" in f for f in aksjonaerregister.valider(oppgave))


def test_de_tre_leserne_gir_samme_selskap():
    cfg = _gyldig_config()
    a = aarsregnskap.les_config(copy.deepcopy(cfg))
    s, _ = skattemelding.les_config(copy.deepcopy(cfg))
    k = aksjonaerregister.les_config(copy.deepcopy(cfg))
    assert a.selskap == s.selskap == k.selskap
    assert a.regnskapsaar == s.regnskapsaar == k.regnskapsaar


def test_fjoraar_med_tom_seksjon_gir_tomme_modeller():
    cfg = _gyldig_config()
    cfg["foregaaende_aar"] = {"resultatregnskap": None, "balanse": {"eiendeler": None}}
    regnskap = aarsregnskap.les_config(cfg)
    assert regnskap.foregaaende_aar_resultat.aarsresultat == 0.0
    assert regnskap.foregaaende_aar_balanse.eiendeler.sum == 0.0
