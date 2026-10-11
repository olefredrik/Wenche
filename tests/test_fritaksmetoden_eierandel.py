"""
Grensen for fullt utbyttefritak etter fritaksmetoden (issue #181).

Utbytte er helt fritatt bare når mottakeren eier MER enn ni tideler av aksjene (sktl. § 2-38
sjette ledd, jf. konsernvilkåret i § 10-4). Nøyaktig 90 % gir 3 %-sjablonen. Før regnet Wenche
90 % som fullt fritatt, og eierandelen ble kuttet til heltall, så 90,5 % ville blitt 90 % og
feilaktig skattlagt etter rettelsen. Nå leses eierandelen som desimaltall, med komma eller
punktum, og verdier utenfor 0-100 gir en lesbar feil i stedet for en stille beregning.
"""
import math

import pytest

from wenche import skattemelding as sm
from wenche.models import Finansposter, Resultatregnskap, SkattemeldingKonfig
from wenche.skatteberegning import beregn_skatt

UTBYTTE = 100000
SJABLON = math.ceil(UTBYTTE * 0.03)  # 3 000 kr skattepliktig


def _resultat() -> Resultatregnskap:
    return Resultatregnskap(finansposter=Finansposter(utbytte_fra_datterselskap=UTBYTTE))


def _skattepliktig_utbytte(eierandel) -> float:
    konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_for_fritaksmetoden=eierandel)
    return beregn_skatt(_resultat(), konfig).skattepliktig_utbytte


@pytest.mark.parametrize(
    "eierandel, forventet",
    [
        (50, SJABLON),
        (89.99, SJABLON),
        (90, SJABLON),  # nøyaktig ni tideler er ikke «mer enn»
        (90.0, SJABLON),
        (90.01, 0),
        (90.5, 0),
        (91, 0),
        (100, 0),
    ],
)
def test_grensen_for_fullt_fritak_er_mer_enn_90_prosent(eierandel, forventet):
    assert _skattepliktig_utbytte(eierandel) == forventet


def test_visningen_bruker_sjablonen_ved_noyaktig_90_prosent(regnskap_med_utbytte):
    konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_for_fritaksmetoden=90)
    tekst = sm.generer(regnskap_med_utbytte, konfig)
    assert "sjablonregel, 3 %" in tekst
    assert "100 % fritatt" not in tekst


def _config(eierandel) -> dict:
    return {
        "resultatregnskap": {"finansposter": {"utbytte_fra_datterselskap": UTBYTTE}},
        "skattemelding": {"anvend_fritaksmetoden": True, "eierandel_for_fritaksmetoden": eierandel},
    }


@pytest.mark.parametrize(
    "verdi, forventet",
    [
        (None, 100.0),
        ("", 100.0),
        ("  ", 100.0),
        (90, 90.0),
        (90.5, 90.5),
        ("90.5", 90.5),
        ("90,5", 90.5),  # komma i config.yaml blir en streng i YAML
        (" 90,5 ", 90.5),
        ("100", 100.0),
        (0, 0.0),
    ],
)
def test_leseren_tar_desimaler_med_komma_og_punktum(verdi, forventet):
    konfig = sm._les_skattekonfig(_config(verdi))
    assert konfig.eierandel_for_fritaksmetoden == forventet


def test_desimal_over_90_kuttes_ikke_til_heltall():
    # Regresjonsvakt: int(float("90,5")) ville gitt 90 og dermed 3 %-sjablon.
    beregning, _ = sm.beregn_skatt_fra_config(_config("90,5"))
    assert beregning.skattepliktig_utbytte == 0
    beregning, _ = sm.beregn_skatt_fra_config(_config(90))
    assert beregning.skattepliktig_utbytte == SJABLON


@pytest.mark.parametrize(
    "verdi, melding",
    [
        ("abc", "må være et tall"),
        ("90,5,1", "må være et tall"),
        (150, "mellom 0 og 100"),
        (-1, "mellom 0 og 100"),
        (100.01, "mellom 0 og 100"),
        ("nan", "mellom 0 og 100"),
        ("inf", "mellom 0 og 100"),
    ],
)
def test_ugyldig_eierandel_gir_lesbar_feil(verdi, melding):
    with pytest.raises(ValueError, match=melding):
        sm._les_skattekonfig(_config(verdi))
    feil = sm.valider_skattekonfig(_config(verdi))
    assert len(feil) == 1
    assert feil[0].startswith("Eierandel for fritaksmetoden")
    assert melding in feil[0]


def test_gyldig_eierandel_gir_ingen_avvik():
    assert sm.valider_skattekonfig(_config("90,5")) == []
    assert sm.valider_skattekonfig({}) == []


def test_valider_selskap_tar_med_eierandelen():
    # valider_selskap er porten alle byggestier går gjennom før skattemeldingen bygges.
    feil = sm.valider_selskap(_config(150))
    assert any("Eierandel for fritaksmetoden" in f for f in feil)
