"""
Skattekostnad som egen linje i årsregnskapet (rskl. § 6-1 nr. 19).

Før dette regnet modellen «resultat før skatt» som årsresultat direkte, altså implisitt
skattekostnad 0. Det gikk bra så lenge selskapet hadde underskudd eller null skattepliktig
resultat, men et passivt holdingselskap med renteinntekt har en reell skattekostnad. Da
manglet oppstillingsplanen en påkrevd linje, og balansen hadde ingen riktig plass til
skattegjelden.

Testene dekker tre ting:
  1. Ny linje kommer med i begge innsendingene, med riktige orid/koder og plassering.
  2. Skattemessig resultat reduseres IKKE av skattekostnaden (den er ikke fradragsberettiget,
     sktl. § 6-1), verken i næringsspesifikasjonen eller i underskuddsgrunnlaget.
  3. Et regnskap uten skattekostnad gir uendret XML, så eksisterende brukere ikke berøres.
"""

from xml.etree.ElementTree import fromstring

from wenche import aarsregnskap as ar
from wenche import skattemelding as sm
from wenche.brg_xml import generer_underskjema
from wenche.models import (
    KortsiktigGjeld,
    Resultatregnskap,
    Finansposter,
    SkattemeldingKonfig,
)
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skattemelding_xml import generer_skattemelding_fra_konfig

_NS = "{urn:no:skatteetaten:fastsetting:formueinntekt:naeringsspesifikasjon:ekstern:v6}"
_SM_NS = "{urn:no:skatteetaten:fastsetting:formueinntekt:skattemelding:upersonlig:ekstern:v5}"
_PARTSNUMMER = 123456789


class TestModell:
    def test_aarsresultat_er_etter_skatt(self):
        r = Resultatregnskap(
            finansposter=Finansposter(andre_finansinntekter=50000),
            skattekostnad=11000,
        )
        assert r.resultat_foer_skatt == 50000
        assert r.aarsresultat == 39000

    def test_uten_skattekostnad_er_aarsresultat_lik_resultat_foer_skatt(self):
        r = Resultatregnskap(finansposter=Finansposter(andre_finansinntekter=50000))
        assert r.aarsresultat == r.resultat_foer_skatt == 50000

    def test_betalbar_skatt_teller_i_kortsiktig_gjeld(self):
        kg = KortsiktigGjeld(leverandoergjeld=2000, betalbar_skatt=11000)
        assert kg.sum == 13000


class TestConfigLesing:
    def _config(self, **resultat_ekstra):
        return {
            "selskap": {
                "navn": "Test AS",
                "org_nummer": "123456789",
                "daglig_leder": "D L",
                "styreleder": "D L",
                "forretningsadresse": "Vei 1, 0001 OSLO",
                "stiftelsesaar": 2018,
                "aksjekapital": 30000,
            },
            "regnskapsaar": 2025,
            "resultatregnskap": {
                "finansposter": {"andre_finansinntekter": 50000},
                **resultat_ekstra,
            },
            "balanse": {
                "egenkapital_og_gjeld": {
                    "kortsiktig_gjeld": {"betalbar_skatt": 11000},
                },
            },
        }

    def test_leser_skattekostnad_og_betalbar_skatt(self):
        regnskap = ar.les_config(self._config(skattekostnad=11000))
        assert regnskap.resultatregnskap.skattekostnad == 11000
        assert regnskap.resultatregnskap.aarsresultat == 39000
        kg = regnskap.balanse.egenkapital_og_gjeld.kortsiktig_gjeld
        assert kg.betalbar_skatt == 11000

    def test_manglende_skattekostnad_blir_null(self):
        regnskap = ar.les_config(self._config())
        assert regnskap.resultatregnskap.skattekostnad == 0.0

    def test_blank_skattekostnad_blir_null(self):
        # Skjemaet sender tom streng for et blankt tallfelt.
        regnskap = ar.les_config(self._config(skattekostnad=""))
        assert regnskap.resultatregnskap.skattekostnad == 0.0


