"""
Egenkapitalavstemmingens koder: hvilken egenkapitalendringstype hvert beløp får.

Kodene enumereres ikke i XSD-en (`skatt:eksternKodeliste`), så lokal XSD-validering fanger
verken en ugyldig kode eller en kode plassert på feil side av avstemmingen. Skatteetatens
kodeliste `2025_egenkapitalendringstype` er derfor sjekket inn under tests/kodelister/ og
brukt som autoritet her: hver kode Wenche kan sende må finnes der, være gyldig for
virksomhetstype `oevrigSelskap` og regnskapspliktstype `fullRegnskapsplikt` (kombinasjonen
Wenche alltid sender), og ligge i den kategorien Wenche plasserer den i.

Skatteetaten har bekreftet (SSV-5813) at egenkapitalendringstypen ikke inngår i noen
maskinell kontroll: et feilvalg gir en uriktig opplysning og ikke et avvik. Derav denne
testen framfor tt02.
"""

from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest

from wenche.aarsregnskap import advarsler, valider
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
)
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "naeringsspesifikasjon:ekstern:v6"
)
_KODELISTE_NS = "urn:no:skatteetaten:informasjonsforvaltning:kodeliste:v2"
_KODELISTE = (
    Path(__file__).parent / "kodelister" / "2025_egenkapitalendringstype.xml"
)
_PARTSNUMMER = 3001587644

# Hver kode Wenche kan sende i egenkapitalavstemmingen, med siden den havner på.
# Legger du en ny kode i naeringsspesifikasjon_xml, hører den inn her: uten den faller
# test_ingen_ukjente_koder, som er meningen med vakten.
KODER = {
    "kontantinnskudd": "tillegg",
    "tinginnskudd": "tillegg",
    "aaretsOverskudd": "tillegg",
    "annenPositivEndringIEgenkapital": "tillegg",
    "aaretsUnderskudd": "fradrag",
    "annenNegativEndringIEgenkapital": "fradrag",
}


def _selskap(**kwargs) -> Selskap:
    felt = dict(
        navn="Test Holding AS",
        org_nummer="123456789",
        daglig_leder="Ola Nordmann",
        styreleder="Ola Nordmann",
        forretningsadresse="Testveien 1, 0001 Oslo",
        stiftelsesaar=2018,
        aksjekapital=30000,
    )
    felt.update(kwargs)
    return Selskap(**felt)


def _balanse(
    *,
    aksjekapital: float = 0.0,
    overkursfond: float = 0.0,
    annen_egenkapital: float = 0.0,
    bankinnskudd: float = 0.0,
    aksjer: float = 0.0,
    kortsiktig_gjeld: float = 0.0,
) -> Balanse:
    return Balanse(
        eiendeler=Eiendeler(
            anleggsmidler=Anleggsmidler(andre_aksjer=aksjer),
            omloepmidler=Omloepmidler(bankinnskudd=bankinnskudd),
        ),
        egenkapital_og_gjeld=EgenkapitalOgGjeld(
            egenkapital=Egenkapital(
                aksjekapital=aksjekapital,
                overkursfond=overkursfond,
                annen_egenkapital=annen_egenkapital,
            ),
            langsiktig_gjeld=LangsiktigGjeld(),
            kortsiktig_gjeld=KortsiktigGjeld(annen_kortsiktig_gjeld=kortsiktig_gjeld),
        ),
    )


def _resultat(*, inntekt: float = 0.0, kostnad: float = 0.0) -> Resultatregnskap:
    return Resultatregnskap(
        driftsinntekter=Driftsinntekter(),
        driftskostnader=Driftskostnader(andre_driftskostnader=kostnad),
        finansposter=Finansposter(utbytte_fra_datterselskap=inntekt),
    )


def _endringer(regnskap: Aarsregnskap) -> list[tuple[str, float]]:
    """(kode, beløp) i den rekkefølgen de står i XML-en."""
    root = fromstring(
        generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER).decode("utf-8")
    )
    avstemming = root.find(f"{{{_NS}}}egenkapitalavstemming")
    assert avstemming is not None
    endringer = []
    for endring in avstemming.findall(f"{{{_NS}}}egenkapitalendring"):
        kode = endring.findtext(
            f"{{{_NS}}}egenkapitalendringstype/{{{_NS}}}egenkapitalendringstype"
        )
        beloep = endring.findtext(f"{{{_NS}}}beloep/{{{_NS}}}beloep/{{{_NS}}}beloep")
        endringer.append((kode, float(beloep)))
    return endringer


def _summer(regnskap: Aarsregnskap) -> tuple[float, float]:
    """(sumTilleggIEgenkapital, sumFradragIEgenkapital), 0 når elementet mangler."""
    root = fromstring(
        generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER).decode("utf-8")
    )
    avstemming = root.find(f"{{{_NS}}}egenkapitalavstemming")
    assert avstemming is not None

    def hent(tag: str) -> float:
        verdi = avstemming.findtext(f"{{{_NS}}}{tag}/{{{_NS}}}beloep/{{{_NS}}}beloep")
        return float(verdi) if verdi is not None else 0.0

    return hent("sumTilleggIEgenkapital"), hent("sumFradragIEgenkapital")


