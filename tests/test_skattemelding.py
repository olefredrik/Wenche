"""
Tester for skattemeldingsgenerering i wenche/skattemelding.py.
Verifiserer skattberegning, fritaksmetoden og fremførbart underskudd.
"""

import math

from wenche.models import SkattemeldingKonfig
from wenche.skattemelding import generer


def test_generer_returnerer_streng(eksempel_regnskap):
    konfig = SkattemeldingKonfig()
    tekst = generer(eksempel_regnskap, konfig)
    assert isinstance(tekst, str)
    assert len(tekst) > 0


def test_inneholder_selskapsnavn(eksempel_regnskap):
    konfig = SkattemeldingKonfig()
    tekst = generer(eksempel_regnskap, konfig)
    assert "Test Holding AS" in tekst


def test_inneholder_orgnummer(eksempel_regnskap):
    konfig = SkattemeldingKonfig()
    tekst = generer(eksempel_regnskap, konfig)
    assert "123456789" in tekst


def _skatt_linje(tekst: str) -> str:
    """Returnerer innholdet i skattelinjen, strippet for whitespace."""
    return next(l.strip() for l in tekst.splitlines() if "Beregnet skatt" in l)


def test_ingen_skatt_ved_underskudd(eksempel_regnskap):
    """Selskap med kun driftskostnader og ingen inntekter skal ikke betale skatt."""
    konfig = SkattemeldingKonfig()
    tekst = generer(eksempel_regnskap, konfig)
    assert _skatt_linje(tekst).endswith("0 kr")


def test_fritaksmetoden_under_90_prosent_eierandel(regnskap_med_utbytte):
    """Ved eierandel < 90 % gjelder sjablonregelen: 3 % er skattepliktig."""
    konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_datterselskap=50)
    tekst = generer(regnskap_med_utbytte, konfig)
    assert "fritatt, 97 %" in tekst
    assert "sjablonregel, 3 %" in tekst


def test_fritaksmetoden_over_90_prosent_eierandel(regnskap_med_utbytte):
    """Ved eierandel ≥ 90 % er hele utbyttet fritatt — ingen sjablonregel."""
    konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_datterselskap=100)
    tekst = generer(regnskap_med_utbytte, konfig)
    assert "100 % fritatt" in tekst
    assert "sjablonregel" not in tekst


def test_fritaksmetoden_under_90_skattepliktig_beloep(regnskap_med_utbytte):
    """3 % av 100 000 kr utbytte = 3 000 kr skattepliktig; skatt = 0 (inntekt = -2 500)."""
    # Driftsresultat = -5500, skattepliktig utbytte = ceil(100000 * 0.03) = 3000
    # Skattepliktig inntekt = -5500 + 3000 = -2500 → ingen skatt
    konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_datterselskap=50)
    tekst = generer(regnskap_med_utbytte, konfig)
    assert _skatt_linje(tekst).endswith("0 kr")


def test_fritaksmetoden_over_90_ingen_skatt(regnskap_med_utbytte):
    """Ved eierandel ≥ 90 % og negativt driftsresultat skal det ikke beregnes skatt."""
    # Driftsresultat = -5500, skattepliktig utbytte = 0 → ingen skatt
    konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_datterselskap=100)
    tekst = generer(regnskap_med_utbytte, konfig)
    assert _skatt_linje(tekst).endswith("0 kr")


def test_uten_fritaksmetoden_full_skatt(regnskap_med_utbytte):
    """Uten fritaksmetoden er hele utbyttet skattepliktig."""
    konfig = SkattemeldingKonfig(anvend_fritaksmetoden=False)
    tekst = generer(regnskap_med_utbytte, konfig)
    # Skattepliktig = -5500 + 100000 = 94500; skatt = ceil(94500 * 0.22) = 20790
    # _nok() bruker tusenskilletegn (mellomrom): "20 790 kr"
    assert "20 790 kr" in tekst
    assert "fritatt" not in tekst


def test_fremfoerbart_underskudd_reduserer_skatt(regnskap_med_utbytte):
    """Fremførbart underskudd skal trekkes fra skattepliktig inntekt."""
    konfig = SkattemeldingKonfig(
        anvend_fritaksmetoden=False,
        underskudd_til_fremfoering=94500,  # Dekker hele inntekten
    )
    tekst = generer(regnskap_med_utbytte, konfig)
    assert _skatt_linje(tekst).endswith("0 kr")
    assert "fremf. underskudd" in tekst


def test_balansekontroll_ok(eksempel_regnskap):
    konfig = SkattemeldingKonfig()
    tekst = generer(eksempel_regnskap, konfig)
    assert "Balansekontroll: OK" in tekst


def test_sammenligningstall_vises_naar_tilgjengelig(eksempel_regnskap):
    """Når foregående år er fylt inn, skal sammenligningstall vises i rapporten."""
    from wenche.models import Resultatregnskap, Driftskostnader
    eksempel_regnskap.foregaaende_aar_resultat = Resultatregnskap(
        driftskostnader=Driftskostnader(andre_driftskostnader=4000)
    )
    konfig = SkattemeldingKonfig()
    tekst = generer(eksempel_regnskap, konfig)
    assert "SAMMENLIGNINGSTALL" in tekst
    assert "§ 6-6" in tekst


def test_advarsel_naar_sammenligningstall_mangler(eksempel_regnskap):
    """Når foregående år ikke er fylt inn, skal rapporten advare om manglende sammenligningstall."""
    konfig = SkattemeldingKonfig()
    tekst = generer(eksempel_regnskap, konfig)
    assert "Sammenligningstall" in tekst
    assert "§ 6-6" in tekst


def test_balansekontroll_advarsel():
    """Ubalansert balanse skal gi advarsel i rapporten."""
    from wenche.models import (
        Aarsregnskap, Balanse, Eiendeler, Omloepmidler, EgenkapitalOgGjeld,
        Egenkapital, Resultatregnskap, Selskap,
    )
    selskap = Selskap(
        navn="Ubalansert AS", org_nummer="999999999",
        daglig_leder="Test", styreleder="Test",
        forretningsadresse="Testveien 1", stiftelsesaar=2020, aksjekapital=10000,
    )
    regnskap = Aarsregnskap(
        selskap=selskap,
        regnskapsaar=2025,
        resultatregnskap=Resultatregnskap(),
        balanse=Balanse(
            eiendeler=Eiendeler(omloepmidler=Omloepmidler(bankinnskudd=50000)),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=10000),
            ),
        ),
    )
    konfig = SkattemeldingKonfig()
    tekst = generer(regnskap, konfig)
    assert "ADVARSEL" in tekst
