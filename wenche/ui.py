"""
Wenche — webgrensesnitt (Streamlit).

Start med: wenche ui
For testmiljø: WENCHE_ENV=test wenche ui
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
from wenche import auth
from wenche.altinn_client import AltinnClient
from wenche.xbrl import generer_ixbrl

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
    "fritaksmetoden": True,
    "antall_aksjonaerer": 1,
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
            verdier["fritaksmetoden"] = bool(sm.get("anvend_fritaksmetoden", True))

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
        "skattemelding": {
            "underskudd_til_fremfoering": int(st.session_state["underskudd"]),
            "anvend_fritaksmetoden": bool(st.session_state["fritaksmetoden"]),
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


# ---------------------------------------------------------------------------
# Side-oppsett
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Wenche", layout="wide")
st.title("Wenche")
st.caption("Enkel innsending av regnskap og skattedokumenter til norske myndigheter")

fane_selskap, fane_regnskap, fane_aksjonaerer, fane_generer = st.tabs(
    ["🏢 Selskap", "📊 Regnskap og balanse", "👥 Aksjonærer", "📄 Generer"]
)


# ---------------------------------------------------------------------------
# Fane 1: Selskapsopplysninger
# ---------------------------------------------------------------------------

with fane_selskap:
    st.subheader("Selskapsopplysninger")
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
        st.number_input("Regnskapsår", min_value=2000, max_value=2100, key="regnskapsaar")

    st.divider()
    if st.button("Lagre selskapsopplysninger", type="primary"):
        lagre_config()
        st.success(f"Lagret til {CONFIG_FIL.resolve()}")


# ---------------------------------------------------------------------------
# Fane 2: Regnskap og balanse
# ---------------------------------------------------------------------------

with fane_regnskap:
    st.subheader("Resultatregnskap")
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
        st.number_input("Utbytte fra datterselskap", min_value=0, step=1000, key="utbytte_fra_datterselskap")
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
        st.number_input("Aksjer i datterselskap", min_value=0, step=1000, key="aksjer_i_datterselskap")
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


# ---------------------------------------------------------------------------
# Fane 3: Aksjonærer
# ---------------------------------------------------------------------------

with fane_aksjonaerer:
    st.subheader("Aksjonærer")
    st.number_input("Antall aksjonærer", min_value=1, max_value=20, key="antall_aksjonaerer")
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
                st.number_input("Innbetalt kapital per aksje (NOK)", min_value=0, key=f"a_kap_{i}")


# ---------------------------------------------------------------------------
# Fane 4: Generer dokumenter
# ---------------------------------------------------------------------------

with fane_generer:
    st.subheader("Generer dokumenter")
    st.markdown("**Skattemelding-innstillinger**")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input(
            "Fremførbart underskudd fra tidligere år (NOK)", min_value=0, step=1000, key="underskudd"
        )
    with col2:
        st.checkbox(
            "Anvend fritaksmetoden",
            key="fritaksmetoden",
            help="Sett til true for holdingselskaper som eier aksjer i datterselskaper",
        )

    st.divider()

    def bygg_regnskap() -> Aarsregnskap:
        return Aarsregnskap(
            selskap=Selskap(
                navn=st.session_state["navn"],
                org_nummer=st.session_state["org_nummer"],
                daglig_leder=st.session_state["daglig_leder"],
                styreleder=st.session_state["styreleder"],
                forretningsadresse=st.session_state["forretningsadresse"],
                stiftelsesaar=int(st.session_state["stiftelsesaar"]),
                aksjekapital=int(st.session_state["aksjekapital"]),
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
        )

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Generer skattemelding", use_container_width=True):
            regnskap = bygg_regnskap()
            konfig = SkattemeldingKonfig(
                underskudd_til_fremfoering=int(st.session_state["underskudd"]),
                anvend_fritaksmetoden=bool(st.session_state["fritaksmetoden"]),
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
        if st.button("Last ned iXBRL (årsregnskap)", use_container_width=True):
            regnskap = bygg_regnskap()
            feil = ar_modul.valider(regnskap)
            if feil:
                for f in feil:
                    st.error(f)
            else:
                ixbrl = generer_ixbrl(regnskap)
                st.download_button(
                    "Last ned årsregnskap.html",
                    data=ixbrl,
                    file_name=f"aarsregnskap_{int(st.session_state['regnskapsaar'])}_{st.session_state['org_nummer']}.html",
                    mime="application/xhtml+xml",
                )

    with col3:
        if st.button("Last ned RF-1086 XML", use_container_width=True):
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
                xml = akr_modul.generer_xml(oppgave)
                st.download_button(
                    "Last ned aksjonaerregister.xml",
                    data=xml,
                    file_name=f"aksjonaerregister_{int(st.session_state['regnskapsaar'])}_{st.session_state['org_nummer']}.xml",
                    mime="application/xml",
                )

    # -----------------------------------------------------------------------
    # Innsending til Altinn
    # -----------------------------------------------------------------------

    st.divider()
    st.subheader("Send til Altinn")

    env = os.getenv("WENCHE_ENV", "prod")
    if env == "test":
        st.info("Miljø: **Testmiljø (tt02)** — ingen ekte innsending")
    else:
        st.warning(
            "Miljø: **Produksjon** — innsending er bindende. "
            "Start med `WENCHE_ENV=test wenche ui` for å teste mot testmiljøet først."
        )

    def hent_token():
        try:
            return auth.get_altinn_token()
        except RuntimeError as e:
            st.error(f"Autentisering feilet:\n\n{e}")
            return None

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
                        with st.spinner("Sender årsregnskap til Altinn..."):
                            with AltinnClient(token) as klient:
                                ar_modul.send_inn(regnskap, klient)
                        st.success(
                            f"Årsregnskap for {regnskap.regnskapsaar} sendt inn til "
                            f"Brønnøysundregistrene."
                        )
                    except Exception as e:
                        st.error(f"Innsending feilet:\n\n{e}")

    with col2:
        if st.button("Send aksjonærregister til Altinn", use_container_width=True):
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
                token = hent_token()
                if token:
                    try:
                        with st.spinner("Sender aksjonærregister til Altinn..."):
                            with AltinnClient(token) as klient:
                                akr_modul.send_inn(oppgave, klient)
                        st.success(
                            f"Aksjonærregisteroppgave for {int(st.session_state['regnskapsaar'])} sendt inn."
                        )
                    except Exception as e:
                        st.error(f"Innsending feilet:\n\n{e}")
