"""
Innsending for et skjønnsfastsatt selskap (issue #180).

Leverer ikke selskapet innen fristen, kan Skatteetaten skjønnsfastsette skattemeldingen.
Gjeldende skattemelding har da gjelderSkjoennsfastsetting=true, og en ny innsending må være en
klage: skattemeldingen må ha flagget og konvolutten innsendingsformaal=klage, ellers svarer
Skatteetaten UGYLDIG_KLAGE_PÅ_SKJØNNSFASTSETTING_UP. Klagen er ellers en vanlig komplett
skattemelding med selskapets egne tall (SSV-6235, verifisert i tt02 2026-10-22).

Normalstien skal være uendret: uten skjønn ingen flagg og innsendingsformaal=egenfastsetting.
"""
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wenche import innsending as tjeneste
from wenche.cli import main
from wenche.skattemelding_xml import er_skjoennsfastsatt, generer_skattemelding_upersonlig
from wenche.web.backend import miljo
from wenche.web.backend.app import lag_app

_NS = "urn:no:skatteetaten:fastsetting:formueinntekt:skattemelding:upersonlig:ekstern:v5"

# Utdrag av gjeldende skattemelding for en skjønnsfastsatt org i tt02.
_SKJOENNSFASTSATT = (
    f'<skattemelding xmlns="{_NS}"><partsnummer>3001212933</partsnummer>'
    "<inntektsaar>2025</inntektsaar>"
    "<formueOgGjeld><gjeld><annenGjeld><beloepSomHeltall>0</beloepSomHeltall></annenGjeld>"
    "</gjeld></formueOgGjeld>"
    "<gjelderSkjoennsfastsetting>true</gjelderSkjoennsfastsetting></skattemelding>"
).encode("utf-8")

_VANLIG = (
    f'<skattemelding xmlns="{_NS}"><partsnummer>3001212933</partsnummer>'
    "<inntektsaar>2025</inntektsaar></skattemelding>"
).encode("utf-8")

_CONFIG_FIL = Path(__file__).resolve().parent.parent / "config.example.yaml"


