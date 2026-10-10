"""
Gevinst og tap ved realisasjon av aksjer under fritaksmetoden (sktl. § 2-38).

Før dette gjaldt fritaksmetoden i Wenche bare utbytte. En aksjegevinst måtte føres som
andre finansinntekter og ble skattlagt fullt, og et aksjetap ble trukket fra, selv om
gevinsten er skattefri og tapet ikke fradragsberettiget for aksjer innenfor
fritaksmetoden. 3 %-sjablonen gjelder bare utbytte, ikke gevinst.

Testene dekker:
  1. Skatteberegningen fritar gevinsten og nekter fradrag for tapet, uansett eierandel.
  2. Næringsspesifikasjonen fører 8074/8174 og forklarer differansen med permanente
     forskjeller fra kodelisten 2025_permanentForskjellstype.
  3. SAF-T-importen leser 8074/8174 til de nye feltene og advarer.
  4. Bakoverkompatibilitet: uten feltene er alt som før, og årsregnskapet til
     Brønnøysund er uendret av at beløpet er skilt ut.
"""

import re
from xml.etree.ElementTree import fromstring

import pytest

from wenche import aarsregnskap as ar
from wenche import skattemelding as sm
from wenche.brg_xml import generer_underskjema
from wenche.models import (
    Aarsregnskap,
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
from wenche.saft import importer_bytes
from wenche.skatteberegning import beregn_skatt

from tests.test_saft import _konto, _saft_xml

_NS = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"
_PARTSNUMMER = 123456789

_GEVINST_KODE = "regnskapsmessigGevinstVedRealisasjonAvFinansielleInstrumenter"
_TAP_KODE = "regnskapsmessigTapVedRealisasjonAvFinansielleInstrumenter"


def _regnskap(selskap, finansposter: Finansposter) -> Aarsregnskap:
    """Holdingselskap uten skattekostnad der bankinnskuddet tar opp årsresultatet."""
    r = Resultatregnskap(finansposter=finansposter)
    return Aarsregnskap(
        selskap=selskap,
        regnskapsaar=2025,
        resultatregnskap=r,
        balanse=Balanse(
            eiendeler=Eiendeler(
                omloepmidler=Omloepmidler(bankinnskudd=30000 + r.aarsresultat),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(
                    aksjekapital=30000, annen_egenkapital=r.aarsresultat
                ),
            ),
        ),
    )


def _uten_rad_id(xml: bytes) -> bytes:
    """altinnRowId er en tilfeldig UUID per linje, og skal ikke telle i sammenligningen."""
    return re.sub(rb'altinnRowId="[^"]*"', b"", xml)


def _root(regnskap, konfig=None):
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


def _skattemessig(root) -> float:
    el = root.find(
        f"{_NS}beregnetNaeringsinntekt/{_NS}skattemessigResultat/{_NS}beloep/{_NS}beloep"
    )
    return float(el.text) if el is not None else 0.0


def _aarsresultat(root) -> float:
    return float(
        root.find(f"{_NS}resultatregnskap/{_NS}aarsresultat/{_NS}beloep/{_NS}beloep").text
    )


def _resultatkoder(root) -> dict[str, str]:
    """{kode: beløp} for finansinntekt- og finanskostnad-forekomstene."""
    koder = {}
    for seksjon in ("finansinntekt", "finanskostnad"):
        for el in root.findall(f"{_NS}resultatregnskap/{_NS}{seksjon}/*"):
            koder[el.find(f"{_NS}id").text] = el.find(
                f"{_NS}beloep/{_NS}beloep/{_NS}beloep"
            ).text
    return koder


class TestSkatteberegning:
    def test_gevinst_er_skattefri(self):
        r = Resultatregnskap(
            finansposter=Finansposter(
                andre_finansinntekter=10000, gevinst_ved_realisasjon_av_aksjer=200000
            )
        )
        b = beregn_skatt(r, SkattemeldingKonfig())
        assert b.fritatt_gevinst_aksjer == 200000
        assert b.skattepliktig_inntekt_brutto == 10000
        assert b.beregnet_skatt == 2200

    def test_tap_gir_ikke_fradrag(self):
        r = Resultatregnskap(
            finansposter=Finansposter(
                andre_finansinntekter=10000, tap_ved_realisasjon_av_aksjer=50000
            )
        )
        b = beregn_skatt(r, SkattemeldingKonfig())
        assert b.ikke_fradragsberettiget_tap_aksjer == 50000
        assert b.skattepliktig_inntekt_brutto == 10000
        assert b.nytt_underskudd == 0

    def test_ingen_sjablon_paa_gevinst_ved_lav_eierandel(self):
        # 3 %-sjablonen (§ 2-38 sjette ledd) gjelder utbytte, ikke gevinst.
        r = Resultatregnskap(
            finansposter=Finansposter(
                utbytte_fra_datterselskap=100000, gevinst_ved_realisasjon_av_aksjer=100000
            )
        )
        b = beregn_skatt(r, SkattemeldingKonfig(eierandel_for_fritaksmetoden=20))
        assert b.skattepliktig_utbytte == 3000
        assert b.fritatt_gevinst_aksjer == 100000
        assert b.skattepliktig_inntekt_brutto == 3000

    def test_uten_fritaksmetoden_skattlegges_gevinst_og_tap_fullt(self):
        r = Resultatregnskap(
            finansposter=Finansposter(
                gevinst_ved_realisasjon_av_aksjer=80000, tap_ved_realisasjon_av_aksjer=30000
            )
        )
        b = beregn_skatt(r, SkattemeldingKonfig(anvend_fritaksmetoden=False))
        assert b.fritatt_gevinst_aksjer == 0
        assert b.ikke_fradragsberettiget_tap_aksjer == 0
        assert b.skattepliktig_inntekt_brutto == 50000

    def test_samme_som_for_naar_feltene_mangler(self):
        # Samme regnskap, før og etter: gevinsten ført som andre finansinntekter gir
        # akkurat det gamle resultatet, siden de nye feltene er 0.
        r = Resultatregnskap(
            finansposter=Finansposter(
                utbytte_fra_datterselskap=100000,
                andre_finansinntekter=200000,
                andre_finanskostnader=5000,
            )
        )
        b = beregn_skatt(r, SkattemeldingKonfig(eierandel_for_fritaksmetoden=50))
        assert b.skattepliktig_inntekt_brutto == 3000 + 200000 - 5000
        assert b.fritatt_gevinst_aksjer == 0
        assert b.ikke_fradragsberettiget_tap_aksjer == 0


class TestNaeringsspesifikasjon:
    def test_egne_resultatkoder(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(
                gevinst_ved_realisasjon_av_aksjer=200000, tap_ved_realisasjon_av_aksjer=50000
            ),
        )
        koder = _resultatkoder(_root(regnskap))
        assert koder == {"8074": "200000.00", "8174": "50000.00"}

    def test_permanente_forskjeller(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(
                andre_finansinntekter=10000,
                gevinst_ved_realisasjon_av_aksjer=200000,
                tap_ved_realisasjon_av_aksjer=50000,
            ),
        )
        root = _root(regnskap)
        assert _forskjeller(root) == {_GEVINST_KODE: 200000.0, _TAP_KODE: 50000.0}
        # Invarianten SKD kryssjekker: årsresultat + tillegg - fradrag == skattemessig.
        assert _aarsresultat(root) + 50000 - 200000 == _skattemessig(root) == 10000.0

    def test_kodene_er_tillegg_og_fradrag(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(
                gevinst_ved_realisasjon_av_aksjer=200000, tap_ved_realisasjon_av_aksjer=50000
            ),
        )
        forskjell = _root(regnskap).find(
            f"{_NS}forskjellMellomRegnskapsmessigOgSkattemessigVerdi"
        )
        tillegg = forskjell.find(f"{_NS}sumTilleggINaeringsinntekt/{_NS}beloep/{_NS}beloep")
        fradrag = forskjell.find(f"{_NS}sumFradragINaeringsinntekt/{_NS}beloep/{_NS}beloep")
        assert tillegg.text == "50000.00"
        assert fradrag.text == "200000.00"

    def test_uten_fritaksmetoden_ingen_forskjell(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap, Finansposter(gevinst_ved_realisasjon_av_aksjer=200000)
        )
        root = _root(regnskap, SkattemeldingKonfig(anvend_fritaksmetoden=False))
        assert _forskjeller(root) == {}
        assert _skattemessig(root) == 200000.0

    def test_sammen_med_utbytte(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(
                utbytte_fra_datterselskap=100000, gevinst_ved_realisasjon_av_aksjer=40000
            ),
        )
        root = _root(regnskap, SkattemeldingKonfig(eierandel_for_fritaksmetoden=30))
        assert _forskjeller(root) == {
            "tilbakefoeringAvInntektsfoertUtbytte": 100000.0,
            "skattepliktigDelAvUtbytterOgUtdelinger": 3000.0,
            _GEVINST_KODE: 40000.0,
        }
        assert _skattemessig(root) == 3000.0

    def test_validerer_mot_xsd(self, eksempel_selskap):
        etree = pytest.importorskip("lxml.etree")
        from tests.test_xsd_validering import _XSD_DIR

        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(
                gevinst_ved_realisasjon_av_aksjer=200000, tap_ved_realisasjon_av_aksjer=50000
            ),
        )
        schema = etree.XMLSchema(
            etree.parse(str(_XSD_DIR / "naeringsspesifikasjon_v6_ekstern.xsd"))
        )
        doc = etree.fromstring(generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER))
        assert schema.validate(doc), schema.error_log


