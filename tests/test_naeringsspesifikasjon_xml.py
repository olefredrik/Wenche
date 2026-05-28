"""
Tester for naeringsspesifikasjon_xml.py.

Verifiserer at næringsoppgave-XML (RF-1167 v6) er strukturelt korrekt:
- Riktig namespace og rootelement
- Obligatoriske felt (partsreferanse, inntektsaar, virksomhet)
- Kodelister for resultat- og balanseforekomster
- Filtrering av null-poster (elementer med beloep=0 utelates)
- Annen egenkapital: 2050 (positiv) vs 2080 (negativ/udekket tap)
- skalBekreftesAvRevisor
- Output er gyldig UTF-8 XML
"""

from xml.etree.ElementTree import fromstring

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
)
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon

_NS = (
    "urn:no:skatteetaten:fastsetting:formueinntekt:"
    "naeringsspesifikasjon:ekstern:v6"
)

_PARTSNUMMER = 3001587644


def _parse(regnskap: Aarsregnskap):
    return fromstring(generer_naeringsspesifikasjon(regnskap, _PARTSNUMMER).decode("utf-8"))


def _lag_regnskap(**kwargs) -> Aarsregnskap:
    """Bygger et minimalt Aarsregnskap med angitte overrides."""
    defaults = dict(
        selskap=Selskap(
            navn="Test Holding AS",
            org_nummer="123456789",
            daglig_leder="Ola Nordmann",
            styreleder="Ola Nordmann",
            forretningsadresse="Testveien 1, 0001 Oslo",
            stiftelsesaar=2020,
            aksjekapital=30000,
        ),
        regnskapsaar=2024,
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
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=-34300),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=67200),
            ),
        ),
    )
    defaults.update(kwargs)
    return Aarsregnskap(**defaults)


def _finn_kode(root, kode: str) -> bool:
    """Returnerer True hvis en resultatOgBalanseregnskapstype med gitt kode finnes i XML-en."""
    for el in root.iter(f"{{{_NS}}}resultatOgBalanseregnskapstype"):
        if el.text == kode:
            return True
    return False


# ---------------------------------------------------------------------------
# Grunnstruktur
# ---------------------------------------------------------------------------

class TestGrunnstruktur:
    def test_rootelement(self):
        root = _parse(_lag_regnskap())
        assert f"{{{_NS}}}naeringsspesifikasjon" == root.tag

    def test_partsreferanse(self):
        root = _parse(_lag_regnskap())
        el = root.find(f"{{{_NS}}}partsreferanse")
        assert el is not None
        assert el.text == str(_PARTSNUMMER)

    def test_inntektsaar(self):
        root = _parse(_lag_regnskap())
        el = root.find(f"{{{_NS}}}inntektsaar")
        assert el is not None
        assert el.text == "2024"

    def test_output_er_gyldig_utf8_xml(self):
        result = generer_naeringsspesifikasjon(_lag_regnskap(), _PARTSNUMMER)
        assert isinstance(result, bytes)
        fromstring(result.decode("utf-8"))


# ---------------------------------------------------------------------------
# Resultatregnskap — inkludering og kodelister
# ---------------------------------------------------------------------------

class TestResultatregnskap:
    def test_salgsinntekter_kode_3200(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(salgsinntekter=100000),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(),
            )
        )
        assert _finn_kode(_parse(regnskap), "3200")

    def test_andre_driftsinntekter_kode_3900(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(andre_driftsinntekter=20000),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(),
            )
        )
        assert _finn_kode(_parse(regnskap), "3900")

    def test_loennskostnader_kode_5000(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(loennskostnader=500000),
                finansposter=Finansposter(),
            )
        )
        assert _finn_kode(_parse(regnskap), "5000")

    def test_avskrivninger_kode_6000(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(avskrivninger=10000),
                finansposter=Finansposter(),
            )
        )
        assert _finn_kode(_parse(regnskap), "6000")

    def test_andre_driftskostnader_kode_6700(self):
        assert _finn_kode(_parse(_lag_regnskap()), "6700")

    def test_utbytte_fra_datterselskap_kode_8090(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(utbytte_fra_datterselskap=50000),
            )
        )
        assert _finn_kode(_parse(regnskap), "8090")

    def test_andre_finansinntekter_kode_8050(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(andre_finansinntekter=5000),
            )
        )
        assert _finn_kode(_parse(regnskap), "8050")

    def test_rentekostnader_kode_8150(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(rentekostnader=1175),
            )
        )
        assert _finn_kode(_parse(regnskap), "8150")

    def test_andre_finanskostnader_kode_8160(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(andre_finanskostnader=500),
            )
        )
        assert _finn_kode(_parse(regnskap), "8160")

    def test_null_inntekter_gir_ingen_driftsinntekt_element(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(andre_driftskostnader=5500),
                finansposter=Finansposter(),
            )
        )
        root = _parse(regnskap)
        res = root.find(f"{{{_NS}}}resultatregnskap")
        assert res.find(f"{{{_NS}}}driftsinntekt") is not None
        # Ingen forekomster under driftsinntekt
        di = res.find(f"{{{_NS}}}driftsinntekt")
        assert len(list(di)) == 0

    def test_null_finansposter_gir_ingen_finanselementer(self):
        root = _parse(_lag_regnskap())
        res = root.find(f"{{{_NS}}}resultatregnskap")
        assert res.find(f"{{{_NS}}}finansinntekt") is None
        assert res.find(f"{{{_NS}}}finanskostnad") is None


