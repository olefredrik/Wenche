"""
Wenche — webgrensesnitt (Streamlit).

Start med: wenche ui
Miljøvalg (test/prod) gjøres i selve grensesnittet.
"""

import os
from pathlib import Path

import streamlit as st
import yaml

from wenche.models import (
    Aarsregnskap,
    Aksjonaer,
    Aksjonaerregisteroppgave,
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
    SkattemeldingKonfig,
)
from wenche import skattemelding as sm_modul
from wenche import aarsregnskap as ar_modul
from wenche import aksjonaerregister as akr_modul
from wenche import auth, systembruker
from wenche.altinn_client import AltinnClient
from wenche.brg_xml import generer_hovedskjema, generer_underskjema
from wenche.skd_client import SkdAksjonaerClient

# ---------------------------------------------------------------------------
# Initialisering av session_state fra config.yaml (ved oppstart / refresh)
# ---------------------------------------------------------------------------

CONFIG_FIL = Path("config.yaml")

_DEFAULTS = {
    "navn": "Mitt Holding AS",
    "org_nummer": "123456789",
    "daglig_leder": "Ola Nordmann",
    "styreleder": "Ola Nordmann",
    "forretningsadresse": "Gateveien 1, 0001 Oslo",
    "stiftelsesaar": 2020,
    "aksjekapital": 30000,
    "kontakt_epost": "",
    "regnskapsaar": 2025,
    "salgsinntekter": 0,
    "andre_driftsinntekter": 0,
    "loennskostnader": 0,
    "avskrivninger": 0,
    "andre_driftskostnader": 5500,
    "utbytte_fra_datterselskap": 0,
    "andre_finansinntekter": 0,
    "rentekostnader": 0,
    "andre_finanskostnader": 0,
    "aksjer_i_datterselskap": 100000,
    "andre_aksjer": 0,
    "langsiktige_fordringer": 0,
    "kortsiktige_fordringer": 0,
    "bankinnskudd": 1200,
    "ek_aksjekapital": 30000,
    "overkursfond": 0,
    "annen_egenkapital": -34300,
    "laan_fra_aksjonaer": 105500,
    "andre_langsiktige_laan": 0,
    "leverandoergjeld": 0,
    "skyldige_offentlige_avgifter": 0,
    "annen_kortsiktig_gjeld": 0,
    "underskudd": 0,
    "fritaksmetoden": False,
    "eierandel_datterselskap": 100,
    "antall_aksjonaerer": 1,
    # Foregående år (sammenligningstall, rskl. § 6-6)
    "f_salgsinntekter": 0,
    "f_andre_driftsinntekter": 0,
    "f_loennskostnader": 0,
    "f_avskrivninger": 0,
    "f_andre_driftskostnader": 0,
    "f_utbytte_fra_datterselskap": 0,
    "f_andre_finansinntekter": 0,
    "f_rentekostnader": 0,
    "f_andre_finanskostnader": 0,
    "f_aksjer_i_datterselskap": 0,
    "f_andre_aksjer": 0,
    "f_langsiktige_fordringer": 0,
    "f_kortsiktige_fordringer": 0,
    "f_bankinnskudd": 0,
    "f_ek_aksjekapital": 0,
    "f_overkursfond": 0,
    "f_annen_egenkapital": 0,
    "f_laan_fra_aksjonaer": 0,
    "f_andre_langsiktige_laan": 0,
    "f_leverandoergjeld": 0,
    "f_skyldige_offentlige_avgifter": 0,
    "f_annen_kortsiktig_gjeld": 0,
}

