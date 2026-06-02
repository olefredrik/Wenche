"""
Oppsett-endepunkter for self-hosted Wenche: Maskinporten-credentials, privat nøkkel,
tilkoblingstest og systembruker-onboarding (registrer system → opprett forespørsel →
godkjenn i Altinn med BankID → sjekk status). Porten fra Oppsett-fanen i `wenche/ui.py`.

Miljøet er låst per kjøring (WENCHE_ENV), så vi trenger ikke flippe env per kall slik
NiceGUI gjorde — auth-flyten peker allerede mot riktig miljø.
"""
from __future__ import annotations

import json
import os
import re

import httpx
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from wenche import auth, systembruker

from . import miljo

router = APIRouter(prefix="/api/oppsett", tags=["oppsett"])


def _vendor_orgnr() -> str:
    """Operatør-/vendor-orgnr er alltid ditt eget ORG_NUMMER, også i testmiljø."""
    return os.getenv("ORG_NUMMER", "").strip()


def _party_orgnr() -> str:
    """Rapportør-orgnr systembrukeren gjelder: Tenor-test-orgnr i test, ellers eget orgnr."""
    if miljo.er_test():
        return os.getenv("SKD_TEST_ORG_NUMMER", "").strip() or _vendor_orgnr()
    return _vendor_orgnr()


def _client_id() -> str:
    return miljo.les_konfig_for_milj("MASKINPORTEN_CLIENT_ID")


# ---------------------------------------------------------------------------
# Status (kun lokale filer/env — ingen nettverk)
# ---------------------------------------------------------------------------

@router.get("/status")
def status() -> dict:
    """Lokal oppsett-status: credentials satt, nøkkel funnet, systembruker-forespørsel finnes."""
    env = miljo.aktiv_env()
    client_id = miljo.les_konfig_for_milj("MASKINPORTEN_CLIENT_ID")
    kid = miljo.les_konfig_for_milj("MASKINPORTEN_KID")
    orgnr = miljo.aktiv_orgnr()
    mangler = [
        navn
        for navn, verdi in [("Klient-ID", client_id), ("Nøkkel-ID", kid), ("Orgnr", orgnr)]
        if not verdi
    ]
    nokkel_sti = miljo.privat_nokkel_sti()
    from pathlib import Path

    nokkel_ok = Path(nokkel_sti).exists()
    return {
        "env": env,
        "credentials": {
            "client_id": client_id,
            "kid": kid,
            "orgnr": orgnr,
            "mangler": mangler,
            "komplett": not mangler,
        },
        "nokkel": {"ok": nokkel_ok, "sti": nokkel_sti},
        "systembruker": {
            "har_forespoersel": bool(miljo.les_request_id()),
            "confirm_url": miljo.les_confirm_url() or None,
        },
    }


# ---------------------------------------------------------------------------
# Lagre credentials + nøkkel (skriver til ~/.wenche/.env)
# ---------------------------------------------------------------------------

class Credentials(BaseModel):
    client_id: str = ""
    kid: str = ""
    orgnr: str = ""


@router.put("/credentials")
def lagre_credentials(body: Credentials) -> dict:
    """Lagre Maskinporten client-id/kid + orgnr for aktivt miljø i ~/.wenche/.env."""
    from dotenv import set_key

    miljo.sikre_bruker_env_fil()
    env_fil = str(miljo._BRUKER_ENV_FIL)
    suffix = miljo.aktiv_env().upper()

    for verdi, env_navn in [
        (body.client_id, f"MASKINPORTEN_CLIENT_ID_{suffix}"),
        (body.kid, f"MASKINPORTEN_KID_{suffix}"),
    ]:
        set_key(env_fil, env_navn, verdi or "")
        os.environ[env_navn] = verdi or ""

    orgnr_var = miljo.orgnr_var()
    set_key(env_fil, orgnr_var, body.orgnr or "")
    if body.orgnr:
        os.environ[orgnr_var] = body.orgnr
    else:
        os.environ.pop(orgnr_var, None)

    return {"ok": True}


class Nokkel(BaseModel):
    pem: str