class TestBakoverkompatibilitet:
    def test_config_uten_feltene_leses_som_null(self):
        r = ar._les_resultat({"finansposter": {"andre_finansinntekter": 5000}})
        assert r.finansposter.gevinst_ved_realisasjon_av_aksjer == 0
        assert r.finansposter.tap_ved_realisasjon_av_aksjer == 0

    def test_config_med_feltene_leses(self):
        r = ar._les_resultat(
            {
                "finansposter": {
                    "gevinst_ved_realisasjon_av_aksjer": 1000,
                    "tap_ved_realisasjon_av_aksjer": "",
                }
            }
        )
        assert r.finansposter.gevinst_ved_realisasjon_av_aksjer == 1000
        assert r.finansposter.tap_ved_realisasjon_av_aksjer == 0
        assert r.finansposter.sum_inntekter == 1000

    def test_aarsregnskapet_er_uendret_av_utskillingen(self, eksempel_selskap):
        # Gevinst og tap rapporteres sammen med andre finansinntekter og -kostnader til
        # Brønnøysund, så XML-en er lik enten beløpet er skilt ut eller ikke.
        foer = _regnskap(
            eksempel_selskap,
            Finansposter(andre_finansinntekter=210000, andre_finanskostnader=50000),
        )
        etter = _regnskap(
            eksempel_selskap,
            Finansposter(
                andre_finansinntekter=10000,
                gevinst_ved_realisasjon_av_aksjer=200000,
                tap_ved_realisasjon_av_aksjer=50000,
            ),
        )
        assert _uten_rad_id(generer_underskjema(foer)) == _uten_rad_id(
            generer_underskjema(etter)
        )

    def test_rapporten_viser_fritatt_gevinst(self, eksempel_selskap):
        regnskap = _regnskap(
            eksempel_selskap,
            Finansposter(
                gevinst_ved_realisasjon_av_aksjer=200000, tap_ved_realisasjon_av_aksjer=50000
            ),
        )
        tekst = sm.generer(regnskap, SkattemeldingKonfig())
        assert "Aksjegevinst (100 % fritatt)" in tekst
        assert "Aksjetap (ikke fradrag)" in tekst

    def test_rapporten_uendret_uten_feltene(self, regnskap_med_utbytte):
        tekst = sm.generer(regnskap_med_utbytte, SkattemeldingKonfig())
        assert "realisasjon" not in tekst
        assert "Aksjegevinst" not in tekst
        assert "Aksjetap" not in tekst