if "initialisert" not in st.session_state:
    verdier = dict(_DEFAULTS)
    if CONFIG_FIL.exists():
        try:
            with open(CONFIG_FIL, encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            s = cfg.get("selskap", {})
            verdier["navn"] = s.get("navn", verdier["navn"])
            verdier["org_nummer"] = str(s.get("org_nummer", verdier["org_nummer"]))
            verdier["daglig_leder"] = s.get("daglig_leder", verdier["daglig_leder"])
            verdier["styreleder"] = s.get("styreleder", verdier["styreleder"])
            verdier["forretningsadresse"] = s.get("forretningsadresse", verdier["forretningsadresse"])
            verdier["stiftelsesaar"] = int(s.get("stiftelsesaar", verdier["stiftelsesaar"]))
            verdier["aksjekapital"] = int(s.get("aksjekapital", verdier["aksjekapital"]))
            verdier["kontakt_epost"] = s.get("kontakt_epost", verdier["kontakt_epost"])
            verdier["regnskapsaar"] = int(cfg.get("regnskapsaar", verdier["regnskapsaar"]))

            rr = cfg.get("resultatregnskap", {})
            verdier["salgsinntekter"] = int(rr.get("driftsinntekter", {}).get("salgsinntekter", 0))
            verdier["andre_driftsinntekter"] = int(rr.get("driftsinntekter", {}).get("andre_driftsinntekter", 0))
            verdier["loennskostnader"] = int(rr.get("driftskostnader", {}).get("loennskostnader", 0))
            verdier["avskrivninger"] = int(rr.get("driftskostnader", {}).get("avskrivninger", 0))
            verdier["andre_driftskostnader"] = int(rr.get("driftskostnader", {}).get("andre_driftskostnader", 5500))
            verdier["utbytte_fra_datterselskap"] = int(rr.get("finansposter", {}).get("utbytte_fra_datterselskap", 0))
            verdier["andre_finansinntekter"] = int(rr.get("finansposter", {}).get("andre_finansinntekter", 0))
            verdier["rentekostnader"] = int(rr.get("finansposter", {}).get("rentekostnader", 0))
            verdier["andre_finanskostnader"] = int(rr.get("finansposter", {}).get("andre_finanskostnader", 0))

            b = cfg.get("balanse", {})
            anl = b.get("eiendeler", {}).get("anleggsmidler", {})
            oml = b.get("eiendeler", {}).get("omloepmidler", {})
            ek = b.get("egenkapital_og_gjeld", {}).get("egenkapital", {})
            lg = b.get("egenkapital_og_gjeld", {}).get("langsiktig_gjeld", {})
            kg = b.get("egenkapital_og_gjeld", {}).get("kortsiktig_gjeld", {})
            verdier["aksjer_i_datterselskap"] = int(anl.get("aksjer_i_datterselskap", 100000))
            verdier["andre_aksjer"] = int(anl.get("andre_aksjer", 0))
            verdier["langsiktige_fordringer"] = int(anl.get("langsiktige_fordringer", 0))
            verdier["kortsiktige_fordringer"] = int(oml.get("kortsiktige_fordringer", 0))
            verdier["bankinnskudd"] = int(oml.get("bankinnskudd", 1200))
            verdier["ek_aksjekapital"] = int(ek.get("aksjekapital", 30000))
            verdier["overkursfond"] = int(ek.get("overkursfond", 0))
            verdier["annen_egenkapital"] = int(ek.get("annen_egenkapital", -34300))
            verdier["laan_fra_aksjonaer"] = int(lg.get("laan_fra_aksjonaer", 105500))
            verdier["andre_langsiktige_laan"] = int(lg.get("andre_langsiktige_laan", 0))
            verdier["leverandoergjeld"] = int(kg.get("leverandoergjeld", 0))
            verdier["skyldige_offentlige_avgifter"] = int(kg.get("skyldige_offentlige_avgifter", 0))
            verdier["annen_kortsiktig_gjeld"] = int(kg.get("annen_kortsiktig_gjeld", 0))

            sm = cfg.get("skattemelding", {})
            verdier["underskudd"] = int(sm.get("underskudd_til_fremfoering", 0))
            verdier["fritaksmetoden"] = bool(sm.get("anvend_fritaksmetoden", False))
            verdier["eierandel_datterselskap"] = int(sm.get("eierandel_datterselskap", 100))

            fa = cfg.get("foregaaende_aar", {})
            frr = fa.get("resultatregnskap", {})
            fb_ = fa.get("balanse", {})
            fanl = fb_.get("eiendeler", {}).get("anleggsmidler", {})
            foml = fb_.get("eiendeler", {}).get("omloepmidler", {})
            fek_ = fb_.get("egenkapital_og_gjeld", {}).get("egenkapital", {})
            flg_ = fb_.get("egenkapital_og_gjeld", {}).get("langsiktig_gjeld", {})
            fkg_ = fb_.get("egenkapital_og_gjeld", {}).get("kortsiktig_gjeld", {})
            verdier["f_salgsinntekter"] = int(frr.get("driftsinntekter", {}).get("salgsinntekter", 0))
            verdier["f_andre_driftsinntekter"] = int(frr.get("driftsinntekter", {}).get("andre_driftsinntekter", 0))
            verdier["f_loennskostnader"] = int(frr.get("driftskostnader", {}).get("loennskostnader", 0))
            verdier["f_avskrivninger"] = int(frr.get("driftskostnader", {}).get("avskrivninger", 0))
            verdier["f_andre_driftskostnader"] = int(frr.get("driftskostnader", {}).get("andre_driftskostnader", 0))
            verdier["f_utbytte_fra_datterselskap"] = int(frr.get("finansposter", {}).get("utbytte_fra_datterselskap", 0))
            verdier["f_andre_finansinntekter"] = int(frr.get("finansposter", {}).get("andre_finansinntekter", 0))
            verdier["f_rentekostnader"] = int(frr.get("finansposter", {}).get("rentekostnader", 0))
            verdier["f_andre_finanskostnader"] = int(frr.get("finansposter", {}).get("andre_finanskostnader", 0))
            verdier["f_aksjer_i_datterselskap"] = int(fanl.get("aksjer_i_datterselskap", 0))
            verdier["f_andre_aksjer"] = int(fanl.get("andre_aksjer", 0))
            verdier["f_langsiktige_fordringer"] = int(fanl.get("langsiktige_fordringer", 0))
            verdier["f_kortsiktige_fordringer"] = int(foml.get("kortsiktige_fordringer", 0))
            verdier["f_bankinnskudd"] = int(foml.get("bankinnskudd", 0))
            verdier["f_ek_aksjekapital"] = int(fek_.get("aksjekapital", 0))
            verdier["f_overkursfond"] = int(fek_.get("overkursfond", 0))
            verdier["f_annen_egenkapital"] = int(fek_.get("annen_egenkapital", 0))
            verdier["f_laan_fra_aksjonaer"] = int(flg_.get("laan_fra_aksjonaer", 0))
            verdier["f_andre_langsiktige_laan"] = int(flg_.get("andre_langsiktige_laan", 0))
            verdier["f_leverandoergjeld"] = int(fkg_.get("leverandoergjeld", 0))
            verdier["f_skyldige_offentlige_avgifter"] = int(fkg_.get("skyldige_offentlige_avgifter", 0))
            verdier["f_annen_kortsiktig_gjeld"] = int(fkg_.get("annen_kortsiktig_gjeld", 0))

            aksjonaerer_raw = cfg.get("aksjonaerer", [])
            verdier["antall_aksjonaerer"] = len(aksjonaerer_raw)
            for i, a in enumerate(aksjonaerer_raw):
                verdier[f"a_navn_{i}"] = a.get("navn", "")
                verdier[f"a_fnr_{i}"] = str(a.get("fodselsnummer", ""))
                verdier[f"a_aksjer_{i}"] = int(a.get("antall_aksjer", 1))
                verdier[f"a_klasse_{i}"] = a.get("aksjeklasse", "ordinære")
                verdier[f"a_utbytte_{i}"] = int(a.get("utbytte_utbetalt", 0))
                verdier[f"a_kap_{i}"] = int(a.get("innbetalt_kapital_per_aksje", 0))
        except Exception:
            pass  # Feil i config.yaml — bruk defaults

    for k, v in verdier.items():
        st.session_state[k] = v
    st.session_state["initialisert"] = True


def lagre_config():
    """Skriver gjeldende verdier til config.yaml."""
    antall = int(st.session_state.get("antall_aksjonaerer", 1))
    data = {
        "selskap": {
            "navn": st.session_state["navn"],
            "org_nummer": st.session_state["org_nummer"],
            "daglig_leder": st.session_state["daglig_leder"],
            "styreleder": st.session_state["styreleder"],
            "forretningsadresse": st.session_state["forretningsadresse"],
            "stiftelsesaar": int(st.session_state["stiftelsesaar"]),
            "aksjekapital": int(st.session_state["aksjekapital"]),
            "kontakt_epost": st.session_state["kontakt_epost"],
        },
        "regnskapsaar": int(st.session_state["regnskapsaar"]),
        "resultatregnskap": {
            "driftsinntekter": {
                "salgsinntekter": int(st.session_state["salgsinntekter"]),
                "andre_driftsinntekter": int(st.session_state["andre_driftsinntekter"]),
            },
            "driftskostnader": {
                "loennskostnader": int(st.session_state["loennskostnader"]),
                "avskrivninger": int(st.session_state["avskrivninger"]),
                "andre_driftskostnader": int(st.session_state["andre_driftskostnader"]),
            },
            "finansposter": {
                "utbytte_fra_datterselskap": int(st.session_state["utbytte_fra_datterselskap"]),
                "andre_finansinntekter": int(st.session_state["andre_finansinntekter"]),
                "rentekostnader": int(st.session_state["rentekostnader"]),
                "andre_finanskostnader": int(st.session_state["andre_finanskostnader"]),
            },
        },
        "balanse": {
            "eiendeler": {
                "anleggsmidler": {
                    "aksjer_i_datterselskap": int(st.session_state["aksjer_i_datterselskap"]),
                    "andre_aksjer": int(st.session_state["andre_aksjer"]),
                    "langsiktige_fordringer": int(st.session_state["langsiktige_fordringer"]),
                },
                "omloepmidler": {
                    "kortsiktige_fordringer": int(st.session_state["kortsiktige_fordringer"]),
                    "bankinnskudd": int(st.session_state["bankinnskudd"]),
                },
            },
            "egenkapital_og_gjeld": {
                "egenkapital": {
                    "aksjekapital": int(st.session_state["ek_aksjekapital"]),
                    "overkursfond": int(st.session_state["overkursfond"]),
                    "annen_egenkapital": int(st.session_state["annen_egenkapital"]),
                },
                "langsiktig_gjeld": {
                    "laan_fra_aksjonaer": int(st.session_state["laan_fra_aksjonaer"]),
                    "andre_langsiktige_laan": int(st.session_state["andre_langsiktige_laan"]),
                },
                "kortsiktig_gjeld": {
                    "leverandoergjeld": int(st.session_state["leverandoergjeld"]),
                    "skyldige_offentlige_avgifter": int(st.session_state["skyldige_offentlige_avgifter"]),
                    "annen_kortsiktig_gjeld": int(st.session_state["annen_kortsiktig_gjeld"]),
                },
            },
        },
        "foregaaende_aar": {
            "resultatregnskap": {
                "driftsinntekter": {
                    "salgsinntekter": int(st.session_state["f_salgsinntekter"]),
                    "andre_driftsinntekter": int(st.session_state["f_andre_driftsinntekter"]),
                },
                "driftskostnader": {
                    "loennskostnader": int(st.session_state["f_loennskostnader"]),
                    "avskrivninger": int(st.session_state["f_avskrivninger"]),
                    "andre_driftskostnader": int(st.session_state["f_andre_driftskostnader"]),
                },
                "finansposter": {
                    "utbytte_fra_datterselskap": int(st.session_state["f_utbytte_fra_datterselskap"]),
                    "andre_finansinntekter": int(st.session_state["f_andre_finansinntekter"]),
                    "rentekostnader": int(st.session_state["f_rentekostnader"]),
                    "andre_finanskostnader": int(st.session_state["f_andre_finanskostnader"]),
                },
            },
            "balanse": {
                "eiendeler": {
                    "anleggsmidler": {
                        "aksjer_i_datterselskap": int(st.session_state["f_aksjer_i_datterselskap"]),
                        "andre_aksjer": int(st.session_state["f_andre_aksjer"]),
                        "langsiktige_fordringer": int(st.session_state["f_langsiktige_fordringer"]),
                    },
                    "omloepmidler": {
                        "kortsiktige_fordringer": int(st.session_state["f_kortsiktige_fordringer"]),
                        "bankinnskudd": int(st.session_state["f_bankinnskudd"]),
                    },
                },
                "egenkapital_og_gjeld": {
                    "egenkapital": {
                        "aksjekapital": int(st.session_state["f_ek_aksjekapital"]),
                        "overkursfond": int(st.session_state["f_overkursfond"]),
                        "annen_egenkapital": int(st.session_state["f_annen_egenkapital"]),
                    },
                    "langsiktig_gjeld": {
                        "laan_fra_aksjonaer": int(st.session_state["f_laan_fra_aksjonaer"]),
                        "andre_langsiktige_laan": int(st.session_state["f_andre_langsiktige_laan"]),
                    },
                    "kortsiktig_gjeld": {
                        "leverandoergjeld": int(st.session_state["f_leverandoergjeld"]),
                        "skyldige_offentlige_avgifter": int(st.session_state["f_skyldige_offentlige_avgifter"]),
                        "annen_kortsiktig_gjeld": int(st.session_state["f_annen_kortsiktig_gjeld"]),
                    },
                },
            },
        },
        "skattemelding": {
            "underskudd_til_fremfoering": int(st.session_state["underskudd"]),
            "anvend_fritaksmetoden": bool(st.session_state["fritaksmetoden"]),
            "eierandel_datterselskap": int(st.session_state["eierandel_datterselskap"]),
        },
        "aksjonaerer": [
            {
                "navn": st.session_state.get(f"a_navn_{i}", ""),
                "fodselsnummer": st.session_state.get(f"a_fnr_{i}", ""),
                "antall_aksjer": int(st.session_state.get(f"a_aksjer_{i}", 1)),
                "aksjeklasse": st.session_state.get(f"a_klasse_{i}", "ordinære"),
                "utbytte_utbetalt": int(st.session_state.get(f"a_utbytte_{i}", 0)),
                "innbetalt_kapital_per_aksje": int(st.session_state.get(f"a_kap_{i}", 0)),
            }
            for i in range(antall)
        ],
    }
    with open(CONFIG_FIL, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)


_WENCHE_DIR = Path.home() / ".wenche"
_REQUEST_ID_FIL = _WENCHE_DIR / "systembruker_request_id.txt"


def _lagre_request_id(request_id: str) -> None:
    _WENCHE_DIR.mkdir(exist_ok=True)
    _REQUEST_ID_FIL.write_text(request_id, encoding="utf-8")


def _les_request_id() -> str:
    if _REQUEST_ID_FIL.exists():
        return _REQUEST_ID_FIL.read_text(encoding="utf-8").strip()
    return ""


# ---------------------------------------------------------------------------
# Side-oppsett
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Wenche", layout="wide")
st.title("Wenche")
st.caption("Enkel innsending av regnskap og skattedokumenter til norske myndigheter")

fane_oppsett, fane_selskap, fane_regnskap, fane_aksjonaerer, fane_dokumenter, fane_send = st.tabs(
    ["1. Oppsett", "2. Selskap", "3. Regnskap og balanse", "4. Aksjonærer", "5. Dokumenter", "6. Send til Altinn"]
)


# ---------------------------------------------------------------------------
# Fane 1: Oppsett og tilkoblingssjekk
# ---------------------------------------------------------------------------

def _sjekk_konfig() -> list[tuple[bool, str, str]]:
    """
    Kjører statiske konfigurasjonsjekker uten nettverkskall.
    Returnerer liste av (ok, tittel, detalj).
    """
    resultater = []

    client_id = os.getenv("MASKINPORTEN_CLIENT_ID")
    resultater.append((
        bool(client_id),
        "MASKINPORTEN_CLIENT_ID",
        "Satt" if client_id else "Mangler — legg til i .env-filen",
    ))

    kid = os.getenv("MASKINPORTEN_KID")
    resultater.append((
        bool(kid),
        "MASKINPORTEN_KID",
        "Satt" if kid else "Mangler — legg til i .env-filen",
    ))

    orgnr = os.getenv("ORG_NUMMER")
    resultater.append((
        bool(orgnr),
        "ORG_NUMMER",
        "Satt" if orgnr else "Mangler — legg til i konfigurasjonsskjemaet over",
    ))

    nokkel_sti = os.getenv("MASKINPORTEN_PRIVAT_NOKKEL", "maskinporten_privat.pem")
    nokkel_ok = Path(nokkel_sti).exists()
    resultater.append((
        nokkel_ok,
        "Privat nøkkel",
        f"Funnet: {nokkel_sti}" if nokkel_ok else f"Finner ikke filen: {nokkel_sti}",
    ))

    env = os.getenv("WENCHE_ENV", "prod")
    resultater.append((
        True,
        "Miljø",
        f"{'Testmiljø (tt02)' if env == 'test' else 'Produksjon'} — endre med WENCHE_ENV=test i .env",
    ))

    return resultater


with fane_oppsett:
    st.subheader("Steg 1 av 6 — Oppsett og tilkobling")
    st.caption(
        "Fyll inn Maskinporten-konfigurasjonen din og test tilkoblingen mot Altinn "
        "før du begynner å fylle inn selskapsinformasjon."
    )

    # --- Konfigurasjonsskjema ---
    st.markdown("#### Konfigurasjon")
    st.info(
        "Klient-ID og Nøkkel-ID finner du i [Digdirs selvbetjeningsportal](https://sjolvbetjening.samarbeid.digdir.no/) "
        "under din Maskinporten-klient. Se [oppsettsveiledningen](https://olefredrik.github.io/Wenche/oppsett/) "
        "hvis du ikke har opprettet en klient ennå.",
        icon="ℹ️",
    )
    st.caption(
        "Verdiene lagres i `.env`-filen i arbeidsmappen din og brukes automatisk ved neste oppstart."
    )

    dot_env_fil = Path(".env")

    col1, col2 = st.columns(2)
    with col1:
        inp_client_id = st.text_input(
            "Klient-ID",
            value=os.getenv("MASKINPORTEN_CLIENT_ID", ""),
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            help="UUID-en til Maskinporten-klienten din fra Digdirs selvbetjeningsportal. Lagres som MASKINPORTEN_CLIENT_ID i .env.",
        )
        inp_kid = st.text_input(
            "Nøkkel-ID",
            value=os.getenv("MASKINPORTEN_KID", ""),
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            help="UUID-en som portalen tildelte nøkkelen din — synlig i nøkkellisten under klienten. Lagres som MASKINPORTEN_KID i .env.",
        )
        inp_orgnr = st.text_input(
            "Organisasjonsnummer",
            value=os.getenv("ORG_NUMMER", ""),
            placeholder="123456789",
            help="Organisasjonsnummeret til selskapet du sender inn på vegne av. Lagres som ORG_NUMMER i .env.",
        )
    with col2:
        inp_env = st.selectbox(
            "Miljø",
            options=["prod", "test"],
            index=0 if os.getenv("WENCHE_ENV", "prod") == "prod" else 1,
            help="Velg 'test' for å bruke Altinn tt02-testmiljøet. Lagres som WENCHE_ENV i .env.",
        )
        opplastet_nokkel = st.file_uploader(
            "Last opp privat nøkkel (.pem)",
            type=["pem"],
            help="Din maskinporten_privat.pem-fil. Lagres lokalt — sendes aldri til noen server.",
        )

    if st.button("Lagre konfigurasjon", type="primary"):
        dot_env_fil.touch(exist_ok=True)
        from dotenv import set_key
        endringer = False

        if inp_client_id:
            set_key(str(dot_env_fil), "MASKINPORTEN_CLIENT_ID", inp_client_id)
            os.environ["MASKINPORTEN_CLIENT_ID"] = inp_client_id
            endringer = True

        if inp_kid:
            set_key(str(dot_env_fil), "MASKINPORTEN_KID", inp_kid)
            os.environ["MASKINPORTEN_KID"] = inp_kid
            endringer = True

        if inp_orgnr:
            set_key(str(dot_env_fil), "ORG_NUMMER", inp_orgnr)
            os.environ["ORG_NUMMER"] = inp_orgnr
            endringer = True

        set_key(str(dot_env_fil), "WENCHE_ENV", inp_env)
        os.environ["WENCHE_ENV"] = inp_env
        endringer = True

        if opplastet_nokkel is not None:
            nokkel_sti = Path("maskinporten_privat.pem")
            nokkel_sti.write_bytes(opplastet_nokkel.read())
            nokkel_sti.chmod(0o600)
            set_key(str(dot_env_fil), "MASKINPORTEN_PRIVAT_NOKKEL", str(nokkel_sti))
            os.environ["MASKINPORTEN_PRIVAT_NOKKEL"] = str(nokkel_sti)
            endringer = True

        if endringer:
            st.success("Konfigurasjon lagret.")
            st.rerun()

    # --- Statusoversikt ---
    st.markdown("---")
    st.markdown("#### Status")
    sjekker = _sjekk_konfig()
    alle_ok = all(ok for ok, _, _ in sjekker)
    for ok, tittel, detalj in sjekker:
        ikon = "✅" if ok else "⚠️"
        st.markdown(f"{ikon} **{tittel}** — {detalj}")

    # --- Tilkoblingstest ---
    st.markdown("---")
    st.markdown("#### Tilkoblingstest")
    st.caption(
        "Henter et midlertidig token fra Maskinporten og veksler det mot et Altinn-token. "
        "Ingen data sendes inn."
    )

    if not alle_ok:
        st.warning("Fiks konfigurasjonsfeilene ovenfor og lagre før du tester tilkoblingen.")
    else:
        if st.button("Test tilkobling mot Altinn", type="primary"):
            with st.spinner("Kobler til Maskinporten og Altinn..."):
                try:
                    auth.login()
                    st.success(
                        "Tilkobling OK — Maskinporten og Altinn svarte som forventet. "
                        "Gå videre til steg 2 for å fylle inn selskapsinformasjon."
                    )
                except RuntimeError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"Uventet feil: {e}")

    # --- Systembruker-oppsett ---
    st.markdown("---")
    with st.expander("Systembruker-oppsett (gjøres én gang per miljø)", expanded=False):
        st.caption(
            "Altinn 3 krever at Wenche er registrert som et leverandørsystem og at organisasjonen din "
            "har godkjent en systembruker. Dette gjøres én gang — og på nytt hvis du bytter miljø."
        )

        if not alle_ok:
            st.warning("Fiks konfigurasjonsfeilene ovenfor og lagre før du setter opp systembruker.")
        else:
            st.markdown("**Steg 1 — Registrer Wenche i systemregisteret**")
            st.caption("Registrerer Wenche i Altinns systemregister med riktige tilgangsrettigheter. Kan kjøres på nytt uten skade — oppdaterer automatisk hvis systemet allerede finnes.")
            if st.button("Registrer Wenche i systemregisteret"):
                with st.spinner("Registrerer system..."):
                    try:
                        token = auth.login_admin()
                        orgnr = os.getenv("ORG_NUMMER")
                        client_id = os.getenv("MASKINPORTEN_CLIENT_ID")
                        svar = systembruker.registrer_system(token, orgnr, client_id)
                        if svar.get("oppdatert"):
                            st.success("System oppdatert i systemregisteret.")
                        else:
                            st.success("System registrert i systemregisteret.")
                    except Exception as e:
                        st.error(f"Feil: {e}")

            st.markdown("**Steg 2 — Opprett systembrukerforespørsel**")
            st.caption("Sender en forespørsel til organisasjonen og returnerer en godkjenningslenke.")
            if st.button("Opprett systembrukerforespørsel"):
                with st.spinner("Oppretter forespørsel..."):
                    try:
                        token = auth.login_admin()
                        orgnr = os.getenv("ORG_NUMMER")
                        svar = systembruker.opprett_forespørsel(token, orgnr, orgnr)
                        request_id = svar.get("id", "")
                        if request_id:
                            _lagre_request_id(request_id)
                        st.success(f"Forespørsel opprettet (status: {svar['status']})")
                        st.info(f"**Steg 3 — Godkjenn i nettleseren**\n\nÅpne lenken nedenfor, logg inn og godkjenn tilgangen for organisasjonen din:\n\n{svar['confirmUrl']}")
                    except Exception as e:
                        st.error(f"Feil: {e}")

            st.markdown("**Sjekk godkjenningsstatus**")
            st.caption("Sjekker om systembrukerforespørselen er godkjent av organisasjonen.")
            if st.button("Sjekk status"):
                request_id = _les_request_id()
                if not request_id:
                    st.warning("Ingen lagret forespørsels-ID. Opprett en systembrukerforespørsel først (steg 2).")
                else:
                    with st.spinner("Henter status..."):
                        try:
                            token = auth.login_admin()
                            svar = systembruker.hent_forespørsel_status(token, request_id)
                            status = svar.get("status", "ukjent")
                            if status == "Accepted":
                                st.success(f"Systembruker er godkjent. Du kan nå logge inn og sende inn dokumenter.")
                            elif status == "New":
                                st.info(f"Forespørselen venter på godkjenning. Bruk lenken fra steg 2 til å godkjenne i nettleseren.")
                            elif status == "Rejected":
                                st.error(f"Forespørselen ble avvist. Opprett en ny forespørsel.")
                            else:
                                st.info(f"Status: {status}")
                        except Exception as e:
                            st.error(f"Feil: {e}")

        st.markdown(
            "Trenger du hjelp? Se [oppsettsveiledningen](https://olefredrik.github.io/Wenche/oppsett/) i dokumentasjonen."
        )


