"""
Regnskapsperioden, inkludert kort første regnskapsår (rskl. § 1-7).

Et selskap stiftet i løpet av året har et første regnskapsår fra stiftelsesdatoen til 31.
desember, og den perioden skal rapporteres både til Brønnøysund og Skatteetaten.

Forlenget første regnskapsår (§ 1-7 andre ledd) støttes ikke. Det spenner over to kalenderår,
mens skattemeldingen leveres per inntektsår. Wenche sendte før én skattemelding for hele
perioden og ingen for stiftelsesåret (issue #193).

Testene dekker:
  1. Standardoppførselen er uendret: uten oppgitt periode er den fortsatt hele kalenderåret.
  2. En oppgitt periode kommer med i begge innsendingene.
  3. Valideringen fanger perioder som ikke kan tolkes entydig av mottakerne, og perioder over
     to kalenderår.
  4. Skattemeldingen stoppes før noe hentes eller sendes når perioden er ugyldig.
  5. Aksjonærregisteroppgaven bruker eksakt stiftelsesdato når den er kjent.
"""

import copy
from datetime import date
from unittest.mock import Mock, patch
from xml.etree.ElementTree import fromstring

import pytest
import yaml
from click.testing import CliRunner

from wenche import aarsregnskap as ar
from wenche import innsending as tjeneste
from wenche.aksjonaerregister import generer_hovedskjema_xml
from wenche.brg_xml import generer_hovedskjema
from wenche.cli import main
from wenche.models import (
    Aksjonaer,
    Aksjonaerregisteroppgave,
    Balanse,
    Egenkapital,
    EgenkapitalOgGjeld,
    Eiendeler,
    Omloepmidler,
    Resultatregnskap,
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
            egenkapital_og_gjeld=EgenkapitalOgGjeld(egenkapital=Egenkapital(aksjekapital=30000)),
        ),
        **kwargs,
    )


class TestPeriodeEgenskaper:
    def test_standard_er_hele_kalenderaaret(self, eksempel_selskap):
        r = _regnskap(eksempel_selskap, regnskapsaar=2025)
        assert r.periode_start == date(2025, 1, 1)
        assert r.periode_slutt == date(2025, 12, 31)

    def test_kort_foerste_aar(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsaar=2026,
            regnskapsstart=date(2026, 11, 20),
        )
        assert r.periode_start == date(2026, 11, 20)
        assert r.periode_slutt == date(2026, 12, 31)


class TestErFoersteRegnskapsaar:
    """Definisjonen deles av fjorårsadvarselen og egenkapitalavstemmingen."""

    def test_stiftet_tidligere_aar_er_ikke_foerste(self, eksempel_selskap):
        # stiftelsesaar 2020 i fixturen
        assert not _regnskap(eksempel_selskap, regnskapsaar=2025).er_foerste_regnskapsaar

    def test_stiftelsesaar_lik_regnskapsaar_er_foerste(self, eksempel_selskap):
        eksempel_selskap.stiftelsesaar = 2025
        assert _regnskap(eksempel_selskap, regnskapsaar=2025).er_foerste_regnskapsaar

    def test_stiftelsesdato_utenfor_perioden_teller_ikke(self, eksempel_selskap):
        eksempel_selskap.stiftelsesdato = date(2020, 3, 14)
        assert not _regnskap(eksempel_selskap, regnskapsaar=2025).er_foerste_regnskapsaar


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
        r = ar.les_config(self._config(regnskapsstart="2025-11-20", regnskapsslutt="2026-12-31"))
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

    def test_iso_datetime_godtas(self):
        # Et JS Date serialiseres til JSON som "2025-11-20T00:00:00.000Z". SPA-en lager
        # ikke lenger slike (den parser YAML med CORE_SCHEMA), men lagrede configer fra
        # før kan bære formen, og da skal innsendingen gå, ikke feile på formatet.
        r = ar.les_config(
            self._config(
                regnskapsstart="2025-11-20T00:00:00.000Z",
                regnskapsslutt="2026-12-31T00:00:00.000Z",
                selskap={"stiftelsesdato": "2025-11-20T00:00:00Z"},
            )
        )
        assert r.periode_start == date(2025, 11, 20)
        assert r.periode_slutt == date(2026, 12, 31)
        assert r.selskap.stiftelsesdato == date(2025, 11, 20)

    def test_tull_med_t_i_seg_avvises_fortsatt(self):
        with pytest.raises(ValueError, match="ÅÅÅÅ-MM-DD"):
            ar.les_config(self._config(regnskapsstart="TULLT"))


class TestValidering:
    def test_snudd_periode_avvises(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2026, 12, 31),
            regnskapsslutt=date(2026, 1, 1),
        )
        feil = ar.valider(r)
        assert any("slutter før den starter" in f for f in feil)

    def test_forlenget_foerste_aar_avvises(self, eksempel_selskap):
        # 14 måneder er lovlig etter rskl. § 1-7 andre ledd, men skattemeldingen leveres per
        # kalenderår, og Wenche bygger den fra samme periode (issue #193).
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2025, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        feil = ar.valider(r)
        assert any("to kalenderår" in f and "kort første regnskapsår" in f for f in feil)

    def test_kort_foerste_aar_godtas(self, eksempel_selskap):
        eksempel_selskap.stiftelsesaar = 2026
        eksempel_selskap.stiftelsesdato = date(2026, 11, 20)
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2026, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        assert ar.valider(r) == []

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
            regnskapsstart=date(2026, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        assert any("året perioden avsluttes" in f for f in ar.valider(r))

    def test_vanlig_aar_validerer_uten_periodefeil(self, eksempel_regnskap):
        assert ar.valider(eksempel_regnskap) == []


class TestAdvarsler:
    def test_advarer_naar_start_avviker_fra_stiftelsesdato(self, eksempel_selskap):
        eksempel_selskap.stiftelsesdato = date(2026, 11, 20)
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2026, 12, 1),
            regnskapsslutt=date(2026, 12, 31),
        )
        assert any("ble stiftet" in a for a in ar.advarsler(r))

    def test_ingen_periodeadvarsel_for_vanlig_aar(self, eksempel_regnskap):
        adv = ar.advarsler(eksempel_regnskap)
        assert not any("Regnskapsperioden" in a for a in adv)


