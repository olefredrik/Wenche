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
    """
    Gir regnskapet sammenligningstall som henger sammen med året, så verken fjorårsadvarselen
    eller advarselen om uforklart egenkapitalendring utløses: fjorårets egenkapital er årets
    minus årsresultatet, pluss utbytte utbetalt i året. Kalles sist, etter at egenkapital og
    utbytte er satt.
    """
    ek = regnskap.balanse.egenkapital_og_gjeld.egenkapital
    inngaaende = (
        ek.sum - regnskap.resultatregnskap.aarsresultat + regnskap.utbytte_utbetalt
    )
    return replace(
        regnskap,
        foregaaende_aar_balanse=Balanse(
            eiendeler=Eiendeler(omloepmidler=Omloepmidler(bankinnskudd=inngaaende)),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(
                    aksjekapital=ek.aksjekapital,
                    overkursfond=ek.overkursfond,
                    annen_egenkapital=inngaaende - ek.aksjekapital - ek.overkursfond,
                )
            ),
        ),
    )


def test_ingen_advarsel_uten_utbytte(eksempel_regnskap):
    # Negativ fri egenkapital, men intet utbytte (og fjorår oppgitt) → ingen advarsel.
    assert eksempel_regnskap.utbytte_utbetalt == 0
    assert advarsler(_med_fjoraar(eksempel_regnskap)) == []


def test_advarsel_utbytte_uten_fri_egenkapital(eksempel_regnskap):
    # Akkumulert underskudd (negativ fri EK) + utbetalt utbytte → advarsel.
    regnskap = _med_fjoraar(replace(eksempel_regnskap, utbytte_utbetalt=10000))
    adv = advarsler(regnskap)
    assert len(adv) == 1
    assert "fri egenkapital" in adv[0]
    assert "§ 8-1" in adv[0]


def test_ingen_advarsel_utbytte_med_dekning(regnskap_med_utbytte):
    # Positiv annen egenkapital (60 200) gir dekning for utbytte.
    regnskap = _med_fjoraar(replace(regnskap_med_utbytte, utbytte_utbetalt=50000))
    assert advarsler(regnskap) == []


def test_overkursfond_teller_som_fri_egenkapital(eksempel_regnskap):
    # Overkursfond er fri egenkapital og dekker utbyttet selv om annen EK er negativ.
    ek = Egenkapital(aksjekapital=30000, overkursfond=50000, annen_egenkapital=-34300)
    regnskap = _med_fjoraar(replace(_med_ek(eksempel_regnskap, ek), utbytte_utbetalt=10000))
    assert advarsler(regnskap) == []


def test_advarsel_manglende_fjoraarstall(eksempel_regnskap):
    # Stiftet 2020, regnskap 2025, tomt fjorår → advarsel om sammenligningstall (§ 6-6).
    assert eksempel_regnskap.selskap.stiftelsesaar < eksempel_regnskap.regnskapsaar
    adv = advarsler(eksempel_regnskap)
    assert any("§ 6-6" in a for a in adv)
    assert any("sammenligningstall" in a for a in adv)


def test_ingen_fjoraar_advarsel_for_nystiftet(eksempel_regnskap):
    # Stiftet samme år som regnskapet → ingen sammenligningstall påkrevd, ingen advarsel.
    # Fellesfixturen har annen egenkapital -34 300 mot årsresultat -5 500, så som første år
    # gir den advarselen om uforklart egenkapitalendring. Den testes for seg nedenfor.
    nystiftet = replace(
        eksempel_regnskap,
        selskap=replace(eksempel_regnskap.selskap, stiftelsesaar=eksempel_regnskap.regnskapsaar),
    )
    assert not any("sammenligningstall" in a for a in advarsler(nystiftet))


def test_avsatt_utbytte_over_fri_egenkapital_gir_advarsel(eksempel_regnskap):
    """
    En avsetning er en utdeling etter aksjeloven § 8-1, og er allerede trukket fra annen
    egenkapital. Uten dette gikk en avsetning som tømmer fri egenkapital stille gjennom,
    siden den gamle sjekken bare så på utbetalt utbytte.
    """
    ekg = eksempel_regnskap.balanse.egenkapital_og_gjeld
    ekg.egenkapital.overkursfond = 0
    ekg.egenkapital.annen_egenkapital = -5000
    ekg.kortsiktig_gjeld.avsatt_utbytte = 50000

    meldinger = advarsler(eksempel_regnskap)

    assert any("avsatt utbytte" in m for m in meldinger)
    assert any("§ 8-1" in m for m in meldinger)