# ---------------------------------------------------------------------------
# Fane 2: Selskapsopplysninger
# ---------------------------------------------------------------------------

with fane_selskap:
    st.subheader("Steg 2 av 6 — Selskapsopplysninger")
    st.caption("Fyll inn grunnleggende informasjon om selskapet. Fortsett til steg 3 når du er ferdig.")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Selskapsnavn", key="navn")
        st.text_input("Organisasjonsnummer (9 siffer)", key="org_nummer")
        st.text_input("Daglig leder", key="daglig_leder")
        st.text_input("Styreleder", key="styreleder")
    with col2:
        st.text_input("Forretningsadresse", key="forretningsadresse")
        st.number_input("Stiftelsesår", min_value=1900, max_value=2100, key="stiftelsesaar")
        st.number_input("Aksjekapital (NOK)", min_value=0, step=1000, key="aksjekapital")
        st.text_input(
            "Kontakt-e-post",
            key="kontakt_epost",
            help="Påkrevd for aksjonærregisteroppgave (RF-1086).",
        )
        st.number_input("Regnskapsår", min_value=2000, max_value=2100, key="regnskapsaar")

    st.divider()
    if st.button("Lagre selskapsopplysninger", type="primary"):
        lagre_config()
        st.success(f"Lagret til {CONFIG_FIL.resolve()}")