class TestBrgUnderskjema:
    def test_skattekostnad_linje_med_orid(self, regnskap_med_skattekostnad):
        xml = generer_underskjema(regnskap_med_skattekostnad).decode("utf-8")
        assert '<skattekostnad altinnRowId=' in xml
        assert '<aarets orid="11835">11000</aarets>' in xml
        assert '<fjoraarets orid="11836">0</fjoraarets>' in xml

    def test_skattekostnad_staar_mellom_resultat_foer_skatt_og_aarsresultat(
        self, regnskap_med_skattekostnad
    ):
        # XSD-sekvensen i Resultat er rekkefølge-bundet.
        xml = generer_underskjema(regnskap_med_skattekostnad).decode("utf-8")
        pos_foer = xml.index("<resultatFoerSkattekostnad>")
        pos_skatt = xml.index("<skattekostnad altinnRowId=")
        pos_aars = xml.index("<aarsresultat>")
        assert pos_foer < pos_skatt < pos_aars

    def test_aarsresultat_er_etter_skatt_i_xml(self, regnskap_med_skattekostnad):
        xml = generer_underskjema(regnskap_med_skattekostnad).decode("utf-8")
        assert '<aarets orid="167">50000</aarets>' in xml   # resultat før skatt
        assert '<aarets orid="172">39000</aarets>' in xml   # årsresultat

    def test_betalbar_skatt_i_kortsiktig_gjeld(self, regnskap_med_skattekostnad):
        xml = generer_underskjema(regnskap_med_skattekostnad).decode("utf-8")
        assert '<betalbarSkatt altinnRowId=' in xml
        assert '<aarets orid="2483">11000</aarets>' in xml
        assert '<aarets orid="85">11000</aarets>' in xml    # sum kortsiktig gjeld

    def test_betalbar_skatt_staar_foer_skyldige_offentlige_avgifter(
        self, regnskap_med_skattekostnad
    ):
        xml = generer_underskjema(regnskap_med_skattekostnad).decode("utf-8")
        pos_lev = xml.index("<balanseKortsiktigGjeld>")
        pos_skatt = xml.index("<betalbarSkatt altinnRowId=")
        pos_sum = xml.index("<sumKortsiktigGjeld>")
        assert pos_lev < pos_skatt < pos_sum

    def test_uten_skattekostnad_ingen_linje(self, eksempel_regnskap):
        # Baklengs-kompatibilitet: et holdingselskap uten skattepliktig inntekt skal få
        # nøyaktig samme XML som før endringen.
        xml = generer_underskjema(eksempel_regnskap).decode("utf-8")
        assert "<skattekostnad" not in xml
        assert "<betalbarSkatt" not in xml


class TestNaeringsspesifikasjon:
    def _root(self, regnskap):
        return fromstring(
            generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER).decode("utf-8")
        )

    def _beloep(self, el):
        """Beløp i et avledet sum-element (BeloepMedSkattemessigeEgenskaper)."""
        return el.find(f"{_NS}beloep/{_NS}beloep").text

    def _forekomst_beloep(self, el):
        """Beløp i en linjeforekomst, som har ett innkapslingsnivå mer enn sum-elementene."""
        return el.find(f"{_NS}beloep/{_NS}beloep/{_NS}beloep").text

    def test_skattekostnad_forekomst_med_kode_8300(self, regnskap_med_skattekostnad):
        root = self._root(regnskap_med_skattekostnad)
        kostnad = root.find(f"{_NS}resultatregnskap/{_NS}skattekostnad/{_NS}kostnad")
        assert kostnad is not None
        assert kostnad.find(f"{_NS}id").text == "8300"
        assert (
            kostnad.find(
                f"{_NS}type/{_NS}resultatOgBalanseregnskapstype"
            ).text
            == "8300"
        )
        assert self._forekomst_beloep(kostnad) == "11000.00"

    def test_sum_skattekostnad_emitteres(self, regnskap_med_skattekostnad):
        root = self._root(regnskap_med_skattekostnad)
        sum_el = root.find(f"{_NS}resultatregnskap/{_NS}sumSkattekostnad")
        assert sum_el is not None
        assert self._beloep(sum_el) == "11000.00"

    def test_aarsresultat_er_etter_skatt(self, regnskap_med_skattekostnad):
        root = self._root(regnskap_med_skattekostnad)
        aars = root.find(f"{_NS}resultatregnskap/{_NS}aarsresultat")
        assert self._beloep(aars) == "39000.00"

    def test_skattemessig_resultat_er_foer_skatt(self, regnskap_med_skattekostnad):
        # Kjernen i fiksen: skattekostnaden er ikke fradragsberettiget, så det skattemessige
        # resultatet skal være 50 000, ikke årsresultatet på 39 000. Ellers ville
        # næringsspesifikasjonen oppgitt et grunnlag som var 22 % for lavt.
        root = self._root(regnskap_med_skattekostnad)
        bni = root.find(f"{_NS}beregnetNaeringsinntekt")
        assert self._beloep(bni.find(f"{_NS}skattemessigResultat")) == "50000.00"
        fordelt = bni.find(
            f"{_NS}fordeltBeregnetNaeringsinntektForUpersonligSkattepliktig"
        )
        assert self._beloep(fordelt.find(f"{_NS}fordeltSkattemessigResultat")) == "50000.00"
        assert (
            self._beloep(fordelt.find(f"{_NS}fordeltSkattemessigResultatEtterKorreksjon"))
            == "50000.00"
        )

    def test_betalbar_skatt_som_gjeld_med_kode_2500(self, regnskap_med_skattekostnad):
        root = self._root(regnskap_med_skattekostnad)
        gjeld = root.findall(
            f"{_NS}balanseregnskap/{_NS}gjeldOgEgenkapital/{_NS}kortsiktigGjeld/{_NS}gjeld"
        )
        koder = {g.find(f"{_NS}id").text: self._forekomst_beloep(g) for g in gjeld}
        assert koder == {"2500": "11000.00"}

    def test_uten_skattekostnad_ingen_skattekostnad_element(self, regnskap_med_utbytte):
        root = self._root(regnskap_med_utbytte)
        assert root.find(f"{_NS}resultatregnskap/{_NS}skattekostnad") is None
        assert root.find(f"{_NS}resultatregnskap/{_NS}sumSkattekostnad") is None


