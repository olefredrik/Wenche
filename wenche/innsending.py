"""
Delt innsendings-orkestrering brukt av CLI, hostet og self-hosted.

Auth-agnostisk med vilje: kalleren anskaffer tokens/klienter (self-hosted: brukerens egen
Maskinporten-innlogging; hostet: vendor-creds + systembruker-godkjent kunde-org) og sender
dem inn hit. Bygging og validering (`valider_*`) er rent lokalt — ingen nettverk, ingen disk,
ingen binding kreves — slik at dry-run er identisk i alle tre frontene.

Tidligere lå denne orkestreringen duplisert i `cli.py`, `ui.py` og `hosted/api/innsending.py`.
"""
from __future__ import annotations

from typing import Any

from wenche import aarsregnskap as _ar
from wenche import aksjonaerregister as _akr
from wenche import skattemelding as _sm
from wenche.altinn_client import AltinnClient
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skattemelding_xml import (
    er_skjoennsfastsatt,
    generer_skattemelding_fra_konfig,
    hent_partsnummer,
)
from wenche.skd_client import SkdAksjonaerClient
from wenche.skd_skattemelding_client import SkdSkattemeldingClient

Config = str | dict[str, Any]

# Vises før en innsending som blir klage på skjønnsfastsetting (issue #180). Delt av CLI og
# begge SPA-ene, så brukeren får samme forklaring uansett hvor de sender fra.
SKJOENN_KLAGE_FORKLARING = (
    "Skatteetaten har skjønnsfastsatt skattemeldingen for {aar}, som regel fordi den ikke ble "
    "levert innen fristen. Sender du nå, blir innsendingen en klage på skjønnsfastsettingen. "
    "Klagen inneholder selskapets egne tall og ber Skatteetaten fastsette skatten etter dem. "
    "Skatteetaten behandler den som en klagesak, så det kan ta lengre tid enn en vanlig "
    "innsending."
)


class InnsendingValideringsfeil(Exception):
    """Blokkerende valideringsfeil oppdaget før innsending. Bærer feillisten."""

    def __init__(self, feil: list[str]) -> None:
        self.feil = feil
        super().__init__("; ".join(feil))


# ---------------------------------------------------------------------------
# Dry-run / validering — rent lokalt, ingen nettverk
# ---------------------------------------------------------------------------

def valider_aarsregnskap(config: Config) -> dict:
    regnskap = _ar.les_config(config)
    feil = _ar.valider(regnskap)
    return {"ok": not feil, "feil": feil, "advarsler": _ar.advarsler(regnskap)}


def valider_aksjonaer(config: Config) -> dict:
    oppgave = _akr.les_config(config)
    feil = _akr.valider(oppgave)
    return {"ok": not feil, "feil": feil, "antall_aksjonaerer": len(oppgave.aksjonaerer)}


def valider_skattemelding(config: Config) -> dict:
    # Lokal bygging uten nettverk/partsnummer. SKD-validering skjer ved ekte innsending.
    # Sjekk de påkrevde selskapsfeltene først: et ufullstendig selskap (typisk etter SAF-T-import)
    # skal bli et rettbart avvik i bekreft-modalen, ikke en naken int('')/float('')-500.
    feil = _sm.valider_selskap(config)
    if feil:
        return {"ok": False, "feil": feil}
    regnskap, _konfig = _sm.les_config(config)
    return {"ok": True, "feil": [], "regnskapsaar": regnskap.regnskapsaar}


# ---------------------------------------------------------------------------
# Ekte innsending — kalleren gir ferdig autentisert klient/token
# ---------------------------------------------------------------------------

def send_aarsregnskap(config: Config, altinn_klient: AltinnClient) -> dict:
    """Send årsregnskap til Brønnøysundregistrene. Returnerer signeringslenke i `resultat`."""
    regnskap = _ar.les_config(config)
    feil = _ar.valider(regnskap)
    if feil:
        raise InnsendingValideringsfeil(feil)
    resultat = _ar.send_inn(regnskap, altinn_klient)
    return {"sendt": True, "resultat": resultat}