# ---------------------------------------------------------------------------
# Tilfellene, ett per rad. Dekker til sammen alle kodene i KODER.
# ---------------------------------------------------------------------------

def _nystiftet_med_tinginnskudd(tinginnskudd: float = 70000) -> Aarsregnskap:
    """Stiftet i regnskapsåret med 30k kontant + 70k ting, driftsunderskudd 6 500."""
    return Aarsregnskap(
        selskap=_selskap(
            stiftelsesaar=2024,
            aksjekapital=30000,
            tinginnskudd_ved_stiftelse=tinginnskudd,
        ),
        regnskapsaar=2024,
        resultatregnskap=_resultat(kostnad=6500),
        balanse=_balanse(
            aksjekapital=30000,
            overkursfond=70000,
            annen_egenkapital=-6500,
            aksjer=100000,
            kortsiktig_gjeld=6500,
        ),
        foregaaende_aar_balanse=_balanse(),
    )


def _overskudd_med_utbytte() -> Aarsregnskap:
    """Overskudd 95 000, utbytte 80 000 utbetalt i året."""
    return Aarsregnskap(
        selskap=_selskap(),
        regnskapsaar=2024,
        resultatregnskap=_resultat(inntekt=95000),
        balanse=_balanse(aksjekapital=30000, annen_egenkapital=65000, bankinnskudd=95000),
        foregaaende_aar_balanse=_balanse(
            aksjekapital=30000, annen_egenkapital=50000, bankinnskudd=80000
        ),
        utbytte_utbetalt=80000,
    )


def _uforklart_oekning() -> Aarsregnskap:
    """Egenkapitalen stiger 20 000 uten resultat og uten kapitalforhøyelse."""
    return Aarsregnskap(
        selskap=_selskap(),
        regnskapsaar=2024,
        resultatregnskap=_resultat(),
        balanse=_balanse(aksjekapital=30000, annen_egenkapital=70000, bankinnskudd=100000),
        foregaaende_aar_balanse=_balanse(
            aksjekapital=30000, annen_egenkapital=50000, bankinnskudd=80000
        ),
    )


def _uforklart_nedgang_uten_utbytte() -> Aarsregnskap:
    """Egenkapitalen faller 20 000 uten resultat og uten utbytte."""
    return Aarsregnskap(
        selskap=_selskap(),
        regnskapsaar=2024,
        resultatregnskap=_resultat(),
        balanse=_balanse(aksjekapital=30000, annen_egenkapital=50000, bankinnskudd=80000),
        foregaaende_aar_balanse=_balanse(
            aksjekapital=30000, annen_egenkapital=70000, bankinnskudd=100000
        ),
    )


def _nedgang_stoerre_enn_utbytte() -> Aarsregnskap:
    """Egenkapitalen faller 30 000, hvorav 10 000 er utbetalt utbytte."""
    return Aarsregnskap(
        selskap=_selskap(),
        regnskapsaar=2024,
        resultatregnskap=_resultat(),
        balanse=_balanse(aksjekapital=30000, annen_egenkapital=40000, bankinnskudd=70000),
        foregaaende_aar_balanse=_balanse(
            aksjekapital=30000, annen_egenkapital=70000, bankinnskudd=100000
        ),
        utbytte_utbetalt=10000,
    )


ALLE_TILFELLER = [
    _nystiftet_med_tinginnskudd,
    _overskudd_med_utbytte,
    _uforklart_oekning,
    _uforklart_nedgang_uten_utbytte,
]


# ---------------------------------------------------------------------------
# Tinginnskudd (punkt 1 i issue #159)
# ---------------------------------------------------------------------------

