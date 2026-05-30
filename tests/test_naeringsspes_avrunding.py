"""
Tester for avrunding til hele kroner i næringsspesifikasjonen (issue #105).

Næringsspesifikasjonen sendte tidligere ører, som Skatteetaten avkortet i
visningen — det ga 1-krones sprik mot årsregnskapet (som rundes) og en balanse
som ikke gikk opp visuelt. Disse testene bruker OFL Holdings faktiske 2025-tall
med ører og verifiserer at alt rundes til hele kroner og balanserer, og at de
avledede summene (#92) forblir konsistente med linjepostene.
"""

from xml.etree.ElementTree import fromstring

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
_PARTSNUMMER = 3001587644


def _ofl_holding_2025() -> Aarsregnskap:
    """OFL Holding 2025 med faktiske ører (kilden til issue #105)."""
    return Aarsregnskap(
        selskap=Selskap(
            navn="OFL HOLDING AS",
            org_nummer="922020523",
            daglig_leder="Ole Fredrik Lie",
            styreleder="Ole Fredrik Lie",
            forretningsadresse="4010 Stavanger",
            stiftelsesaar=2018,
            aksjekapital=30000,
        ),
        regnskapsaar=2025,
        resultatregnskap=Resultatregnskap(
            driftsinntekter=Driftsinntekter(),
            driftskostnader=Driftskostnader(andre_driftskostnader=5104.75),
            finansposter=Finansposter(),
        ),
        balanse=Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(andre_aksjer=33947.95),
                omloepmidler=Omloepmidler(bankinnskudd=3445.25),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=-5288.75),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=12681.95),
            ),
        ),
        foregaaende_aar_balanse=Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(andre_aksjer=33947.95),
                omloepmidler=Omloepmidler(bankinnskudd=50),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=-184),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=4181.95),
            ),
        ),
    )


def _parse():
    return fromstring(generer_naeringsspesifikasjon(_ofl_holding_2025(), _PARTSNUMMER).decode("utf-8"))


def _beloep(root, tag: str) -> float:
    """Innerste beloep-verdi for første element med gitt tag."""
    el = root.find(f".//{{{_NS}}}{tag}/{{{_NS}}}beloep/{{{_NS}}}beloep")
    assert el is not None and el.text, f"Fant ikke beloep for {tag}"
    return float(el.text)


class TestHeleKronerAvrunding:
    def test_alle_belop_er_hele_kroner(self):
        # Ingen emittert beløp skal ha ører igjen (alt slutter på .00).
        root = _parse()
        leafs = [
            el.text for el in root.iter(f"{{{_NS}}}beloep")
            if el.text and el.text.strip()
        ]
        assert leafs, "Forventet minst ett beløp"
        for verdi in leafs:
            assert verdi.endswith(".00"), f"{verdi} har ører igjen"

    def test_linjeposter_rundet_som_aarsregnskapet(self):
        root = _parse()
        assert _beloep(root, "sumDriftskostnad") == 5105.0
        assert _beloep(root, "sumBalanseverdiForAnleggsmiddel") == 33948.0
        assert _beloep(root, "sumBalanseverdiForOmloepsmiddel") == 3445.0
        assert _beloep(root, "sumLangsiktigGjeld") == 12682.0
        assert _beloep(root, "aarsresultat") == -5105.0
        assert _beloep(root, "skattemessigResultat") == -5105.0

    def test_balansen_gaar_opp(self):
        root = _parse()
        eiendeler = _beloep(root, "sumBalanseverdiForEiendel")
        gjeld_og_ek = _beloep(root, "sumGjeldOgEgenkapital")
        assert eiendeler == 37393.0
        assert gjeld_og_ek == 37393.0
        # Sum egenkapital + sum langsiktig gjeld == sum gjeld og egenkapital
        assert _beloep(root, "sumEgenkapital") + _beloep(root, "sumLangsiktigGjeld") == gjeld_og_ek

    def test_egenkapitalavstemming_balanserer(self):
        root = _parse()
        inngaaende = _beloep(root, "inngaaendeEgenkapital")
        fradrag = _beloep(root, "sumFradragIEgenkapital")
        utgaaende = _beloep(root, "utgaaendeEgenkapital")
        assert inngaaende == 29816.0
        assert fradrag == 5105.0
        assert utgaaende == 24711.0
        # Kjernen i #105: inngaaende − fradrag == utgaaende, eksakt.
        assert inngaaende - fradrag == utgaaende