def send_aksjonaer(config: Config, skd_klient: SkdAksjonaerClient) -> dict:
    """Send aksjonærregisteroppgave (RF-1086) til Skatteetaten."""
    oppgave = _akr.les_config(config)
    # Pre-valider her slik at web-flytene får en strukturert feilliste (422). Uten dette
    # treffer valideringen i `_akr.send_inn`, som er CLI-rettet og gjør print + SystemExit.
    feil = _akr.valider(oppgave)
    if feil:
        raise InnsendingValideringsfeil(feil)
    svar = _akr.send_inn(oppgave, skd_klient)
    return {"sendt": True, "resultat": svar}


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

    Henter forhåndsutfylt for å utlede partsnummer/gjeldende dokument-id, med mindre kalleren
    oppgir `partsnummer` direkte (brukes i SKDs testmiljø der forhåndsutfylt ikke finnes).
    Kan kaste `SkattemeldingValideringsfeil` fra `skd_klient.send`.

    Er gjeldende skattemelding skjønnsfastsatt, blir innsendingen en klage. Uten
    `bekreft_klage` sendes da ingenting; svaret har `krever_bekreftelse` og en forklaring
    som kalleren viser brukeren før den prøver igjen med `bekreft_klage=True`.
    """
    regnskap, konfig = _sm.les_config(config)
    skjoennsfastsatt = False
    if partsnummer is None:
        forhåndsutfylt, gjeldende_dokument_id = skd_klient.hent_forhåndsutfylt_med_id(
            regnskap.regnskapsaar, orgnr
        )
        # hent_partsnummer kaster ValueError (eller en XML-parse-/decode-feil) hvis svaret fra
        # SKDs visnings-API ikke bærer et partsnummer. Det er en upstream-/tilgjengelighets-
        # tilstand (skattemeldingen for orgen/året er kanskje ikke klargjort hos Skatteetaten),
        # ikke en feil i tallene. Gjør den om til en lesbar RuntimeError, ellers slipper en
        # uventet exception-type forbi 502-fellen i hostet `_utfor` og blir en naken 500.
        try:
            partsnummer = hent_partsnummer(forhåndsutfylt)
        except Exception as e:
            raise RuntimeError(
                f"Skatteetaten ga ikke en brukbar forhåndsutfylt skattemelding for {orgnr} "
                f"(inntektsår {regnskap.regnskapsaar}); fant ikke partsnummer. Ingenting er "
                "sendt inn. Skattemeldingen for dette året er kanskje ikke klargjort hos "
                "Skatteetaten ennå. Prøv igjen senere, eller ta kontakt."
            ) from e
        skjoennsfastsatt = er_skjoennsfastsatt(forhåndsutfylt)
    if skjoennsfastsatt and not bekreft_klage:
        return {
            "sendt": False,
            "krever_bekreftelse": "klage_paa_skjoennsfastsetting",
            "melding": SKJOENN_KLAGE_FORKLARING.format(aar=regnskap.regnskapsaar),
        }
    skattemelding_xml = generer_skattemelding_fra_konfig(
        regnskap, konfig, partsnummer, gjelder_skjoennsfastsetting=skjoennsfastsatt
    )
    naeringsspesifikasjon_xml = generer_naeringsspesifikasjon(regnskap, partsnummer, konfig)
    # send() returnerer Altinn-lenken der brukeren signerer (som årsregnskapet), ikke en
    # instans-ID. Legges i `resultat` slik at UI-ene viser «venter på signatur» + lenken.
    signeringslenke = skd_klient.send(
        inntektsaar=regnskap.regnskapsaar,
        orgnr=orgnr,
        skattemelding_xml=skattemelding_xml,
        altinn_token=altinn_token,
        naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
        gjeldende_dokument_id=gjeldende_dokument_id,
        innsendingsformaal="klage" if skjoennsfastsatt else "egenfastsetting",
    )
    return {"sendt": True, "resultat": signeringslenke, "klage": skjoennsfastsatt}
