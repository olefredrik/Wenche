"""
Regresjon: når SKDs visnings-API ikke gir et brukbart partsnummer i den forhåndsutfylte
skattemeldingen, kastet `hent_partsnummer` en bar `ValueError`. I hostet `_utfor` er ikke
ValueError i fangst-listen, så den ble en naken HTTP 500 («Uventet feil under innsending»).
send_skattemelding gjør den nå om til en lesbar RuntimeError (-> 502), uten å sende noe inn.
"""
from unittest.mock import Mock

import pytest

from wenche import innsending as tjeneste

_CONFIG = {
    "selskap": {"navn": "Test AS", "org_nummer": "314273818", "daglig_leder": "Ola Nordmann",
                "styreleder": "Ola Nordmann", "forretningsadresse": "Testveien 1, 0001 Oslo",
                "stiftelsesaar": 2018, "aksjekapital": 30000, "kontakt_epost": "test@example.no"},
    "regnskapsaar": 2024,
    "resultatregnskap": {
        "driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
        "driftskostnader": {"loennskostnader": 0, "avskrivninger": 0, "andre_driftskostnader": 0},
        "finansposter": {"utbytte_fra_datterselskap": 0, "andre_finansinntekter": 0,
                         "rentekostnader": 0, "andre_finanskostnader": 0}},
    "balanse": {
        "eiendeler": {"anleggsmidler": {"aksjer_i_datterselskap": 0, "andre_aksjer": 0, "langsiktige_fordringer": 0},
                      "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000}},
        "egenkapital_og_gjeld": {
            "egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 0},
            "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
            "kortsiktig_gjeld": {"leverandoergjeld": 0, "skyldige_offentlige_avgifter": 0, "annen_kortsiktig_gjeld": 0}}},
    "skattemelding": {"anvend_fritaksmetoden": False, "boersnotert": False,
                      "underskudd_til_fremfoering": 0, "formuesverdi_aksjer": 0},
    "aksjonaerer": [{"navn": "Kari", "fodselsnummer": "24847799354", "antall_aksjer": 300,
                     "aksjeklasse": "ordinære", "utbytte_utbetalt": 0, "innbetalt_kapital_per_aksje": 100}],
}

# Forhåndsutfylt uten <partsnummer> (typisk hvis skattemeldingen for året ikke er klargjort).
_UTEN_PARTSNUMMER = (
    '<skattemelding xmlns="urn:no:skatteetaten:fastsetting:formueinntekt:'
    'skattemelding:upersonlig:ekstern:v5"><inntektsaar>2024</inntektsaar></skattemelding>'
).encode("utf-8")


def test_manglende_partsnummer_gir_lesbar_runtimeerror_ikke_500():
    skd = Mock()
    skd.hent_forhåndsutfylt_med_id.return_value = (_UTEN_PARTSNUMMER, None)
    with pytest.raises(RuntimeError) as ei:
        tjeneste.send_skattemelding(_CONFIG, skd, "altinn-token", orgnr="314273818")
    melding = str(ei.value)
    assert "partsnummer" in melding and "Ingenting er" in melding
    skd.send.assert_not_called()  # ingenting sendt inn