class TestTilbakefoertSkattekostnad:
    """
    Skattekostnaden må tilbakeføres som permanent forskjell.

    Skatteetaten utleder sitt eget skattemessige resultat fra ÅRSRESULTATET pluss
    permanente forskjeller, ikke fra resultat før skatt. Uten tilbakeføringen regner SKD
    22 % lavere enn påstanden vår og svarer validertMedFeil med avvikNaeringsopplysninger
    og merknaden N_AVVIK_TILBAKEFØRT_SKATTEKOSTNAD. Verifisert mot tt02 2026-08-05: uten
    denne seksjonen validertMedFeil, med den validertOK og SKDs beregnede inntekt lik vår.
    """

    def _root(self, regnskap, konfig=None):
        return fromstring(
            generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER, konfig).decode("utf-8")
        )

    def _forskjell(self, root):
        return root.find(f"{_NS}forskjellMellomRegnskapsmessigOgSkattemessigVerdi")

    def test_permanent_forskjell_med_riktig_kode(self, regnskap_med_skattekostnad):
        perm = self._forskjell(self._root(regnskap_med_skattekostnad)).find(
            f"{_NS}permanentForskjell"
        )
        assert perm.find(f"{_NS}id").text == "positivSkattekostnad"
        assert (
            perm.find(f"{_NS}permanentForskjellstype/{_NS}permanentForskjellstype").text
            == "positivSkattekostnad"
        )
        assert (
            perm.find(f"{_NS}beloep/{_NS}beloep/{_NS}beloep").text == "11000.00"
        )

    def test_sum_tillegg_i_naeringsinntekt(self, regnskap_med_skattekostnad):
        forskjell = self._forskjell(self._root(regnskap_med_skattekostnad))
        sum_el = forskjell.find(f"{_NS}sumTilleggINaeringsinntekt")
        assert sum_el.find(f"{_NS}beloep/{_NS}beloep").text == "11000.00"
        assert forskjell.find(f"{_NS}sumFradragINaeringsinntekt") is None

    def test_negativ_skattekostnad_gaar_til_fradrag(self, regnskap_med_skattekostnad):
        # En negativ skattekostnad (skatteinntekt) løfter årsresultatet over resultat før
        # skatt, og må da trekkes fra for å komme tilbake til det skattemessige resultatet.
        regnskap_med_skattekostnad.resultatregnskap.skattekostnad = -4000
        forskjell = self._forskjell(self._root(regnskap_med_skattekostnad))
        perm = forskjell.find(f"{_NS}permanentForskjell")
        assert perm.find(f"{_NS}id").text == "negativSkattekostnad"
        assert perm.find(f"{_NS}beloep/{_NS}beloep/{_NS}beloep").text == "4000.00"
        assert forskjell.find(f"{_NS}sumFradragINaeringsinntekt") is not None
        assert forskjell.find(f"{_NS}sumTilleggINaeringsinntekt") is None

    def test_tilbakefoering_stemmer_med_skattemessig_resultat(
        self, regnskap_med_skattekostnad
    ):
        # Invarianten SKD kryssjekker: årsresultat + tilbakeført skattekostnad
        # == skattemessig resultat.
        root = self._root(regnskap_med_skattekostnad)
        aars = float(
            root.find(f"{_NS}resultatregnskap/{_NS}aarsresultat/{_NS}beloep/{_NS}beloep").text
        )
        tillegg = float(
            self._forskjell(root)
            .find(f"{_NS}sumTilleggINaeringsinntekt/{_NS}beloep/{_NS}beloep")
            .text
        )
        skattemessig = float(
            root.find(
                f"{_NS}beregnetNaeringsinntekt/{_NS}skattemessigResultat"
                f"/{_NS}beloep/{_NS}beloep"
            ).text
        )
        assert aars + tillegg == skattemessig == 50000.0

    def test_ingen_seksjon_uten_forskjeller(self, eksempel_regnskap):
        # Bare driftskostnader: ingen skattekostnad og ingen fritatt utbytte, altså
        # ingenting å forklare mellom regnskap og skattegrunnlag.
        assert self._forskjell(self._root(eksempel_regnskap)) is None