@router.post("/nokkel")
def lagre_nokkel(body: Nokkel) -> dict:
    """Lagre den private RSA-nøkkelen lokalt i ~/.wenche/ (chmod 600). Sendes aldri videre."""
    if "PRIVATE KEY" not in body.pem:
        raise HTTPException(status_code=422, detail="Filen ser ikke ut som en PEM privat nøkkel.")
    from dotenv import set_key

    miljo.sikre_bruker_env_fil()
    miljo._PRIVAT_NOKKEL_FIL.write_text(body.pem, encoding="utf-8")
    try:
        miljo._PRIVAT_NOKKEL_FIL.chmod(0o600)
    except OSError:
        pass
    abs_sti = str(miljo._PRIVAT_NOKKEL_FIL)
    set_key(str(miljo._BRUKER_ENV_FIL), "MASKINPORTEN_PRIVAT_NOKKEL", abs_sti)
    os.environ["MASKINPORTEN_PRIVAT_NOKKEL"] = abs_sti
    return {"ok": True, "sti": abs_sti}


# ---------------------------------------------------------------------------
# Tilkoblingstest
# ---------------------------------------------------------------------------

def _tolk_feilmelding(raw: str) -> str:
    """Oversett rå auth-feilmelding til brukervennlig norsk."""
    env = miljo.aktiv_env()
    milj = "testmiljøet (tt02)" if env == "test" else "produksjonsmiljøet"
    portal = (
        "sjolvbetjening.test.samarbeid.digdir.no"
        if env == "test"
        else "sjolvbetjening.samarbeid.digdir.no"
    )
    if "Maskinporten svarte" in raw:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                p = json.loads(m.group(0))
                kode = p.get("error", "")
                beskr = p.get("error_description", "")
                if kode == "invalid_grant" and "Client authentication" in beskr:
                    return (
                        f"Klient-ID-en din er ikke registrert i {milj} hos Maskinporten. "
                        f"Sjekk at klienten er opprettet i riktig portal ({portal}) og at "
                        f"klient-ID + nøkkel-ID matcher det som ligger der."
                    )
                if kode == "invalid_grant":
                    return f"Maskinporten avviste innloggingen: {beskr or kode}."
                if kode == "invalid_client":
                    return f"Maskinporten kjenner ikke klient-ID-en i {milj}."
                if kode == "invalid_scope":
                    return (
                        "Klienten mangler ett eller flere scopes du har prøvd å hente. "
                        f"Legg dem til på klienten i {portal}."
                    )
                return f"Maskinporten-feil ({kode}): {beskr or 'ingen detaljer'}."
            except (json.JSONDecodeError, AttributeError):
                pass
        m = re.search(r"svarte (\d+)", raw)
        if m:
            return (
                f"Maskinporten svarte med HTTP {m.group(1)} for {milj}. "
                "Sjekk credentials og at klienten er registrert i riktig miljø."
            )
    return raw.split("\n")[0]


@router.post("/test-tilkobling")
def test_tilkobling() -> dict:
    """Test Maskinporten + Altinn-veksling, og rapporter systembruker-status hvis auth gikk bra."""
    try:
        auth.login(lagre_token=False)
    except RuntimeError as e:
        return {"auth_ok": False, "melding": _tolk_feilmelding(str(e))}
    except httpx.HTTPStatusError as e:
        kode = e.response.status_code
        if kode == 401:
            melding = (
                "Altinn avviste tokenet (HTTP 401). Vanligste årsak: "
                "altinn:instances.* er ikke aktivert på klienten."
            )
        elif kode == 403:
            melding = "Altinn avslo tilgangen (HTTP 403)."
        else:
            melding = f"Altinn svarte med HTTP {kode}."
        return {"auth_ok": False, "melding": melding}
    except Exception as e:
        return {"auth_ok": False, "melding": f"Uventet feil ({type(e).__name__}): {e}"}

    resultat = {"auth_ok": True, "melding": "Maskinporten og Altinn godtok credentials"}
    request_id = miljo.les_request_id()
    if not request_id:
        resultat["systembruker"] = {"status": "ikke_opprettet", "melding": "Ingen forespørsel opprettet ennå"}
        return resultat
    try:
        token = auth.login_admin()
        svar = systembruker.hent_forespørsel_status(token, request_id)
        resultat["systembruker"] = _tolk_systembruker_status(svar.get("status", "ukjent"))
    except Exception as e:
        resultat["systembruker"] = {"status": "feil", "melding": f"Kunne ikke hente status: {type(e).__name__}"}
    return resultat