# ---------------------------------------------------------------------------
# Balanse — inkludering og kodelister
# ---------------------------------------------------------------------------

class TestBalanse:
    def test_aksjer_i_datterselskap_kode_1313(self):
        assert _finn_kode(_parse(_lag_regnskap()), "1313")

    def test_andre_aksjer_kode_1350(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(andre_aksjer=33947),
                omloepmidler=Omloepmidler(bankinnskudd=375),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=-184),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=4181),
                kortsiktig_gjeld=KortsiktigGjeld(annen_kortsiktig_gjeld=1500),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "1350")

    def test_langsiktige_fordringer_kode_1390(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(langsiktige_fordringer=50000),
                omloepmidler=Omloepmidler(bankinnskudd=1000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=21000),
                langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=0),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "1390")

    def test_kortsiktige_fordringer_kode_1500(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(kortsiktige_fordringer=5000, bankinnskudd=500),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=75500),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "1500")

    def test_bankinnskudd_kode_1920(self):
        assert _finn_kode(_parse(_lag_regnskap()), "1920")

    def test_aksjekapital_kode_2000(self):
        assert _finn_kode(_parse(_lag_regnskap()), "2000")

    def test_overkursfond_kode_2020(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(bankinnskudd=5000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, overkursfond=75000),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "2020")

    def test_positiv_annen_egenkapital_kode_2050(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=130000),
                omloepmidler=Omloepmidler(bankinnskudd=0),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=100000),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "2050")
        assert not _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "2080")

    def test_negativ_annen_egenkapital_kode_2080(self):
        assert _finn_kode(_parse(_lag_regnskap()), "2080")
        assert not _finn_kode(_parse(_lag_regnskap()), "2050")

    def test_laan_fra_aksjonaer_kode_2250(self):
        assert _finn_kode(_parse(_lag_regnskap()), "2250")

    def test_andre_langsiktige_laan_kode_2290(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(bankinnskudd=10000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=30000),
                langsiktig_gjeld=LangsiktigGjeld(andre_langsiktige_laan=50000),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "2290")

    def test_leverandoergjeld_kode_2400(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(bankinnskudd=5000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=75000),
                kortsiktig_gjeld=KortsiktigGjeld(leverandoergjeld=0, annen_kortsiktig_gjeld=0),
            ),
        )
        balanse2 = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(bankinnskudd=5000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=73500),
                kortsiktig_gjeld=KortsiktigGjeld(leverandoergjeld=1500),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse2)), "2400")

    def test_skyldige_offentlige_avgifter_kode_2600(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(bankinnskudd=5000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=72000),
                kortsiktig_gjeld=KortsiktigGjeld(skyldige_offentlige_avgifter=3000),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "2600")

    def test_annen_kortsiktig_gjeld_kode_2990(self):
        balanse = Balanse(
            eiendeler=Eiendeler(
                anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                omloepmidler=Omloepmidler(bankinnskudd=5000),
            ),
            egenkapital_og_gjeld=EgenkapitalOgGjeld(
                egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=73500),
                kortsiktig_gjeld=KortsiktigGjeld(annen_kortsiktig_gjeld=1500),
            ),
        )
        assert _finn_kode(_parse(_lag_regnskap(balanse=balanse)), "2990")

    def test_null_gjeld_gir_ingen_gjeld_element(self):
        regnskap = _lag_regnskap()
        root = _parse(regnskap)
        gek = root.find(f".//{{{_NS}}}gjeldOgEgenkapital")
        assert gek.find(f"{{{_NS}}}kortsiktigGjeld") is None