class TestSaft:
    def test_8074_og_8174_faar_egne_linjer(self):
        cfg = importer_bytes(
            _saft_xml(
                _konto("finansinntekt", "8074", ub_kredit=200000)
                + _konto("finansinntekt", "8050", ub_kredit=5000)
                + _konto("finanskostnad", "8174", ub_debet=50000)
            )
        )
        fp = cfg["resultatregnskap"]["finansposter"]
        assert fp["gevinst_ved_realisasjon_av_aksjer"] == 200000
        assert fp["tap_ved_realisasjon_av_aksjer"] == 50000
        assert fp["andre_finansinntekter"] == 5000
        assert fp["andre_finanskostnader"] == 0
        assert any("8074" in a for a in cfg["_advarsler"])

    def test_verdiendringer_gir_advarsel(self):
        cfg = importer_bytes(
            _saft_xml(
                _konto("finansinntekt", "8080", ub_kredit=7000)
                + _konto("finanskostnad", "8115", ub_debet=3000)
            )
        )
        fp = cfg["resultatregnskap"]["finansposter"]
        assert fp["andre_finansinntekter"] == 7000
        assert fp["andre_finanskostnader"] == 3000
        assert any("8080, 8115" in a for a in cfg["_advarsler"])

    def test_vanlig_import_uten_aksjeposter_har_ingen_advarsel(self):
        cfg = importer_bytes(_saft_xml(_konto("finansinntekt", "8050", ub_kredit=5000)))
        assert "_advarsler" not in cfg
        fp = cfg["resultatregnskap"]["finansposter"]
        assert fp["gevinst_ved_realisasjon_av_aksjer"] == 0
        assert fp["tap_ved_realisasjon_av_aksjer"] == 0