def _config() -> dict:
    return {
        "selskap": {"navn": "Test AS", "org_nummer": "310137715", "daglig_leder": "Ola Nordmann",
                    "styreleder": "Ola Nordmann", "forretningsadresse": "Testveien 1, 0001 Oslo",
                    "stiftelsesaar": 2018, "aksjekapital": 30000, "kontakt_epost": "test@example.no"},
        "regnskapsaar": 2025,
        "resultatregnskap": {
            "driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
            "driftskostnader": {"loennskostnader": 0, "avskrivninger": 0, "andre_driftskostnader": 0},
            "finansposter": {"utbytte_fra_datterselskap": 0, "andre_finansinntekter": 0,
                             "rentekostnader": 0, "andre_finanskostnader": 0}},
        "balanse": {
            "eiendeler": {"anleggsmidler": {"aksjer_i_datterselskap": 0, "andre_aksjer": 0,
                                            "langsiktige_fordringer": 0},
                          "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000}},
            "egenkapital_og_gjeld": {
                "egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 0},
                "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
                "kortsiktig_gjeld": {"leverandoergjeld": 0, "skyldige_offentlige_avgifter": 0,
                                     "annen_kortsiktig_gjeld": 0}}},
        "skattemelding": {"anvend_fritaksmetoden": False, "boersnotert": False,
                          "underskudd_til_fremfoering": 0, "formuesverdi_aksjer": 0},
        "aksjonaerer": [{"navn": "Kari", "fodselsnummer": "24847799354", "antall_aksjer": 300,
                         "aksjeklasse": "ordinære", "utbytte_utbetalt": 0,
                         "innbetalt_kapital_per_aksje": 100}],
    }


# ---------------------------------------------------------------------------
# Oppdagelse og XML
# ---------------------------------------------------------------------------

def test_oppdager_skjoennsfastsatt():
    assert er_skjoennsfastsatt(_SKJOENNSFASTSATT) is True


def test_vanlig_skattemelding_er_ikke_skjoennsfastsatt():
    assert er_skjoennsfastsatt(_VANLIG) is False


def test_flagget_utelates_som_standard():
    xml = generer_skattemelding_upersonlig(partsnummer=1, inntektsaar=2025)
    assert b"gjelderSkjoennsfastsetting" not in xml


def test_flagget_staar_foer_verdsettingAvAksje():
    xml = generer_skattemelding_upersonlig(
        partsnummer=1, inntektsaar=2025, formue_verdi_foer_rabatt=100, samlet_gjeld=0,
        gjelder_skjoennsfastsetting=True,
    ).decode()
    assert "<gjelderSkjoennsfastsetting>true</gjelderSkjoennsfastsetting>" in xml
    assert xml.index("gjelderSkjoennsfastsetting") < xml.index("verdsettingAvAksje")


def test_flagget_validerer_mot_xsd():
    etree = pytest.importorskip("lxml.etree")
    import wenche

    xsd = Path(wenche.__file__).parent / "xsd" / "skattemeldingUpersonlig_v5_ekstern.xsd"
    schema = etree.XMLSchema(etree.parse(str(xsd)))
    xml = generer_skattemelding_upersonlig(
        partsnummer=1, inntektsaar=2025, boersnotert=False, harytelse=False,
        formue_verdi_foer_rabatt=100, samlet_gjeld=0, gjelder_skjoennsfastsetting=True,
    )
    assert schema.validate(etree.fromstring(xml)), schema.error_log


# ---------------------------------------------------------------------------
# send_skattemelding (delt av hostet og self-hosted)
# ---------------------------------------------------------------------------

def _skd(forhaandsutfylt: bytes) -> Mock:
    skd = Mock()
    skd.hent_forhåndsutfylt_med_id.return_value = (forhaandsutfylt, "SKI:756:114129")
    skd.send.return_value = "https://af.tt02.altinn.no/inbox"
    return skd


def test_skjoennsfastsatt_krever_bekreftelse_og_sender_ingenting():
    skd = _skd(_SKJOENNSFASTSATT)
    svar = tjeneste.send_skattemelding(_config(), skd, "altinn", orgnr="310137715")
    assert svar["sendt"] is False
    assert svar["krever_bekreftelse"] == "klage_paa_skjoennsfastsetting"
    assert "klage" in svar["melding"] and "2025" in svar["melding"]
    skd.send.assert_not_called()


def test_bekreftet_klage_sendes_med_flagg_og_klageformaal():
    skd = _skd(_SKJOENNSFASTSATT)
    svar = tjeneste.send_skattemelding(
        _config(), skd, "altinn", orgnr="310137715", bekreft_klage=True
    )
    assert svar == {"sendt": True, "resultat": "https://af.tt02.altinn.no/inbox", "klage": True}
    kw = skd.send.call_args.kwargs
    assert kw["innsendingsformaal"] == "klage"
    assert b"<gjelderSkjoennsfastsetting>true</gjelderSkjoennsfastsetting>" in kw["skattemelding_xml"]


def test_vanlig_innsending_er_egenfastsetting_uten_flagg():
    skd = _skd(_VANLIG)
    svar = tjeneste.send_skattemelding(_config(), skd, "altinn", orgnr="310137715")
    assert svar["sendt"] is True and svar["klage"] is False
    kw = skd.send.call_args.kwargs
    assert kw["innsendingsformaal"] == "egenfastsetting"
    assert b"gjelderSkjoennsfastsetting" not in kw["skattemelding_xml"]


# ---------------------------------------------------------------------------
# Self-hosted rute: bekreft_klage sendes videre
# ---------------------------------------------------------------------------

def test_rute_sender_bekreft_klage_videre(monkeypatch):
    import wenche.auth as auth_mod

    monkeypatch.setattr(miljo, "_AKTIV_ENV", miljo._AKTIV_ENV)
    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("SKD_TEST_ORG_NUMMER", "310137715")
    monkeypatch.setattr(auth_mod, "get_skd_skattemelding_tokens",
                        lambda: {"maskinporten_token": "m", "altinn_token": "a"})
    kall = {}

    def falsk_send(config, skd, altinn_token, *, orgnr, bekreft_klage=False):
        kall["bekreft_klage"] = bekreft_klage
        return {"sendt": True, "resultat": "x", "klage": bekreft_klage}

    monkeypatch.setattr(tjeneste, "send_skattemelding", falsk_send)
    with TestClient(lag_app(env="test", serve_spa=False)) as klient:
        r = klient.post("/api/innsending/skattemelding?bekreft_klage=true", json=_config())
    assert r.status_code == 200, r.text
    assert kall["bekreft_klage"] is True


# ---------------------------------------------------------------------------
# CLI: send-skattemelding spør før klagen sendes
# ---------------------------------------------------------------------------

def _kjoer_cli(monkeypatch, forhaandsutfylt: bytes, svar: str):
    monkeypatch.delenv("WENCHE_ENV", raising=False)
    monkeypatch.delenv("SKD_TEST_PARTSNUMMER", raising=False)
    with patch(
        "wenche.auth.get_skd_skattemelding_tokens",
        return_value={"maskinporten_token": "m", "altinn_token": "a"},
    ), patch("wenche.skd_skattemelding_client.SkdSkattemeldingClient") as Client:
        skd = Client.return_value.__enter__.return_value
        skd.hent_forhåndsutfylt_med_id.return_value = (forhaandsutfylt, "SKI:756:114129")
        skd.send.return_value = "https://af.tt02.altinn.no/inbox"
        result = CliRunner().invoke(
            main, ["send-skattemelding", "--config", str(_CONFIG_FIL)], input=svar
        )
    return result, skd


def test_cli_avbryter_klage_uten_ja(monkeypatch):
    result, skd = _kjoer_cli(monkeypatch, _SKJOENNSFASTSATT, "n\n")
    assert result.exit_code == 1
    assert "skjønnsfastsatt" in result.output
    skd.send.assert_not_called()


def test_cli_sender_klage_etter_ja(monkeypatch):
    result, skd = _kjoer_cli(monkeypatch, _SKJOENNSFASTSATT, "j\n")
    assert result.exit_code == 0, result.output
    assert skd.send.call_args.kwargs["innsendingsformaal"] == "klage"


def test_cli_vanlig_innsending_spør_ikke(monkeypatch):
    result, skd = _kjoer_cli(monkeypatch, _VANLIG, "")
    assert result.exit_code == 0, result.output
    assert skd.send.call_args.kwargs["innsendingsformaal"] == "egenfastsetting"


def test_hostet_rute_sender_bekreft_klage_videre(monkeypatch):
    import importlib

    monkeypatch.setenv("WENCHE_ENV", "test")
    monkeypatch.setenv("HOSTED_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("HOSTED_INVITE_SECRET", "test-invite-secret")
    from hosted.api import config
    from hosted.api import innsending as hostet_innsending
    from hosted.api.auth import lag_invite_token

    config.settings.cache_clear()
    from hosted.api import main as main_mod

    importlib.reload(main_mod)
    monkeypatch.setattr(hostet_innsending, "krev_vendor", lambda: ("creds", None))
    # Systembruker-godkjenningen er utenfor det som testes her; orgen kommer fra økten.
    monkeypatch.setattr(hostet_innsending, "krev_kunde_org", lambda request: "310137715")
    monkeypatch.setattr(hostet_innsending.wauth, "hent_tokens_for",
                        lambda *a, **k: {"maskinporten_token": "m", "altinn_token": "a"})
    kall = {}

    def falsk_send(config, skd, altinn_token, *, orgnr, bekreft_klage=False):
        kall["bekreft_klage"] = bekreft_klage
        return {"sendt": True, "resultat": "x", "klage": bekreft_klage}

    monkeypatch.setattr(tjeneste, "send_skattemelding", falsk_send)
    try:
        with TestClient(main_mod.app) as klient:
            token = lag_invite_token("310137715")
            assert klient.post("/api/auth/invite", json={"token": token}).json()["invited"] is True
            r = klient.post("/api/innsending/skattemelding?bekreft_klage=true", json=_config())
    finally:
        config.settings.cache_clear()
    assert r.status_code == 200, r.text
    assert kall["bekreft_klage"] is True