# ---------------------------------------------------------------------------
# Virksomhet-seksjon
# ---------------------------------------------------------------------------

class TestVirksomhet:
    def test_virksomhet_er_tilstede(self):
        root = _parse(_lag_regnskap())
        assert root.find(f"{{{_NS}}}virksomhet") is not None

    def test_regnskapspliktstype(self):
        root = _parse(_lag_regnskap())
        el = root.find(f".//{{{_NS}}}regnskapspliktstype/{{{_NS}}}regnskapspliktstype")
        assert el is not None
        assert el.text == "fullRegnskapsplikt"

    def test_regnskapsperiode_start(self):
        root = _parse(_lag_regnskap())
        el = root.find(f".//{{{_NS}}}regnskapsperiode/{{{_NS}}}start/{{{_NS}}}dato")
        assert el is not None
        assert el.text == "2024-01-01"

    def test_regnskapsperiode_slutt(self):
        root = _parse(_lag_regnskap())
        el = root.find(f".//{{{_NS}}}regnskapsperiode/{{{_NS}}}slutt/{{{_NS}}}dato")
        assert el is not None
        assert el.text == "2024-12-31"

    def test_virksomhetstype(self):
        root = _parse(_lag_regnskap())
        el = root.find(f".//{{{_NS}}}virksomhetstype/{{{_NS}}}virksomhetstype")
        assert el is not None
        assert el.text == "oevrigSelskap"

    def test_regeltype_for_aarsregnskap(self):
        root = _parse(_lag_regnskap())
        el = root.find(f".//{{{_NS}}}regeltypeForAarsregnskap/{{{_NS}}}regeltypeForAarsregnskap")
        assert el is not None
        assert el.text == "regnskapslovensReglerForSmaaForetak"


# ---------------------------------------------------------------------------
# skalBekreftesAvRevisor
# ---------------------------------------------------------------------------

class TestRevisor:
    def test_ikke_revidert_gir_false(self):
        root = _parse(_lag_regnskap())
        el = root.find(f"{{{_NS}}}skalBekreftesAvRevisor")
        assert el is not None
        assert el.text == "false"

    def test_revidert_gir_true(self):
        root = _parse(_lag_regnskap(revideres=True))
        el = root.find(f"{{{_NS}}}skalBekreftesAvRevisor")
        assert el.text == "true"


# ---------------------------------------------------------------------------
# Beløpsformat
# ---------------------------------------------------------------------------

class TestBeloepsformat:
    def test_beloep_har_to_desimaler(self):
        root = _parse(_lag_regnskap())
        # Finn første beloep-element med tekst
        for el in root.iter(f"{{{_NS}}}beloep"):
            if el.text and "." in el.text:
                assert len(el.text.split(".")[1]) == 2
                break

    def test_heltall_beloep_har_to_desimaler(self):
        root = _parse(_lag_regnskap())
        for el in root.iter(f"{{{_NS}}}beloep"):
            if el.text:
                assert "." in el.text
                break


# ---------------------------------------------------------------------------
# Avledede summer
#
# SKD krever at vi echo-er våre egne beregnede summer for kryssvalidering.
# Manglende felt flagges som «manglerNaeringsopplysninger» i etterBeregning
# (SSV/tilbakemelding 2026-05) selv om resultatAvValidering er «validertOK».
# ---------------------------------------------------------------------------

