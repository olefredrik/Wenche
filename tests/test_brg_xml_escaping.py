"""Tekstfelt i BRG-XML-en escapes, så et selskapsnavn med & eller < ikke gir ugyldig XML."""

import dataclasses
import xml.etree.ElementTree as ET

from wenche.brg_xml import generer_hovedskjema, generer_underskjema

NS_H = "http://schema.brreg.no/regnsys/aarsregnskap_vanlig"


def _med(regnskap, navn, daglig_leder):
    selskap = dataclasses.replace(regnskap.selskap, navn=navn, daglig_leder=daglig_leder)
    return dataclasses.replace(regnskap, selskap=selskap)


def test_hovedskjema_escaper_navn_og_signatar(eksempel_regnskap):
    navn = "Smith & Sønn <Holding> AS"
    signatar = 'Kari "K" O\'Brien & Co'
    regnskap = _med(eksempel_regnskap, navn, signatar)
    root = ET.fromstring(generer_hovedskjema(regnskap))  # kastet ParseError uten escaping
    assert root.find(f".//{{{NS_H}}}navn").text == navn
    assert root.find(f".//{{{NS_H}}}bekreftendeSelskapsrepresentant").text == signatar


def test_underskjema_er_gyldig_xml_med_spesialtegn_i_selskapet(eksempel_regnskap):
    ET.fromstring(generer_underskjema(_med(eksempel_regnskap, "A & B AS", "C < D")))
