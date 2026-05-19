"""
Wenche — webgrensesnitt (NiceGUI).

Start med: wenche ui
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx
import yaml
from nicegui import app, run, ui

from wenche import (
    aarsregnskap as ar_modul,
    aksjonaerregister as akr_modul,
    auth,
    noter as noter_modul,
    skattemelding as sm_modul,
    systembruker,
)
from wenche.altinn_client import AltinnClient
from wenche.brg_xml import generer_hovedskjema, generer_underskjema
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
    LaanTilNaerstaaende,
    LangsiktigGjeld,
    Noter,
    Omloepmidler,
    Resultatregnskap,
    Selskap,
    SkattemeldingKonfig,
)
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import SkdSkattemeldingClient
from wenche.skattemelding_xml import generer_skattemelding_upersonlig, hent_partsnummer
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon

CONFIG_FIL = Path("config.yaml")
_WENCHE_DIR = Path.home() / ".wenche"
_REQUEST_ID_FIL = _WENCHE_DIR / "systembruker_request_id.txt"


# ---------------------------------------------------------------------------
# Tilstandsklasser
# ---------------------------------------------------------------------------

@dataclass
class AksjonaerState:
    navn: str = ""
    fodselsnummer: str = ""
    antall_aksjer: int = 1
    aksjeklasse: str = "ordinære"
    utbytte_utbetalt: float = 0.0
    innbetalt_kapital_per_aksje: float = 0.0


@dataclass
class LaanState:
    motpart: str = ""
    saldo: float = 0.0
    retning: str = "långiver"
    rente_prosent: float = 0.0
    sikkerhet: str = ""


@dataclass
class AppState:
    # Selskap
    navn: str = "Mitt Holding AS"
    org_nummer: str = "123456789"
    daglig_leder: str = "Ola Nordmann"
    styreleder: str = "Ola Nordmann"
    forretningsadresse: str = "Gateveien 1, 0001 Oslo"
    stiftelsesaar: int = 2020
    aksjekapital: float = 30000.0
    kontakt_epost: str = ""
    regnskapsaar: int = 2025

    # Resultatregnskap — inneværende år
    salgsinntekter: float = 0.0
    andre_driftsinntekter: float = 0.0
    loennskostnader: float = 0.0
    avskrivninger: float = 0.0
    andre_driftskostnader: float = 5500.0
    utbytte_fra_datterselskap: float = 0.0
    andre_finansinntekter: float = 0.0
    rentekostnader: float = 0.0
    andre_finanskostnader: float = 0.0

    # Balanse — Eiendeler
    aksjer_i_datterselskap: float = 100000.0
    andre_aksjer: float = 0.0
    langsiktige_fordringer: float = 0.0
    kortsiktige_fordringer: float = 0.0
    bankinnskudd: float = 1200.0

    # Balanse — Egenkapital og gjeld
    ek_aksjekapital: float = 30000.0
    overkursfond: float = 0.0
    annen_egenkapital: float = -34300.0
    laan_fra_aksjonaer: float = 105500.0
    andre_langsiktige_laan: float = 0.0
    leverandoergjeld: float = 0.0
    skyldige_offentlige_avgifter: float = 0.0
    annen_kortsiktig_gjeld: float = 0.0

    # Skattemelding
    underskudd: float = 0.0
    fritaksmetoden: bool = False
    eierandel_datterselskap: int = 100

    # Lister
    aksjonaerer: list[AksjonaerState] = field(default_factory=lambda: [AksjonaerState()])
    antall_ansatte: int = 0
    laan_til_naerstaaende: list[LaanState] = field(default_factory=list)

    # Foregående år — Resultatregnskap
    f_salgsinntekter: float = 0.0
    f_andre_driftsinntekter: float = 0.0
    f_loennskostnader: float = 0.0
    f_avskrivninger: float = 0.0
    f_andre_driftskostnader: float = 0.0
    f_utbytte_fra_datterselskap: float = 0.0
    f_andre_finansinntekter: float = 0.0
    f_rentekostnader: float = 0.0
    f_andre_finanskostnader: float = 0.0

    # Foregående år — Balanse
    f_aksjer_i_datterselskap: float = 0.0
    f_andre_aksjer: float = 0.0
    f_langsiktige_fordringer: float = 0.0
    f_kortsiktige_fordringer: float = 0.0
    f_bankinnskudd: float = 0.0
    f_ek_aksjekapital: float = 0.0
    f_overkursfond: float = 0.0
    f_annen_egenkapital: float = 0.0
    f_laan_fra_aksjonaer: float = 0.0
    f_andre_langsiktige_laan: float = 0.0
    f_leverandoergjeld: float = 0.0
    f_skyldige_offentlige_avgifter: float = 0.0
    f_annen_kortsiktig_gjeld: float = 0.0

    # --- Beregnede summer ---

    @property
    def sum_driftsinntekter(self) -> float:
        return self.salgsinntekter + self.andre_driftsinntekter

    @property
    def sum_driftskostnader(self) -> float:
        return self.loennskostnader + self.avskrivninger + self.andre_driftskostnader

    @property
    def driftsresultat(self) -> float:
        return self.sum_driftsinntekter - self.sum_driftskostnader

    @property
    def resultat_foer_skatt(self) -> float:
        return (
            self.driftsresultat
            + self.utbytte_fra_datterselskap
            + self.andre_finansinntekter
            - self.rentekostnader
            - self.andre_finanskostnader
        )

    @property
    def sum_anleggsmidler(self) -> float:
        return self.aksjer_i_datterselskap + self.andre_aksjer + self.langsiktige_fordringer

    @property
    def sum_omloepmidler(self) -> float:
        return self.kortsiktige_fordringer + self.bankinnskudd

    @property
    def sum_eiendeler(self) -> float:
        return self.sum_anleggsmidler + self.sum_omloepmidler

    @property
    def sum_egenkapital(self) -> float:
        return self.ek_aksjekapital + self.overkursfond + self.annen_egenkapital

    @property
    def sum_langsiktig_gjeld(self) -> float:
        return self.laan_fra_aksjonaer + self.andre_langsiktige_laan

    @property
    def sum_kortsiktig_gjeld(self) -> float:
        return (
            self.leverandoergjeld
            + self.skyldige_offentlige_avgifter
            + self.annen_kortsiktig_gjeld
        )

    @property
    def sum_ek_og_gjeld(self) -> float:
        return self.sum_egenkapital + self.sum_langsiktig_gjeld + self.sum_kortsiktig_gjeld

    @property
    def balanseforskjell(self) -> float:
        return self.sum_eiendeler - self.sum_ek_og_gjeld

    @property
    def er_i_balanse(self) -> bool:
        return abs(self.balanseforskjell) < 0.01

    # --- Bygg modell-objekter ---

    def bygg_selskap(self) -> Selskap:
        return Selskap(
            navn=self.navn,
            org_nummer=self.org_nummer,
            daglig_leder=self.daglig_leder,
            styreleder=self.styreleder,
            forretningsadresse=self.forretningsadresse,
            stiftelsesaar=int(self.stiftelsesaar),
            aksjekapital=float(self.aksjekapital),
            kontakt_epost=self.kontakt_epost,
        )

    def bygg_regnskap(self) -> Aarsregnskap:
        utbytte_utbetalt = sum(a.utbytte_utbetalt for a in self.aksjonaerer)
        return Aarsregnskap(
            selskap=self.bygg_selskap(),
            regnskapsaar=int(self.regnskapsaar),
            utbytte_utbetalt=utbytte_utbetalt,
            resultatregnskap=Resultatregnskap(
                driftsinntekter=Driftsinntekter(self.salgsinntekter, self.andre_driftsinntekter),
                driftskostnader=Driftskostnader(self.loennskostnader, self.avskrivninger, self.andre_driftskostnader),
                finansposter=Finansposter(self.utbytte_fra_datterselskap, self.andre_finansinntekter, self.rentekostnader, self.andre_finanskostnader),
            ),
            balanse=Balanse(
                eiendeler=Eiendeler(
                    anleggsmidler=Anleggsmidler(self.aksjer_i_datterselskap, self.andre_aksjer, self.langsiktige_fordringer),
                    omloepmidler=Omloepmidler(self.kortsiktige_fordringer, self.bankinnskudd),
                ),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(self.ek_aksjekapital, self.overkursfond, self.annen_egenkapital),
                    langsiktig_gjeld=LangsiktigGjeld(self.laan_fra_aksjonaer, self.andre_langsiktige_laan),
                    kortsiktig_gjeld=KortsiktigGjeld(self.leverandoergjeld, self.skyldige_offentlige_avgifter, self.annen_kortsiktig_gjeld),
                ),
            ),
            foregaaende_aar_resultat=Resultatregnskap(
                driftsinntekter=Driftsinntekter(self.f_salgsinntekter, self.f_andre_driftsinntekter),
                driftskostnader=Driftskostnader(self.f_loennskostnader, self.f_avskrivninger, self.f_andre_driftskostnader),
                finansposter=Finansposter(self.f_utbytte_fra_datterselskap, self.f_andre_finansinntekter, self.f_rentekostnader, self.f_andre_finanskostnader),
            ),
            foregaaende_aar_balanse=Balanse(
                eiendeler=Eiendeler(
                    anleggsmidler=Anleggsmidler(self.f_aksjer_i_datterselskap, self.f_andre_aksjer, self.f_langsiktige_fordringer),
                    omloepmidler=Omloepmidler(self.f_kortsiktige_fordringer, self.f_bankinnskudd),
                ),
                egenkapital_og_gjeld=EgenkapitalOgGjeld(
                    egenkapital=Egenkapital(self.f_ek_aksjekapital, self.f_overkursfond, self.f_annen_egenkapital),
                    langsiktig_gjeld=LangsiktigGjeld(self.f_laan_fra_aksjonaer, self.f_andre_langsiktige_laan),
                    kortsiktig_gjeld=KortsiktigGjeld(self.f_leverandoergjeld, self.f_skyldige_offentlige_avgifter, self.f_annen_kortsiktig_gjeld),
                ),
            ),
        )

    def bygg_oppgave(self) -> Aksjonaerregisteroppgave:
        return Aksjonaerregisteroppgave(
            selskap=self.bygg_selskap(),
            regnskapsaar=int(self.regnskapsaar),
            aksjonaerer=[
                Aksjonaer(
                    navn=a.navn,
                    fodselsnummer=a.fodselsnummer,
                    antall_aksjer=int(a.antall_aksjer),
                    aksjeklasse=a.aksjeklasse,
                    utbytte_utbetalt=a.utbytte_utbetalt,
                    innbetalt_kapital_per_aksje=a.innbetalt_kapital_per_aksje,
                )
                for a in self.aksjonaerer
            ],
        )

    def bygg_noter(self) -> Noter:
        return Noter(
            antall_ansatte=self.antall_ansatte,
            laan_til_naerstaaende=[
                LaanTilNaerstaaende(
                    motpart=l.motpart,
                    saldo=l.saldo,
                    retning=l.retning,
                    rente_prosent=l.rente_prosent,
                    sikkerhet=l.sikkerhet,
                )
                for l in self.laan_til_naerstaaende
            ],
        )

    def les_config(self) -> None:
        if not CONFIG_FIL.exists():
            return
        try:
            with open(CONFIG_FIL, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}

            s = cfg.get("selskap", {})
            self.navn = s.get("navn", self.navn)
            self.org_nummer = str(s.get("org_nummer", self.org_nummer))
            self.daglig_leder = s.get("daglig_leder", self.daglig_leder)
            self.styreleder = s.get("styreleder", self.styreleder)
            self.forretningsadresse = s.get("forretningsadresse", self.forretningsadresse)
            self.stiftelsesaar = int(s.get("stiftelsesaar", self.stiftelsesaar))
            self.aksjekapital = float(s.get("aksjekapital", self.aksjekapital))
            self.kontakt_epost = s.get("kontakt_epost", self.kontakt_epost)
            self.regnskapsaar = int(cfg.get("regnskapsaar", self.regnskapsaar))

            rr = cfg.get("resultatregnskap", {})
            di = rr.get("driftsinntekter", {})
            dk = rr.get("driftskostnader", {})
            fp = rr.get("finansposter", {})
            self.salgsinntekter = float(di.get("salgsinntekter", 0))
            self.andre_driftsinntekter = float(di.get("andre_driftsinntekter", 0))
            self.loennskostnader = float(dk.get("loennskostnader", 0))
            self.avskrivninger = float(dk.get("avskrivninger", 0))
            self.andre_driftskostnader = float(dk.get("andre_driftskostnader", 5500))
            self.utbytte_fra_datterselskap = float(fp.get("utbytte_fra_datterselskap", 0))
            self.andre_finansinntekter = float(fp.get("andre_finansinntekter", 0))
            self.rentekostnader = float(fp.get("rentekostnader", 0))
            self.andre_finanskostnader = float(fp.get("andre_finanskostnader", 0))

            b = cfg.get("balanse", {})
            anl = b.get("eiendeler", {}).get("anleggsmidler", {})
            oml = b.get("eiendeler", {}).get("omloepmidler", {})
            ek = b.get("egenkapital_og_gjeld", {}).get("egenkapital", {})
            lg = b.get("egenkapital_og_gjeld", {}).get("langsiktig_gjeld", {})
            kg = b.get("egenkapital_og_gjeld", {}).get("kortsiktig_gjeld", {})
            self.aksjer_i_datterselskap = float(anl.get("aksjer_i_datterselskap", 100000))
            self.andre_aksjer = float(anl.get("andre_aksjer", 0))
            self.langsiktige_fordringer = float(anl.get("langsiktige_fordringer", 0))
            self.kortsiktige_fordringer = float(oml.get("kortsiktige_fordringer", 0))
            self.bankinnskudd = float(oml.get("bankinnskudd", 1200))
            self.ek_aksjekapital = float(ek.get("aksjekapital", 30000))
            self.overkursfond = float(ek.get("overkursfond", 0))
            self.annen_egenkapital = float(ek.get("annen_egenkapital", -34300))
            self.laan_fra_aksjonaer = float(lg.get("laan_fra_aksjonaer", 105500))
            self.andre_langsiktige_laan = float(lg.get("andre_langsiktige_laan", 0))
            self.leverandoergjeld = float(kg.get("leverandoergjeld", 0))
            self.skyldige_offentlige_avgifter = float(kg.get("skyldige_offentlige_avgifter", 0))
            self.annen_kortsiktig_gjeld = float(kg.get("annen_kortsiktig_gjeld", 0))

            sm_cfg = cfg.get("skattemelding", {})
            self.underskudd = float(sm_cfg.get("underskudd_til_fremfoering", 0))
            self.fritaksmetoden = bool(sm_cfg.get("anvend_fritaksmetoden", False))
            self.eierandel_datterselskap = int(sm_cfg.get("eierandel_datterselskap", 100))

            fa = cfg.get("foregaaende_aar", {})
            frr = fa.get("resultatregnskap", {})
            fdi = frr.get("driftsinntekter", {})
            fdk = frr.get("driftskostnader", {})
            ffp = frr.get("finansposter", {})
            self.f_salgsinntekter = float(fdi.get("salgsinntekter", 0))
            self.f_andre_driftsinntekter = float(fdi.get("andre_driftsinntekter", 0))
            self.f_loennskostnader = float(fdk.get("loennskostnader", 0))
            self.f_avskrivninger = float(fdk.get("avskrivninger", 0))
            self.f_andre_driftskostnader = float(fdk.get("andre_driftskostnader", 0))
            self.f_utbytte_fra_datterselskap = float(ffp.get("utbytte_fra_datterselskap", 0))
            self.f_andre_finansinntekter = float(ffp.get("andre_finansinntekter", 0))
            self.f_rentekostnader = float(ffp.get("rentekostnader", 0))
            self.f_andre_finanskostnader = float(ffp.get("andre_finanskostnader", 0))

            fb = fa.get("balanse", {})
            fanl = fb.get("eiendeler", {}).get("anleggsmidler", {})
            foml = fb.get("eiendeler", {}).get("omloepmidler", {})
            fek = fb.get("egenkapital_og_gjeld", {}).get("egenkapital", {})
            flg = fb.get("egenkapital_og_gjeld", {}).get("langsiktig_gjeld", {})
            fkg = fb.get("egenkapital_og_gjeld", {}).get("kortsiktig_gjeld", {})
            self.f_aksjer_i_datterselskap = float(fanl.get("aksjer_i_datterselskap", 0))
            self.f_andre_aksjer = float(fanl.get("andre_aksjer", 0))
            self.f_langsiktige_fordringer = float(fanl.get("langsiktige_fordringer", 0))
            self.f_kortsiktige_fordringer = float(foml.get("kortsiktige_fordringer", 0))
            self.f_bankinnskudd = float(foml.get("bankinnskudd", 0))
            self.f_ek_aksjekapital = float(fek.get("aksjekapital", 0))
            self.f_overkursfond = float(fek.get("overkursfond", 0))
            self.f_annen_egenkapital = float(fek.get("annen_egenkapital", 0))
            self.f_laan_fra_aksjonaer = float(flg.get("laan_fra_aksjonaer", 0))
            self.f_andre_langsiktige_laan = float(flg.get("andre_langsiktige_laan", 0))
            self.f_leverandoergjeld = float(fkg.get("leverandoergjeld", 0))
            self.f_skyldige_offentlige_avgifter = float(fkg.get("skyldige_offentlige_avgifter", 0))
            self.f_annen_kortsiktig_gjeld = float(fkg.get("annen_kortsiktig_gjeld", 0))

            aksjonaerer_raw = cfg.get("aksjonaerer", [])
            if aksjonaerer_raw:
                self.aksjonaerer = [
                    AksjonaerState(
                        navn=a.get("navn", ""),
                        fodselsnummer=str(a.get("fodselsnummer", "")),
                        antall_aksjer=int(a.get("antall_aksjer", 1)),
                        aksjeklasse=a.get("aksjeklasse", "ordinære"),
                        utbytte_utbetalt=float(a.get("utbytte_utbetalt", 0)),
                        innbetalt_kapital_per_aksje=float(a.get("innbetalt_kapital_per_aksje", 0)),
                    )
                    for a in aksjonaerer_raw
                ]

            noter_cfg = cfg.get("noter", {})
            self.antall_ansatte = int(noter_cfg.get("antall_ansatte", 0))
            self.laan_til_naerstaaende = [
                LaanState(
                    motpart=l.get("motpart", l.get("mottaker", "")),
                    saldo=float(l.get("saldo", l.get("beloep", 0))),
                    retning=l.get("retning", "långiver"),
                    rente_prosent=float(l.get("rente_prosent", 0.0)),
                    sikkerhet=l.get("sikkerhet", ""),
                )
                for l in noter_cfg.get("laan_til_naerstaaende", [])
            ]
        except Exception:
            pass

    def lagre_config(self) -> None:
        data = {
            "selskap": {
                "navn": self.navn,
                "org_nummer": self.org_nummer,
                "daglig_leder": self.daglig_leder,
                "styreleder": self.styreleder,
                "forretningsadresse": self.forretningsadresse,
                "stiftelsesaar": int(self.stiftelsesaar),
                "aksjekapital": float(self.aksjekapital),
                "kontakt_epost": self.kontakt_epost,
            },
            "regnskapsaar": int(self.regnskapsaar),
            "resultatregnskap": {
                "driftsinntekter": {
                    "salgsinntekter": self.salgsinntekter,
                    "andre_driftsinntekter": self.andre_driftsinntekter,
                },
                "driftskostnader": {
                    "loennskostnader": self.loennskostnader,
                    "avskrivninger": self.avskrivninger,
                    "andre_driftskostnader": self.andre_driftskostnader,
                },
                "finansposter": {
                    "utbytte_fra_datterselskap": self.utbytte_fra_datterselskap,
                    "andre_finansinntekter": self.andre_finansinntekter,
                    "rentekostnader": self.rentekostnader,
                    "andre_finanskostnader": self.andre_finanskostnader,
                },
            },
            "balanse": {
                "eiendeler": {
                    "anleggsmidler": {
                        "aksjer_i_datterselskap": self.aksjer_i_datterselskap,
                        "andre_aksjer": self.andre_aksjer,
                        "langsiktige_fordringer": self.langsiktige_fordringer,
                    },
                    "omloepmidler": {
                        "kortsiktige_fordringer": self.kortsiktige_fordringer,
                        "bankinnskudd": self.bankinnskudd,
                    },
                },
                "egenkapital_og_gjeld": {
                    "egenkapital": {
                        "aksjekapital": self.ek_aksjekapital,
                        "overkursfond": self.overkursfond,
                        "annen_egenkapital": self.annen_egenkapital,
                    },
                    "langsiktig_gjeld": {
                        "laan_fra_aksjonaer": self.laan_fra_aksjonaer,
                        "andre_langsiktige_laan": self.andre_langsiktige_laan,
                    },
                    "kortsiktig_gjeld": {
                        "leverandoergjeld": self.leverandoergjeld,
                        "skyldige_offentlige_avgifter": self.skyldige_offentlige_avgifter,
                        "annen_kortsiktig_gjeld": self.annen_kortsiktig_gjeld,
                    },
                },
            },
            "skattemelding": {
                "underskudd_til_fremfoering": self.underskudd,
                "anvend_fritaksmetoden": self.fritaksmetoden,
                "eierandel_datterselskap": int(self.eierandel_datterselskap),
            },
            "aksjonaerer": [
                {
                    "navn": a.navn,
                    "fodselsnummer": a.fodselsnummer,
                    "antall_aksjer": int(a.antall_aksjer),
                    "aksjeklasse": a.aksjeklasse,
                    "utbytte_utbetalt": a.utbytte_utbetalt,
                    "innbetalt_kapital_per_aksje": a.innbetalt_kapital_per_aksje,
                }
                for a in self.aksjonaerer
            ],
            "foregaaende_aar": {
                "resultatregnskap": {
                    "driftsinntekter": {
                        "salgsinntekter": self.f_salgsinntekter,
                        "andre_driftsinntekter": self.f_andre_driftsinntekter,
                    },
                    "driftskostnader": {
                        "loennskostnader": self.f_loennskostnader,
                        "avskrivninger": self.f_avskrivninger,
                        "andre_driftskostnader": self.f_andre_driftskostnader,
                    },
                    "finansposter": {
                        "utbytte_fra_datterselskap": self.f_utbytte_fra_datterselskap,
                        "andre_finansinntekter": self.f_andre_finansinntekter,
                        "rentekostnader": self.f_rentekostnader,
                        "andre_finanskostnader": self.f_andre_finanskostnader,
                    },
                },
                "balanse": {
                    "eiendeler": {
                        "anleggsmidler": {
                            "aksjer_i_datterselskap": self.f_aksjer_i_datterselskap,
                            "andre_aksjer": self.f_andre_aksjer,
                            "langsiktige_fordringer": self.f_langsiktige_fordringer,
                        },
                        "omloepmidler": {
                            "kortsiktige_fordringer": self.f_kortsiktige_fordringer,
                            "bankinnskudd": self.f_bankinnskudd,
                        },
                    },
                    "egenkapital_og_gjeld": {
                        "egenkapital": {
                            "aksjekapital": self.f_ek_aksjekapital,
                            "overkursfond": self.f_overkursfond,
                            "annen_egenkapital": self.f_annen_egenkapital,
                        },
                        "langsiktig_gjeld": {
                            "laan_fra_aksjonaer": self.f_laan_fra_aksjonaer,
                            "andre_langsiktige_laan": self.f_andre_langsiktige_laan,
                        },
                        "kortsiktig_gjeld": {
                            "leverandoergjeld": self.f_leverandoergjeld,
                            "skyldige_offentlige_avgifter": self.f_skyldige_offentlige_avgifter,
                            "annen_kortsiktig_gjeld": self.f_annen_kortsiktig_gjeld,
                        },
                    },
                },
            },
            "noter": {
                "antall_ansatte": self.antall_ansatte,
                "laan_til_naerstaaende": [
                    {
                        "motpart": l.motpart,
                        "saldo": l.saldo,
                        "retning": l.retning,
                        "rente_prosent": l.rente_prosent,
                        "sikkerhet": l.sikkerhet,
                    }
                    for l in self.laan_til_naerstaaende
                ],
            },
        }
        with open(CONFIG_FIL, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)


# Globalt tilstandsobjekt — initialisert fra config.yaml ved oppstart
state = AppState()
state.les_config()


# ---------------------------------------------------------------------------
# Hjelpefunksjoner
# ---------------------------------------------------------------------------

def kr(v: float) -> str:
    """Formater beløp med norsk tusenskilletegn."""
    return f"{v:,.0f}".replace(",", "\u00a0") + " kr"


def _les_konfig_for_milj(navn: str, env: str, default: str = "") -> str:
    """
    Les credential-verdi for gitt miljø.

    Prøver først miljø-spesifikk variant ({navn}_{TEST|PROD}), faller tilbake
    til generisk variabelnavn for brukere som kun har ett sett credentials.
    """
    return os.getenv(f"{navn}_{env.upper()}") or os.getenv(navn) or default


def _sjekk_konfig() -> list[tuple[bool, str, str]]:
    resultater = []
    env = os.getenv("WENCHE_ENV", "prod")
    suffix = env.upper()

    client_id = _les_konfig_for_milj("MASKINPORTEN_CLIENT_ID", env)
    resultater.append((
        bool(client_id),
        f"MASKINPORTEN_CLIENT_ID for {suffix}",
        "Satt" if client_id else f"Mangler. Sett MASKINPORTEN_CLIENT_ID_{suffix} (eller MASKINPORTEN_CLIENT_ID som fallback) i .env",
    ))
    kid = _les_konfig_for_milj("MASKINPORTEN_KID", env)
    resultater.append((
        bool(kid),
        f"MASKINPORTEN_KID for {suffix}",
        "Satt" if kid else f"Mangler. Sett MASKINPORTEN_KID_{suffix} (eller MASKINPORTEN_KID som fallback) i .env",
    ))
    orgnr = os.getenv("ORG_NUMMER")
    resultater.append((bool(orgnr), "ORG_NUMMER", "Satt" if orgnr else "Mangler. Legg til i .env-filen"))
    nokkel_sti = _les_konfig_for_milj("MASKINPORTEN_PRIVAT_NOKKEL", env, "maskinporten_privat.pem")
    nokkel_ok = Path(nokkel_sti).exists()
    resultater.append((nokkel_ok, "Privat nøkkel", f"Funnet: {nokkel_sti}" if nokkel_ok else f"Finner ikke: {nokkel_sti}"))
    resultater.append((True, "Miljø", f"{'Testmiljø (tt02)' if env == 'test' else 'Produksjon'}, bytt i Oppsett-fanen"))
    return resultater


def _lagre_request_id(request_id: str) -> None:
    _WENCHE_DIR.mkdir(exist_ok=True)
    _REQUEST_ID_FIL.write_text(request_id, encoding="utf-8")


def _les_request_id() -> str:
    if _REQUEST_ID_FIL.exists():
        return _REQUEST_ID_FIL.read_text(encoding="utf-8").strip()
    return ""


# ---------------------------------------------------------------------------
# Gjenbrukbare UI-komponenter
# ---------------------------------------------------------------------------

def seksjonstittel(tekst: str) -> None:
    ui.label(tekst).classes("text-base font-semibold text-slate-700 mt-4 mb-1")


def metric_kort(tittel: str, verdi: str, farge: str = "slate") -> ui.label:
    """Viser en nøkkelverdi med tittel. Returnerer verdi-labelen for oppdatering."""
    with ui.card().classes(f"bg-{farge}-50 border border-{farge}-200 p-3 min-w-36"):
        ui.label(tittel).classes("text-xs text-slate-500 uppercase tracking-wide")
        lbl = ui.label(verdi).classes(f"text-lg font-semibold text-{farge}-800 font-mono")
    return lbl


def num(label: str, attr: str, obj=None, step: float = 1000, min_val: float | None = 0,
        on_change=None, tooltip: str = "") -> ui.number:
    """Tallinnfelt som oppdaterer state-attributt ved endring."""
    target = obj if obj is not None else state

    def handler(e):
        setattr(target, attr, float(e.value) if e.value is not None else 0.0)
        if on_change:
            on_change()

    kwargs: dict = {
        "label": label,
        "value": getattr(target, attr),
        "step": step,
        "format": "%.0f",
        "on_change": handler,
    }
    if min_val is not None:
        kwargs["min"] = min_val
    el = ui.number(**kwargs).classes("w-full")
    if tooltip:
        el.tooltip(tooltip)
    return el


def txt(label: str, attr: str, obj=None, placeholder: str = "", tooltip: str = "",
        on_change=None) -> ui.input:
    """Tekstinnfelt som oppdaterer state-attributt ved endring."""
    target = obj if obj is not None else state

    def handler(e):
        setattr(target, attr, e.value)
        if on_change:
            on_change()

    el = ui.input(
        label=label,
        value=getattr(target, attr),
        placeholder=placeholder,
        on_change=handler,
    ).classes("w-full")
    if tooltip:
        el.tooltip(tooltip)
    return el


# ---------------------------------------------------------------------------
# Fane 0: Hjem
# ---------------------------------------------------------------------------

def _frist_info(maaned: int, dag: int) -> tuple[str, str, str]:
    """Returner (dato_tekst, status_tekst, farge) basert på dager til neste frist."""
    from wenche.fristsjekk import neste_frist
    today = date.today()
    frist = neste_frist(maaned, dag)
    dager = (frist - today).days
    dato_tekst = f"{frist.day}. {frist.strftime('%B %Y')}".replace(
        "January", "januar").replace("February", "februar").replace(
        "March", "mars").replace("April", "april").replace(
        "May", "mai").replace("June", "juni").replace(
        "July", "juli").replace("August", "august").replace(
        "September", "september").replace("October", "oktober").replace(
        "November", "november").replace("December", "desember")
    if dager <= 30:
        return dato_tekst, f"{dager} dager igjen", "red-600"
    elif dager <= 60:
        return dato_tekst, f"{dager} dager igjen", "amber-500"
    else:
        return dato_tekst, f"{dager} dager igjen", "green-600"


def _fristkort(tittel: str, undertittel: str) -> tuple:
    """Oppretter fristkort med loading-tilstand. Returnerer (card, content)."""
    card = ui.card().classes("w-full p-5 border border-slate-200 shadow-none rounded-xl")
    with card:
        content = ui.column().classes("w-full gap-0")
        with content:
            ui.label(tittel).classes("font-semibold text-slate-800 text-base")
            ui.label(undertittel).classes("text-xs text-slate-500 mb-3")
            with ui.row().classes("items-center gap-2"):
                ui.spinner(size="sm").classes("text-slate-400")
                ui.label("Sjekker status...").classes("text-xs text-slate-400 italic")
    return card, content


def _fristkort_innfridd(card, content, tittel: str, undertittel: str, result) -> None:
    """Vis fristkort som fullført — grønt, ingen frist, tydelig bekreftelse."""
    card.classes(remove="border-slate-200", add="border-green-200 bg-green-50/50")
    content.clear()
    with content:
        ui.label(tittel).classes("font-semibold text-slate-800 text-base")
        ui.label(undertittel).classes("text-xs text-slate-500 mb-3")
        with ui.row().classes("items-center gap-2"):
            ui.icon("check_circle").classes("text-green-600 text-2xl")
            ui.label("Levert").classes("text-lg font-bold text-green-700")
        ui.label(result.brukertekst).classes("text-sm text-slate-600 mt-2")
        if result.tidspunkt:
            ui.label(f"Mottatt {result.tidspunkt}").classes("text-xs text-slate-400 mt-1")
        if result.lenke:
            ui.separator().classes("my-3")
            ui.link(
                "Åpne kvittering i Altinn →", result.lenke, new_tab=True
            ).classes("text-sm text-green-700 font-medium")


def _fristkort_ventende(card, content, tittel: str, undertittel: str, maaned: int, dag: int,
                         beskrivelse: str, result=None) -> None:
    """Vis fristkort med nedtelling til frist."""
    dato_tekst, countdown, farge = _frist_info(maaned, dag)
    content.clear()
    with content:
        ui.label(tittel).classes("font-semibold text-slate-800 text-base")
        ui.label(undertittel).classes("text-xs text-slate-500 mb-2")
        if result and result.beskrivelse:
            with ui.row().classes("items-center gap-1 mb-1"):
                ui.icon("schedule").classes("text-slate-400 text-base")
                ui.label(result.beskrivelse).classes("text-sm text-slate-500")
        ui.label(dato_tekst).classes(f"text-sm font-medium text-{farge}")
        ui.label(countdown).classes(f"text-xs text-{farge}")
        ui.separator().classes("my-3")
        ui.label(beskrivelse).classes("text-sm text-slate-600")


def _bygg_hjem_fane(tabs=None, t_oppsett=None) -> None:
    ui.label("Tid for å sende inn papirene igjen?").classes("text-2xl font-semibold mt-2 mb-1")
    ui.label(
        "Wenche ordner årsregnskap, skattemelding og aksjonærregisteroppgave "
        "for holdingselskapet ditt. Fyll ut tallene i steg 1–5, send inn i steg 6."
    ).classes("text-slate-500 text-sm mb-2")
    with ui.row().classes("gap-1 mb-6 flex-wrap"):
        ui.label("Første gang? Ta en titt i").classes("text-sm text-slate-500")
        ui.link("dokumentasjonen", "https://olefredrik.github.io/Wenche/", new_tab=True).classes("text-sm")
        ui.label(", der finner du hjelp til å sette opp alt riktig.").classes("text-sm text-slate-500")

    orgnr_konfigurert = bool(state.org_nummer) and state.org_nummer != "123456789"

    if not orgnr_konfigurert:
        with ui.card().classes(
            "w-full p-4 mb-4 bg-amber-50 border border-amber-200 shadow-none rounded-xl"
        ):
            with ui.row().classes("items-center gap-3 w-full"):
                ui.icon("info").classes("text-amber-600 text-2xl")
                with ui.column().classes("gap-1 flex-grow"):
                    ui.label("Organisasjonsnummer mangler").classes(
                        "font-semibold text-amber-900"
                    )
                    ui.label(
                        "Fyll inn organisasjonsnummer i Oppsett-fanen for å aktivere "
                        "automatisk statussjekk."
                    ).classes("text-sm text-amber-900")
                if tabs is not None and t_oppsett is not None:
                    ui.button(
                        "Åpne Oppsett",
                        on_click=lambda: tabs.set_value(t_oppsett),
                    ).props("color=amber-7 size=sm flat icon=arrow_forward")

    with ui.row().classes("items-center gap-3 mb-3"):
        ui.label("Frister").classes("text-lg font-semibold")
        oppdater_knapp = ui.button(
            "Oppdater status",
            on_click=lambda: sjekk_alle_frister(),
        ).props("outline color=primary size=sm flat icon=refresh")
        if not orgnr_konfigurert:
            oppdater_knapp.disable()
            oppdater_knapp.tooltip("Fyll inn organisasjonsnummer i Oppsett-fanen først")

    frister = [
        {"key": "skattemelding", "tittel": "Skattemelding", "undertittel": "RF-1167 + RF-1028",
         "maaned": 5, "dag": 31,
         "beskrivelse": "Wenche beregner skatten og sender skattemeldingen digitalt via Altinn i steg 6."},
        {"key": "aarsregnskap", "tittel": "Årsregnskap", "undertittel": "Brønnøysundregistrene",
         "maaned": 7, "dag": 31,
         "beskrivelse": "Sendes digitalt via Altinn i steg 6. "
                        "Krever signering med BankID av daglig leder eller styreleder."},
        {"key": "aksjonaerregister", "tittel": "Aksjonærregisteroppgave",
         "undertittel": "RF-1086, Skatteetaten", "maaned": 1, "dag": 31,
         "beskrivelse": "Sendes maskinelt til Skatteetatens API via steg 6. "
                        "Ingen manuell signering nødvendig."},
    ]

    from wenche.fristsjekk import FristStatus

    kort: dict[str, tuple] = {}
    with ui.grid(columns=3).classes("w-full gap-4"):
        for f in frister:
            if f["key"] == "aksjonaerregister":
                # Ingen automatisk sjekk — vis sluttilstand direkte uten spinner.
                card, content = _fristkort(f["tittel"], f["undertittel"])
                _fristkort_ventende(
                    card, content, f["tittel"], f["undertittel"],
                    f["maaned"], f["dag"], f["beskrivelse"],
                    FristStatus(beskrivelse="Ingen automatisk sjekk tilgjengelig"),
                )
            elif not orgnr_konfigurert:
                # Ingen API-sjekk uten orgnr — hopp over spinner og vis ventende direkte.
                card, content = _fristkort(f["tittel"], f["undertittel"])
                _fristkort_ventende(
                    card, content, f["tittel"], f["undertittel"],
                    f["maaned"], f["dag"], f["beskrivelse"],
                )
            else:
                card, content = _fristkort(f["tittel"], f["undertittel"])
            kort[f["key"]] = (card, content, f)

    async def _sjekk_en_frist(key, check_fn, orgnr, aar):
        """Kjør én fristsjekk og oppdater kortet."""
        card, content, info = kort[key]
        try:
            result = await run.io_bound(check_fn, orgnr, aar)
            if result.innfridd:
                _fristkort_innfridd(card, content, info["tittel"], info["undertittel"], result)
            else:
                _fristkort_ventende(
                    card, content, info["tittel"], info["undertittel"],
                    info["maaned"], info["dag"], info["beskrivelse"], result,
                )
        except Exception:
            _fristkort_ventende(
                card, content, info["tittel"], info["undertittel"],
                info["maaned"], info["dag"], info["beskrivelse"],
            )

    async def sjekk_alle_frister():
        import asyncio
        from wenche.fristsjekk import (
            regnskapsaar_for_frist,
            sjekk_aarsregnskap,
            sjekk_skattemelding,
        )

        orgnr = state.org_nummer

        # Ikke send API-kall med placeholder eller tomt org.nr.
        # Kortene er allerede bygget i ventende-tilstand når dette er tilfelle.
        if not orgnr or orgnr == "123456789":
            return

        # Hvert kort sjekkes for sitt eget regnskapsår, utledet fra fristen.
        # Slik blir API-statusen konsistent med nedtellingen i samme kort.
        skattemelding_aar = regnskapsaar_for_frist(
            kort["skattemelding"][2]["maaned"], kort["skattemelding"][2]["dag"]
        )
        aarsregnskap_aar = regnskapsaar_for_frist(
            kort["aarsregnskap"][2]["maaned"], kort["aarsregnskap"][2]["dag"]
        )

        await asyncio.gather(
            _sjekk_en_frist("skattemelding", sjekk_skattemelding, orgnr, skattemelding_aar),
            _sjekk_en_frist("aarsregnskap", sjekk_aarsregnskap, orgnr, aarsregnskap_aar),
        )

    # Sjekk automatisk ved sidelasting kun hvis orgnr er konfigurert.
    if orgnr_konfigurert:
        ui.timer(1.0, sjekk_alle_frister, once=True)

    ui.separator().classes("my-6")
    ui.label("Ansvarsfraskrivelse").classes("text-sm font-semibold text-slate-700 mb-1")
    ui.label(
        "Wenche er et hjelpeverktøy for enkle holdingselskaper og er i aktiv utvikling. "
        "Det er ikke en erstatning for profesjonell regnskapsbistand. "
        "Kontroller alltid at genererte dokumenter er korrekte før innsending. "
        "Du er selv ansvarlig for at innsendte opplysninger er riktige."
    ).classes("text-xs text-slate-500")


# ---------------------------------------------------------------------------
# Fane 1: Oppsett
# ---------------------------------------------------------------------------

def _bygg_oppsett_fane() -> None:
    ui.label("Steg 1 av 6").classes("text-xs text-slate-400 mt-2 uppercase tracking-wide")
    ui.label("Oppsett og tilkobling").classes("text-lg font-semibold")
    ui.label(
        "Fyll inn Maskinporten-konfigurasjonen og test tilkoblingen mot Altinn."
    ).classes("text-slate-500 text-sm mb-4")

    # --- Aktivt miljø ---
    seksjonstittel("Aktivt miljø")
    ui.label(
        "Avgjør hvilket sett credentials Wenche bruker. Du kan konfigurere "
        "begge miljø samtidig under, og bytte aktivt miljø her uten å redigere noe annet."
    ).classes("text-sm text-slate-500 mb-3")

    dot_env_fil = Path(".env")
    aktivt_env = os.getenv("WENCHE_ENV", "prod")

    inp_env = ui.radio(
        {"test": "Testmiljø (tt02)", "prod": "Produksjon"},
        value=aktivt_env,
    ).props("inline color=primary")

    # Når brukeren bytter radio-knappen, oppdater os.environ umiddelbart slik
    # at andre faner (særlig Hjem-fanens statussjekk) reflekterer det nye
    # miljøet uten å vente på Lagre-klikk. Lagre-knappen persisterer fortsatt
    # endringen til .env-filen.
    def _radio_endret():
        os.environ["WENCHE_ENV"] = inp_env.value
        miljo_navn = "testmiljø" if inp_env.value == "test" else "produksjon"
        ui.notify(
            f"Aktivt miljø satt til {miljo_navn}. Klikk Lagre for å persistere.",
            type="info",
        )

    inp_env.on_value_change(lambda _: _radio_endret())

    # --- Credentials per miljø ---
    ui.separator().classes("my-4")
    seksjonstittel("Maskinporten-credentials")
    ui.label(
        "Klient-ID og Nøkkel-ID finner du i Digdirs selvbetjeningsportal. "
        "Test- og prod-Maskinporten er separate registre — fyll inn credentials "
        "for hvert miljø du har registrert klient i."
    ).classes("text-sm text-slate-500 mb-3")

    test_card_inputs: dict[str, ui.input] = {}
    prod_card_inputs: dict[str, ui.input] = {}

    with ui.grid(columns=2).classes("w-full gap-4"):
        # Test-card
        with ui.card().classes("w-full p-4 border border-slate-200 shadow-none rounded-xl"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("science").classes("text-slate-500")
                ui.label("Testmiljø (tt02)").classes("font-semibold text-slate-800")
            test_card_inputs["client_id"] = ui.input(
                "Klient-ID (test)",
                value=_les_konfig_for_milj("MASKINPORTEN_CLIENT_ID", "test"),
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            ).classes("w-full")
            test_card_inputs["kid"] = ui.input(
                "Nøkkel-ID (test)",
                value=_les_konfig_for_milj("MASKINPORTEN_KID", "test"),
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            ).classes("w-full")

        # Prod-card
        with ui.card().classes("w-full p-4 border border-slate-200 shadow-none rounded-xl"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("business").classes("text-slate-700")
                ui.label("Produksjon").classes("font-semibold text-slate-800")
            prod_card_inputs["client_id"] = ui.input(
                "Klient-ID (prod)",
                value=_les_konfig_for_milj("MASKINPORTEN_CLIENT_ID", "prod"),
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            ).classes("w-full")
            prod_card_inputs["kid"] = ui.input(
                "Nøkkel-ID (prod)",
                value=_les_konfig_for_milj("MASKINPORTEN_KID", "prod"),
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            ).classes("w-full")

    # --- Felles for begge miljø ---
    ui.separator().classes("my-4")
    seksjonstittel("Felles innstillinger")
    ui.label(
        "Disse gjelder uansett aktivt miljø."
    ).classes("text-sm text-slate-500 mb-3")

    with ui.grid(columns=2).classes("w-full gap-4"):
        inp_orgnr = ui.input(
            "Organisasjonsnummer",
            value=os.getenv("ORG_NUMMER", ""),
            placeholder="123456789",
        ).classes("w-full").tooltip("Organisasjonsnummeret til selskapet du sender inn på vegne av.")

        pem_opplasting = ui.upload(
            label="Last opp privat nøkkel (.pem)",
            auto_upload=True,
        ).props("flat bordered").classes("w-full").tooltip("Din maskinporten_privat.pem-fil. Lagres lokalt og sendes aldri til noen server.")

    pem_bytes_holder: list[bytes] = []

    def pem_mottatt(e):
        pem_bytes_holder.clear()
        pem_bytes_holder.append(e.content.read())
        ui.notify("Nøkkelfil lastet opp. Klikk 'Lagre konfigurasjon' for å lagre.", type="info")

    pem_opplasting.on_upload(pem_mottatt)

    async def lagre_konfig():
        from dotenv import set_key
        dot_env_fil.touch(exist_ok=True)
        valgt_env = inp_env.value

        # Lagre credentials per miljø — begge sett skrives uavhengig av aktivt miljø.
        for kort_env, inputs in [("test", test_card_inputs), ("prod", prod_card_inputs)]:
            suffix = kort_env.upper()
            if inputs["client_id"].value:
                navn = f"MASKINPORTEN_CLIENT_ID_{suffix}"
                set_key(str(dot_env_fil), navn, inputs["client_id"].value)
                os.environ[navn] = inputs["client_id"].value
            if inputs["kid"].value:
                navn = f"MASKINPORTEN_KID_{suffix}"
                set_key(str(dot_env_fil), navn, inputs["kid"].value)
                os.environ[navn] = inputs["kid"].value

        if inp_orgnr.value:
            set_key(str(dot_env_fil), "ORG_NUMMER", inp_orgnr.value)
            os.environ["ORG_NUMMER"] = inp_orgnr.value
        set_key(str(dot_env_fil), "WENCHE_ENV", valgt_env)
        os.environ["WENCHE_ENV"] = valgt_env
        if pem_bytes_holder:
            nokkel_sti = Path("maskinporten_privat.pem")
            nokkel_sti.write_bytes(pem_bytes_holder[0])
            nokkel_sti.chmod(0o600)
            set_key(str(dot_env_fil), "MASKINPORTEN_PRIVAT_NOKKEL", str(nokkel_sti))
            os.environ["MASKINPORTEN_PRIVAT_NOKKEL"] = str(nokkel_sti)
        konfig_status.refresh()
        miljo_navn = "testmiljø" if valgt_env == "test" else "produksjon"
        ui.notify(f"Konfigurasjon lagret. Aktivt miljø: {miljo_navn}.", type="positive")

    ui.button("Lagre konfigurasjon", on_click=lagre_konfig).props("color=primary").classes("mt-2")

    # --- Statusoversikt ---
    ui.separator().classes("my-4")
    seksjonstittel("Status")

    @ui.refreshable
    def konfig_status():
        sjekker = _sjekk_konfig()
        for ok, tittel, detalj in sjekker:
            ikon = "✅" if ok else "⚠️"
            ui.label(f"{ikon}  {tittel}: {detalj}").classes(
                "text-sm " + ("text-green-700" if ok else "text-amber-700")
            )

    konfig_status()

    # --- Tilkoblingstest ---
    ui.separator().classes("my-4")
    seksjonstittel("Tilkoblingstest")
    ui.label(
        "Tester Maskinporten og Altinn-veksling for hvert miljø som har credentials konfigurert. "
        "Ingen data sendes inn og tokens lagres ikke."
    ).classes("text-sm text-slate-500 mb-2")

    test_resultat_container = ui.column().classes("w-full gap-1 mt-3")

    def _milj_har_credentials(env: str) -> bool:
        return bool(
            _les_konfig_for_milj("MASKINPORTEN_CLIENT_ID", env)
            and _les_konfig_for_milj("MASKINPORTEN_KID", env)
        )

    def _tolk_feilmelding(env: str, raw: str) -> str:
        """Oversett rå auth-feilmelding til brukervennlig norsk."""
        import json
        import re

        miljo = "testmiljøet (tt02)" if env == "test" else "produksjonsmiljøet"
        portal = (
            "sjolvbetjening.test.samarbeid.digdir.no"
            if env == "test"
            else "sjolvbetjening.samarbeid.digdir.no"
        )

        # Maskinporten-feil: "Maskinporten svarte 400:\n{...json...}"
        if "Maskinporten svarte" in raw:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                try:
                    p = json.loads(m.group(0))
                    kode = p.get("error", "")
                    beskr = p.get("error_description", "")

                    if kode == "invalid_grant" and "Client authentication" in beskr:
                        return (
                            f"Klient-ID-en din er ikke registrert i {miljo} "
                            f"hos Maskinporten. Sjekk at klienten er opprettet "
                            f"i riktig portal ({portal}) og at klient-ID + "
                            f"nøkkel-ID i {('test' if env == 'test' else 'prod')}-kortet "
                            f"matcher det som ligger der."
                        )
                    if kode == "invalid_grant":
                        return f"Maskinporten avviste innloggingen: {beskr or kode}."
                    if kode == "invalid_client":
                        return f"Maskinporten kjenner ikke klient-ID-en i {miljo}."
                    if kode == "invalid_scope":
                        return (
                            "Klienten mangler ett eller flere scopes du har "
                            f"prøvd å hente. Legg dem til på klienten i {portal}."
                        )
                    return f"Maskinporten-feil ({kode}): {beskr or 'ingen detaljer'}."
                except (json.JSONDecodeError, AttributeError):
                    pass

            m = re.search(r"svarte (\d+)", raw)
            if m:
                return (
                    f"Maskinporten svarte med HTTP {m.group(1)} for {miljo}. "
                    "Sjekk credentials og at klienten er registrert i riktig miljø."
                )

        # Andre RuntimeError-meldinger (manglende env, manglende nøkkelfil osv.)
        # Vis bare første linje for å holde meldingen kort.
        return raw.split("\n")[0]

    def _test_for_milj(env: str) -> tuple[bool, str]:
        """Test tilkobling for ett spesifikt miljø. Returnerer (ok, melding)."""
        opprinnelig_env = os.environ.get("WENCHE_ENV")
        os.environ["WENCHE_ENV"] = env
        try:
            auth.login(lagre_token=False)
            return True, "Tilkobling OK"
        except RuntimeError as e:
            return False, _tolk_feilmelding(env, str(e))
        except httpx.HTTPStatusError as e:
            kode = e.response.status_code
            if kode == 401:
                return False, (
                    f"Altinn avviste tokenet (HTTP 401). Maskinporten-tokenet "
                    f"ble hentet, men Altinn aksepterer det ikke. Vanligste "
                    f"årsak: scopene altinn:instances.* er ikke aktivert på "
                    f"klienten din i dette miljøet."
                )
            if kode == 403:
                return False, (
                    f"Altinn avslo tilgangen (HTTP 403). Sjekk at systembruker "
                    f"er opprettet og godkjent for org.nr. {os.getenv('ORG_NUMMER', '')}."
                )
            return False, f"Altinn svarte med HTTP {kode}."
        except Exception as e:
            return False, f"Uventet feil ({type(e).__name__}): {e}"
        finally:
            if opprinnelig_env is None:
                os.environ.pop("WENCHE_ENV", None)
            else:
                os.environ["WENCHE_ENV"] = opprinnelig_env

    async def test_tilkobling():
        test_resultat_container.clear()
        n = ui.notification("Tester tilkobling for begge miljø...", spinner=True, timeout=None)

        resultater = []
        for env in ["test", "prod"]:
            if not _milj_har_credentials(env):
                resultater.append((env, None, "Ingen credentials konfigurert"))
                continue
            ok, melding = await run.io_bound(_test_for_milj, env)
            resultater.append((env, ok, melding))

        n.dismiss()

        with test_resultat_container:
            for env, ok, melding in resultater:
                miljo_navn = "Testmiljø (tt02)" if env == "test" else "Produksjon"
                if ok is None:
                    ikon, farge = "remove_circle_outline", "text-slate-400"
                elif ok:
                    ikon, farge = "check_circle", "text-green-600"
                else:
                    ikon, farge = "error", "text-red-600"
                # Grid med fast ikon-kolonne og fleksibel tekst-kolonne så lange
                # meldinger wrapper i tekstkolonnen i stedet for å skyve ikonet
                # ned på egen linje.
                with ui.element("div").classes(
                    "grid grid-cols-[auto_1fr] gap-2 items-start w-full"
                ):
                    ui.icon(ikon).classes(f"{farge} text-base mt-0.5")
                    with ui.column().classes("gap-0 min-w-0"):
                        ui.label(miljo_navn).classes("text-sm font-medium text-slate-800")
                        ui.label(melding).classes(f"text-xs {farge}")

    ui.button("Test tilkobling mot Altinn", on_click=test_tilkobling).props("color=primary outline")

    # --- Systembruker-oppsett ---
    ui.separator().classes("my-4")
    with ui.expansion("Systembruker-oppsett (gjøres én gang per miljø)").classes("w-full"):
        ui.label(
            "Altinn 3 krever at Wenche er registrert som leverandørsystem og at organisasjonen din "
            "har godkjent en systembruker. Dette gjøres én gang, og på nytt hvis du bytter miljø."
        ).classes("text-sm text-slate-500 mb-3")

        seksjonstittel("Steg 1. Registrer Wenche i systemregisteret")
        ui.label(
            "Registrerer Wenche i Altinns systemregister. Kan kjøres på nytt uten skade."
        ).classes("text-sm text-slate-500 mb-2")

        async def registrer_system():
            n = ui.notification("Registrerer system i Altinn...", spinner=True, timeout=None)
            try:
                token = await run.io_bound(auth.login_admin)
                orgnr = os.getenv("ORG_NUMMER")
                client_id = os.getenv("MASKINPORTEN_CLIENT_ID")
                svar = await run.io_bound(systembruker.registrer_system, token, orgnr, client_id)
                n.message = "System oppdatert." if svar.get("oppdatert") else "System registrert."
                n.spinner = False
                n.type = "positive"
                n.timeout = 5
            except Exception as e:
                n.message = f"Feil: {e}"
                n.spinner = False
                n.type = "negative"
                n.timeout = 0
                n.close_button = "Lukk"

        ui.button("Registrer Wenche i systemregisteret", on_click=registrer_system).props("color=primary outline")

        seksjonstittel("Steg 1b. Oppdater rettigheter på eksisterende systembruker")
        ui.label(
            "Hvis systembrukeren allerede er godkjent og du har lagt til nye rettigheter, "
            "send en endringsforespørsel. Eksisterende rettigheter beholdes — kun nye legges til."
        ).classes("text-sm text-slate-500 mb-2")
        endrings_url_container = ui.element("div")

        async def oppdater_systembruker():
            n = ui.notification("Henter systembrukere...", spinner=True, timeout=None)
            try:
                token = await run.io_bound(auth.login_admin)
                vendor_orgnr = os.getenv("ORG_NUMMER")
                env = os.getenv("WENCHE_ENV", "prod")
                orgnr = os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr
                brukere = await run.io_bound(systembruker.hent_systembrukere, token, vendor_orgnr)
                if not brukere:
                    n.message = "Ingen aktive systembrukere funnet. Bruk steg 2 for å opprette ny."
                    n.spinner = False
                    n.type = "info"
                    n.timeout = 6
                    return
                # Finn systembrukeren for riktig party-org (i test: SKD_TEST_ORG_NUMMER)
                treff = next(
                    (b for b in brukere if b.get("reporteeOrgNo") == orgnr),
                    brukere[0],
                )
                bruker_id = treff["id"]
                # Send kun den nye skattemelding-rettigheten.
                # Altinn-API-et krever at uendrede rettigheter utelates fra changerequest.
                svar = await run.io_bound(
                    systembruker.opprett_endringsforespørsel,
                    token,
                    bruker_id,
                    [systembruker._SKATTEMELDING_RETT],
                )
                confirm_url = svar.get("confirmUrl") or svar.get("ConfirmUrl", "")
                endrings_url_container.clear()
                with endrings_url_container:
                    ui.link("Godkjenn i Altinn →", confirm_url, new_tab=True).classes("text-blue-600 font-medium text-sm")
                n.message = f"Endringsforespørsel opprettet (status: {svar.get('status', '')})"
                n.spinner = False
                n.type = "positive"
                n.timeout = 5
            except Exception as e:
                n.message = f"Feil: {e}"
                n.spinner = False
                n.type = "negative"
                n.timeout = 0
                n.close_button = "Lukk"

        ui.button("Oppdater systembruker-rettigheter", on_click=oppdater_systembruker).props("color=primary outline")

        seksjonstittel("Steg 2. Opprett systembrukerforespørsel")
        godkjenn_url_container = ui.element("div")

        async def opprett_forespørsel():
            n = ui.notification("Oppretter systembrukerforespørsel...", spinner=True, timeout=None)
            try:
                token = await run.io_bound(auth.login_admin)
                vendor_orgnr = os.getenv("ORG_NUMMER")
                env = os.getenv("WENCHE_ENV", "prod")
                party_orgnr = os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr
                svar = await run.io_bound(systembruker.opprett_forespørsel, token, vendor_orgnr, party_orgnr)
                request_id = svar.get("id", "")
                if request_id:
                    _lagre_request_id(request_id)
                confirm_url = svar.get("confirmUrl", "")
                godkjenn_url_container.clear()
                with godkjenn_url_container:
                    ui.link("Godkjenn i Altinn →", confirm_url, new_tab=True).classes("text-blue-600 font-medium text-sm")
                n.message = f"Forespørsel opprettet (status: {svar['status']})"
                n.spinner = False
                n.type = "positive"
                n.timeout = 5
            except Exception as e:
                n.message = f"Feil: {e}"
                n.spinner = False
                n.type = "negative"
                n.timeout = 0
                n.close_button = "Lukk"

        ui.button("Opprett systembrukerforespørsel", on_click=opprett_forespørsel).props("color=primary outline")

        seksjonstittel("Sjekk godkjenningsstatus")

        async def sjekk_status():
            request_id = _les_request_id()
            if not request_id:
                ui.notify("Ingen lagret forespørsels-ID. Opprett en forespørsel først.", type="warning")
                return
            n = ui.notification("Henter status...", spinner=True, timeout=None)
            try:
                token = await run.io_bound(auth.login_admin)
                svar = await run.io_bound(systembruker.hent_forespørsel_status, token, request_id)
                status = svar.get("status", "ukjent")
                n.spinner = False
                n.timeout = 6
                if status == "Accepted":
                    n.message = "Systembruker er godkjent. Du kan nå sende inn dokumenter."
                    n.type = "positive"
                elif status == "New":
                    n.message = "Forespørselen venter på godkjenning."
                    n.type = "info"
                elif status == "Rejected":
                    n.message = "Forespørselen ble avvist. Opprett en ny forespørsel."
                    n.type = "negative"
                    n.timeout = 0
                    n.close_button = "Lukk"
                else:
                    n.message = f"Status: {status}"
                    n.type = "info"
            except Exception as e:
                n.message = f"Feil: {e}"
                n.spinner = False
                n.type = "negative"
                n.timeout = 0
                n.close_button = "Lukk"

        ui.button("Sjekk status", on_click=sjekk_status).props("color=primary outline")


# ---------------------------------------------------------------------------
# Fane 2: Selskapsopplysninger
# ---------------------------------------------------------------------------

def _bygg_selskap_fane() -> None:
    ui.label("Steg 2 av 6").classes("text-xs text-slate-400 mt-2 uppercase tracking-wide")
    ui.label("Selskapsopplysninger").classes("text-lg font-semibold")
    ui.label("Fyll inn grunnleggende informasjon om selskapet.").classes("text-slate-500 text-sm mb-4")

    # SAF-T import
    with ui.expansion(
        "Importer fra SAF-T Financial",
        caption="Anbefalt for nye brukere, fyll inn alle tall automatisk",
        icon="file_upload",
    ).props("bordered").classes("w-full mb-4"):
        ui.label(
            "SAF-T Financial er et standardisert revisjonsfilformat som brukes av alle norske regnskapssystemer "
            "(Fiken, Tripletex, Visma, Uni Micro, PowerOffice Go m.fl.). "
            "Du kan eksportere SAF-T fra regnskapssystemet ditt og importere det her for å fylle inn tall automatisk.\n\n"
            "Merk: Felt som daglig leder, styreleder, stiftelsesår, aksjonærer og foregående års resultat "
            "finnes ikke i SAF-T og må fylles inn manuelt."
        ).classes("text-sm text-slate-600 mb-3 whitespace-pre-line")

        saft_bytes_holder: list[bytes] = []

        saft_opplasting = ui.upload(
            label="Last opp SAF-T Financial XML-fil",
            auto_upload=True,
        ).props("flat bordered").classes("w-full")

        def saft_mottatt(e):
            saft_bytes_holder.clear()
            saft_bytes_holder.append(e.content.read())
            ui.notify(f"Fil lastet opp: {e.name}", type="info")

        saft_opplasting.on_upload(saft_mottatt)

        async def importer_saft():
            if not saft_bytes_holder:
                ui.notify("Last opp en SAF-T-fil først.", type="warning")
                return
            from wenche.saft import importer as importer_saft_fil
            try:
                with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
                    tmp.write(saft_bytes_holder[0])
                    tmp_sti = tmp.name

                data = await run.io_bound(importer_saft_fil, tmp_sti)
                Path(tmp_sti).unlink(missing_ok=True)

                # Bevar felt SAF-T ikke dekker
                if CONFIG_FIL.exists():
                    with open(CONFIG_FIL, encoding="utf-8") as f_eks:
                        eks = yaml.safe_load(f_eks) or {}
                    for felt in ("daglig_leder", "styreleder", "stiftelsesaar", "kontakt_epost"):
                        eks_verdi = eks.get("selskap", {}).get(felt)
                        if eks_verdi:
                            data["selskap"][felt] = eks_verdi
                    for bevar in ("aksjonaerer", "skattemelding", "noter"):
                        if eks.get(bevar):
                            data[bevar] = eks[bevar]

                with open(CONFIG_FIL, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)

                state.les_config()
                ui.notify(f"SAF-T importert for {state.navn}.", type="positive")
            except Exception as e:
                ui.notify(f"Feil ved import: {e}", type="negative", timeout=0)

        ui.button("Importer SAF-T", on_click=importer_saft).props("color=primary outline").classes("mt-2")

    ui.separator().classes("my-2")

    with ui.grid(columns=2).classes("w-full gap-4"):
        txt("Selskapsnavn", "navn")
        txt("Forretningsadresse", "forretningsadresse")
        txt("Organisasjonsnummer (9 siffer)", "org_nummer", placeholder="123456789")
        num("Stiftelsesår", "stiftelsesaar", step=1, min_val=1900)
        txt("Daglig leder", "daglig_leder")
        num("Aksjekapital (NOK)", "aksjekapital", step=1000)
        txt("Styreleder", "styreleder")
        txt(
            "Kontakt-e-post",
            "kontakt_epost",
            tooltip="Påkrevd for aksjonærregisteroppgave (RF-1086).",
        )
        num("Regnskapsår", "regnskapsaar", step=1, min_val=2000)

    ui.separator().classes("my-4")

    def lagre_selskap():
        state.lagre_config()
        ui.notify(f"Lagret til {CONFIG_FIL.resolve()}", type="positive")

    ui.button("Lagre selskapsopplysninger", on_click=lagre_selskap).props("color=primary")


# ---------------------------------------------------------------------------
# Fane 3: Regnskap og balanse
# ---------------------------------------------------------------------------

def _bygg_regnskap_fane() -> None:
    ui.label("Steg 3 av 6").classes("text-xs text-slate-400 mt-2 uppercase tracking-wide")
    ui.label("Regnskap og balanse").classes("text-lg font-semibold")
    ui.label("Fyll inn tall fra resultatregnskapet og balansen.").classes("text-slate-500 text-sm mb-4")

    # Samlede metrikker (oppdateres reaktivt)
    with ui.row().classes("gap-3 flex-wrap mb-4"):
        lbl_driftsinntekter = metric_kort("Sum driftsinntekter", kr(state.sum_driftsinntekter))
        lbl_driftskostnader = metric_kort("Sum driftskostnader", kr(state.sum_driftskostnader))
        lbl_driftsresultat = metric_kort("Driftsresultat", kr(state.driftsresultat))
        lbl_resultat = metric_kort("Resultat før skatt", kr(state.resultat_foer_skatt))

    def oppdater_rr():
        lbl_driftsinntekter.set_text(kr(state.sum_driftsinntekter))
        lbl_driftskostnader.set_text(kr(state.sum_driftskostnader))
        lbl_driftsresultat.set_text(kr(state.driftsresultat))
        lbl_resultat.set_text(kr(state.resultat_foer_skatt))

    # Resultatregnskap-inndata
    with ui.grid(columns=2).classes("w-full gap-6"):
        with ui.column():
            seksjonstittel("Driftsinntekter")
            num("Salgsinntekter", "salgsinntekter", on_change=oppdater_rr)
            num("Andre driftsinntekter", "andre_driftsinntekter", on_change=oppdater_rr)

            seksjonstittel("Driftskostnader")
            num("Lønnskostnader", "loennskostnader", on_change=oppdater_rr)
            num("Avskrivninger", "avskrivninger", on_change=oppdater_rr)
            num("Andre driftskostnader", "andre_driftskostnader", on_change=oppdater_rr)

        with ui.column():
            seksjonstittel("Finansinntekter")
            num(
                "Utbytte fra datterselskap",
                "utbytte_fra_datterselskap",
                on_change=oppdater_rr,
                tooltip="Utbytte mottatt fra heleide datterselskaper. Inngår i vurderingen av fritaksmetoden.",
            )
            num("Andre finansinntekter", "andre_finansinntekter", on_change=oppdater_rr)

            seksjonstittel("Finanskostnader")
            num("Rentekostnader", "rentekostnader", on_change=oppdater_rr)
            num("Andre finanskostnader", "andre_finanskostnader", on_change=oppdater_rr)

    ui.separator().classes("my-6")
    ui.label("Balanse").classes("text-lg font-semibold")

    # Balansesjekk-banner (oppdateres reaktivt)
    balanse_banner = ui.label("").classes("text-sm font-semibold mt-2 mb-4")

    with ui.row().classes("gap-3 flex-wrap mb-4"):
        lbl_eiendeler = metric_kort("Sum eiendeler", kr(state.sum_eiendeler))
        lbl_ek_gjeld = metric_kort("Sum EK og gjeld", kr(state.sum_ek_og_gjeld))

    def oppdater_balanse():
        lbl_eiendeler.set_text(kr(state.sum_eiendeler))
        lbl_ek_gjeld.set_text(kr(state.sum_ek_og_gjeld))
        if state.er_i_balanse:
            balanse_banner.set_text("✓ Balansen stemmer")
            balanse_banner.classes(remove="text-red-600", add="text-green-600")
        else:
            balanse_banner.set_text(f"✗ Differanse: {kr(state.balanseforskjell)}")
            balanse_banner.classes(remove="text-green-600", add="text-red-600")

    oppdater_balanse()

    with ui.grid(columns=2).classes("w-full gap-6"):
        with ui.column():
            seksjonstittel("Eiendeler")
            ui.label("Anleggsmidler").classes("text-xs text-slate-500 uppercase tracking-wide mt-2")
            num(
                "Aksjer i datterselskap",
                "aksjer_i_datterselskap",
                on_change=oppdater_balanse,
                tooltip="Kostpris for aksjer i heleide datterselskaper (typisk over 90 % eierandel).",
            )
            num("Andre aksjer", "andre_aksjer", on_change=oppdater_balanse)
            num("Langsiktige fordringer", "langsiktige_fordringer", on_change=oppdater_balanse)

            ui.label("Omløpsmidler").classes("text-xs text-slate-500 uppercase tracking-wide mt-3")
            num("Kortsiktige fordringer", "kortsiktige_fordringer", on_change=oppdater_balanse)
            num("Bankinnskudd", "bankinnskudd", step=100, on_change=oppdater_balanse)

        with ui.column():
            seksjonstittel("Egenkapital og gjeld")
            ui.label("Egenkapital").classes("text-xs text-slate-500 uppercase tracking-wide mt-2")
            num("Aksjekapital (balanse)", "ek_aksjekapital", on_change=oppdater_balanse)
            num("Overkursfond", "overkursfond", min_val=None, on_change=oppdater_balanse)
            num(
                "Annen egenkapital (negativ ved underskudd)",
                "annen_egenkapital",
                min_val=None,
                on_change=oppdater_balanse,
            )

            ui.label("Langsiktig gjeld").classes("text-xs text-slate-500 uppercase tracking-wide mt-3")
            num("Lån fra aksjonær", "laan_fra_aksjonaer", on_change=oppdater_balanse)
            num("Andre langsiktige lån", "andre_langsiktige_laan", on_change=oppdater_balanse)

            ui.label("Kortsiktig gjeld").classes("text-xs text-slate-500 uppercase tracking-wide mt-3")
            num("Leverandørgjeld", "leverandoergjeld", on_change=oppdater_balanse)
            num("Skyldige offentlige avgifter", "skyldige_offentlige_avgifter", on_change=oppdater_balanse)
            num("Annen kortsiktig gjeld", "annen_kortsiktig_gjeld", on_change=oppdater_balanse)

    # Sammenligningstall — foregående år
    ui.separator().classes("my-6")
    with ui.expansion("Sammenligningstall, foregående år (påkrevd, rskl. § 6-6)").classes("w-full"):
        ui.label(
            "Fyll inn tilsvarende tall fra fjorårets regnskap. "
            "Disse brukes som sammenligningstall i årsregnskapet til Brønnøysundregistrene."
        ).classes("text-sm text-slate-500 mb-3")

        ui.label("Resultatregnskap").classes("text-base font-semibold mt-2 mb-2")
        with ui.grid(columns=2).classes("w-full gap-4"):
            num("Salgsinntekter", "f_salgsinntekter")
            num("Utbytte fra datterselskap", "f_utbytte_fra_datterselskap")
            num("Andre driftsinntekter", "f_andre_driftsinntekter")
            num("Andre finansinntekter", "f_andre_finansinntekter")
            num("Lønnskostnader", "f_loennskostnader")
            num("Rentekostnader", "f_rentekostnader")
            num("Avskrivninger", "f_avskrivninger")
            num("Andre finanskostnader", "f_andre_finanskostnader")
            num("Andre driftskostnader", "f_andre_driftskostnader")

        ui.label("Balanse").classes("text-base font-semibold mt-4 mb-2")
        with ui.grid(columns=2).classes("w-full gap-4"):
            num("Aksjer i datterselskap", "f_aksjer_i_datterselskap")
            num("Aksjekapital", "f_ek_aksjekapital")
            num("Andre aksjer", "f_andre_aksjer")
            num("Overkursfond", "f_overkursfond", min_val=None)
            num("Langsiktige fordringer", "f_langsiktige_fordringer")
            num("Annen egenkapital", "f_annen_egenkapital", min_val=None)
            num("Kortsiktige fordringer", "f_kortsiktige_fordringer")
            num("Lån fra aksjonær", "f_laan_fra_aksjonaer")
            num("Bankinnskudd", "f_bankinnskudd", step=100)
            num("Andre langsiktige lån", "f_andre_langsiktige_laan")
            ui.label("").classes("w-full")
            num("Leverandørgjeld", "f_leverandoergjeld")
            ui.label("").classes("w-full")
            num("Skyldige offentlige avgifter", "f_skyldige_offentlige_avgifter")
            ui.label("").classes("w-full")
            num("Annen kortsiktig gjeld", "f_annen_kortsiktig_gjeld")

    ui.separator().classes("my-4")

    def lagre_regnskap():
        state.lagre_config()
        ui.notify(f"Lagret til {CONFIG_FIL.resolve()}", type="positive")

    ui.button("Lagre regnskapstall", on_click=lagre_regnskap).props("color=primary")


# ---------------------------------------------------------------------------
# Fane 4: Aksjonærer
# ---------------------------------------------------------------------------

def _bygg_aksjonaer_fane() -> None:
    ui.label("Steg 4 av 6").classes("text-xs text-slate-400 mt-2 uppercase tracking-wide")
    ui.label("Aksjonærer").classes("text-lg font-semibold")
    ui.label("Fyll inn opplysninger om aksjonærene.").classes("text-slate-500 text-sm mb-4")

    @ui.refreshable
    def aksjonaer_liste() -> None:
        for i, a in enumerate(state.aksjonaerer):
            with ui.expansion(
                f"Aksjonær {i + 1}" + (f", {a.navn}" if a.navn else ""),
                value=(i == 0),
            ).classes("w-full mb-2"):
                with ui.grid(columns=2).classes("w-full gap-4"):
                    txt("Navn", "navn", obj=a, on_change=aksjonaer_liste.refresh)
                    num("Antall aksjer", "antall_aksjer", obj=a, step=1, min_val=1)
                    txt("Fødselsnummer (11 siffer)", "fodselsnummer", obj=a)
                    num("Utbytte utbetalt (NOK)", "utbytte_utbetalt", obj=a, min_val=0)
                    txt("Aksjeklasse", "aksjeklasse", obj=a)
                    num(
                        "Innbetalt kapital per aksje (NOK)",
                        "innbetalt_kapital_per_aksje",
                        obj=a,
                        step=1,
                        min_val=0,
                        tooltip="Aksjekapital delt på antall aksjer. Eks: 30 000 kr / 100 aksjer = 300 kr per aksje.",
                    )

                if len(state.aksjonaerer) > 1:
                    def fjern(idx=i):
                        state.aksjonaerer.pop(idx)
                        aksjonaer_liste.refresh()
                    ui.button("Fjern aksjonær", on_click=fjern).props("flat color=negative size=sm").classes("mt-2")

    aksjonaer_liste()

    def legg_til():
        state.aksjonaerer.append(AksjonaerState())
        aksjonaer_liste.refresh()

    ui.separator().classes("my-4")
    with ui.row().classes("gap-3"):
        ui.button("+ Legg til aksjonær", on_click=legg_til).props("outline color=primary")

        def lagre_aksjonaerer():
            state.lagre_config()
            ui.notify(f"Lagret til {CONFIG_FIL.resolve()}", type="positive")

        ui.button("Lagre aksjonærer", on_click=lagre_aksjonaerer).props("color=primary")

    # Advarsel om manglende navn
    mangler_navn = any(not a.navn for a in state.aksjonaerer)
    if mangler_navn:
        ui.label(
            "⚠️  En eller flere aksjonærer mangler navn. Fyll inn og lagre."
        ).classes("text-amber-700 text-sm mt-2")


# ---------------------------------------------------------------------------
# Fane 5: Dokumenter
# ---------------------------------------------------------------------------

def _bygg_dokumenter_fane() -> None:
    ui.label("Steg 5 av 6").classes("text-xs text-slate-400 mt-2 uppercase tracking-wide")
    ui.label("Last ned dokumenter").classes("text-lg font-semibold")
    ui.label(
        "Generer og last ned dokumentene for gjennomgang. Gå til steg 6 når du er klar til å sende inn."
    ).classes("text-slate-500 text-sm mb-4")

    # Skattemelding-innstillinger
    seksjonstittel("Skattemelding-innstillinger")
    with ui.grid(columns=2).classes("w-full gap-4 mb-4"):
        num(
            "Fremførbart underskudd fra tidligere år (NOK)",
            "underskudd",
            min_val=0,
            tooltip="Finnes i fjorårets skattemelding (RF-1028). Sett til 0 hvis selskapet er nytt.",
        )
        with ui.column():
            fritaks_sjekkboks = ui.checkbox(
                "Anvend fritaksmetoden",
                value=state.fritaksmetoden,
                on_change=lambda e: setattr(state, "fritaksmetoden", e.value),
            ).tooltip(
                "Gjelder dersom selskapet har mottatt utbytte fra datterselskaper. "
                "Ved eierandel ≥ 90 % er hele utbyttet skattefritt."
            )
            num(
                "Eierandel i datterselskap (%)",
                "eierandel_datterselskap",
                step=1,
                min_val=0,
            )

    ui.separator().classes("my-4")

    # Nedlastinger
    with ui.grid(columns=3).classes("w-full gap-4"):

        async def last_ned_skattemelding():
            try:
                regnskap = state.bygg_regnskap()
                konfig = SkattemeldingKonfig(
                    underskudd_til_fremfoering=state.underskudd,
                    anvend_fritaksmetoden=state.fritaksmetoden,
                    eierandel_datterselskap=int(state.eierandel_datterselskap),
                )
                tekst = await run.io_bound(sm_modul.generer, regnskap, konfig)
                filnavn = f"skattemelding_{state.regnskapsaar}_{state.org_nummer}.txt"
                ui.download(tekst.encode("utf-8"), filnavn)
            except Exception as e:
                ui.notify(f"Feil: {e}", type="negative", timeout=0)

        ui.button("Last ned skattemelding", on_click=last_ned_skattemelding).props("color=primary outline").classes("w-full")

        async def last_ned_aarsregnskap():
            try:
                regnskap = state.bygg_regnskap()
                feil = ar_modul.valider(regnskap)
                if feil:
                    for f in feil:
                        ui.notify(f, type="negative")
                    return
                orgnr = state.org_nummer
                aar = int(state.regnskapsaar)
                hoved = await run.io_bound(generer_hovedskjema, regnskap)
                under = await run.io_bound(generer_underskjema, regnskap)
                ui.download(hoved, f"aarsregnskap_{aar}_{orgnr}_hovedskjema.xml")
                ui.download(under, f"aarsregnskap_{aar}_{orgnr}_underskjema.xml")
            except Exception as e:
                ui.notify(f"Feil: {e}", type="negative", timeout=0)

        ui.button("Last ned årsregnskap (XML)", on_click=last_ned_aarsregnskap).props("color=primary outline").classes("w-full")

        async def last_ned_aksjonaerregister():
            try:
                oppgave = state.bygg_oppgave()
                feil = akr_modul.valider(oppgave)
                if feil:
                    for f in feil:
                        ui.notify(f, type="negative")
                    return
                base = f"aksjonaerregister_{state.regnskapsaar}_{state.org_nummer}"
                hoved_xml = await run.io_bound(akr_modul.generer_hovedskjema_xml, oppgave)
                ui.download(hoved_xml, f"{base}_hovedskjema.xml")
                for i, aksjonaer in enumerate(oppgave.aksjonaerer, 1):
                    under_xml = await run.io_bound(akr_modul.generer_underskjema_xml, aksjonaer, oppgave)
                    ui.download(under_xml, f"{base}_underskjema_{i}.xml")
            except Exception as e:
                ui.notify(f"Feil: {e}", type="negative", timeout=0)

        ui.button("Last ned aksjonærregister (XML)", on_click=last_ned_aksjonaerregister).props("color=primary outline").classes("w-full")

    with ui.column().classes("gap-0 mt-1"):
        ui.label("Skattemeldingen sendes digitalt via «Send til Altinn»-fanen, eller manuelt på skatteetaten.no.").classes("text-xs text-slate-500")

    # Obligatoriske noter
    ui.separator().classes("my-6")
    seksjonstittel("Obligatoriske noter")
    ui.label(
        "Regnskapsloven krever at alle foretak utarbeider noter til årsregnskapet. "
        "For små foretak gjelder §§ 7-35 (regnskapsprinsipper), 7-43 (ansatte), "
        "7-45 (lån til nærstående) og 7-46 (fortsatt drift). "
        "Notene sendes ikke inn digitalt. De skal undertegnes av styret og oppbevares av selskapet."
    ).classes("text-sm text-slate-600 mb-3")

    with ui.grid(columns=2).classes("w-full gap-4 mb-4"):
        num(
            "Antall ansatte i regnskapsåret",
            "antall_ansatte",
            step=1,
            min_val=0,
            tooltip=(
                "Tell bare med personer som mottar lønn fra selskapet. "
                "For et passivt holdingselskap uten lønnsutbetalinger er riktig svar 0."
            ),
        )

    @ui.refreshable
    def laan_liste() -> None:
        for i, l in enumerate(state.laan_til_naerstaaende):
            with ui.expansion(
                f"Lån {i + 1}" + (f", {l.motpart}" if l.motpart else ""),
                value=True,
            ).classes("w-full mb-2"):
                ui.select(
                    {
                        "långiver": "Selskapet er långiver, har gitt lån til nærstående",
                        "låntaker": "Selskapet er låntaker, nærstående har gitt lån til selskapet",
                    },
                    label="Selskapets rolle",
                    value=l.retning,
                    on_change=lambda e, laan=l: (
                        setattr(laan, "retning", e.value),
                        laan_liste.refresh(),
                    ),
                ).classes("w-full mb-2")

                if l.retning == "långiver":
                    ui.label(
                        "⚠️  Lån fra AS til personlig aksjonær beskattes løpende som utbytte "
                        "etter skatteloven § 5-22 (gjeldende fra 1. oktober 2022)."
                    ).classes("text-amber-700 text-sm mb-2")

                with ui.grid(columns=2).classes("w-full gap-4"):
                    txt("Nærstående part (navn)", "motpart", obj=l)
                    num(
                        "Rentesats (%)",
                        "rente_prosent",
                        obj=l,
                        step=0.1,
                        min_val=0,
                        tooltip="0 % er lovlig for lån fra aksjonær til selskapet.",
                    )
                    num(
                        "Utestående saldo per 31.12 (NOK)",
                        "saldo",
                        obj=l,
                        min_val=0,
                        tooltip="Samlet gjenstående beløp per 31. desember.",
                    )
                    txt(
                        "Sikkerhet",
                        "sikkerhet",
                        obj=l,
                        tooltip="F.eks. 'pant i aksjer', 'personlig kausjon' eller la stå tomt.",
                    )

                def fjern_laan(idx=i):
                    state.laan_til_naerstaaende.pop(idx)
                    laan_liste.refresh()
                ui.button("Fjern lån", on_click=fjern_laan).props("flat color=negative size=sm").classes("mt-2")

    laan_liste()

    def legg_til_laan():
        state.laan_til_naerstaaende.append(LaanState())
        laan_liste.refresh()

    with ui.row().classes("gap-3 mt-2"):
        ui.button("+ Legg til lån til nærstående", on_click=legg_til_laan).props("outline color=primary")

        async def last_ned_noter():
            try:
                regnskap = state.bygg_regnskap()
                noter = state.bygg_noter()
                tekst = await run.io_bound(noter_modul.generer, regnskap, noter)
                filnavn = f"noter_{state.regnskapsaar}_{state.org_nummer}.txt"
                ui.download(tekst.encode("utf-8"), filnavn)
            except Exception as e:
                ui.notify(f"Feil: {e}", type="negative", timeout=0)

        ui.button("Last ned noter", on_click=last_ned_noter).props("color=primary outline")


# ---------------------------------------------------------------------------
# Fane 6: Send til Altinn
# ---------------------------------------------------------------------------

def _bygg_send_fane() -> None:
    ui.label("Steg 6 av 6").classes("text-xs text-slate-400 mt-2 uppercase tracking-wide")
    ui.label("Send til Altinn").classes("text-lg font-semibold")
    ui.label(
        "Send dokumentene digitalt til Brønnøysundregistrene og Skatteetaten via Altinn."
    ).classes("text-slate-500 text-sm mb-4")

    prod_advarsel = ui.label(
        "⚠️  Du har valgt produksjonsmiljøet. Innsending er bindende og kan ikke trekkes tilbake."
    ).classes("text-amber-700 text-sm mb-4")
    prod_advarsel.set_visibility(False)

    def env_endret(e):
        prod_advarsel.set_visibility(e.value == "prod")

    env_valg = ui.radio(
        {"test": "Testmiljø (tt02), ingen ekte innsending", "prod": "Produksjon, innsending er bindende"},
        value="test",
        on_change=env_endret,
    ).classes("mb-2")

    async def hent_altinn_token() -> str | None:
        try:
            return await run.io_bound(auth.get_altinn_token)
        except RuntimeError as e:
            feilmelding = str(e)
            if "invalid_altinn_customer_configuration" in feilmelding:
                ui.notify(
                    "Systembrukeren er ikke godkjent ennå. Gå til 1. Oppsett → Systembruker-oppsett.",
                    type="negative",
                    timeout=0,
                )
            else:
                ui.notify(f"Autentisering feilet: {feilmelding}", type="negative", timeout=0)
            return None

    async def send_aarsregnskap():
        regnskap = state.bygg_regnskap()
        feil = ar_modul.valider(regnskap)
        if feil:
            for f in feil:
                ui.notify(f, type="negative")
            return
        n = ui.notification("Henter Altinn-token...", spinner=True, timeout=None)
        token = await hent_altinn_token()
        if not token:
            n.dismiss()
            return
        try:
            n.message = "Laster opp årsregnskap til Altinn..."
            def _send():
                with AltinnClient(token, env=env_valg.value) as klient:
                    return ar_modul.send_inn(regnskap, klient)
            sign_url = await run.io_bound(_send)
            n.message = f"Årsregnskap for {regnskap.regnskapsaar} er lastet opp og klar for signering."
            n.spinner = False
            n.type = "positive"
            n.timeout = 0
            n.close_button = "Lukk"
            aarsregnskap_resultat.clear()
            with aarsregnskap_resultat:
                ui.label("Dokumentet venter på din signatur i Altinn:").classes("text-sm text-slate-600")
                ui.link("Signer i Altinn →", sign_url, new_tab=True).classes("text-blue-600 font-medium")
        except Exception as e:
            n.message = f"Innsending feilet: {e}"
            n.spinner = False
            n.type = "negative"
            n.timeout = 0
            n.close_button = "Lukk"

    async def send_aksjonaerregister():
        oppgave = state.bygg_oppgave()
        feil = akr_modul.valider(oppgave)
        if feil:
            for f in feil:
                ui.notify(f, type="negative")
            return
        n = ui.notification("Henter Maskinporten-token med SKD-scope...", spinner=True, timeout=None)
        try:
            skd_token = await run.io_bound(auth.get_skd_aksjonaer_token)
            n.message = "Sender aksjonærregisteroppgave til Skatteetaten..."

            def _send():
                with SkdAksjonaerClient(skd_token, env=env_valg.value) as klient:
                    return akr_modul.send_inn(oppgave, klient)

            svar = await run.io_bound(_send)
            n.message = f"Aksjonærregisteroppgave for {state.regnskapsaar} er sendt til Skatteetaten."
            n.spinner = False
            n.type = "positive"
            n.timeout = 0
            n.close_button = "Lukk"
            if svar:
                ui.notify(f"Forsendelse-ID: {svar.get('forsendelseId')}", type="info")
        except Exception as e:
            n.message = f"Innsending feilet: {e}"
            n.spinner = False
            n.type = "negative"
            n.timeout = 0
            n.close_button = "Lukk"

    async def send_skattemelding():
        regnskap = state.bygg_regnskap()
        orgnr = os.getenv("SKD_TEST_ORG_NUMMER", state.org_nummer) if env_valg.value == "test" else state.org_nummer
        n = ui.notification("Henter tokens for skattemelding...", spinner=True, timeout=None)
        try:
            tokens = await run.io_bound(auth.get_skd_skattemelding_tokens)
            n.message = "Henter forhåndsutfylt skattemelding..."

            def _hent_og_send():
                with SkdSkattemeldingClient(tokens["maskinporten_token"], env=env_valg.value) as skd:
                    test_partsnummer = os.getenv("SKD_TEST_PARTSNUMMER") if env_valg.value == "test" else None
                    if test_partsnummer:
                        partsnummer = int(test_partsnummer)
                    else:
                        forhåndsutfylt = skd.hent_forhåndsutfylt(int(state.regnskapsaar), orgnr)
                        partsnummer = hent_partsnummer(forhåndsutfylt)
                    skattemelding_xml = generer_skattemelding_upersonlig(
                        partsnummer=partsnummer,
                        inntektsaar=int(state.regnskapsaar),
                        fremfoert_underskudd=int(state.underskudd),
                    )
                    naeringsspesifikasjon_xml = generer_naeringsspesifikasjon(regnskap, partsnummer)
                    return skd.send(
                        inntektsaar=int(state.regnskapsaar),
                        orgnr=orgnr,
                        skattemelding_xml=skattemelding_xml,
                        altinn_token=tokens["altinn_token"],
                        naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
                    )

            n.message = "Sender skattemelding via Altinn3..."
            instans_id = await run.io_bound(_hent_og_send)
            n.message = f"Skattemelding for {state.regnskapsaar} er sendt til Skatteetaten."
            n.spinner = False
            n.type = "positive"
            n.timeout = 0
            n.close_button = "Lukk"
            ui.notify(f"Instans-ID: {instans_id}", type="info")
        except Exception as e:
            n.message = f"Innsending feilet: {e}"
            n.spinner = False
            n.type = "negative"
            n.timeout = 0
            n.close_button = "Lukk"

    ui.separator().classes("my-4")
    with ui.grid(columns=3).classes("w-full gap-4"):
        ui.button("Send årsregnskap til Altinn", on_click=send_aarsregnskap).props("color=primary").classes("w-full")
        ui.button(
            "Send aksjonærregister til Skatteetaten", on_click=send_aksjonaerregister
        ).props("color=primary").classes("w-full")
        ui.button(
            "Send skattemelding til Skatteetaten", on_click=send_skattemelding
        ).props("color=primary").classes("w-full")

    aarsregnskap_resultat = ui.column().classes("mt-3")


# ---------------------------------------------------------------------------
# Hovedside
# ---------------------------------------------------------------------------

@ui.page("/")
def main() -> None:
    ui.add_css("""
        :root { --q-primary: #2563eb; }
        body { font-family: 'Inter', system-ui, sans-serif; background: #f8fafc; }
        .q-tab__label { font-size: 0.8rem; }
        .q-expansion-item__content { padding: 0 16px 12px; }
        .q-notification__actions .q-btn { color: white !important; }
        .q-btn { text-transform: none !important; letter-spacing: 0.01em !important; }
        .q-tab__label { text-transform: none !important; }
        .q-uploader__subtitle { display: none !important; }
        .q-uploader { border: 1px solid #e2e8f0 !important; box-shadow: none !important; }
        .q-uploader__header { background: #f8fafc !important; color: #475569 !important; }
        .q-uploader__title { font-size: 0.875rem; font-weight: 500; }
        .q-uploader__subtitle { font-size: 0.75rem; }
        .q-uploader__list { min-height: 0 !important; }
    """)
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">'
    )

    with ui.header().classes("bg-slate-800 text-white px-6 py-3 flex items-center gap-4 shadow"):
        ui.label("Wenche").classes("text-xl font-semibold tracking-tight")
        ui.label("Innsending til norske myndigheter").classes("text-sm text-slate-400")

    with ui.footer().classes("bg-white border-t border-slate-200 px-6 py-3"):
        with ui.row().classes("items-center justify-center gap-1 text-xs text-slate-400 w-full"):
            ui.label("Wenche er utviklet av Ole Fredrik Lie og tilgjengelig som")
            ui.link("åpen kildekode", "https://github.com/olefredrik/Wenche", new_tab=True).classes("text-xs text-slate-400")
            ui.label("under MIT-lisens.")

    with ui.tabs().classes("w-full bg-white shadow-sm") as tabs:
        t_hjem = ui.tab("Hjem")
        t_oppsett = ui.tab("1. Oppsett")
        t_selskap = ui.tab("2. Selskap")
        t_regnskap = ui.tab("3. Regnskap")
        t_aksjonaerer = ui.tab("4. Aksjonærer")
        t_dokumenter = ui.tab("5. Dokumenter")
        t_send = ui.tab("6. Send til Altinn")

    with ui.tab_panels(tabs, value=t_hjem).classes("w-full max-w-5xl mx-auto px-4 py-6"):
        with ui.tab_panel(t_hjem):
            _bygg_hjem_fane(tabs, t_oppsett)
        with ui.tab_panel(t_oppsett):
            _bygg_oppsett_fane()
        with ui.tab_panel(t_selskap):
            _bygg_selskap_fane()
        with ui.tab_panel(t_regnskap):
            _bygg_regnskap_fane()
        with ui.tab_panel(t_aksjonaerer):
            _bygg_aksjonaer_fane()
        with ui.tab_panel(t_dokumenter):
            _bygg_dokumenter_fane()
        with ui.tab_panel(t_send):
            _bygg_send_fane()


# ---------------------------------------------------------------------------
# Inngangspunkt
# ---------------------------------------------------------------------------

def run_app() -> None:
    ui.run(
        title="Wenche",
        port=8080,
        reload=False,
        show=True,
        favicon="👵",
    )
