"""
Utbytte fra andre aksjer, altså fra selskaper som verken er datterselskap eller tilknyttet
selskap (typisk en eierandel under 20 %).

Før dette hadde Wenche bare utbytte_fra_datterselskap, og alt mottatt utbytte ble sendt
til Brønnøysund som «Inntekt på investering i datterselskap og tilknyttet selskap». Skatten
var riktig, men årsregnskapet viste utbyttet på feil linje.

Testene dekker:
  1. Skatteberegningen: utbytte fra andre aksjer får alltid 3 %-sjablonen, også når
     utbyttet fra datterselskapet er helt fritatt.
  2. Årsregnskapet: egen linje (andreInvesteringer), og gevinst ved realisasjon av aksjer
     på linjen for annen finansinntekt.
  3. Næringsspesifikasjonen: samme kode (8090) og samme permanente forskjeller som før,
     regnet av samlet utbytte.
  4. Advarselen om utbytte fra datterselskap uten aksjer i datterselskap.
  5. Bakoverkompatibilitet: uten feltet er alt som før.
"""

from xml.etree.ElementTree import fromstring

import pytest

from wenche import aarsregnskap as ar
from wenche import skattemelding as sm
from wenche.brg_xml import generer_underskjema
from wenche.models import (
    Aarsregnskap,
    Anleggsmidler,
    Balanse,
    Egenkapital,
    EgenkapitalOgGjeld,
    Eiendeler,
    Finansposter,
    Omloepmidler,
    Resultatregnskap,
    SkattemeldingKonfig,
)
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skatteberegning import beregn_skatt

_NS = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"
_PARTSNUMMER = 123456789


def _regnskap(
    selskap, finansposter: Finansposter, aksjer_i_datterselskap: float = 0.0
) -> Aarsregnskap:
    """Holdingselskap uten skattekostnad der bankinnskuddet tar opp årsresultatet."""
    r = Resultatregnskap(finansposter=finansposter)
    return Aarsregnskap(
        selskap=selskap,
        regnskapsaar=2025,
        resultatregnskap=r,
        balanse=Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(
                    aksjer_i_datterselskap=aksjer_i_datterselskap, andre_aksjer=50000
                ),
                omloepmidler=Omloepmidler(bankinnskudd=30000 + r.aarsresultat),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(
                    aksjekapital=80000 + aksjer_i_datterselskap,
                    annen_egenkapital=r.aarsresultat,
                ),
            ),
        ),
    )


def _ns_root(regnskap, konfig=None):
    return fromstring(
        generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER, konfig).decode("utf-8")
    )


def _forskjeller(root) -> dict[str, float]:
    forskjell = root.find(f"{_NS}forskjellMellomRegnskapsmessigOgSkattemessigVerdi")
    if forskjell is None:
        return {}
    return {
        p.find(f"{_NS}id").text: float(p.find(f"{_NS}beloep/{_NS}beloep/{_NS}beloep").text)
        for p in forskjell.findall(f"{_NS}permanentForskjell")
    }


