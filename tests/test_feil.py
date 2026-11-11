"""Feilhierarkiet i wenche.feil: strukturerte felt, lesbare meldinger, aldri svarkropp i meldingen."""

import httpx

from wenche.feil import (
    AuthFeil,
    KonfigFeil,
    MyndighetsFeil,
    ValideringsFeil,
    WencheFeil,
    brukermelding,
    finn_feilkode,
)


def _svar(status: int, tekst: str, url: str = "https://platform.altinn.no/x") -> httpx.Response:
    req = httpx.Request("POST", url)
    return httpx.Response(status, text=tekst, request=req)


def test_alle_feil_er_runtimeerror_for_eldre_kallsteder():
    for feil in (KonfigFeil("x"), ValideringsFeil(["a"]), MyndighetsFeil("altinn", "s")):
        assert isinstance(feil, WencheFeil)
        assert isinstance(feil, RuntimeError)


def test_valideringsfeil_baerer_listen():
    e = ValideringsFeil(["Balansen går ikke opp", "Orgnr mangler"])
    assert e.feil == ["Balansen går ikke opp", "Orgnr mangler"]
    assert "Balansen" in str(e)


def test_fra_svar_plukker_kode_fra_json_og_holder_kroppen_unna_meldingen():
    kropp = '{"detail": "intern-detalj-hemmelig", "code": "AUTH-00004"}'
    e = MyndighetsFeil.fra_svar(
        "altinn", "oppretting av systembruker-forespørsel", _svar(400, kropp)
    )
    assert e.status == 400
    assert e.kode == "AUTH-00004"
    assert e.kropp == kropp
    assert e.url == "https://platform.altinn.no/x"
    assert "intern-detalj-hemmelig" not in str(e)
    assert "AUTH-00004" in str(e) and "400" in str(e) and "oppretting" in str(e)


def test_finn_feilkode_fra_json_og_tekst():
    assert finn_feilkode('{"error": "invalid_grant"}') == "invalid_grant"
    assert finn_feilkode("Feil: AUTH-00004 existing SystemUser") == "AUTH-00004"
    assert finn_feilkode("bare tekst") is None
    assert finn_feilkode("") is None


def test_nettverksfeil_uten_request_gir_ingen_url_men_lesbar_melding():
    e = MyndighetsFeil.fra_nettverksfeil(
        "skatteetaten", "validering av skattemeldingen", httpx.ConnectError("x")
    )
    assert e.status is None
    assert e.url is None
    assert "tidsavbrudd" in str(e)
    assert "tidsavbrudd" in brukermelding(e)


def test_brukermelding_navngir_steg_og_status_uten_kropp():
    e = MyndighetsFeil.fra_svar(
        "skatteetaten", "henting av forhåndsutfylt skattemelding", _svar(500, "<stacktrace/>")
    )
    m = brukermelding(e)
    assert "serverfeil" in m and "500" in m and "forhåndsutfylt" in m
    assert "stacktrace" not in m
    e403 = MyndighetsFeil("altinn", "oppretting av innsending i Altinn", status=403)
    assert "403" in brukermelding(e403) and "systembrukeren" in brukermelding(e403)


def test_beskrivelse_foelger_med_i_meldingen():
    e = MyndighetsFeil(
        "skatteetaten",
        "henting av forhåndsutfylt skattemelding",
        kode="mangler-partsnummer",
        beskrivelse="Fant ikke partsnummer. Ingenting er sendt inn.",
    )
    assert "partsnummer" in str(e) and "Ingenting er sendt inn" in str(e)
    assert "Ingenting er sendt inn" in brukermelding(e)


def test_kjent_kode_faar_forklaring_i_begge_meldinger():
    e = MyndighetsFeil(
        "altinn", "oppretting av systembruker-forespørsel i Altinn", status=400, kode="AUTH-00004"
    )
    assert "AUTH-00004" in str(e) and "allerede en systembruker" in str(e)
    assert "allerede en systembruker" in brukermelding(e)


def test_authfeil_fra_maskinporten_svar():
    kropp = '{"error": "invalid_grant", "error_description": "Client authentication failed"}'
    e = AuthFeil.fra_maskinporten_svar(_svar(401, kropp, url="https://maskinporten.no/token"))
    assert e.kode == "invalid_grant"
    assert e.beskrivelse == "Client authentication failed"
    assert "Maskinporten avviste innloggingen" in str(e) and "401" in str(e)
    assert brukermelding(e) == str(e)
