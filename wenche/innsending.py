"""
Delt innsendings-orkestrering brukt av CLI, hostet og self-hosted.

Auth-agnostisk med vilje: kalleren anskaffer tokens/klienter (self-hosted: brukerens egen
Maskinporten-innlogging; hostet: vendor-creds + systembruker-godkjent kunde-org) og sender
dem inn hit. Bygging og validering (`valider_*`) er rent lokalt, uten nettverk, disk eller
binding, slik at dry-run er identisk i alle tre frontene.

Feil meldes som typer fra `wenche.feil`: `ValideringsFeil` (blokkerende lokale feil, med
listen), `MyndighetsFeil` (et kall mot Altinn/Skatteetaten feilet, med steg og status) og
`SkattemeldingValideringsfeil` (Skatteetatens valider-tjeneste avviste meldingen).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from wenche import aarsregnskap as _ar
from wenche import aksjonaerregister as _akr
from wenche import configfelt as _configfelt
from wenche import skattemelding as _sm
from wenche.altinn_client import AltinnClient
from wenche.feil import KonfigFeil, MyndighetsFeil, ValideringsFeil
from wenche.models import Aarsregnskap
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skattemelding_xml import (
    er_skjoennsfastsatt,
    generer_skattemelding_fra_konfig,
    hent_partsnummer,
)
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import SkdSkattemeldingClient

Config = str | dict[str, Any]

# Eldre navn på valideringsfeilen; samme klasse.
InnsendingValideringsfeil = ValideringsFeil

# Vises før en innsending som blir klage på skjønnsfastsetting (issue #180). Delt av CLI og
# begge SPA-ene, så brukeren får samme forklaring uansett hvor de sender fra.
SKJOENN_KLAGE_FORKLARING = (
    "Skatteetaten har skjønnsfastsatt skattemeldingen for {aar}, som regel fordi den ikke ble "
    "levert innen fristen. Sender du nå, blir innsendingen en klage på skjønnsfastsettingen. "
    "Klagen inneholder selskapets egne tall og ber Skatteetaten fastsette skatten etter dem. "
    "Skatteetaten behandler den som en klagesak, så det kan ta lengre tid enn en vanlig "
    "innsending."
)


# ---------------------------------------------------------------------------
# Dry-run / validering: rent lokalt, ingen nettverk
# ---------------------------------------------------------------------------


def _konfigfeil_svar(e: KonfigFeil, config: Config) -> dict:
    """Dry-run-svaret når configen ikke lar seg lese: et rettbart punkt, ikke en kastet feil."""
    return {
        "ok": False,
        "feil": [str(e)],
        "advarsler": _configfelt.advarsel_om_ukjente_felt(config),
    }


def valider_aarsregnskap(config: Config) -> dict:
    try:
        regnskap = _ar.les_config(config)
    except KonfigFeil as e:
        return _konfigfeil_svar(e, config)
    feil = _ar.valider(regnskap)
    advarsler = _ar.advarsler(regnskap) + _configfelt.advarsel_om_ukjente_felt(config)
    return {"ok": not feil, "feil": feil, "advarsler": advarsler}


def valider_aksjonaer(config: Config) -> dict:
    try:
        oppgave = _akr.les_config(config)
    except KonfigFeil as e:
        return _konfigfeil_svar(e, config)
    feil = _akr.valider(oppgave)
    return {
        "ok": not feil,
        "feil": feil,
        "advarsler": _configfelt.advarsel_om_ukjente_felt(config),
        "antall_aksjonaerer": len(oppgave.aksjonaerer),
    }


def valider_skattemelding(config: Config) -> dict:
    # Lokal bygging uten nettverk/partsnummer. SKD-validering skjer ved ekte innsending.
    # Sjekk de påkrevde selskapsfeltene først: et ufullstendig selskap (typisk etter SAF-T-import)
    # skal bli et rettbart avvik i bekreft-modalen, ikke en naken int('')/float('')-500.
    # Et ukjent felt kan forklare et felt som mangler, så advarselen følger også feilsvarene.
    advarsler = _configfelt.advarsel_om_ukjente_felt(config)
    feil = _sm.valider_selskap(config)
    if feil:
        return {"ok": False, "feil": feil, "advarsler": advarsler}
    try:
        regnskap, _konfig = _sm.les_config(config)
    except KonfigFeil as e:
        return _konfigfeil_svar(e, config)
    # Skattemeldingen leveres per kalenderår og bygges fra årsregnskapets periode, så en
    # periode over to kalenderår ville gitt en skattemelding for feil periode.
    feil = _ar.valider_periode(regnskap)
    if feil:
        return {"ok": False, "feil": feil, "advarsler": advarsler}
    return {"ok": True, "feil": [], "advarsler": advarsler, "regnskapsaar": regnskap.regnskapsaar}


# ---------------------------------------------------------------------------
# Ekte innsending: kalleren gir ferdig autentisert klient/token
# ---------------------------------------------------------------------------


def send_aarsregnskap(config: Config, altinn_klient: AltinnClient) -> dict:
    """Send årsregnskap til Brønnøysundregistrene. Returnerer signeringslenke i `resultat`.
    Kaster ValideringsFeil ved blokkerende feil, uten å sende noe."""
    regnskap = _ar.les_config(config)
    resultat = _ar.send_inn(regnskap, altinn_klient)
    return {"sendt": True, "resultat": resultat}


def send_aksjonaer(config: Config, skd_klient: SkdAksjonaerClient) -> dict:
    """Send aksjonærregisteroppgave (RF-1086) til Skatteetaten. Kaster ValideringsFeil ved
    blokkerende feil, uten å sende noe."""
    oppgave = _akr.les_config(config)
    svar = _akr.send_inn(oppgave, skd_klient)
    return {"sendt": True, "resultat": svar}


@dataclass(frozen=True)
class SkattemeldingBygg:
    """Alt som trengs for å validere eller sende en skattemelding, bygd fra config."""

    regnskap: Aarsregnskap
    skattemelding_xml: bytes
    naeringsspesifikasjon_xml: bytes
    partsnummer: int
    gjeldende_dokument_id: str | None
    skjoennsfastsatt: bool

    @property
    def innsendingsformaal(self) -> str:
        """'klage' når gjeldende skattemelding er skjønnsfastsatt, ellers 'egenfastsetting'.
        Endringsanmodning velges aldri av Wenche (SSV-6235)."""
        return "klage" if self.skjoennsfastsatt else "egenfastsetting"


def bygg_skattemelding(
    config: Config,
    skd_klient: SkdSkattemeldingClient,
    *,
    orgnr: str,
    partsnummer: int | None = None,
    gjeldende_dokument_id: str | None = None,
) -> SkattemeldingBygg:
    """
    Bygg skattemelding og næringsspesifikasjon for AS, klare for validering eller innsending.

    Henter forhåndsutfylt for å utlede partsnummer, gjeldende dokument-id og om meldingen er
    skjønnsfastsatt, med mindre kalleren oppgir `partsnummer` direkte (SKDs testmiljø der
    forhåndsutfylt ikke finnes). Stopper med ValideringsFeil før noe hentes hvis
    regnskapsperioden ikke kan gi én skattemelding.
    """
    regnskap, konfig = _sm.les_config(config)
    feil = _ar.valider_periode(regnskap)
    if feil:
        raise ValideringsFeil(feil)
    skjoennsfastsatt = False
    if partsnummer is None:
        forhaandsutfylt, gjeldende_dokument_id = skd_klient.hent_forhaandsutfylt_med_id(
            regnskap.regnskapsaar, orgnr
        )
        # hent_partsnummer kaster ValueError (eller en XML-parse-/decode-feil) hvis svaret fra
        # SKDs visnings-API ikke bærer et partsnummer. Det er en upstream-/tilgjengelighets-
        # tilstand (skattemeldingen for orgen/året er kanskje ikke klargjort hos Skatteetaten),
        # ikke en feil i tallene: meld det som MyndighetsFeil med forklaring.
        try:
            partsnummer = hent_partsnummer(forhaandsutfylt)
        except Exception as e:
            raise MyndighetsFeil(
                "skatteetaten",
                "henting av forhåndsutfylt skattemelding",
                kode="mangler-partsnummer",
                beskrivelse=(
                    f"Skatteetaten ga ikke en brukbar forhåndsutfylt skattemelding for {orgnr} "
                    f"(inntektsår {regnskap.regnskapsaar}); fant ikke partsnummer. Ingenting er "
                    "sendt inn. Skattemeldingen for dette året er kanskje ikke klargjort hos "
                    "Skatteetaten ennå. Prøv igjen senere, eller ta kontakt."
                ),
            ) from e
        skjoennsfastsatt = er_skjoennsfastsatt(forhaandsutfylt)
    return SkattemeldingBygg(
        regnskap=regnskap,
        skattemelding_xml=generer_skattemelding_fra_konfig(
            regnskap, konfig, partsnummer, gjelder_skjoennsfastsetting=skjoennsfastsatt
        ),
        naeringsspesifikasjon_xml=generer_naeringsspesifikasjon(regnskap, partsnummer, konfig),
        partsnummer=partsnummer,
        gjeldende_dokument_id=gjeldende_dokument_id,
        skjoennsfastsatt=skjoennsfastsatt,
    )


def send_skattemelding(
    config: Config,
    skd_klient: SkdSkattemeldingClient,
    altinn_token: str,
    *,
    orgnr: str,
    partsnummer: int | None = None,
    gjeldende_dokument_id: str | None = None,
    bekreft_klage: bool = False,
) -> dict:
    """
    Bygg og send skattemelding + næringsspesifikasjon for AS via Altinn3.

    Kan kaste `SkattemeldingValideringsfeil` fra `skd_klient.send`. Er gjeldende skattemelding
    skjønnsfastsatt, blir innsendingen en klage. Uten `bekreft_klage` sendes da ingenting;
    svaret har `krever_bekreftelse` og en forklaring som kalleren viser brukeren før den
    prøver igjen med `bekreft_klage=True`.
    """
    bygg = bygg_skattemelding(
        config,
        skd_klient,
        orgnr=orgnr,
        partsnummer=partsnummer,
        gjeldende_dokument_id=gjeldende_dokument_id,
    )
    if bygg.skjoennsfastsatt and not bekreft_klage:
        return {
            "sendt": False,
            "krever_bekreftelse": "klage_paa_skjoennsfastsetting",
            "melding": SKJOENN_KLAGE_FORKLARING.format(aar=bygg.regnskap.regnskapsaar),
        }
    # send() returnerer Altinn-lenken der brukeren signerer (som årsregnskapet), ikke en
    # instans-ID. Legges i `resultat` slik at UI-ene viser «venter på signatur» + lenken.
    signeringslenke = skd_klient.send(
        inntektsaar=bygg.regnskap.regnskapsaar,
        orgnr=orgnr,
        skattemelding_xml=bygg.skattemelding_xml,
        altinn_token=altinn_token,
        naeringsspesifikasjon_xml=bygg.naeringsspesifikasjon_xml,
        gjeldende_dokument_id=bygg.gjeldende_dokument_id,
        innsendingsformaal=bygg.innsendingsformaal,
    )
    return {"sendt": True, "resultat": signeringslenke, "klage": bygg.skjoennsfastsatt}