class TestSkatteberegning:
    def test_andre_aksjer_gir_sjablon(self):
        r = Resultatregnskap(finansposter=Finansposter(utbytte_fra_andre_aksjer=20000))
        b = beregn_skatt(r, SkattemeldingKonfig(eierandel_for_fritaksmetoden=10))
        assert b.utbytte == 20000
        assert b.skattepliktig_utbytte == 600
        assert b.fritatt_utbytte == 19400

    def test_sjablon_paa_andre_aksjer_selv_om_datterselskapet_er_fullt_fritatt(self):
        # Eierandelen over 90 % gjelder datterselskapet. Utbyttet fra andre aksjer kan aldri
        # komme fra et konsernselskap, så det får 3 %-sjablonen uansett.
        r = Resultatregnskap(
            finansposter=Finansposter(
                utbytte_fra_datterselskap=100000, utbytte_fra_andre_aksjer=20000
            )
        )
        b = beregn_skatt(r, SkattemeldingKonfig(eierandel_for_fritaksmetoden=100))
        assert b.utbytte == 120000
        assert b.skattepliktig_utbytte == 600
        assert b.fritatt_utbytte == 119400

    def test_sjablon_paa_samlet_utbytte_ved_lav_eierandel(self):
        r = Resultatregnskap(
            finansposter=Finansposter(
                utbytte_fra_datterselskap=100000, utbytte_fra_andre_aksjer=20000
            )
        )
        b = beregn_skatt(r, SkattemeldingKonfig(eierandel_for_fritaksmetoden=60))
        assert b.skattepliktig_utbytte == 3600

    def test_uten_fritaksmetoden_skattlegges_alt(self):
        r = Resultatregnskap(finansposter=Finansposter(utbytte_fra_andre_aksjer=20000))
        b = beregn_skatt(r, SkattemeldingKonfig(anvend_fritaksmetoden=False))
        assert b.skattepliktig_utbytte == 20000
        assert b.skattepliktig_inntekt_brutto == 20000

    def test_fullt_fritak_uendret_uten_andre_aksjer(self):
        r = Resultatregnskap(finansposter=Finansposter(utbytte_fra_datterselskap=100000))
        b = beregn_skatt(r, SkattemeldingKonfig(eierandel_for_fritaksmetoden=100))
        assert b.skattepliktig_utbytte == 0
        assert b.fritatt_utbytte == 100000


class TestAarsregnskap:
    def test_egen_linje_for_andre_aksjer(self, eksempel_selskap):
        regnskap = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_andre_aksjer=20000))
        xml = generer_underskjema(regnskap).decode()
        assert "<andreInvesteringer" in xml
        assert '<beskrivelse orid="29005">Utbytte fra andre aksjer</beskrivelse>' in xml
        assert '<aarets orid="27936">20000</aarets>' in xml
        assert "investeringDatterforetakTilknyttetSelskap" not in xml
        assert '<aarets orid="153">20000</aarets>' in xml  # sum finansinntekter

    def test_rekkefoelgen_foelger_skjemaet(self, eksempel_selskap):
        # Underskjemaet er en XSD-sekvens: datterselskap, andre investeringer, annen
        # renteinntekt, annen finansinntekt, sum.
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(
                utbytte_fra_datterselskap=10000,
                utbytte_fra_andre_aksjer=20000,
                andre_finansinntekter=300,
                gevinst_ved_realisasjon_av_aksjer=4000,
            ),
            aksjer_i_datterselskap=40000,
        )
        xml = generer_underskjema(regnskap).decode()
        rekkefoelge = [
            "<investeringDatterforetakTilknyttetSelskap",
            "<andreInvesteringer",
            "<annenRenteinntekt",
            "<annenFinansinntekt",
            "<sumFinansinntekter",
        ]
        posisjoner = [xml.index(tag) for tag in rekkefoelge]
        assert posisjoner == sorted(posisjoner)
        assert '<aarets orid="153">34300</aarets>' in xml

    def test_ingen_linje_uten_utbytte_fra_andre_aksjer(self, eksempel_selskap):
        regnskap = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_datterselskap=20000))
        assert "andreInvesteringer" not in generer_underskjema(regnskap).decode()


class TestNaeringsspesifikasjon:
    def test_samme_kode_og_forskjeller_av_samlet_utbytte(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(utbytte_fra_datterselskap=100000, utbytte_fra_andre_aksjer=20000),
            aksjer_i_datterselskap=40000,
        )
        root = _ns_root(regnskap, SkattemeldingKonfig(eierandel_for_fritaksmetoden=100))
        koder = {
            el.find(f"{_NS}id").text: el.find(f"{_NS}beloep/{_NS}beloep/{_NS}beloep").text
            for el in root.findall(f"{_NS}resultatregnskap/{_NS}finansinntekt/*")
        }
        assert koder == {"8090": "120000.00"}
        assert _forskjeller(root) == {
            "tilbakefoeringAvInntektsfoertUtbytte": 120000.0,
            "skattepliktigDelAvUtbytterOgUtdelinger": 600.0,
        }

    def test_validerer_mot_xsd(self, eksempel_selskap):
        etree = pytest.importorskip("lxml.etree")
        from tests.test_xsd_validering import _XSD_DIR

        regnskap = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_andre_aksjer=20000))
        schema = etree.XMLSchema(
            etree.parse(str(_XSD_DIR / "naeringsspesifikasjon_v6_ekstern.xsd"))
        )
        doc = etree.fromstring(generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER))
        assert schema.validate(doc), schema.error_log


