"""
Tester for aksjonær-stien i wenche/innsending.py.

Historikk: `valider_aksjonaer` returnerte tidligere alltid ok=True uten å kjøre
valideringen, og `send_aksjonaer` lot valideringen i `aksjonaerregister.send_inn`
slå til, som gjør print + SystemExit(1) (CLI-rettet). I web-kontekst ga det en
uforklart 500 og brukeren fikk aldri se feilene. Disse testene låser den nye
atferden: strukturert feilliste ved dry-run og `InnsendingValideringsfeil` ved
ekte innsending, samme mønster som årsregnskap.
"""
from unittest.mock import MagicMock

import pytest

from wenche.innsending import (
    InnsendingValideringsfeil,
    send_aksjonaer,
    valider_aksjonaer,
)


def _gyldig_config() -> dict:
    return {
        "regnskapsaar": 2024,
        "selskap": {
            "navn": "Test Holding AS",
            "org_nummer": "123456789",
            "daglig_leder": "Ola Nordmann",
            "styreleder": "Ola Nordmann",
            "forretningsadresse": "Testveien 1, 0001 Oslo",
            "stiftelsesaar": 2020,
            "aksjekapital": 30000,
            "kontakt_epost": "ola@test.no",
        },
        "aksjonaerer": [
            {
                "navn": "Ola Nordmann",
                "fodselsnummer": "20916997389",
                "antall_aksjer": 100,
                "aksjeklasse": "A",
                "utbytte_utbetalt": 0,
                "innbetalt_kapital_per_aksje": 300,
            }
        ],
    }


def _ugyldig_config() -> dict:
    cfg = _gyldig_config()
    del cfg["selskap"]["kontakt_epost"]
    cfg["aksjonaerer"][0]["fodselsnummer"] = "12345"
    return cfg


def test_valider_aksjonaer_ok_for_gyldig_config():
    resultat = valider_aksjonaer(_gyldig_config())
    assert resultat["ok"] is True
    assert resultat["feil"] == []
    assert resultat["antall_aksjonaerer"] == 1


def test_valider_aksjonaer_returnerer_feilliste():
    resultat = valider_aksjonaer(_ugyldig_config())
    assert resultat["ok"] is False
    assert any("kontakt_epost" in f for f in resultat["feil"])
    assert any("fødselsnummer" in f.lower() for f in resultat["feil"])


def test_send_aksjonaer_kaster_valideringsfeil_uten_aa_sende():
    klient = MagicMock()
    with pytest.raises(InnsendingValideringsfeil) as exc_info:
        send_aksjonaer(_ugyldig_config(), klient)
    assert exc_info.value.feil  # feillisten følger med exception-en
    klient.assert_not_called()  # ingenting skal ha truffet SKD-klienten


def test_send_aksjonaer_kaster_aldri_systemexit():
    """Valideringsfeil skal bli InnsendingValideringsfeil, aldri SystemExit (BaseException)."""
    try:
        send_aksjonaer(_ugyldig_config(), MagicMock())
    except InnsendingValideringsfeil:
        pass  # forventet
    # SystemExit ville sluppet forbi except-blokken over og feilet testen.