class TestTinginnskudd:
    def test_deler_stiftelsesinnskuddet_i_kontant_og_ting(self):
        assert _endringer(_nystiftet_med_tinginnskudd()) == [
            ("kontantinnskudd", 30000.0),
            ("tinginnskudd", 70000.0),
            ("aaretsUnderskudd", 6500.0),
        ]

    def test_hele_innskuddet_som_ting_gir_ingen_kontantpost(self):
        endringer = _endringer(_nystiftet_med_tinginnskudd(tinginnskudd=100000))
        assert endringer == [
            ("tinginnskudd", 100000.0),
            ("aaretsUnderskudd", 6500.0),
        ]

    def test_uoppgitt_tinginnskudd_gir_kontantinnskudd_som_foer(self):
        """Standardstien er uendret: uten feltet skal XML-en se ut som før 1.4.0."""
        endringer = _endringer(_nystiftet_med_tinginnskudd(tinginnskudd=0))
        assert endringer == [
            ("kontantinnskudd", 100000.0),
            ("aaretsUnderskudd", 6500.0),
        ]

    def test_summen_er_uavhengig_av_fordelingen(self):
        """Fordelingen flytter beløp mellom to koder, den endrer ikke avstemmingen."""
        for tinginnskudd in (0, 30000, 100000):
            assert _summer(_nystiftet_med_tinginnskudd(tinginnskudd)) == (100000.0, 6500.0)

    def test_stoerre_enn_innskuddet_stopper_innsendingen(self):
        regnskap = _nystiftet_med_tinginnskudd(tinginnskudd=150000)
        feil = [f for f in valider(regnskap) if "Tinginnskudd" in f]
        assert len(feil) == 1
        assert "150,000.00" in feil[0] and "100,000.00" in feil[0]

    def test_negativt_tinginnskudd_stopper_innsendingen(self):
        regnskap = _nystiftet_med_tinginnskudd(tinginnskudd=-1000)
        assert [f for f in valider(regnskap) if "Tinginnskudd" in f]

    def test_klemmes_i_xml_selv_om_valideringen_omgaas(self):
        """XML-en skal aldri rapportere mer tinginnskudd enn det faktiske innskuddet."""
        endringer = _endringer(_nystiftet_med_tinginnskudd(tinginnskudd=150000))
        assert endringer == [
            ("tinginnskudd", 100000.0),
            ("aaretsUnderskudd", 6500.0),
        ]

    def test_ignoreres_utenfor_foerste_regnskapsaar(self):
        """En config som bæres videre fra år til år skal ikke stoppe innsendingen."""
        regnskap = _overskudd_med_utbytte()
        regnskap.selskap.tinginnskudd_ved_stiftelse = 70000

        assert [f for f in valider(regnskap) if "Tinginnskudd" in f] == []
        assert any("Tinginnskudd" in a for a in advarsler(regnskap))
        assert all(kode != "tinginnskudd" for kode, _ in _endringer(regnskap))


# ---------------------------------------------------------------------------
# Kodelistevakten
# ---------------------------------------------------------------------------

def _kodeliste() -> dict[str, dict]:
    """{teknisk navn: {kategori, virksomhetstyper, regnskapspliktstyper}} fra fixturen."""
    root = fromstring(_KODELISTE.read_text(encoding="utf-8"))
    koder = {}
    for kode in root.findall(f"{{{_KODELISTE_NS}}}kode"):
        navn = kode.findtext(f"{{{_KODELISTE_NS}}}tekniskNavn")
        tillegg = kode.find(f"{{{_KODELISTE_NS}}}kodetillegg")
        koder[navn] = {
            "kategori": tillegg.findtext(f"{{{_KODELISTE_NS}}}kategori"),
            "virksomhetstyper": {
                el.text
                for el in tillegg.findall(f"{{{_KODELISTE_NS}}}virksomhetstype")
            },
            "regnskapspliktstyper": {
                el.text
                for el in tillegg.findall(f"{{{_KODELISTE_NS}}}regnskapspliktstype")
            },
        }
    return koder


class TestKodeliste:
    @pytest.mark.parametrize("kode", sorted(KODER))
    def test_koden_finnes_og_er_gyldig_for_wenches_kombinasjon(self, kode):
        oppslag = _kodeliste().get(kode)

        assert oppslag is not None, f"{kode} finnes ikke i 2025_egenkapitalendringstype"
        # Wenche sender alltid virksomhetstype oevrigSelskap og regnskapspliktstype
        # fullRegnskapsplikt, jf. virksomhet-elementet i naeringsspesifikasjon_xml.
        assert "oevrigSelskap" in oppslag["virksomhetstyper"]
        assert "fullRegnskapsplikt" in oppslag["regnskapspliktstyper"]

    @pytest.mark.parametrize("kode", sorted(KODER))
    def test_kategorien_stemmer_med_siden_wenche_bruker(self, kode):
        assert _kodeliste()[kode]["kategori"] == KODER[kode]

    @pytest.mark.parametrize("lag_regnskap", ALLE_TILFELLER)
    def test_ingen_ukjente_koder(self, lag_regnskap):
        """Alt XML-byggingen kan produsere må være dekket av KODER, ellers er vakten blind."""
        for kode, _ in _endringer(lag_regnskap()):
            assert kode in KODER, f"{kode} er ikke dekket av kodelistevakten"

    @pytest.mark.parametrize("lag_regnskap", ALLE_TILFELLER)
    def test_kodene_ligger_paa_riktig_side_av_avstemmingen(self, lag_regnskap):
        """
        Kodelistens kategori, ikke Wenches egen mening, avgjør hvilken sum et beløp hører til.
        Havner en fradragskode i tilleggssummen, går avstemmingen opp med feil fortegn.
        """
        regnskap = lag_regnskap()
        kodeliste = _kodeliste()
        forventet_tillegg = sum(
            beloep
            for kode, beloep in _endringer(regnskap)
            if kodeliste[kode]["kategori"] == "tillegg"
        )
        forventet_fradrag = sum(
            beloep
            for kode, beloep in _endringer(regnskap)
            if kodeliste[kode]["kategori"] == "fradrag"
        )

        assert _summer(regnskap) == (forventet_tillegg, forventet_fradrag)

    def test_alle_kodene_er_dekket_av_tilfellene(self):
        """Uten dette kunne KODER inneholde en kode ingen test faktisk genererer."""
        sett = {kode for lag in ALLE_TILFELLER for kode, _ in _endringer(lag())}
        assert sett == set(KODER)
