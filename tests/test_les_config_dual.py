"""
Den delte grensen mellom standalone (CLI/NiceGUI) og den hostede appen:
`les_config` må godta BÅDE en filsti (standalone leser config.yaml) OG en allerede parset
dict (hosted sender config i request-body), og gi IDENTISK resultat. Brekker noen denne
ekvivalensen, brekker enten standalone eller webapp i stillhet, derav disse regresjonsvaktene.
"""
import copy

import yaml

from wenche import aarsregnskap as ar
from wenche import aksjonaerregister as akr
from wenche import skattemelding as sm

_CFG = {
    "selskap": {
        "navn": "Delt Test AS",
        "org_nummer": "314273818",
        "daglig_leder": "Ola Nordmann",
        "styreleder": "Ola Nordmann",
        "forretningsadresse": "Testveien 1, 0001 Oslo",
        "stiftelsesaar": 2018,
        "aksjekapital": 30000,
        "kontakt_epost": "test@example.no",
    },
    "regnskapsaar": 2024,
    "resultatregnskap": {
        "driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
        "driftskostnader": {"loennskostnader": 0, "avskrivninger": 0, "andre_driftskostnader": 5500},
        "finansposter": {
            "utbytte_fra_datterselskap": 100000,
            "andre_finansinntekter": 0,
            "rentekostnader": 0,
            "andre_finanskostnader": 0,
        },
    },
    "balanse": {
        "eiendeler": {
            "anleggsmidler": {"aksjer_i_datterselskap": 100000, "andre_aksjer": 0, "langsiktige_fordringer": 0},
            "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 64500},
        },
        "egenkapital_og_gjeld": {
            "egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 134500},
            "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
            "kortsiktig_gjeld": {"leverandoergjeld": 0, "skyldige_offentlige_avgifter": 0, "annen_kortsiktig_gjeld": 0},
        },
    },
    "skattemelding": {
        "underskudd_til_fremfoering": 0,
        "formuesverdi_aksjer": 0,
        "anvend_fritaksmetoden": True,
        "boersnotert": False,
    },
    "aksjonaerer": [
        {
            "navn": "Kari Nordmann",
            "fodselsnummer": "24847799354",
            "antall_aksjer": 300,
            "aksjeklasse": "ordinære",
            "utbytte_utbetalt": 0,
            "innbetalt_kapital_per_aksje": 100,
        }
    ],
}


def _fil(tmp_path):
    f = tmp_path / "config.yaml"
    f.write_text(yaml.safe_dump(_CFG, allow_unicode=True), encoding="utf-8")
    return str(f)


def test_aarsregnskap_dict_og_fil_gir_likt(tmp_path):
    assert ar.les_config(dict(_CFG)) == ar.les_config(_fil(tmp_path))


def test_skattemelding_dict_og_fil_gir_likt(tmp_path):
    assert sm.les_config(dict(_CFG)) == sm.les_config(_fil(tmp_path))


def test_aksjonaer_dict_og_fil_gir_likt(tmp_path):
    assert akr.les_config(dict(_CFG)) == akr.les_config(_fil(tmp_path))


def test_delvis_fjoraar_uten_underseksjoner_kraesjer_ikke():
    # Regresjon: skjemaet utelater urørte (valgfrie) felt, så et delvis utfylt fjorår mangler
    # hele underseksjoner (her driftsinntekter). Før kastet _les_resultat KeyError på det direkte
    # oppslaget -> «Uventet feil under innsending» (HTTP 500). Nå leses de manglende som 0.
    cfg = copy.deepcopy(_CFG)
    cfg["foregaaende_aar"] = {
        "resultatregnskap": {"driftskostnader": {"andre_driftskostnader": 5.5},
                             "finansposter": {"rentekostnader": 70086}},
        "balanse": {"eiendeler": {"anleggsmidler": {"andre_aksjer": 2271521.28}}},
    }
    regnskap = ar.les_config(cfg)
    assert regnskap.foregaaende_aar_resultat.driftsinntekter.salgsinntekter == 0
    assert regnskap.foregaaende_aar_resultat.driftskostnader.andre_driftskostnader == 5.5
    assert regnskap.foregaaende_aar_balanse.eiendeler.anleggsmidler.andre_aksjer == 2271521.28
    # skattemelding deler de samme leserne
    sm.les_config(cfg)


def test_tomme_strenger_i_tallfelt_tolkes_som_null():
    # Regresjon: et blankt tallfelt sendes som "" fra skjemaet. Før ble float("")/int("") en
    # naken 500; nå tolkes tomt som 0 (og tom eierandel som 100 %, tom samlet_verdi som None).
    cfg = copy.deepcopy(_CFG)
    cfg["balanse"]["eiendeler"]["omloepmidler"]["bankinnskudd"] = ""
    cfg["skattemelding"]["underskudd_til_fremfoering"] = ""
    cfg["skattemelding"]["eierandel_for_fritaksmetoden"] = ""
    cfg["skattemelding"]["samlet_verdi_bak_aksjene"] = ""
    regnskap = ar.les_config(cfg)
    assert regnskap.balanse.eiendeler.omloepmidler.bankinnskudd == 0
    _, konfig = sm.les_config(cfg)
    assert konfig.underskudd_til_fremfoering == 0
    assert konfig.eierandel_for_fritaksmetoden == 100
    assert konfig.samlet_verdi_bak_aksjene is None