class TestFritaksmetoden:
    """
    Utbytte som er fritatt etter fritaksmetoden skal ikke stå som skattepliktig inntekt.

    Før dette oppgav næringsspesifikasjonen brutto utbytte som skattemessig resultat, mens
    Wenches egen skatteberegning bare skattla 3 %-sjablonen. Innsendingen var altså
    internt inkonsistent: den påsto et skattegrunnlag som ikke stemte med skattekostnaden.
    SKDs validering fanger det ikke, fordi den bare kryssjekker årsresultat + permanente
    forskjeller mot skattemessig resultat.
    """

    def _root(self, regnskap, konfig):
        return fromstring(
            generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER, konfig).decode("utf-8")
        )

    def _forskjeller(self, root):
        """{kode: beløp} for alle permanente forskjeller."""
        forskjell = root.find(f"{_NS}forskjellMellomRegnskapsmessigOgSkattemessigVerdi")
        if forskjell is None:
            return {}
        return {
            p.find(f"{_NS}id").text: float(
                p.find(f"{_NS}beloep/{_NS}beloep/{_NS}beloep").text
            )
            for p in forskjell.findall(f"{_NS}permanentForskjell")
        }

    def _skattemessig(self, root):
        el = root.find(
            f"{_NS}beregnetNaeringsinntekt/{_NS}skattemessigResultat/{_NS}beloep/{_NS}beloep"
        )
        return float(el.text) if el is not None else 0.0

    def _utbytteregnskap(self, eksempel_selskap, utbytte, skattekostnad):
        from wenche.models import (
            Aarsregnskap,
            Balanse,
            Egenkapital,
            EgenkapitalOgGjeld,
            Eiendeler,
            Omloepmidler,
        )

        return Aarsregnskap(
            selskap=eksempel_selskap,
            regnskapsaar=2025,
            resultatregnskap=Resultatregnskap(
                finansposter=Finansposter(utbytte_fra_datterselskap=utbytte),
                skattekostnad=skattekostnad,
            ),
            balanse=Balanse(
                eiendeler=Eiendeler(omloepmidler=Omloepmidler(bankinnskudd=utbytte)),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(annen_egenkapital=utbytte)
                ),
            ),
        )

    def test_helt_fritatt_utbytte_gir_null_skattepliktig(self, eksempel_selskap):
        # Eierandel >= 90 %: hele utbyttet er fritatt, ingen skatt, ingen 3 %-sjablon.
        regnskap = self._utbytteregnskap(eksempel_selskap, 1000000, 0)
        konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_for_fritaksmetoden=100)
        root = self._root(regnskap, konfig)
        forskjeller = self._forskjeller(root)
        assert forskjeller == {"tilbakefoeringAvInntektsfoertUtbytte": 1000000.0}
        assert self._skattemessig(root) == 0.0

    def test_sjablonregelen_gir_tre_prosent_som_skattepliktig(self, eksempel_selskap):
        # Eierandel < 90 %: 3 % av utbyttet er skattepliktig, resten fritatt.
        regnskap = self._utbytteregnskap(eksempel_selskap, 1000000, 6600)
        konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_for_fritaksmetoden=80)
        root = self._root(regnskap, konfig)
        assert self._forskjeller(root) == {
            "positivSkattekostnad": 6600.0,
            "skattepliktigDelAvUtbytterOgUtdelinger": 30000.0,
            "tilbakefoeringAvInntektsfoertUtbytte": 1000000.0,
        }
        assert self._skattemessig(root) == 30000.0

    def test_uten_fritaksmetoden_er_utbyttet_fullt_skattepliktig(self, eksempel_selskap):
        # Fritaksmetoden av: ingen tilbakeføring, hele utbyttet er skattepliktig.
        regnskap = self._utbytteregnskap(eksempel_selskap, 1000000, 220000)
        konfig = SkattemeldingKonfig(anvend_fritaksmetoden=False)
        root = self._root(regnskap, konfig)
        assert self._forskjeller(root) == {"positivSkattekostnad": 220000.0}
        assert self._skattemessig(root) == 1000000.0

    def test_invariant_aarsresultat_pluss_tillegg_minus_fradrag(self, eksempel_selskap):
        # Invarianten SKD kryssjekker, for alle tre variantene.
        for eierandel, fritak, skattekostnad in [(100, True, 0), (80, True, 6600), (0, False, 220000)]:
            regnskap = self._utbytteregnskap(eksempel_selskap, 1000000, skattekostnad)
            konfig = SkattemeldingKonfig(
                anvend_fritaksmetoden=fritak, eierandel_for_fritaksmetoden=eierandel
            )
            root = self._root(regnskap, konfig)
            forskjell = root.find(f"{_NS}forskjellMellomRegnskapsmessigOgSkattemessigVerdi")

            def _sum(tag):
                el = forskjell.find(f"{_NS}{tag}/{_NS}beloep/{_NS}beloep")
                return float(el.text) if el is not None else 0.0

            aars = float(
                root.find(
                    f"{_NS}resultatregnskap/{_NS}aarsresultat/{_NS}beloep/{_NS}beloep"
                ).text
            )
            utledet = aars + _sum("sumTilleggINaeringsinntekt") - _sum("sumFradragINaeringsinntekt")
            assert utledet == self._skattemessig(root), (
                f"invarianten brytes for eierandel={eierandel}, fritak={fritak}"
            )

    def test_skattemessig_resultat_null_emitteres_ved_aktivitet(self, eksempel_selskap):
        # Helt fritatt utbytte gir legitimt 0 i skattepliktig inntekt. Utelates påstanden,
        # beregner SKD 0 selv og flagger manglerNaeringsopplysninger (verifisert mot tt02).
        regnskap = self._utbytteregnskap(eksempel_selskap, 1000000, 0)
        konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_for_fritaksmetoden=100)
        root = self._root(regnskap, konfig)
        assert root.find(f"{_NS}beregnetNaeringsinntekt") is not None
        assert self._skattemessig(root) == 0.0

    def test_hvilende_selskap_utelater_seksjonen(self, eksempel_selskap):
        # Ingen poster i resultatregnskapet: SKD forventer ikke seksjonen, og innsendingen
        # er ren uten den. Skal ikke endres av at 0 nå emitteres ved aktivitet.
        from wenche.models import Aarsregnskap, Balanse

        regnskap = Aarsregnskap(
            selskap=eksempel_selskap,
            regnskapsaar=2025,
            resultatregnskap=Resultatregnskap(),
            balanse=Balanse(),
        )
        root = self._root(regnskap, SkattemeldingKonfig())
        assert root.find(f"{_NS}beregnetNaeringsinntekt") is None

    def test_fritatt_utbytte_med_kostnader_gir_skattemessig_underskudd(self, eksempel_selskap):
        # Regnskapsmessig overskudd, skattemessig underskudd: utbyttet er fritatt, mens
        # kostnadene er fradragsberettigede. Underskuddet skal føres til fremføring.
        regnskap = self._utbytteregnskap(eksempel_selskap, 1000000, 0)
        regnskap.resultatregnskap.driftskostnader.andre_driftskostnader = 50000
        konfig = SkattemeldingKonfig(anvend_fritaksmetoden=True, eierandel_for_fritaksmetoden=100)
        assert regnskap.resultatregnskap.aarsresultat == 950000  # regnskapsmessig overskudd
        assert self._skattemessig(self._root(regnskap, konfig)) == -50000.0
        xml = generer_skattemelding_fra_konfig(regnskap, konfig, _PARTSNUMMER).decode("utf-8")
        samlet = fromstring(xml).find(
            f"{_SM_NS}inntektOgUnderskudd/{_SM_NS}samletUnderskudd/{_SM_NS}beloep"
            f"/{_SM_NS}beloepSomHeltall"
        )
        assert samlet.text == "50000"