class TestAdvarsel:
    def _har_advarsel(self, regnskap) -> bool:
        return any("Utbytte fra andre aksjer" in a for a in ar.advarsler(regnskap))

    def test_utbytte_fra_datterselskap_uten_aksjer_i_datterselskap(self, eksempel_selskap):
        regnskap = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_datterselskap=20000))
        assert self._har_advarsel(regnskap)

    def test_ingen_advarsel_med_aksjer_i_datterselskap(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(utbytte_fra_datterselskap=20000),
            aksjer_i_datterselskap=40000,
        )
        assert not self._har_advarsel(regnskap)

    def test_ingen_advarsel_for_tilknyttet_selskap(self, eksempel_selskap):
        # 20-50 %: tilknyttet selskap. Aksjene står under andre aksjer, men utbyttet hører
        # hjemme på linjen for datterselskap og tilknyttet selskap.
        regnskap = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_datterselskap=20000))
        regnskap.eierandel_for_utbytte = 25
        assert not self._har_advarsel(regnskap)

    def test_advarsel_ved_eierandel_under_20(self, eksempel_selskap):
        regnskap = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_datterselskap=20000))
        regnskap.eierandel_for_utbytte = 10
        assert self._har_advarsel(regnskap)

    def test_eierandelen_leses_fra_skattemelding_seksjonen(self):
        cfg = {
            "selskap": {
                "navn": "X AS", "org_nummer": "123456789", "daglig_leder": "A",
                "styreleder": "A", "forretningsadresse": "Gate 1", "stiftelsesaar": 2022,
                "aksjekapital": 30000,
            },
            "regnskapsaar": 2025,
            "resultatregnskap": {},
            "balanse": {},
        }
        assert ar.les_config(cfg).eierandel_for_utbytte is None
        cfg["skattemelding"] = {"eierandel_for_fritaksmetoden": "25,5"}
        assert ar.les_config(cfg).eierandel_for_utbytte == 25.5

    def test_ingen_advarsel_naar_utbyttet_staar_paa_riktig_linje(self, eksempel_selskap):
        regnskap = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_andre_aksjer=20000))
        assert not self._har_advarsel(regnskap)


class TestBakoverkompatibilitet:
    def test_config_uten_feltet_leses_som_null(self):
        r = ar._les_resultat({"finansposter": {"utbytte_fra_datterselskap": 5000}})
        assert r.finansposter.utbytte_fra_andre_aksjer == 0
        assert r.finansposter.sum_utbytte == 5000

    def test_config_med_feltet_leses(self):
        r = ar._les_resultat({"finansposter": {"utbytte_fra_andre_aksjer": "20000"}})
        assert r.finansposter.utbytte_fra_andre_aksjer == 20000
        assert r.finansposter.sum_inntekter == 20000

    def test_rapporten_viser_linjen_bare_ved_behov(self, eksempel_selskap):
        uten = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_datterselskap=20000))
        med = _regnskap(eksempel_selskap, Finansposter(utbytte_fra_andre_aksjer=20000))
        konfig = SkattemeldingKonfig(eierandel_for_fritaksmetoden=10)
        assert "Utbytte fra andre aksjer" not in sm.generer(uten, konfig)
        rapport = sm.generer(med, konfig)
        assert "Utbytte fra andre aksjer" in rapport
        assert "Utbytte (sjablonregel, 3 %)" in rapport
