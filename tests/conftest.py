"""
Delte testfiksturer for Wenche-testsuiten.
"""

import pytest

from wenche.models import (
    Aarsregnskap,
    Anleggsmidler,
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
    Selskap,
    SkattemeldingKonfig,
)


@pytest.fixture
def eksempel_selskap():
    return Selskap(
        navn="Test Holding AS",
        org_nummer="123456789",
        daglig_leder="Ola Nordmann",
        styreleder="Ola Nordmann",
        forretningsadresse="Testveien 1, 0001 Oslo",
        stiftelsesaar=2020,
        aksjekapital=30000,
    )


@pytest.fixture
def eksempel_regnskap(eksempel_selskap):
    """
    Enkelt holdingselskap med kun driftskostnader og aksjer i datterselskap.
    Balansen er i balanse: eiendeler = EK + gjeld = 101 200 kr.
    """
    return Aarsregnskap(
        selskap=eksempel_selskap,
        regnskapsaar=2025,
        resultatregnskap=Resultatregnskap(
            driftsinntekter=Driftsinntekter(),
            driftskostnader=Driftskostnader(andre_driftskostnader=5500),
            finansposter=Finansposter(),
        ),
        balanse=Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(bankinnskudd=1200),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(
                    aksjekapital=30000,
                    annen_egenkapital=-34300,
                ),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=105500),
            ),
        ),
    )


@pytest.fixture
def regnskap_med_utbytte(eksempel_selskap):
    """Holdingselskap som har mottatt utbytte fra datterselskap."""
    return Aarsregnskap(
        selskap=eksempel_selskap,
        regnskapsaar=2025,
        resultatregnskap=Resultatregnskap(
            driftsinntekter=Driftsinntekter(),
            driftskostnader=Driftskostnader(andre_driftskostnader=5500),
            finansposter=Finansposter(utbytte_fra_datterselskap=100000),
        ),
        balanse=Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=200000),
                omloepmidler=Omloepmidler(bankinnskudd=95700),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(
                    aksjekapital=30000,
                    annen_egenkapital=60200,
                ),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=205500),
            ),
        ),
    )