class TestAvledetSummer:
    def _beloep(self, root, path: str) -> float:
        """
        Hent ut det innerste beloep-elementets verdi (struktur
        <{tag}><beloep><beloep>...</beloep></beloep></{tag}>) for en gitt sti.
        """
        ns_path = ".//".join(f"{{{_NS}}}{p}" for p in path.split("/"))
        el = root.find(f".//{ns_path}")
        assert el is not None, f"Fant ikke {path}"
        verdi = el.find(f"{{{_NS}}}beloep/{{{_NS}}}beloep")
        assert verdi is not None and verdi.text, f"Fant ikke beloep-tekst i {path}"
        return float(verdi.text)

    def test_sumDriftsinntekt(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(
                    salgsinntekter=100000, andre_driftsinntekter=5000
                ),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(),
            )
        )
        assert self._beloep(_parse(regnskap), "sumDriftsinntekt") == 105000.0

    def test_sumDriftskostnad(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(
                    loennskostnader=20000,
                    avskrivninger=3000,
                    andre_driftskostnader=5000,
                ),
                finansposter=Finansposter(),
            )
        )
        assert self._beloep(_parse(regnskap), "sumDriftskostnad") == 28000.0

    def test_sum_finansinntekt_og_finanskostnad(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(),
                finansposter=Finansposter(
                    utbytte_fra_datterselskap=10000,
                    andre_finansinntekter=2000,
                    rentekostnader=1500,
                    andre_finanskostnader=500,
                ),
            )
        )
        root = _parse(regnskap)
        assert self._beloep(root, "sumFinansinntekt") == 12000.0
        assert self._beloep(root, "sumFinanskostnad") == 2000.0

    def test_aarsresultat_er_resultat_foer_skatt(self):
        # Holdingselskap uten skattekostnad: aarsresultat = resultat_foer_skatt
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(salgsinntekter=100000),
                driftskostnader=Driftskostnader(andre_driftskostnader=80000),
                finansposter=Finansposter(rentekostnader=5000),
            )
        )
        # 100000 - 80000 - 5000 = 15000
        assert self._beloep(_parse(regnskap), "aarsresultat") == 15000.0

    def test_sumBalanseverdiForAnleggsmiddel_og_omloepsmiddel(self):
        regnskap = _lag_regnskap(
            balanse=Balanse(
                eiendeler=Eiendeler(
                    anleggsmidler=Anleggsmidler(
                        aksjer_i_datterselskap=50000, andre_aksjer=20000
                    ),
                    omloepmidler=Omloepmidler(
                        kortsiktige_fordringer=3000, bankinnskudd=10000
                    ),
                ),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(aksjekapital=30000),
                ),
            )
        )
        root = _parse(regnskap)
        assert self._beloep(root, "sumBalanseverdiForAnleggsmiddel") == 70000.0
        assert self._beloep(root, "sumBalanseverdiForOmloepsmiddel") == 13000.0
        assert self._beloep(root, "sumBalanseverdiForEiendel") == 83000.0

    def test_gjeldOgEgenkapital_summer(self):
        regnskap = _lag_regnskap(
            balanse=Balanse(
                eiendeler=Eiendeler(
                    anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=100000),
                ),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=10000),
                    langsiktig_gjeld=LangsiktigGjeld(laan_fra_aksjonaer=50000),
                    kortsiktig_gjeld=KortsiktigGjeld(annen_kortsiktig_gjeld=10000),
                ),
            )
        )
        root = _parse(regnskap)
        assert self._beloep(root, "sumLangsiktigGjeld") == 50000.0
        assert self._beloep(root, "sumKortsiktigGjeld") == 10000.0
        assert self._beloep(root, "sumEgenkapital") == 40000.0
        assert self._beloep(root, "sumGjeldOgEgenkapital") == 100000.0

    def test_beregnetNaeringsinntekt_med_underskudd(self):
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(salgsinntekter=10000),
                driftskostnader=Driftskostnader(andre_driftskostnader=15000),
                finansposter=Finansposter(),
            )
        )
        root = _parse(regnskap)
        assert root.find(f".//{{{_NS}}}beregnetNaeringsinntekt") is not None
        # skattemessigResultat = aarsresultat = -5000
        assert self._beloep(root, "skattemessigResultat") == -5000.0
        # Fordeling på forekomst id=1
        fordelt = root.find(
            f".//{{{_NS}}}fordeltBeregnetNaeringsinntektForUpersonligSkattepliktig"
        )
        assert fordelt is not None
        assert fordelt.find(f"{{{_NS}}}id").text == "1"

    def test_egenkapitalavstemming_har_sumFradragOgUtgaaendeEK_ved_underskudd(self):
        # Inngående EK 30000, årets underskudd 5000 → utgående 25000,
        # sumFradragIEgenkapital = 5000.
        regnskap = _lag_regnskap(
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(),
                driftskostnader=Driftskostnader(andre_driftskostnader=5000),
                finansposter=Finansposter(),
            ),
            balanse=Balanse(
                eiendeler=Eiendeler(
                    anleggsmidler=Anleggsmidler(aksjer_i_datterselskap=25000),
                ),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(aksjekapital=30000, annen_egenkapital=-5000),
                ),
            ),
            foregaaende_aar_balanse=Balanse(
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(aksjekapital=30000),
                ),
            ),
        )
        root = _parse(regnskap)
        assert self._beloep(root, "sumFradragIEgenkapital") == 5000.0
        assert self._beloep(root, "utgaaendeEgenkapital") == 25000.0
        # Ingen sumTilleggIEgenkapital ved underskudd
        assert root.find(f".//{{{_NS}}}sumTilleggIEgenkapital") is None
