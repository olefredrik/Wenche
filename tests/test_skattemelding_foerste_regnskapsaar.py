"""Regresjonstester for skattemeldingen i et nystiftet AS sitt første regnskapsår."""

from unittest.mock import Mock
from xml.etree.ElementTree import fromstring

from wenche import innsending as tjeneste


_NS = (
    "{urn:no:skatteetaten:fastsetting:formueinntekt:"
    "naeringsspesifikasjon:ekstern:v6}"
)
_ORGNR = "123456789"
_PARTSNUMMER = 987654321

_CONFIG = {
    "selskap": {
        "navn": "Syntetisk Holding AS",
        "org_nummer": _ORGNR,
        "daglig_leder": "Test Person",
        "styreleder": "Test Person",
        "forretningsadresse": "Testveien 1, 0001 Oslo",
        "stiftelsesaar": 2025,
        "stiftelsesdato": "2025-10-24",
        "aksjekapital": 30000,
    },
    "regnskapsaar": 2025,
    "regnskapsstart": "2025-10-24",
    "regnskapsslutt": "2025-12-31",
    "resultatregnskap": {
        "driftskostnader": {"andre_driftskostnader": 6500},
    },
    "balanse": {
        "eiendeler": {
            "anleggsmidler": {"andre_aksjer": 200000},
        },
        "egenkapital_og_gjeld": {
            "egenkapital": {
                "aksjekapital": 30000,
                "annen_egenkapital": -6500,
            },
            "langsiktig_gjeld": {
                "laan_fra_aksjonaer": 32500,
                "andre_langsiktige_laan": 144000,
            },
        },
    },
    "skattemelding": {
        "underskudd_til_fremfoering": 0,
        "formuesverdi_aksjer": 200000,
    },
}


def _naeringsspesifikasjon():
    """Kjør samme config-leser og generator som ekte innsending, uten nettverk."""
    skd = Mock()
    tjeneste.send_skattemelding(
        _CONFIG,
        skd,
        "syntetisk-altinn-token",
        orgnr=_ORGNR,
        partsnummer=_PARTSNUMMER,
    )
    xml = skd.send.call_args.kwargs["naeringsspesifikasjon_xml"]
    return fromstring(xml)


def _beloep(parent, tag: str) -> float:
    verdi = parent.findtext(f"{_NS}{tag}/{_NS}beloep/{_NS}beloep")
    assert verdi is not None
    return float(verdi)


def test_skattemeldingsflyten_bevarer_regnskapsperioden():
    root = _naeringsspesifikasjon()
    periode = root.find(f"{_NS}virksomhet/{_NS}regnskapsperiode")

    assert periode is not None
    assert periode.findtext(f"{_NS}start/{_NS}dato") == "2025-10-24"
    assert periode.findtext(f"{_NS}slutt/{_NS}dato") == "2025-12-31"


def test_foerste_regnskapsaar_skiller_kontantinnskudd_fra_underskudd():
    root = _naeringsspesifikasjon()
    avstemming = root.find(f"{_NS}egenkapitalavstemming")

    assert avstemming is not None
    endringer = []
    for endring in avstemming.findall(f"{_NS}egenkapitalendring"):
        kode = endring.findtext(
            f"{_NS}egenkapitalendringstype/{_NS}egenkapitalendringstype"
        )
        endringer.append((kode, _beloep(endring, "beloep")))

    assert endringer == [
        ("kontantinnskudd", 30000.0),
        ("aaretsUnderskudd", 6500.0),
    ]
    assert _beloep(avstemming, "inngaaendeEgenkapital") == 0.0
    assert _beloep(avstemming, "sumTilleggIEgenkapital") == 30000.0
    assert _beloep(avstemming, "sumFradragIEgenkapital") == 6500.0
    assert _beloep(avstemming, "utgaaendeEgenkapital") == 23500.0
