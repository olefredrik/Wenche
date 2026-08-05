"""
Regnskapsperioden, inkludert forlenget første regnskapsår (rskl. § 1-7).

Perioden var hardkodet til 1. januar til 31. desember i regnskapsåret. Et selskap stiftet sent
på året kan etter § 1-7 andre ledd ha et forlenget første regnskapsår på inntil 18 måneder, og
rapporterte da en periode som ikke var den faktiske, både til Brønnøysund og Skatteetaten.
Tallene var riktige, men periodeangivelsen var feil, og den er en del av det signerte
regnskapet.

Testene dekker:
  1. Standardoppførselen er uendret: uten oppgitt periode er den fortsatt hele kalenderåret.
  2. En oppgitt periode kommer med i begge innsendingene.
  3. Valideringen fanger perioder som ikke kan tolkes entydig av mottakerne.
  4. Aksjonærregisteroppgaven bruker eksakt stiftelsesdato når den er kjent.
"""

from datetime import date
from xml.etree.ElementTree import fromstring

import pytest

from wenche import aarsregnskap as ar
from wenche.aksjonaerregister import generer_hovedskjema_xml
from wenche.brg_xml import generer_hovedskjema
from wenche.models import (
    Aksjonaer,
    Aksjonaerregisteroppgave,
    Balanse,
    Egenkapital,
    EgenkapitalOgGjeld,
    Eiendeler,
    Omloepmidler,
    Resultatregnskap,
    Selskap,
)
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon

_NS = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"
_PARTSNUMMER = 123456789


def _regnskap(eksempel_selskap, **kwargs):
    from wenche.models import Aarsregnskap

    return Aarsregnskap(
        selskap=eksempel_selskap,
        regnskapsaar=kwargs.pop("regnskapsaar", 2026),
        resultatregnskap=Resultatregnskap(),
        balanse=Balanse(
            eiendeler=Eiendeler(omloepmidler=Omloepmidler(bankinnskudd=30000)),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000)
            ),
        ),
        **kwargs,
    )


class TestPeriodeEgenskaper:
    def test_standard_er_hele_kalenderaaret(self, eksempel_selskap):
        r = _regnskap(eksempel_selskap, regnskapsaar=2025)
        assert r.periode_start == date(2025, 1, 1)
        assert r.periode_slutt == date(2025, 12, 31)
        assert r.periode_maaneder == 12

    def test_forlenget_foerste_aar(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsaar=2026,
            regnskapsstart=date(2025, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        assert r.periode_start == date(2025, 11, 20)
        assert r.periode_maaneder == 14

    def test_maks_18_maaneder_er_grensen(self, eksempel_selskap):
        # 1. juli til 31. desember året etter er 18 måneder, altså på grensen.
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2025, 7, 1),
            regnskapsslutt=date(2026, 12, 31),
        )
        assert r.periode_maaneder == 18
        assert ar.valider(r) == []


class TestConfigLesing:
    def _config(self, **ekstra):
        return {
            "selskap": {
                "navn": "Test AS",
                "org_nummer": "123456789",
                "daglig_leder": "D L",
                "styreleder": "D L",
                "forretningsadresse": "Vei 1, 0001 OSLO",
                "stiftelsesaar": 2025,
                "aksjekapital": 30000,
                **ekstra.pop("selskap", {}),
            },
            "regnskapsaar": 2026,
            "resultatregnskap": {},
            "balanse": {},
            **ekstra,
        }

    def test_leser_periode_fra_iso_streng(self):
        # Skjemaet sender datoer som streng.
        r = ar.les_config(
            self._config(regnskapsstart="2025-11-20", regnskapsslutt="2026-12-31")
        )
        assert r.periode_start == date(2025, 11, 20)
        assert r.periode_slutt == date(2026, 12, 31)

    def test_leser_periode_fra_yaml_dato(self):
        # YAML tolker en naken YYYY-MM-DD som date.
        r = ar.les_config(
            self._config(regnskapsstart=date(2025, 11, 20), regnskapsslutt=date(2026, 12, 31))
        )
        assert r.periode_start == date(2025, 11, 20)

    def test_tomme_datofelt_gir_kalenderaaret(self):
        r = ar.les_config(self._config(regnskapsstart="", regnskapsslutt=None))
        assert r.periode_start == date(2026, 1, 1)
        assert r.periode_slutt == date(2026, 12, 31)

    def test_leser_stiftelsesdato(self):
        r = ar.les_config(self._config(selskap={"stiftelsesdato": "2025-11-20"}))
        assert r.selskap.stiftelsesdato == date(2025, 11, 20)

    def test_ugyldig_dato_gir_lesbar_feil(self):
        with pytest.raises(ValueError, match="ÅÅÅÅ-MM-DD"):
            ar.les_config(self._config(regnskapsstart="20. november"))