# ---------------------------------------------------------------------------
# Fane 2: Regnskap og balanse
# ---------------------------------------------------------------------------

with fane_regnskap:
    st.subheader("Steg 3 av 6 — Regnskap og balanse")
    st.caption("Fyll inn tall fra resultatregnskapet og balansen. Fortsett til steg 4 når du er ferdig.")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Driftsinntekter**")
        st.number_input("Salgsinntekter", min_value=0, step=1000, key="salgsinntekter")
        st.number_input("Andre driftsinntekter", min_value=0, step=1000, key="andre_driftsinntekter")
        sum_driftsinntekter = st.session_state["salgsinntekter"] + st.session_state["andre_driftsinntekter"]
        st.metric("Sum driftsinntekter", f"{sum_driftsinntekter:,} kr".replace(",", " "))

        st.markdown("**Driftskostnader**")
        st.number_input("Lønnskostnader", min_value=0, step=1000, key="loennskostnader")
        st.number_input("Avskrivninger", min_value=0, step=1000, key="avskrivninger")
        st.number_input("Andre driftskostnader", min_value=0, step=500, key="andre_driftskostnader")
        sum_driftskostnader = (
            st.session_state["loennskostnader"]
            + st.session_state["avskrivninger"]
            + st.session_state["andre_driftskostnader"]
        )
        st.metric("Sum driftskostnader", f"{sum_driftskostnader:,} kr".replace(",", " "))

        driftsresultat = sum_driftsinntekter - sum_driftskostnader
        st.metric("Driftsresultat", f"{driftsresultat:,} kr".replace(",", " "))

    with col2:
        st.markdown("**Finansposter**")
        st.number_input(
            "Utbytte fra datterselskap",
            min_value=0, step=1000, key="utbytte_fra_datterselskap",
            help="Utbytte mottatt fra heleide datterselskaper i regnskapsåret. Inngår i vurderingen av fritaksmetoden.",
        )
        st.number_input("Andre finansinntekter", min_value=0, step=1000, key="andre_finansinntekter")
        st.number_input("Rentekostnader", min_value=0, step=1000, key="rentekostnader")
        st.number_input("Andre finanskostnader", min_value=0, step=1000, key="andre_finanskostnader")
        resultat_foer_skatt = (
            driftsresultat
            + st.session_state["utbytte_fra_datterselskap"]
            + st.session_state["andre_finansinntekter"]
            - st.session_state["rentekostnader"]
            - st.session_state["andre_finanskostnader"]
        )
        st.metric("Resultat før skatt", f"{resultat_foer_skatt:,} kr".replace(",", " "))

    st.divider()
    st.subheader("Balanse")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Eiendeler**")
        st.markdown("*Anleggsmidler*")
        st.number_input(
            "Aksjer i datterselskap",
            min_value=0, step=1000, key="aksjer_i_datterselskap",
            help="Kostpris for aksjer i heleide datterselskaper (typisk over 90 % eierandel).",
        )
        st.number_input("Andre aksjer", min_value=0, step=1000, key="andre_aksjer")
        st.number_input("Langsiktige fordringer", min_value=0, step=1000, key="langsiktige_fordringer")
        sum_anleggsmidler = (
            st.session_state["aksjer_i_datterselskap"]
            + st.session_state["andre_aksjer"]
            + st.session_state["langsiktige_fordringer"]
        )

        st.markdown("*Omløpsmidler*")
        st.number_input("Kortsiktige fordringer", min_value=0, step=1000, key="kortsiktige_fordringer")
        st.number_input("Bankinnskudd", min_value=0, step=100, key="bankinnskudd")
        sum_omloepmidler = st.session_state["kortsiktige_fordringer"] + st.session_state["bankinnskudd"]
        sum_eiendeler = sum_anleggsmidler + sum_omloepmidler
        st.metric("Sum eiendeler", f"{sum_eiendeler:,} kr".replace(",", " "))

    with col2:
        st.markdown("**Egenkapital og gjeld**")
        st.markdown("*Egenkapital*")
        st.number_input("Aksjekapital (balanse)", min_value=0, step=1000, key="ek_aksjekapital")
        st.number_input("Overkursfond", step=1000, key="overkursfond")
        st.number_input("Annen egenkapital (negativ ved underskudd)", step=1000, key="annen_egenkapital")
        sum_egenkapital = (
            st.session_state["ek_aksjekapital"]
            + st.session_state["overkursfond"]
            + st.session_state["annen_egenkapital"]
        )

        st.markdown("*Langsiktig gjeld*")
        st.number_input("Lån fra aksjonær", min_value=0, step=1000, key="laan_fra_aksjonaer")
        st.number_input("Andre langsiktige lån", min_value=0, step=1000, key="andre_langsiktige_laan")
        sum_langsiktig_gjeld = (
            st.session_state["laan_fra_aksjonaer"] + st.session_state["andre_langsiktige_laan"]
        )

        st.markdown("*Kortsiktig gjeld*")
        st.number_input("Leverandørgjeld", min_value=0, step=1000, key="leverandoergjeld")
        st.number_input("Skyldige offentlige avgifter", min_value=0, step=1000, key="skyldige_offentlige_avgifter")
        st.number_input("Annen kortsiktig gjeld", min_value=0, step=1000, key="annen_kortsiktig_gjeld")
        sum_kortsiktig_gjeld = (
            st.session_state["leverandoergjeld"]
            + st.session_state["skyldige_offentlige_avgifter"]
            + st.session_state["annen_kortsiktig_gjeld"]
        )
        sum_ek_og_gjeld = sum_egenkapital + sum_langsiktig_gjeld + sum_kortsiktig_gjeld
        st.metric("Sum egenkapital og gjeld", f"{sum_ek_og_gjeld:,} kr".replace(",", " "))

    differanse = sum_eiendeler - sum_ek_og_gjeld
    if differanse == 0:
        st.success("Balansen stemmer")
    else:
        st.error(f"Balansen stemmer ikke. Differanse: {differanse:,} kr".replace(",", " "))

    st.divider()
    with st.expander("Sammenligningstall — foregående år (påkrevd, rskl. § 6-6)", expanded=False):
        st.caption(
            "Fyll inn tilsvarende tall fra fjorårets regnskap. "
            "Disse brukes som sammenligningstall i årsregnskapet som sendes til Brønnøysundregistrene."
        )
        st.subheader("Resultatregnskap")
        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Salgsinntekter", step=1000, key="f_salgsinntekter")
            st.number_input("Andre driftsinntekter", step=1000, key="f_andre_driftsinntekter")
            st.number_input("Lønnskostnader", step=1000, key="f_loennskostnader")
            st.number_input("Avskrivninger", step=1000, key="f_avskrivninger")
            st.number_input("Andre driftskostnader", step=1000, key="f_andre_driftskostnader")
        with col2:
            st.number_input("Utbytte fra datterselskap", step=1000, key="f_utbytte_fra_datterselskap")
            st.number_input("Andre finansinntekter", step=1000, key="f_andre_finansinntekter")
            st.number_input("Rentekostnader", step=1000, key="f_rentekostnader")
            st.number_input("Andre finanskostnader", step=1000, key="f_andre_finanskostnader")

        st.subheader("Balanse")
        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Aksjer i datterselskap", step=1000, key="f_aksjer_i_datterselskap")
            st.number_input("Andre aksjer", step=1000, key="f_andre_aksjer")
            st.number_input("Langsiktige fordringer", step=1000, key="f_langsiktige_fordringer")
            st.number_input("Kortsiktige fordringer", step=1000, key="f_kortsiktige_fordringer")
            st.number_input("Bankinnskudd", step=1000, key="f_bankinnskudd")
        with col2:
            st.number_input("Aksjekapital", step=1000, key="f_ek_aksjekapital")
            st.number_input("Overkursfond", step=1000, key="f_overkursfond")
            st.number_input("Annen egenkapital", step=1000, key="f_annen_egenkapital")
            st.number_input("Lån fra aksjonær", step=1000, key="f_laan_fra_aksjonaer")
            st.number_input("Andre langsiktige lån", step=1000, key="f_andre_langsiktige_laan")
            st.number_input("Leverandørgjeld", step=1000, key="f_leverandoergjeld")
            st.number_input("Skyldige offentlige avgifter", step=1000, key="f_skyldige_offentlige_avgifter")
            st.number_input("Annen kortsiktig gjeld", step=1000, key="f_annen_kortsiktig_gjeld")

    if st.button("Lagre regnskapstall", type="primary"):
        lagre_config()
        st.success(f"Lagret til {CONFIG_FIL.resolve()}")


