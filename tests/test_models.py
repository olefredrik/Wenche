"""
Tester for datamodellene i wenche/models.py.
Verifiserer at sum-egenskaper, balansesjekk og resultatberegning er korrekte.
"""

from wenche.models import (
    Balanse,
    Driftsinntekter,
    Driftskostnader,
    Egenkapital,
    EgenkapitalOgGjeld,
    Eiendeler,
    Finansposter,
    KortsiktigGjeld,
    LangsiktigGjeld,
    Omloepmidler,
    Resultatregnskap,
    Anleggsmidler,
)


def test_driftsinntekter_sum():
    di = Driftsinntekter(salgsinntekter=100000, andre_driftsinntekter=20000)
    assert di.sum == 120000


def test_driftskostnader_sum():
    dk = Driftskostnader(loennskostnader=50000, avskrivninger=10000, andre_driftskostnader=5000)
    assert dk.sum == 65000


def test_finansposter_sum():
    fp = Finansposter(
        utbytte_fra_datterselskap=100000,
        andre_finansinntekter=5000,
        rentekostnader=3000,
        andre_finanskostnader=1000,
    )
    assert fp.sum_inntekter == 105000
    assert fp.sum_kostnader == 4000


def test_resultatregnskap_driftsresultat(eksempel_regnskap):
    r = eksempel_regnskap.resultatregnskap
    assert r.driftsresultat == -5500  # 0 inntekter - 5500 kostnader


def test_resultatregnskap_resultat_foer_skatt(eksempel_regnskap):
    r = eksempel_regnskap.resultatregnskap
    assert r.resultat_foer_skatt == -5500


def test_balanse_er_i_balanse(eksempel_regnskap):
    assert eksempel_regnskap.balanse.er_i_balanse()


def test_balanse_differanse_er_null(eksempel_regnskap):
    assert eksempel_regnskap.balanse.differanse() == 0


def test_balanse_ikke_i_balanse():
    balanse = Balanse(
        eiendeler=Eiendeler(
            omloepmidler=Omloepmidler(bankinnskudd=100000),
        ),
        egenkapital_og_gjeld=EgenkapitalOgGjeld(
            egenkapital=Egenkapital(aksjekapital=90000),
        ),
    )
    assert not balanse.er_i_balanse()
    assert balanse.differanse() == 10000


def test_egenkapital_negativ_annen_ek():
    """Annen egenkapital kan være negativ ved akkumulert underskudd."""
    ek = Egenkapital(aksjekapital=30000, annen_egenkapital=-34300)
    assert ek.sum == -4300


def test_eiendeler_sum(eksempel_regnskap):
    ei = eksempel_regnskap.balanse.eiendeler
    assert ei.sum == 101200  # 100000 aksjer + 1200 bankinnskudd


def test_egenkapital_og_gjeld_sum(eksempel_regnskap):
    ekg = eksempel_regnskap.balanse.egenkapital_og_gjeld
    assert ekg.sum == 101200  # 30000 - 34300 + 105500