class TestUnderskuddsgrunnlag:
    def test_aarets_underskudd_regnes_foer_skatt(self, eksempel_regnskap):
        # Underskuddsår: resultat før skatt -5 500. En (kunstig) ført skattekostnad skal
        # ikke øke det fremførbare underskuddet, siden den ikke er fradragsberettiget.
        eksempel_regnskap.resultatregnskap.skattekostnad = 1000
        konfig = SkattemeldingKonfig()
        xml = generer_skattemelding_fra_konfig(
            eksempel_regnskap, konfig, _PARTSNUMMER
        ).decode("utf-8")
        root = fromstring(xml)
        samlet = root.find(
            f"{_SM_NS}inntektOgUnderskudd/{_SM_NS}samletUnderskudd/{_SM_NS}beloep"
            f"/{_SM_NS}beloepSomHeltall"
        )
        assert samlet.text == "5500"


class TestVisning:
    def test_viser_foert_skattekostnad_og_aarsresultat(self, regnskap_med_skattekostnad):
        tekst = sm.generer(regnskap_med_skattekostnad, SkattemeldingKonfig())
        assert "Skattekostnad" in tekst
        assert "-11 000 kr" in tekst
        assert "39 000 kr" in tekst

    def test_varsler_naar_skatt_er_beregnet_men_ikke_foert(self, regnskap_med_skattekostnad):
        regnskap_med_skattekostnad.resultatregnskap.skattekostnad = 0
        tekst = sm.generer(regnskap_med_skattekostnad, SkattemeldingKonfig())
        assert "ikke ført" in tekst
        assert "§ 6-1" in tekst

    def test_varsler_ved_avvik_mot_beregningen(self, regnskap_med_skattekostnad):
        regnskap_med_skattekostnad.resultatregnskap.skattekostnad = 9000
        tekst = sm.generer(regnskap_med_skattekostnad, SkattemeldingKonfig())
        assert "avvik" in tekst

    def test_ingen_advarsel_naar_foert_stemmer(self, regnskap_med_skattekostnad):
        tekst = sm.generer(regnskap_med_skattekostnad, SkattemeldingKonfig())
        assert "avvik" not in tekst
        assert "ikke ført" not in tekst