# ---------------------------------------------------------------------------
# Fane 3: Aksjonærer
# ---------------------------------------------------------------------------

with fane_aksjonaerer:
    st.subheader("Steg 4 av 6 — Aksjonærer")
    st.caption("Fyll inn opplysninger om aksjonærene. Fortsett til steg 5 når du er ferdig.")
    st.number_input("Antall aksjonærer", min_value=1, max_value=20, step=1, key="antall_aksjonaerer")
    antall = int(st.session_state["antall_aksjonaerer"])

    for i in range(antall):
        if f"a_navn_{i}" not in st.session_state:
            st.session_state[f"a_navn_{i}"] = ""
            st.session_state[f"a_fnr_{i}"] = ""
            st.session_state[f"a_aksjer_{i}"] = 1
            st.session_state[f"a_klasse_{i}"] = "ordinære"
            st.session_state[f"a_utbytte_{i}"] = 0
            st.session_state[f"a_kap_{i}"] = 0

        with st.expander(f"Aksjonær {i + 1}", expanded=(i == 0)):
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Navn", key=f"a_navn_{i}")
                st.text_input("Fødselsnummer (11 siffer)", key=f"a_fnr_{i}")
                st.number_input("Antall aksjer", min_value=1, key=f"a_aksjer_{i}")
            with c2:
                st.text_input("Aksjeklasse", key=f"a_klasse_{i}")
                st.number_input("Utbytte utbetalt (NOK)", min_value=0, key=f"a_utbytte_{i}")
                st.number_input(
                    "Innbetalt kapital per aksje (NOK)", min_value=0, key=f"a_kap_{i}",
                    help="Aksjekapital delt på antall aksjer. Eks: 30 000 kr / 100 aksjer = 300 kr per aksje.",
                )

    if st.button("Lagre aksjonærer", type="primary"):
        lagre_config()
        st.success(f"Lagret til {CONFIG_FIL.resolve()}")


