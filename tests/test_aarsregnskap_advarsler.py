"""
Ikke-blokkerende advarsler i aarsregnskap.advarsler().

Advarslene skal fange forhold som ikke gjør innsendingen ugyldig, men som
ofte tyder på feil i tallene: utbytte uten dekning i fri egenkapital, og
manglende sammenligningstall for fjoråret (rskl. § 6-6) for et etablert
selskap. De skal IKKE blokkere innsending (det er valider() sin jobb).
"""

from dataclasses import replace

from wenche.aarsregnskap import advarsler
from wenche.models import (
    Balanse,
    Egenkapital,
    EgenkapitalOgGjeld,
    Eiendeler,
    Omloepmidler,
)


def _med_ek(regnskap, egenkapital):
    """Returnerer en kopi av regnskapet med ny egenkapital i balansen."""
    ny_ekg = replace(regnskap.balanse.egenkapital_og_gjeld, egenkapital=egenkapital)
    ny_balanse = replace(regnskap.balanse, egenkapital_og_gjeld=ny_ekg)
    return replace(regnskap, balanse=ny_balanse)


def _med_fjoraar(regnskap):
    """Gir regnskapet ikke-tomme sammenligningstall, så fjorår-advarselen ikke utløses."""
    return replace(
        regnskap,
        foregaaende_aar_balanse=Balanse(
            eiendeler=Eiendeler(omloepmidler=Omloepmidler(bankinnskudd=1000)),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=1000)
            ),
        ),
    )


def test_ingen_advarsel_uten_utbytte(eksempel_regnskap):
    # Negativ fri egenkapital, men intet utbytte (og fjorår oppgitt) → ingen advarsel.
    assert eksempel_regnskap.utbytte_utbetalt == 0
    assert advarsler(_med_fjoraar(eksempel_regnskap)) == []


def test_advarsel_utbytte_uten_fri_egenkapital(eksempel_regnskap):
    # Akkumulert underskudd (negativ fri EK) + utbetalt utbytte → advarsel.
    regnskap = replace(_med_fjoraar(eksempel_regnskap), utbytte_utbetalt=10000)
    adv = advarsler(regnskap)
    assert len(adv) == 1
    assert "fri egenkapital" in adv[0]
    assert "§ 8-1" in adv[0]


def test_ingen_advarsel_utbytte_med_dekning(regnskap_med_utbytte):
    # Positiv annen egenkapital (60 200) gir dekning for utbytte.
    regnskap = replace(_med_fjoraar(regnskap_med_utbytte), utbytte_utbetalt=50000)
    assert advarsler(regnskap) == []


def test_overkursfond_teller_som_fri_egenkapital(eksempel_regnskap):
    # Overkursfond er fri egenkapital og dekker utbyttet selv om annen EK er negativ.
    ek = Egenkapital(aksjekapital=30000, overkursfond=50000, annen_egenkapital=-34300)
    regnskap = replace(_med_ek(_med_fjoraar(eksempel_regnskap), ek), utbytte_utbetalt=10000)
    assert advarsler(regnskap) == []


def test_advarsel_manglende_fjoraarstall(eksempel_regnskap):
    # Stiftet 2020, regnskap 2025, tomt fjorår → advarsel om sammenligningstall (§ 6-6).
    assert eksempel_regnskap.selskap.stiftelsesaar < eksempel_regnskap.regnskapsaar
    adv = advarsler(eksempel_regnskap)
    assert any("§ 6-6" in a for a in adv)
    assert any("sammenligningstall" in a for a in adv)


def test_ingen_fjoraar_advarsel_for_nystiftet(eksempel_regnskap):
    # Stiftet samme år som regnskapet → ingen sammenligningstall påkrevd, ingen advarsel.
    nystiftet = replace(
        eksempel_regnskap,
        selskap=replace(eksempel_regnskap.selskap, stiftelsesaar=eksempel_regnskap.regnskapsaar),
    )
    assert advarsler(nystiftet) == []