class TestValidering:
    def test_snudd_periode_avvises(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2026, 12, 31),
            regnskapsslutt=date(2026, 1, 1),
        )
        feil = ar.valider(r)
        assert any("slutter før den starter" in f for f in feil)

    def test_over_18_maaneder_avvises(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2025, 6, 1),
            regnskapsslutt=date(2026, 12, 31),
        )
        feil = ar.valider(r)
        assert any("18 måneder" in f and "19 måneder" in f for f in feil)

    def test_slutt_maa_vaere_31_desember(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2026, 1, 1),
            regnskapsslutt=date(2026, 6, 30),
        )
        assert any("31. desember" in f for f in ar.valider(r))

    def test_regnskapsaar_maa_vaere_sluttaaret(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsaar=2025,
            regnskapsstart=date(2025, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        assert any("året perioden avsluttes" in f for f in ar.valider(r))

    def test_vanlig_aar_validerer_uten_periodefeil(self, eksempel_regnskap):
        assert ar.valider(eksempel_regnskap) == []


class TestAdvarsler:
    def test_advarer_naar_start_avviker_fra_stiftelsesdato(self, eksempel_selskap):
        eksempel_selskap.stiftelsesdato = date(2025, 11, 20)
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2025, 12, 1),
            regnskapsslutt=date(2026, 12, 31),
        )
        assert any("ble stiftet" in a for a in ar.advarsler(r))

    def test_advarer_om_forlenget_periode(self, eksempel_selskap):
        # Perioden er lovlig og godtas av Skatteetaten (verifisert mot tt02), men den er
        # sjelden nok at brukeren bør se hvilket inntektsår den fastsettes i.
        eksempel_selskap.stiftelsesdato = date(2025, 11, 20)
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2025, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        adv = ar.advarsler(r)
        assert any("forlenget første regnskapsår" in a for a in adv)
        assert any("inntektsår 2026" in a for a in adv)

    def test_ingen_periodeadvarsel_for_vanlig_aar(self, eksempel_regnskap):
        adv = ar.advarsler(eksempel_regnskap)
        assert not any("Regnskapsperioden" in a for a in adv)


class TestXmlUtgang:
    def test_brg_hovedskjema_bruker_perioden(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2025, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        xml = generer_hovedskjema(r).decode("utf-8")
        assert '<regnskapsstart orid="17103">2025-11-20</regnskapsstart>' in xml
        assert '<regnskapsslutt orid="17104">2026-12-31</regnskapsslutt>' in xml
        assert '<regnskapsaar orid="17102">2026</regnskapsaar>' in xml

    def test_brg_hovedskjema_uendret_for_vanlig_aar(self, eksempel_regnskap):
        xml = generer_hovedskjema(eksempel_regnskap).decode("utf-8")
        assert '<regnskapsstart orid="17103">2025-01-01</regnskapsstart>' in xml
        assert '<regnskapsslutt orid="17104">2025-12-31</regnskapsslutt>' in xml

    def test_naeringsspesifikasjon_bruker_perioden(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2025, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        root = fromstring(generer_naeringsspesifikasjon(r, _PARTSNUMMER).decode("utf-8"))
        periode = root.find(f"{_NS}virksomhet/{_NS}regnskapsperiode")
        assert periode.find(f"{_NS}start/{_NS}dato").text == "2025-11-20"
        assert periode.find(f"{_NS}slutt/{_NS}dato").text == "2026-12-31"


class TestAksjonaerregisterStiftelsesdato:
    def _oppgave(self, selskap):
        return Aksjonaerregisteroppgave(
            selskap=selskap,
            regnskapsaar=2025,
            aksjonaerer=[
                Aksjonaer(
                    navn="Ola Nordmann",
                    fodselsnummer="24847799354",
                    antall_aksjer=300,
                    aksjeklasse="ordinære",
                    utbytte_utbetalt=0,
                    innbetalt_kapital_per_aksje=100,
                )
            ],
        )

    def test_bruker_eksakt_stiftelsesdato(self, eksempel_selskap):
        eksempel_selskap.stiftelsesaar = 2025
        eksempel_selskap.stiftelsesdato = date(2025, 11, 20)
        xml = generer_hovedskjema_xml(self._oppgave(eksempel_selskap)).decode("utf-8")
        assert "2025-11-20T00:00:00" in xml
        assert "2025-01-01T00:00:00" not in xml

    def test_faller_tilbake_paa_1_januar_uten_dato(self, eksempel_selskap):
        eksempel_selskap.stiftelsesaar = 2025
        eksempel_selskap.stiftelsesdato = None
        xml = generer_hovedskjema_xml(self._oppgave(eksempel_selskap)).decode("utf-8")
        assert "2025-01-01T00:00:00" in xml


class TestFjoraarsadvarselVedForlengetAar:
    """
    Et forlenget første regnskapsår har ikke noe fjorår, selv om stiftelsesåret er lavere
    enn regnskapsåret. § 6-6-advarselen ba derfor om sammenligningstall som ikke finnes.
    """

    def test_ingen_fjoraarsadvarsel_naar_selskapet_er_stiftet_i_perioden(self, eksempel_selskap):
        eksempel_selskap.stiftelsesaar = 2024
        eksempel_selskap.stiftelsesdato = date(2024, 11, 20)
        r = _regnskap(
            eksempel_selskap,
            regnskapsaar=2025,
            regnskapsstart=date(2024, 11, 20),
            regnskapsslutt=date(2025, 12, 31),
        )
        assert not any("sammenligningstall" in a for a in ar.advarsler(r))

    def test_fjoraarsadvarsel_staar_for_et_vanlig_aar(self, eksempel_selskap):
        # Kontroll: et etablert selskap uten fjorårstall skal fortsatt varsles.
        eksempel_selskap.stiftelsesaar = 2020
        eksempel_selskap.stiftelsesdato = date(2020, 3, 14)
        r = _regnskap(eksempel_selskap, regnskapsaar=2025)
        assert any("sammenligningstall" in a for a in ar.advarsler(r))