# ---------------------------------------------------------------------------
# Fane 4: Dokumenter
# ---------------------------------------------------------------------------

with fane_dokumenter:
    st.subheader("Steg 5 av 6 — Last ned dokumenter")
    st.caption("Generer og last ned dokumentene for gjennomgang. Gå til steg 5 når du er klar til å sende inn.")
    st.markdown("**Skattemelding-innstillinger**")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input(
            "Fremførbart underskudd fra tidligere år (NOK)", min_value=0, step=1000, key="underskudd",
            help="Finnes i fjorårets skattemelding (RF-1028). Sett til 0 hvis selskapet er nytt eller ikke har fremførbart underskudd.",
        )
    with col2:
        st.checkbox(
            "Anvend fritaksmetoden",
            key="fritaksmetoden",
            help=(
                "Gjelder dersom selskapet har mottatt utbytte fra datterselskaper. "
                "Ved eierandel ≥ 90 % er hele utbyttet skattefritt. "
                "Ved eierandel < 90 % er 3 % skattepliktig (sjablonregelen, sktl. § 2-38 sjette ledd)."
            ),
        )
        if st.session_state["fritaksmetoden"]:
            st.number_input(
                "Eierandel i datterselskap (%)",
                min_value=0,
                max_value=100,
                step=1,
                key="eierandel_datterselskap",
                help=(
                    "Selskapets eierandel i datterselskapet som utbytte er mottatt fra. "
                    "Ved eierandel ≥ 90 % er hele utbyttet fritatt (0 % skattepliktig). "
                    "Ved eierandel < 90 % gjelder sjablonregelen: 3 % er skattepliktig."
                ),
            )
        if int(st.session_state.get("utbytte_fra_datterselskap", 0)) > 0 and not st.session_state["fritaksmetoden"]:
            st.info(
                "Du har ført utbytte fra datterselskap. Husk å krysse av for fritaksmetoden "
                "dersom selskapet kvalifiserer (skatteloven § 2-38)."
            )

    st.divider()

    def bygg_regnskap() -> Aarsregnskap:
        antall_aksjona = int(st.session_state.get("antall_aksjonaerer", 1))
        utbytte_utbetalt = sum(
            int(st.session_state.get(f"a_utbytte_{i}", 0)) for i in range(antall_aksjona)
        )
        return Aarsregnskap(
            utbytte_utbetalt=utbytte_utbetalt,
            selskap=Selskap(
                navn=st.session_state["navn"],
                org_nummer=st.session_state["org_nummer"],
                daglig_leder=st.session_state["daglig_leder"],
                styreleder=st.session_state["styreleder"],
                forretningsadresse=st.session_state["forretningsadresse"],
                stiftelsesaar=int(st.session_state["stiftelsesaar"]),
                aksjekapital=int(st.session_state["aksjekapital"]),
                kontakt_epost=st.session_state.get("kontakt_epost", ""),
            ),
            regnskapsaar=int(st.session_state["regnskapsaar"]),
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(
                    salgsinntekter=int(st.session_state["salgsinntekter"]),
                    andre_driftsinntekter=int(st.session_state["andre_driftsinntekter"]),
                ),
                driftskostnader=Driftskostnader(
                    loennskostnader=int(st.session_state["loennskostnader"]),
                    avskrivninger=int(st.session_state["avskrivninger"]),
                    andre_driftskostnader=int(st.session_state["andre_driftskostnader"]),
                ),
                finansposter=Finansposter(
                    utbytte_fra_datterselskap=int(st.session_state["utbytte_fra_datterselskap"]),
                    andre_finansinntekter=int(st.session_state["andre_finansinntekter"]),
                    rentekostnader=int(st.session_state["rentekostnader"]),
                    andre_finanskostnader=int(st.session_state["andre_finanskostnader"]),
                ),
            ),
            balanse=Balanse(
                eiendeler=Eiendeler(
                    anleggsmidler=Anleggsmidler(
                        aksjer_i_datterselskap=int(st.session_state["aksjer_i_datterselskap"]),
                        andre_aksjer=int(st.session_state["andre_aksjer"]),
                        langsiktige_fordringer=int(st.session_state["langsiktige_fordringer"]),
                    ),
                    omloepmidler=Omloepmidler(
                        kortsiktige_fordringer=int(st.session_state["kortsiktige_fordringer"]),
                        bankinnskudd=int(st.session_state["bankinnskudd"]),
                    ),
                ),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(
                        aksjekapital=int(st.session_state["ek_aksjekapital"]),
                        overkursfond=int(st.session_state["overkursfond"]),
                        annen_egenkapital=int(st.session_state["annen_egenkapital"]),
                    ),
                    langsiktig_gjeld=LangsiktigGjeld(
                        laan_fra_aksjonaer=int(st.session_state["laan_fra_aksjonaer"]),
                        andre_langsiktige_laan=int(st.session_state["andre_langsiktige_laan"]),
                    ),
                    kortsiktig_gjeld=KortsiktigGjeld(
                        leverandoergjeld=int(st.session_state["leverandoergjeld"]),
                        skyldige_offentlige_avgifter=int(st.session_state["skyldige_offentlige_avgifter"]),
                        annen_kortsiktig_gjeld=int(st.session_state["annen_kortsiktig_gjeld"]),
                    ),
                ),
            ),
            foregaaende_aar_resultat=Resultatregnskap(
                driftsinntekter=Driftsinntekter(
                    salgsinntekter=int(st.session_state["f_salgsinntekter"]),
                    andre_driftsinntekter=int(st.session_state["f_andre_driftsinntekter"]),
                ),
                driftskostnader=Driftskostnader(
                    loennskostnader=int(st.session_state["f_loennskostnader"]),
                    avskrivninger=int(st.session_state["f_avskrivninger"]),
                    andre_driftskostnader=int(st.session_state["f_andre_driftskostnader"]),
                ),
                finansposter=Finansposter(
                    utbytte_fra_datterselskap=int(st.session_state["f_utbytte_fra_datterselskap"]),
                    andre_finansinntekter=int(st.session_state["f_andre_finansinntekter"]),
                    rentekostnader=int(st.session_state["f_rentekostnader"]),
                    andre_finanskostnader=int(st.session_state["f_andre_finanskostnader"]),
                ),
            ),
            foregaaende_aar_balanse=Balanse(
                eiendeler=Eiendeler(
                    anleggsmidler=Anleggsmidler(
                        aksjer_i_datterselskap=int(st.session_state["f_aksjer_i_datterselskap"]),
                        andre_aksjer=int(st.session_state["f_andre_aksjer"]),
                        langsiktige_fordringer=int(st.session_state["f_langsiktige_fordringer"]),
                    ),
                    omloepmidler=Omloepmidler(
                        kortsiktige_fordringer=int(st.session_state["f_kortsiktige_fordringer"]),
                        bankinnskudd=int(st.session_state["f_bankinnskudd"]),
                    ),
                ),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(
                        aksjekapital=int(st.session_state["f_ek_aksjekapital"]),
                        overkursfond=int(st.session_state["f_overkursfond"]),
                        annen_egenkapital=int(st.session_state["f_annen_egenkapital"]),
                    ),
                    langsiktig_gjeld=LangsiktigGjeld(
                        laan_fra_aksjonaer=int(st.session_state["f_laan_fra_aksjonaer"]),
                        andre_langsiktige_laan=int(st.session_state["f_andre_langsiktige_laan"]),
                    ),
                    kortsiktig_gjeld=KortsiktigGjeld(
                        leverandoergjeld=int(st.session_state["f_leverandoergjeld"]),
                        skyldige_offentlige_avgifter=int(st.session_state["f_skyldige_offentlige_avgifter"]),
                        annen_kortsiktig_gjeld=int(st.session_state["f_annen_kortsiktig_gjeld"]),
                    ),
                ),
            ),
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Generer skattemelding", use_container_width=True):
            regnskap = bygg_regnskap()
            konfig = SkattemeldingKonfig(
                underskudd_til_fremfoering=int(st.session_state["underskudd"]),
                anvend_fritaksmetoden=bool(st.session_state["fritaksmetoden"]),
                eierandel_datterselskap=int(st.session_state["eierandel_datterselskap"]),
            )
            tekst = sm_modul.generer(regnskap, konfig)
            st.code(tekst, language=None)
            st.download_button(
                "Last ned skattemelding.txt",
                data=tekst.encode("utf-8"),
                file_name=f"skattemelding_{int(st.session_state['regnskapsaar'])}_{st.session_state['org_nummer']}.txt",
                mime="text/plain",
            )

    with col2:
        if st.button("Last ned årsregnskap", use_container_width=True):
            regnskap = bygg_regnskap()
            feil = ar_modul.valider(regnskap)
            if feil:
                for f in feil:
                    st.error(f)
            else:
                orgnr = st.session_state["org_nummer"]
                aar = int(st.session_state["regnskapsaar"])
                st.download_button(
                    "Last ned hovedskjema (XML)",
                    data=generer_hovedskjema(regnskap),
                    file_name=f"aarsregnskap_{aar}_{orgnr}_hovedskjema.xml",
                    mime="application/xml",
                )
                st.download_button(
                    "Last ned underskjema (XML)",
                    data=generer_underskjema(regnskap),
                    file_name=f"aarsregnskap_{aar}_{orgnr}_underskjema.xml",
                    mime="application/xml",
                )

    with col3:
        if st.button("Last ned aksjonærregisteroppgave", use_container_width=True):
            regnskap = bygg_regnskap()
            antall = int(st.session_state["antall_aksjonaerer"])
            aksjonaerer = [
                Aksjonaer(
                    navn=st.session_state.get(f"a_navn_{i}", ""),
                    fodselsnummer=st.session_state.get(f"a_fnr_{i}", ""),
                    antall_aksjer=int(st.session_state.get(f"a_aksjer_{i}", 1)),
                    aksjeklasse=st.session_state.get(f"a_klasse_{i}", "ordinære"),
                    utbytte_utbetalt=int(st.session_state.get(f"a_utbytte_{i}", 0)),
                    innbetalt_kapital_per_aksje=int(st.session_state.get(f"a_kap_{i}", 0)),
                )
                for i in range(antall)
            ]
            oppgave = Aksjonaerregisteroppgave(
                selskap=regnskap.selskap,
                regnskapsaar=int(st.session_state["regnskapsaar"]),
                aksjonaerer=aksjonaerer,
            )
            feil = akr_modul.valider(oppgave)
            if feil:
                for f in feil:
                    st.error(f)
            else:
                base = f"aksjonaerregister_{int(st.session_state['regnskapsaar'])}_{st.session_state['org_nummer']}"
                hoved_xml = akr_modul.generer_hovedskjema_xml(oppgave)
                st.download_button(
                    "Last ned Hovedskjema (RF-1086)",
                    data=hoved_xml,
                    file_name=f"{base}_hovedskjema.xml",
                    mime="application/xml",
                )
                for i, aksjonaer in enumerate(oppgave.aksjonaerer, 1):
                    under_xml = akr_modul.generer_underskjema_xml(aksjonaer, oppgave)
                    st.download_button(
                        f"Last ned Underskjema {i} — {aksjonaer.navn}",
                        data=under_xml,
                        file_name=f"{base}_underskjema_{i}.xml",
                        mime="application/xml",
                    )