class TestUforklartEgenkapitalendring:
    """
    Endringen i egenkapitalen som årsresultat, innskudd og utbytte ikke forklarer, sendes som
    «annen endring i egenkapital», og Skatteetaten reagerer først etter innsending (#191).
    Eksempelet fra issuet: et utbytte i et felt Wenche ikke kjenner, forsvinner fra resultatet
    mens balansen beholder det.
    """

    @staticmethod
    def _uforklart(regnskap):
        return [a for a in advarsler(regnskap) if "mer enn årsresultatet" in a]

    @staticmethod
    def _annen_ek(regnskap, delta):
        ek = regnskap.balanse.egenkapital_og_gjeld.egenkapital
        return _med_ek(regnskap, replace(ek, annen_egenkapital=ek.annen_egenkapital + delta))

    def test_sammenhengende_aar_gir_ingen_advarsel(self, eksempel_regnskap):
        assert self._uforklart(_med_fjoraar(eksempel_regnskap)) == []

    def test_uforklart_oekning_gir_advarsel(self, eksempel_regnskap):
        regnskap = self._annen_ek(_med_fjoraar(eksempel_regnskap), 20000)
        adv = self._uforklart(regnskap)
        assert len(adv) == 1
        assert "økt 20,000 NOK" in adv[0]
        assert "annen endring i egenkapital" in adv[0]

    def test_uforklart_nedgang_gir_advarsel(self, eksempel_regnskap):
        regnskap = self._annen_ek(_med_fjoraar(eksempel_regnskap), -5000)
        adv = self._uforklart(regnskap)
        assert len(adv) == 1
        assert "falt 5,000 NOK" in adv[0]

    def test_beloepet_er_det_som_sendes_til_skatteetaten(self, eksempel_regnskap):
        from wenche.naeringsspesifikasjon_xml import egenkapitalavstemming

        regnskap = self._annen_ek(_med_fjoraar(eksempel_regnskap), 20000)
        _, _, tillegg, _ = egenkapitalavstemming(regnskap)
        assert ("annenPositivEndringIEgenkapital", 20000) in tillegg

    def test_avrunding_under_en_krone_gir_ingen_advarsel(self, eksempel_regnskap):
        regnskap = self._annen_ek(_med_fjoraar(eksempel_regnskap), 1)
        assert self._uforklart(regnskap) == []

    def test_tomt_fjoraar_gir_bare_fjoraarsadvarselen(self, eksempel_regnskap):
        # Hele egenkapitalen er da uforklart, og fjorårsadvarselen sier allerede hvorfor.
        adv = advarsler(eksempel_regnskap)
        assert any("sammenligningstall" in a for a in adv)
        assert self._uforklart(eksempel_regnskap) == []

    def test_foerste_aar_forklares_av_innskudd_og_resultat(self, eksempel_regnskap):
        nystiftet = replace(
            eksempel_regnskap,
            selskap=replace(eksempel_regnskap.selskap, stiftelsesaar=eksempel_regnskap.regnskapsaar),
        )
        ek = Egenkapital(
            aksjekapital=30000,
            annen_egenkapital=nystiftet.resultatregnskap.aarsresultat,
        )
        assert self._uforklart(_med_ek(nystiftet, ek)) == []

    def test_foerste_aar_med_uforklart_egenkapital_gir_advarsel(self, eksempel_regnskap):
        # Fellesfixturen: annen egenkapital -34 300 mot årsresultat -5 500.
        nystiftet = replace(
            eksempel_regnskap,
            selskap=replace(eksempel_regnskap.selskap, stiftelsesaar=eksempel_regnskap.regnskapsaar),
        )
        adv = self._uforklart(nystiftet)
        assert len(adv) == 1
        assert "falt 28,800 NOK" in adv[0]
