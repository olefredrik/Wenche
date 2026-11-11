"""Årsverk i årsregnskapet følger antall ansatte i note 2, og dry-run advarer når det er over 0.

Før sto antallAarsverk alltid som 0 uansett hva noten sa. Nå leses `noter` inn på
årsregnskapet, så XML-en og noten kommer fra samme tall."""

import dataclasses
import xml.etree.ElementTree as ET

import pytest

from tests.test_selfhosted_innsending import _gyldig_config
from wenche import aarsregnskap, konfig
from wenche.brg_xml import generer_underskjema
from wenche.feil import KonfigFeil
from wenche.models import Noter

NS_UNDER = "http://schema.brreg.no/regnsys/aarsregnskap_vanlig/underskjema"


def _aarsverk(xml_bytes: bytes) -> str:
    root = ET.fromstring(xml_bytes)  # noqa: S314 (egen generert XML, ingen ekstern kilde)
    el = root.find(f".//{{{NS_UNDER}}}antallAarsverk")
    assert el is not None and el.text is not None
    return el.text


def test_aarsverk_er_null_uten_ansatte(eksempel_regnskap):
    assert eksempel_regnskap.noter.antall_ansatte == 0
    assert _aarsverk(generer_underskjema(eksempel_regnskap)) == "0"


def test_aarsverk_foelger_antall_ansatte_i_noten(eksempel_regnskap):
    med_ansatte = dataclasses.replace(eksempel_regnskap, noter=Noter(antall_ansatte=2))
    assert _aarsverk(generer_underskjema(med_ansatte)) == "2"


def test_ingen_advarsel_om_ansatte_naar_tallet_er_null(eksempel_regnskap):
    assert not [a for a in aarsregnskap.advarsler(eksempel_regnskap) if "ansatt" in a]


@pytest.mark.parametrize(("antall", "ord"), [(1, "1 ansatt i note 2"), (3, "3 ansatte i note 2")])
def test_advarsel_naar_selskapet_har_ansatte(eksempel_regnskap, antall, ord):
    med_ansatte = dataclasses.replace(eksempel_regnskap, noter=Noter(antall_ansatte=antall))
    advarsler = [a for a in aarsregnskap.advarsler(med_ansatte) if "ansatt" in a]
    assert len(advarsler) == 1
    assert ord in advarsler[0]
    assert f"{antall} årsverk" in advarsler[0]
    assert "a-melding" in advarsler[0]


def test_konfig_leser_noter_seksjonen_inn_paa_aarsregnskapet():
    cfg = _gyldig_config()
    cfg["noter"] = {
        "antall_ansatte": 1,
        "laan_til_naerstaaende": [{"motpart": "Kari Eier", "saldo": 50000, "retning": "långiver"}],
    }
    regnskap = konfig.les_aarsregnskap(cfg)
    assert regnskap.noter.antall_ansatte == 1
    assert regnskap.noter.laan_til_naerstaaende[0].motpart == "Kari Eier"
    assert regnskap.noter.laan_til_naerstaaende[0].saldo == 50000.0
    assert regnskap.noter.laan_til_naerstaaende[0].rente_prosent == 0.0


def test_konfig_uten_noter_gir_tomme_noter():
    cfg = _gyldig_config()
    cfg.pop("noter", None)
    regnskap = konfig.les_aarsregnskap(cfg)
    assert regnskap.noter == Noter()


def test_konfig_ugyldig_antall_ansatte_gir_feltsti():
    cfg = _gyldig_config()
    cfg["noter"] = {"antall_ansatte": "to"}
    with pytest.raises(KonfigFeil) as e:
        konfig.les_aarsregnskap(cfg)
    assert e.value.felt == "noter.antall_ansatte"
