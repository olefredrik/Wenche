"""
Dokumentgenerering for forhåndsvisning og nedlasting, delt av hostet og self-hosted.

Genererer lokalt fra config-en i request-body: ingen nettverk, ingenting lagres mellom kall.
Hvert svar er en liste filer med base64-kodet innhold som SPA-en tilbyr som nedlasting. Notene
sendes aldri inn, men kan lastes ned for signering og arkivering hos selskapet.

`lag_router(vakt=..., transform=...)` gir ruteren til hver app: hostet sender invite-vakten som
avhengighet, self-hosted sender test-org-byttet som transform. Alt annet er likt.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException

from wenche import aarsregnskap as ar
from wenche import aksjonaerregister as akr
from wenche import noter as noter_modul
from wenche import skattemelding as sm
from wenche.feil import KonfigFeil
from wenche.models import LaanTilNaerstaaende, Noter

from .svar import Fil, FilerSvar, SkatteberegningSvar

Transform = Callable[[dict], dict]

# Lesbare navn på config-seksjonene les_config slår opp direkte. Et ufullstendig Tall-steg
# (typisk tomt resultatregnskap eller balanse) får les_config til å kaste KeyError på det
# manglende nøkkeloppslaget; uten les_eller_422 ble det en naken HTTP 500. Aksjonærregisteret
# rører ikke resultatregnskap/balanse, så det er det eneste dokumentet som lar seg generere før
# tallene er fylt inn, derav den forvirrende delvise feilen.
_SEKSJON_TEKST = {
    "resultatregnskap": "Resultatregnskapet",
    "balanse": "Balansen",
    "regnskapsaar": "Regnskapsåret",
    "selskap": "Selskapsopplysningene",
    "aksjonaerer": "Aksjonærene",
}


def _422(feil: list[str]) -> HTTPException:
    return HTTPException(status_code=422, detail={"feil": feil})


def les_eller_422(les: Callable[[dict], Any], config: dict) -> Any:
    """Kjør en les_config og gjør en manglende config-seksjon om til en forklarende 422.

    Samme ånd som skattemelding.valider_selskap: en påregnelig, ufullstendig brukertilstand skal
    bli et avvik brukeren kan rette, ikke en uhåndtert serverfeil.
    """
    try:
        return les(config)
    except KonfigFeil as e:
        # wenche.konfig: feltstien sier hvilken seksjon som mangler; andre feil er alt lesbare.
        if e.felt in _SEKSJON_TEKST:
            raise _422([_tall_steg_melding(_SEKSJON_TEKST[e.felt])]) from e
        raise _422([str(e)]) from e
    except KeyError as e:
        felt = str(e.args[0]) if e.args else ""
        navn = _SEKSJON_TEKST.get(felt, f"Feltet «{felt}»" if felt else "Et påkrevd felt")
        raise _422([_tall_steg_melding(navn)]) from e


def _tall_steg_melding(navn: str) -> str:
    return (
        f"{navn} mangler. Fyll inn opplysningene i Tall-steget før du genererer dette dokumentet."
    )


def fil(filnavn: str, innhold: bytes, mime: str) -> Fil:
    return Fil(filnavn=filnavn, mime=mime, base64=base64.b64encode(innhold).decode("ascii"))


def _xml_filer(filer: dict[str, bytes]) -> FilerSvar:
    return FilerSvar(
        filer=[fil(navn, innhold, "application/xml") for navn, innhold in filer.items()]
    )


def _tekstfil(navn: str, tekst: str) -> FilerSvar:
    return FilerSvar(filer=[fil(navn, tekst.encode("utf-8"), "text/plain; charset=utf-8")])


def bygg_noter(config: dict) -> Noter:
    """Bygg Noter-objektet fra config-dict (samme form som skjemaet lagrer)."""
    noter_cfg = config.get("noter") or {}
    return Noter(
        antall_ansatte=int(noter_cfg.get("antall_ansatte", 0)),
        laan_til_naerstaaende=[
            LaanTilNaerstaaende(
                motpart=laan.get("motpart", laan.get("mottaker", "")),
                saldo=float(laan.get("saldo", laan.get("beloep", 0))),
                retning=laan.get("retning", "långiver"),
                rente_prosent=float(laan.get("rente_prosent", 0.0)),
                sikkerhet=laan.get("sikkerhet", ""),
            )
            for laan in noter_cfg.get("laan_til_naerstaaende", [])
        ],
    )


# ---------------------------------------------------------------------------
# Rene generatorer: config inn, filer ut; 422 ved rettbare avvik
# ---------------------------------------------------------------------------


def skattemelding(config: dict) -> FilerSvar:
    feil = sm.valider_selskap(config)
    if feil:
        raise _422(feil)
    regnskap, konfig = les_eller_422(sm.les_config, config)
    tekst = sm.generer(regnskap, konfig)
    return _tekstfil(
        f"skattemelding_{regnskap.regnskapsaar}_{regnskap.selskap.org_nummer}.txt", tekst
    )


def skatteberegning(config: dict) -> SkatteberegningSvar:
    """Beregnet skatt fra tallene i skjemaet, som forslag til skattekostnad-feltet.

    Beregner og returnerer, lagrer ingenting: brukeren avgjør selv om forslaget skal føres
    (samme forhåndsfyll-prinsipp som SAF-T-importen). Gjenbruker skattemelding.beregn_skatt
    så forslaget ikke kan drifte fra tallet visningen viser.
    """
    # Ugyldig eierandel blir en lesbar 422, ikke en naken 500 fra leseren.
    feil = sm.valider_skattekonfig(config)
    if feil:
        raise _422(feil)
    beregning, foert = sm.beregn_skatt_fra_config(config)
    return SkatteberegningSvar(
        beregnet_skatt=round(beregning.beregnet_skatt),
        skattepliktig_inntekt=round(beregning.skattepliktig_inntekt_netto),
        foert_skattekostnad=round(foert),
    )


def aarsregnskap(config: dict) -> FilerSvar:
    regnskap = les_eller_422(ar.les_config, config)
    feil = ar.valider(regnskap)
    if feil:
        raise _422(feil)
    return _xml_filer(ar.bygg_filer(regnskap))


def aksjonaer(config: dict) -> FilerSvar:
    oppgave = les_eller_422(akr.les_config, config)
    feil = akr.valider(oppgave)
    if feil:
        raise _422(feil)
    return _xml_filer(akr.bygg_filer(oppgave))


def noter(config: dict) -> FilerSvar:
    regnskap = les_eller_422(ar.les_config, config)
    tekst = noter_modul.generer(regnskap, bygg_noter(config))
    return _tekstfil(f"noter_{regnskap.regnskapsaar}_{regnskap.selskap.org_nummer}.txt", tekst)


# ---------------------------------------------------------------------------
# Ruteren
# ---------------------------------------------------------------------------


def lag_router(
    *,
    vakt: Callable[..., Any] | None = None,
    transform: Transform = lambda config: config,
) -> APIRouter:
    """
    Ruteren /api/dokumenter/* for én app.

    `vakt` kjøres som FastAPI-avhengighet før hvert kall (hostet: krev_invitert; self-hosted
    har vakten som middleware og sender ingen). `transform` kjøres på config-en før generering
    (self-hosted: miljo.med_test_org). Skatteberegningen bruker ikke org, så den transformeres
    ikke.
    """
    router = APIRouter(
        prefix="/api/dokumenter",
        tags=["dokumenter"],
        dependencies=[Depends(vakt)] if vakt else [],
    )

    @router.post("/skattemelding", response_model=FilerSvar)
    def dok_skattemelding(config: dict[str, Any] = Body(...)) -> FilerSvar:
        return skattemelding(transform(config))

    @router.post("/skatteberegning", response_model=SkatteberegningSvar)
    def dok_skatteberegning(config: dict[str, Any] = Body(...)) -> SkatteberegningSvar:
        return skatteberegning(config)

    @router.post("/aarsregnskap", response_model=FilerSvar)
    def dok_aarsregnskap(config: dict[str, Any] = Body(...)) -> FilerSvar:
        return aarsregnskap(transform(config))

    @router.post("/aksjonaer", response_model=FilerSvar)
    def dok_aksjonaer(config: dict[str, Any] = Body(...)) -> FilerSvar:
        return aksjonaer(transform(config))

    @router.post("/noter", response_model=FilerSvar)
    def dok_noter(config: dict[str, Any] = Body(...)) -> FilerSvar:
        return noter(transform(config))

    return router
