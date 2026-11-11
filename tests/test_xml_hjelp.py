"""Hjelperne XML-byggerne deler (wenche/xml_hjelp.py). Avrundingen er Pythons, med vilje."""

from xml.etree.ElementTree import fromstring

from wenche.xml_hjelp import (
    beloep_tekst,
    desimaltall,
    finn_tekst,
    heltall,
    heltall_tekst,
    lokalnavn,
)


def test_heltall_er_pythons_avrunding():
    assert heltall(2.5) == 2 and heltall(3.5) == 4  # halv til nærmeste partall, som før
    assert heltall(1234.6) == 1235
    assert heltall_tekst(1234.6) == "1235"
    assert heltall_tekst(-0.4) == "0"


def test_beloep_tekst_har_hele_kroner_med_to_desimaler():
    assert beloep_tekst(1234.6) == "1235.00"
    assert beloep_tekst(0) == "0.00"


def test_desimaltall_slik_rf1086_vil_ha_det():
    assert desimaltall(10000, 2) == "10000"
    assert desimaltall(10000.5, 2) == "10000.50"
    assert desimaltall(10000.499, 2) == "10000.50"
    assert desimaltall(300, 6, kompakt=True) == "300"
    assert desimaltall(0.1, 6, kompakt=True) == "0.1"
    assert desimaltall(0.123456789, 6, kompakt=True) == "0.123457"


def test_lokalnavn_og_finn_tekst():
    assert lokalnavn("{urn:no:skatteetaten:x}type") == "type"
    assert lokalnavn("type") == "type"
    root = fromstring('<r xmlns="urn:x"><type> fastsatt </type><tom/></r>')
    assert finn_tekst(root, "type") == "fastsatt"
    assert finn_tekst(root, "tom") is None
    assert finn_tekst(root, "finnes-ikke") is None
