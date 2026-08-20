"""
Skattemeldingen krever stiftelsesår og aksjekapital som tall, i motsetning til årsregnskapet
som tåler tomme verdier. En SAF-T-import bærer ikke disse feltene (issue #130), så en tom verdi
er et reelt og vanlig tilfelle. Før ble det en naken int('')/float('')-500 i de lokale
byggestiene (dry-run og dokumenter). Nå skal det bli et rettbart avvik med lesbar melding.
"""
import pytest

from wenche import aarsregnskap as ar
from wenche import skattemelding as sm
from wenche.innsending import valider_skattemelding


def _config(stiftelsesaar=2018, aksjekapital=30000, dropp=None):
    selskap = {
        "navn": "Galatea Invest AS", "org_nummer": "922236771",
        "daglig_leder": "D L", "styreleder": "S L",
        "forretningsadresse": "Vei 1, 0001 OSLO",
        "stiftelsesaar": stiftelsesaar, "aksjekapital": aksjekapital,
    }
    if dropp:
        del selskap[dropp]
    return {"selskap": selskap, "regnskapsaar": 2025,
            "resultatregnskap": {"driftsinntekter": {}, "driftskostnader": {}, "finansposter": {}},
            "balanse": {"eiendeler": {"anleggsmidler": {}, "omloepmidler": {}},
                        "egenkapital_og_gjeld": {"egenkapital": {}, "langsiktig_gjeld": {},
                                                 "kortsiktig_gjeld": {}}}}


@pytest.mark.parametrize("verdi", ["", None])
def test_tom_stiftelsesaar_gir_lesbart_avvik_ikke_crash(verdi):
    feil = sm.valider_selskap(_config(stiftelsesaar=verdi))
    assert any("Stiftelsesår" in f for f in feil)


@pytest.mark.parametrize("verdi", ["", None])
def test_tom_aksjekapital_gir_lesbart_avvik(verdi):
    feil = sm.valider_selskap(_config(aksjekapital=verdi))
    assert any("Aksjekapital" in f for f in feil)


def test_manglende_felt_fanges():
    feil = sm.valider_selskap(_config(dropp="stiftelsesaar"))
    assert any("Stiftelsesår" in f for f in feil)


def test_komplett_selskap_gir_ingen_avvik():
    assert sm.valider_selskap(_config()) == []


def test_les_config_tom_verdi_gir_lesbar_valueerror_ikke_rå_int():
    # Defense-in-depth for direkte/CLI-kallere: en tom verdi skal gi en forklarende melding,
    # ikke "invalid literal for int() with base 10: ''".
    with pytest.raises(ValueError, match="Stiftelsesår"):
        sm.les_config(_config(stiftelsesaar=""))


def test_aarsregnskap_tåler_samme_tomme_verdi():
    # Bekrefter divergensen som forklarer hvorfor bare skattemelding feilet for brukeren:
    # årsregnskapet leser de samme feltene uten konvertering og krasjer ikke.
    ar.les_config(_config(stiftelsesaar=""))  # skal ikke kaste


def test_valider_skattemelding_returnerer_feil_liste():
    # Samme kontrakt som valider_aarsregnskap: dry-run-svaret bærer en feil-liste som
    # bekreft-modalen viser som rettbare punkter (ok=False), ikke en kastet 500.
    svar = valider_skattemelding(_config(stiftelsesaar=""))
    assert svar["ok"] is False
    assert any("Stiftelsesår" in f for f in svar["feil"])


def test_valider_skattemelding_ok_for_komplett_config():
    svar = valider_skattemelding(_config())
    assert svar["ok"] is True
    assert svar["feil"] == []
    assert svar["regnskapsaar"] == 2025


def test_leser_eksakte_naeringsspesifikasjonsposter():
    config = _config()
    config["naeringsspesifikasjon"] = {
        "poster": [
            {"kategori": "annenDriftskostnad", "kode": "7700", "beloep": 0},
        ]
    }
    _, konfig = sm.les_config(config)
    assert len(konfig.naeringsspesifikasjonsposter) == 1
    assert konfig.naeringsspesifikasjonsposter[0].kode == "7700"


def test_avviser_duplikate_naeringsspesifikasjonsposter():
    config = _config()
    config["naeringsspesifikasjon"] = {
        "poster": [
            {"kategori": "kortsiktigGjeld", "kode": "2740", "beloep": 1},
            {"kategori": "kortsiktigGjeld", "kode": "2740", "beloep": 2},
        ]
    }
    with pytest.raises(ValueError, match="duplikat"):
        sm.les_config(config)


@pytest.mark.parametrize(
    ("post", "melding"),
    [
        ({"kategori": "ukjent", "kode": "7700", "beloep": 1}, "ukjent kategori"),
        (
            {"kategori": "annenDriftskostnad", "kode": "77", "beloep": 1},
            "firesifret kode",
        ),
        (
            {"kategori": "kortsiktigGjeld", "kode": "2740", "beloep": -1},
            "positivt balansebeløp",
        ),
    ],
)
def test_avviser_ugyldige_naeringsspesifikasjonsposter(post, melding):
    config = _config()
    config["naeringsspesifikasjon"] = {"poster": [post]}
    with pytest.raises(ValueError, match=melding):
        sm.les_config(config)