def _tolk_systembruker_status(altinn_status: str) -> dict:
    if altinn_status == "Accepted":
        return {"status": "godkjent", "melding": "Systembruker godkjent", "altinn_status": altinn_status}
    if altinn_status == "New":
        return {"status": "venter", "melding": "Forespørsel venter på godkjenning", "altinn_status": altinn_status}
    if altinn_status == "Rejected":
        return {"status": "avvist", "melding": "Forespørsel avvist — opprett ny", "altinn_status": altinn_status}
    return {"status": "ukjent", "melding": f"Status: {altinn_status}", "altinn_status": altinn_status}


# ---------------------------------------------------------------------------
# Systembruker-onboarding
# ---------------------------------------------------------------------------

@router.post("/registrer-system")
def registrer_system() -> dict:
    """Registrer Wenche i Altinns systemregister (idempotent)."""
    vendor_orgnr = _vendor_orgnr()
    if not vendor_orgnr:
        raise HTTPException(status_code=409, detail="Organisasjonsnummer mangler i oppsettet.")
    token = auth.login_admin()
    svar = systembruker.registrer_system(token, vendor_orgnr, _client_id())
    oppdatert = isinstance(svar, dict) and svar.get("oppdatert", False)
    return {"ok": True, "oppdatert": oppdatert}


@router.post("/systembruker")
def opprett_systembruker() -> dict:
    """Opprett systembruker-forespørsel (registrerer systemet først, idempotent). Returnerer confirm_url."""
    vendor_orgnr = _vendor_orgnr()
    if not vendor_orgnr:
        raise HTTPException(status_code=409, detail="Organisasjonsnummer mangler i oppsettet.")
    token = auth.login_admin()
    systembruker.registrer_system(token, vendor_orgnr, _client_id())
    svar = systembruker.opprett_forespørsel(token, vendor_orgnr, _party_orgnr())
    request_id = svar.get("id", "")
    confirm_url = svar.get("confirmUrl", "")
    if request_id:
        miljo.lagre_request_id(request_id)
    if confirm_url:
        miljo.lagre_confirm_url(confirm_url)
    return {"ok": True, "request_id": request_id, "confirm_url": confirm_url, "status": svar.get("status")}


@router.post("/systembruker/status")
def systembruker_status() -> dict:
    """Sjekk status på den lagrede systembruker-forespørselen."""
    request_id = miljo.les_request_id()
    if not request_id:
        return {"status": "ikke_opprettet", "melding": "Ingen forespørsel opprettet ennå"}
    token = auth.login_admin()
    svar = systembruker.hent_forespørsel_status(token, request_id)
    return _tolk_systembruker_status(svar.get("status", "ukjent"))


@router.post("/systembruker/oppdater")
def oppdater_systembruker() -> dict:
    """Be om oppdaterte rettigheter (skattemelding) på en eksisterende systembruker."""
    vendor_orgnr = _vendor_orgnr()
    token = auth.login_admin()
    brukere = systembruker.hent_systembrukere(token, vendor_orgnr)
    if not brukere:
        raise HTTPException(
            status_code=409,
            detail="Ingen aktive systembrukere funnet. Opprett ny forespørsel først.",
        )
    party = _party_orgnr()
    treff = next((b for b in brukere if b.get("reporteeOrgNo") == party), brukere[0])
    svar = systembruker.opprett_endringsforespørsel(
        token, treff["id"], [systembruker._SKATTEMELDING_RETT]
    )
    confirm_url = svar.get("confirmUrl") or svar.get("ConfirmUrl", "")
    return {"ok": True, "confirm_url": confirm_url, "status": svar.get("status", "")}