class TestBeregning:
    def test_beregn_skatt_fra_config_uten_selskapsopplysninger(self):
        # Forslaget hentes fra Tall-steget, der selskapsfeltene godt kan stå tomme.
        beregning, foert = sm.beregn_skatt_fra_config(
            {"resultatregnskap": {"finansposter": {"andre_finansinntekter": 50000}}}
        )
        assert beregning.beregnet_skatt == 11000
        assert foert == 0.0

    def test_forslag_tar_hensyn_til_sjablonregelen(self):
        beregning, _ = sm.beregn_skatt_fra_config(
            {
                "resultatregnskap": {
                    "finansposter": {"utbytte_fra_datterselskap": 1000000}
                },
                "skattemelding": {
                    "anvend_fritaksmetoden": True,
                    "eierandel_for_fritaksmetoden": 80,
                },
            }
        )
        # 3 % av 1 000 000 er skattepliktig, 22 % av 30 000 = 6 600.
        assert beregning.skattepliktig_utbytte == 30000
        assert beregning.beregnet_skatt == 6600

    def test_foert_skattekostnad_returneres(self):
        _, foert = sm.beregn_skatt_fra_config(
            {"resultatregnskap": {"skattekostnad": 11000}}
        )
        assert foert == 11000


class TestAdvarsler:
    def test_advarer_naar_skattekostnad_mangler_motpost(self, regnskap_med_skattekostnad):
        kg = regnskap_med_skattekostnad.balanse.egenkapital_og_gjeld.kortsiktig_gjeld
        kg.betalbar_skatt = 0
        # Hold balansen i orden, slik at det er motposten (ikke balansen) som varsles.
        regnskap_med_skattekostnad.balanse.eiendeler.omloepmidler.bankinnskudd = 78000
        adv = ar.advarsler(regnskap_med_skattekostnad)
        assert any("betalbar skatt" in a.lower() for a in adv)

    def test_ingen_advarsel_naar_motposten_er_paa_plass(self, regnskap_med_skattekostnad):
        adv = ar.advarsler(regnskap_med_skattekostnad)
        assert not any("betalbar skatt" in a.lower() for a in adv)
