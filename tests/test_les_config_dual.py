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


# ---------------------------------------------------------------------------
# Leser mot leser
# ---------------------------------------------------------------------------
#
# Testene over sammenligner hver leser med seg selv (dict mot fil). Det fanger ikke at de
# tre leserne driver fra hverandre, og det er nettopp det som har skjedd to ganger: et nytt
# felt ble lagt til i én leser, og de andre fortsatte å bruke standardverdien i stillhet.
# Symptomene var feil regnskapsperiode i næringsspesifikasjonen (#156) og 1. januar som
# stiftelsestidspunkt i RF-1086. Configen under fyller derfor ut ALLE valgfrie felt: et felt
# som bare én leser plukker opp, faller igjennom her.

# Selskapet er stiftet i oktober i regnskapsåret, så stiftelsesår, stiftelsesdato og
# periode henger sammen. Et kalenderår ville gjort de tre periodefeltene like uansett.
_CFG_ALLE_FELT = copy.deepcopy(_CFG)
_CFG_ALLE_FELT["selskap"]["stiftelsesaar"] = 2024
_CFG_ALLE_FELT["selskap"]["stiftelsesdato"] = "2024-10-24"
_CFG_ALLE_FELT["selskap"]["tinginnskudd_ved_stiftelse"] = 25000
_CFG_ALLE_FELT["balanse"]["egenkapital_og_gjeld"]["kortsiktig_gjeld"]["avsatt_utbytte"] = 0
_CFG_ALLE_FELT["regnskapsstart"] = "2024-10-24"
_CFG_ALLE_FELT["regnskapsslutt"] = "2024-12-31"

# Eneste feltet som med hensikt bare leses av én leser: e-postadressen er påkrevd for
# RF-1086 og ubrukt i de to andre skjemaene.
_KUN_AKSJONAERREGISTER = {"kontakt_epost"}


def test_aarsregnskap_og_skattemelding_leser_identisk():
    """Skattemeldingen har sin egen config-leser, og den må gi samme Aarsregnskap."""
    fra_aarsregnskap = ar.les_config(copy.deepcopy(_CFG_ALLE_FELT))
    fra_skattemelding, _ = sm.les_config(copy.deepcopy(_CFG_ALLE_FELT))
    assert fra_aarsregnskap == fra_skattemelding


def test_alle_lesere_bygger_samme_selskap():
    """Alle tre leserne må plukke opp de samme selskapsfeltene fra samme config."""
    import dataclasses

    from wenche.models import Selskap

    selskaper = {
        "aarsregnskap": ar.les_config(copy.deepcopy(_CFG_ALLE_FELT)).selskap,
        "skattemelding": sm.les_config(copy.deepcopy(_CFG_ALLE_FELT))[0].selskap,
        "aksjonaerregister": akr.les_config(copy.deepcopy(_CFG_ALLE_FELT)).selskap,
    }
    felles = [
        f.name for f in dataclasses.fields(Selskap) if f.name not in _KUN_AKSJONAERREGISTER
    ]
    for felt in felles:
        verdier = {navn: getattr(s, felt) for navn, s in selskaper.items()}
        assert len(set(verdier.values())) == 1, f"leserne er uenige om {felt}: {verdier}"
        assert verdier["aarsregnskap"] == _forventet_selskapsfelt(felt), felt


def _forventet_selskapsfelt(felt: str):
    """Forventet verdi fra _CFG_ALLE_FELT, så en leser ikke kan «bli enig» om en tom verdi."""
    from datetime import date

    forventet = {
        "navn": "Delt Test AS",
        "org_nummer": "314273818",
        "daglig_leder": "Ola Nordmann",
        "styreleder": "Ola Nordmann",
        "forretningsadresse": "Testveien 1, 0001 Oslo",
        "stiftelsesaar": 2024,
        "aksjekapital": 30000,
        "stiftelsesdato": date(2024, 10, 24),
        "tinginnskudd_ved_stiftelse": 25000.0,
    }
    assert felt in forventet, f"nytt felt i Selskap: bestem om {felt} skal leses av alle"
    return forventet[felt]


def test_regnskapsperioden_naar_alle_veier():
    """Perioden må overleve begge veiene inn til XML-byggingen, ikke bare årsregnskapets."""
    from datetime import date

    for les in (
        lambda c: ar.les_config(c),
        lambda c: sm.les_config(c)[0],
    ):
        regnskap = les(copy.deepcopy(_CFG_ALLE_FELT))
        assert regnskap.periode_start == date(2024, 10, 24)
        assert regnskap.periode_slutt == date(2024, 12, 31)
        assert regnskap.er_foerste_regnskapsaar


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
