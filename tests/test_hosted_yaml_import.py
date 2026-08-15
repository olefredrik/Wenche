"""
Ende-til-ende for config.yaml-importen i skjemaet: YAML → JSON → API.

Importknappen parser YAML i nettleseren og sender resultatet som JSON til API-et. Det ledet
ett stykke tid til en feil ingen test dekket: js-yaml sitt standardskjema gjorde en naken
`2025-10-24` om til et JS Date, som JSON-serialiseres til `2025-10-24T00:00:00.000Z`. Den
formen avvises av <input type="date"> (feltet ble blankt) og av `_dato` i backend, så en
importert regnskapsperiode stoppet innsendingen med en formatfeil om en dato brukeren aldri
skrev.

Testene her går ikke gjennom nettleseren, men gjennom nøyaktig de to formene YAML-parsing kan
produsere, mot de ekte endepunktene. Det holder både den rettede stien og bakoverkompatibilitet
med allerede lagrede configer på plass.
"""

import importlib

import pytest
from fastapi.testclient import TestClient

from hosted.api.auth import lag_invite_token

_INVITE_SECRET = "test-invite-secret"
_ORG = "314273818"


@pytest.fixture
def klient(monkeypatch):
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("HOSTED_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HOSTED_INVITE_SECRET", _INVITE_SECRET)
    from hosted.api import config

    config.settings.cache_clear()
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    with TestClient(main_mod.app) as k:
        k.post("/api/auth/invite", json={"token": lag_invite_token(_ORG)})
        yield k
    config.settings.cache_clear()


def _config(regnskapsstart, regnskapsslutt, stiftelsesdato):
    """Nystiftet selskap med forkortet første regnskapsår, balansert."""
    return {
        "selskap": {
            "navn": "Test AS", "org_nummer": _ORG, "daglig_leder": "D L",
            "styreleder": "D L", "forretningsadresse": "Vei 1, 0001 OSLO",
            "stiftelsesaar": 2025, "stiftelsesdato": stiftelsesdato,
            "aksjekapital": 30000, "kontakt_epost": "a@b.no",
        },
        "regnskapsaar": 2025,
        "regnskapsstart": regnskapsstart,
        "regnskapsslutt": regnskapsslutt,
        "resultatregnskap": {
            "driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
            "driftskostnader": {"loennskostnader": 0, "avskrivninger": 0,
                                "andre_driftskostnader": 0},
            "finansposter": {"utbytte_fra_datterselskap": 0, "andre_finansinntekter": 0,
                             "rentekostnader": 0, "andre_finanskostnader": 0},
            "skattekostnad": 0,
        },
        "balanse": {
            "eiendeler": {
                "anleggsmidler": {"aksjer_i_datterselskap": 0, "andre_aksjer": 0,
                                  "langsiktige_fordringer": 0},
                "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000},
            },
            "egenkapital_og_gjeld": {
                "egenkapital": {"aksjekapital": 30000, "overkursfond": 0,
                                "annen_egenkapital": 0},
                "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
                "kortsiktig_gjeld": {"leverandoergjeld": 0, "betalbar_skatt": 0,
                                     "skyldige_offentlige_avgifter": 0,
                                     "annen_kortsiktig_gjeld": 0},
            },
        },
        "skattemelding": {"underskudd_til_fremfoering": 0, "formuesverdi_aksjer": 0},
    }


# Formen skjemaet sender etter rettelsen (js-yaml med CORE_SCHEMA gir ren tekst).
_REN_DATO = _config("2025-10-24", "2025-12-31", "2025-10-24")

# Formen en allerede lagret config kan bære: JS Date serialisert til JSON.
_ISO_DATETIME = _config(
    "2025-10-24T00:00:00.000Z", "2025-12-31T00:00:00.000Z", "2025-10-24T00:00:00.000Z"
)


@pytest.mark.parametrize("navn,cfg", [("ren dato", _REN_DATO), ("iso-datetime", _ISO_DATETIME)])
@pytest.mark.parametrize("dokument", ["aarsregnskap", "skattemelding"])
def test_dokument_genereres(klient, navn, cfg, dokument):
    r = klient.post(f"/api/dokumenter/{dokument}", json=cfg)
    assert r.status_code == 200, f"{navn}/{dokument}: {r.status_code} {r.text[:300]}"


@pytest.mark.parametrize("navn,cfg", [("ren dato", _REN_DATO), ("iso-datetime", _ISO_DATETIME)])
def test_perioden_naar_frem_til_naeringsspesifikasjonen(klient, navn, cfg):
    """Begge formene skal gi den faktiske perioden, ikke hele kalenderåret."""
    from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
    from wenche import skattemelding as sm

    regnskap, _ = sm.les_config(cfg)
    assert regnskap.periode_start.isoformat() == "2025-10-24", navn
    assert regnskap.periode_slutt.isoformat() == "2025-12-31", navn
    assert regnskap.selskap.stiftelsesdato.isoformat() == "2025-10-24", navn

    ns = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"
    from xml.etree.ElementTree import fromstring

    root = fromstring(generer_naeringsspesifikasjon(regnskap, 123456789))
    periode = root.find(f"{ns}virksomhet/{ns}regnskapsperiode")
    assert periode.findtext(f"{ns}start/{ns}dato") == "2025-10-24", navn


def test_begge_formene_gir_samme_resultat():
    """Datoformen skal ikke kunne påvirke innholdet i innsendingen."""
    from wenche import skattemelding as sm

    ren, _ = sm.les_config(_REN_DATO)
    iso, _ = sm.les_config(_ISO_DATETIME)
    assert ren == iso
