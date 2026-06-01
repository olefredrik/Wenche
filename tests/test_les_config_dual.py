"""
Den delte grensen mellom standalone (CLI/NiceGUI) og den hostede appen:
`les_config` må godta BÅDE en filsti (standalone leser config.yaml) OG en allerede parset
dict (hosted sender config i request-body), og gi IDENTISK resultat. Brekker noen denne
ekvivalensen, brekker enten standalone eller webapp i stillhet, derav disse regresjonsvaktene.
"""
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