class TestXmlUtgang:
    def test_brg_hovedskjema_bruker_perioden(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2026, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        xml = generer_hovedskjema(r).decode("utf-8")
        assert '<regnskapsstart orid="17103">2026-11-20</regnskapsstart>' in xml
        assert '<regnskapsslutt orid="17104">2026-12-31</regnskapsslutt>' in xml
        assert '<regnskapsaar orid="17102">2026</regnskapsaar>' in xml

    def test_brg_hovedskjema_uendret_for_vanlig_aar(self, eksempel_regnskap):
        xml = generer_hovedskjema(eksempel_regnskap).decode("utf-8")
        assert '<regnskapsstart orid="17103">2025-01-01</regnskapsstart>' in xml
        assert '<regnskapsslutt orid="17104">2025-12-31</regnskapsslutt>' in xml

    def test_naeringsspesifikasjon_bruker_perioden(self, eksempel_selskap):
        r = _regnskap(
            eksempel_selskap,
            regnskapsstart=date(2026, 11, 20),
            regnskapsslutt=date(2026, 12, 31),
        )
        root = fromstring(generer_naeringsspesifikasjon(r, _PARTSNUMMER).decode("utf-8"))
        periode = root.find(f"{_NS}virksomhet/{_NS}regnskapsperiode")
        assert periode.find(f"{_NS}start/{_NS}dato").text == "2026-11-20"
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


class TestFjoraarsadvarselVedKortFoersteAar:
    """Et kort første regnskapsår har ikke noe fjorår, så § 6-6-advarselen skal ikke slå inn."""

    def test_ingen_fjoraarsadvarsel_i_stiftelsesaaret(self, eksempel_selskap):
        eksempel_selskap.stiftelsesaar = 2025
        eksempel_selskap.stiftelsesdato = date(2025, 11, 20)
        r = _regnskap(
            eksempel_selskap,
            regnskapsaar=2025,
            regnskapsstart=date(2025, 11, 20),
        )
        assert not any("sammenligningstall" in a for a in ar.advarsler(r))

    def test_fjoraarsadvarsel_staar_for_et_vanlig_aar(self, eksempel_selskap):
        # Kontroll: et etablert selskap uten fjorårstall skal fortsatt varsles.
        eksempel_selskap.stiftelsesaar = 2020
        eksempel_selskap.stiftelsesdato = date(2020, 3, 14)
        r = _regnskap(eksempel_selskap, regnskapsaar=2025)
        assert any("sammenligningstall" in a for a in ar.advarsler(r))


class TestSkattemeldingStopperForlengetAar:
    """
    Skattemeldingen kjørte ikke årsregnskapets validering, så en periode over to kalenderår gikk
    rett til Skatteetaten. Alle veier inn stopper den nå før noe hentes eller sendes.
    """

    _CONFIG = {
        "selskap": {
            "navn": "Syntetisk Holding AS",
            "org_nummer": "123456789",
            "daglig_leder": "Test Person",
            "styreleder": "Test Person",
            "forretningsadresse": "Testveien 1, 0001 Oslo",
            "stiftelsesaar": 2025,
            "stiftelsesdato": "2025-11-20",
            "aksjekapital": 30000,
        },
        "regnskapsaar": 2026,
        "regnskapsstart": "2025-11-20",
        "regnskapsslutt": "2026-12-31",
        "resultatregnskap": {},
        "balanse": {
            "eiendeler": {"omloepmidler": {"bankinnskudd": 30000}},
            "egenkapital_og_gjeld": {"egenkapital": {"aksjekapital": 30000}},
        },
        "skattemelding": {"underskudd_til_fremfoering": 0, "formuesverdi_aksjer": 0},
    }

    def test_validering_i_webflyten_avviser(self):
        svar = tjeneste.valider_skattemelding(copy.deepcopy(self._CONFIG))
        assert not svar["ok"]
        assert any("to kalenderår" in f for f in svar["feil"])

    def test_innsending_avvises_uten_kontakt_med_skatteetaten(self):
        skd = Mock()
        with pytest.raises(tjeneste.InnsendingValideringsfeil):
            tjeneste.send_skattemelding(
                copy.deepcopy(self._CONFIG), skd, "altinn-token", orgnr="123456789"
            )
        skd.hent_forhåndsutfylt_med_id.assert_not_called()
        skd.send.assert_not_called()

    @pytest.mark.parametrize("kommando", ["send-skattemelding", "valider-skattemelding"])
    def test_cli_avviser_foer_innlogging(self, kommando, tmp_path, monkeypatch):
        monkeypatch.delenv("WENCHE_ENV", raising=False)
        config_fil = tmp_path / "config.yaml"
        config_fil.write_text(yaml.safe_dump(self._CONFIG, allow_unicode=True))
        with patch("wenche.auth.get_skd_skattemelding_tokens") as tokens:
            result = CliRunner().invoke(main, [kommando, "--config", str(config_fil)])
        assert result.exit_code == 1
        assert "to kalenderår" in result.output
        tokens.assert_not_called()