# ---------------------------------------------------------------------------
# Fane 5: Send til Altinn
# ---------------------------------------------------------------------------

with fane_send:
    st.subheader("Steg 6 av 6 — Send til Altinn")
    st.caption("Send dokumentene digitalt til Brønnøysundregistrene og Skatteetaten via Altinn.")

    env_valg = st.radio(
        "Miljø",
        options=["test", "prod"],
        format_func=lambda v: "Testmiljø (tt02) — ingen ekte innsending" if v == "test" else "Produksjon — innsending er bindende",
        horizontal=True,
        index=0,
    )
    env = env_valg
    if env == "prod":
        st.warning("Du har valgt produksjonsmiljøet. Innsending er bindende og kan ikke trekkes tilbake.")

    def hent_token():
        try:
            return auth.get_altinn_token()
        except RuntimeError as e:
            feilmelding = str(e)
            if "invalid_altinn_customer_configuration" in feilmelding:
                st.error(
                    "Systembrukeren er ikke godkjent ennå. "
                    "Gå til **1. Oppsett → Systembruker-oppsett** og fullfør steg 2–3."
                )
            else:
                st.error(f"Autentisering feilet:\n\n{feilmelding}")
            return None

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Send årsregnskap til Altinn", use_container_width=True):
            regnskap = bygg_regnskap()
            feil = ar_modul.valider(regnskap)
            if feil:
                for f in feil:
                    st.error(f)
            else:
                token = hent_token()
                if token:
                    try:
                        with st.spinner("Laster opp årsregnskap til Altinn..."):
                            with AltinnClient(token, env=env) as klient:
                                sign_url = ar_modul.send_inn(regnskap, klient)
                        st.success(
                            f"Årsregnskap for {regnskap.regnskapsaar} er lastet opp og klar for signering."
                        )
                        st.info(
                            "Dokumentet venter på din signatur i Altinn. "
                            "Logg inn med BankID og signer for å fullføre innsendingen."
                        )
                        st.link_button("Signer i Altinn", sign_url, type="primary")
                    except Exception as e:
                        st.error(f"Innsending feilet:\n\n{e}")

    with col2:
        if st.button("Send aksjonærregister til Skatteetaten", use_container_width=True):
            regnskap = bygg_regnskap()
            antall = int(st.session_state["antall_aksjonaerer"])
            aksjonaerer = [
                Aksjonaer(
                    navn=st.session_state.get(f"a_navn_{i}", ""),
                    fodselsnummer=st.session_state.get(f"a_fnr_{i}", ""),
                    antall_aksjer=int(st.session_state.get(f"a_aksjer_{i}", 1)),
                    aksjeklasse=st.session_state.get(f"a_klasse_{i}", "ordinære"),
                    utbytte_utbetalt=int(st.session_state.get(f"a_utbytte_{i}", 0)),
                    innbetalt_kapital_per_aksje=int(st.session_state.get(f"a_kap_{i}", 0)),
                )
                for i in range(antall)
            ]
            oppgave = Aksjonaerregisteroppgave(
                selskap=regnskap.selskap,
                regnskapsaar=int(st.session_state["regnskapsaar"]),
                aksjonaerer=aksjonaerer,
            )
            feil = akr_modul.valider(oppgave)
            if feil:
                for f in feil:
                    st.error(f)
            else:
                try:
                    with st.spinner("Henter Maskinporten-token med SKD-scope..."):
                        skd_token = auth.get_skd_aksjonaer_token()
                    with st.spinner("Sender aksjonærregisteroppgave til Skatteetaten..."):
                        with SkdAksjonaerClient(skd_token, env=env) as klient:
                            svar = akr_modul.send_inn(oppgave, klient)
                    st.success(
                        f"Aksjonærregisteroppgave for {int(st.session_state['regnskapsaar'])} er sendt til Skatteetaten."
                    )
                    if svar:
                        st.info(f"Forsendelse-ID: {svar.get('forsendelseId')}")
                except Exception as e:
                        st.error(f"Innsending feilet:\n\n{e}")
