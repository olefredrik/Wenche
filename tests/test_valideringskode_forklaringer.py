"""
Klartekst-forklaringer i formater_valideringsresultat().

Kjente, kryptiske Skatteetaten-koder skal oversettes til hva brukeren kan
gjøre. Forklaringene er rent informative og endrer ikke hva som sendes.
"""

from wenche.skd_skattemelding_client import formater_valideringsresultat


def _res(**kwargs) -> dict:
    base = {
        "resultat": "validertMedFeil",
        "aarsak": None,
        "avvik_ved_validering": [],
        "avvik_etter_beregning": [],
        "veiledning": [],
    }
    base.update(kwargs)
    return base


def test_forklarer_kjent_veiledningskode():
    res = _res(
        veiledning=[
            {
                "veiledningstype": "UP_HAR_NÆRINGSSPESIFIKASJON_MANGLER_SKATTEMELDING",
                "hjelpetekst": "Selskapet mangler skattemelding.",
            }
        ]
    )
    ut = formater_valideringsresultat(res)
    assert "Hva betyr dette?" in ut
    assert "passivt holdingselskap" in ut
    assert "utenfor" in ut
    assert "skatteetaten.no" in ut
    # Forklaringen skal dekke selskap uten aksjer (hvilende), ikke bare anta at
    # det eier aksjer og mangler formuesgrunnlag (jf. issue #138).
    assert "ingen aksjer" in ut
    assert "hvilende" in ut


def test_forklarer_kjent_aarsakskode():
    res = _res(aarsak="innkommendeForespoerselManglerReferanseTilGjeldendeSkattemelding")
    ut = formater_valideringsresultat(res)
    assert "Hva betyr dette?" in ut
    assert "Oppgrader Wenche" in ut


def test_ingen_forklaringsseksjon_ved_ukjente_koder():
    res = _res(
        avvik_ved_validering=[{"avvikstype": "heltUkjentKode", "oevrigInformasjon": "x"}]
    )
    ut = formater_valideringsresultat(res)
    assert "Hva betyr dette?" not in ut


def test_duplikate_koder_forklares_kun_en_gang():
    kode = "UP_HAR_NÆRINGSSPESIFIKASJON_MANGLER_SKATTEMELDING"
    res = _res(
        aarsak=kode,
        veiledning=[{"veiledningstype": kode, "hjelpetekst": "x"}],
    )
    ut = formater_valideringsresultat(res)
    assert ut.count("passivt holdingselskap") == 1


def test_kodelistefeil_peker_paa_egen_postliste():
    # Formen tt02 svarte med 2026-08-20 da en kode utenfor kodelisten ble sendt.
    res = _res(
        aarsak="UgyldigKodelisteverdi",
        avvik_ved_validering=[
            {
                "avvikstype": "UgyldigKodelisteverdi",
                "oevrigInformasjon": (
                    "Verdien er ikke definert i kodeliste 2025_resultatregnskapOgBalanse"
                ),
            },
            {"avvikstype": "verdiAvvikerFraKodeliste", "oevrigInformasjon": "UgyldigKodeverdi:7770"},
        ],
    )
    ut = formater_valideringsresultat(res)
    assert "naeringsspesifikasjon.poster" in ut
    assert "Ingenting er sendt inn" in ut


def test_kodelistefeil_forklares_bare_en_gang():
    # aarsak og to avvikstyper peker på samme feil. Brukeren skal se forklaringen én gang.
    res = _res(
        aarsak="UgyldigKodelisteverdi",
        avvik_ved_validering=[
            {"avvikstype": "UgyldigKodelisteverdi", "oevrigInformasjon": ""},
            {"avvikstype": "verdiAvvikerFraKodeliste", "oevrigInformasjon": "UgyldigKodeverdi:7770"},
        ],
    )
    ut = formater_valideringsresultat(res)
    assert ut.count("finnes ikke i Skatteetatens kodeliste") == 1


def test_kodelistefeil_forklares_ogsaa_uten_aarsak():
    # SKD kan svare med avvikstypen alene. Hintet skal komme uansett.
    res = _res(
        avvik_ved_validering=[
            {"avvikstype": "verdiAvvikerFraKodeliste", "oevrigInformasjon": "UgyldigKodeverdi:7770"},
        ],
    )
    assert "naeringsspesifikasjon.poster" in formater_valideringsresultat(res)


def test_ulike_koder_med_ulik_forklaring_vises_hver_for_seg():
    # Dedupliseringen er på tekst, ikke på antall koder: to ulike feil skal fortsatt gi to svar.
    res = _res(
        aarsak="UgyldigKodelisteverdi",
        avvik_ved_validering=[
            {"avvikstype": "innkommendeForespoerselManglerSporTilUtfoerende", "oevrigInformasjon": ""},
        ],
    )
    ut = formater_valideringsresultat(res)
    assert "finnes ikke i Skatteetatens kodeliste" in ut
    assert "logg inn i Altinn med BankID" in ut
