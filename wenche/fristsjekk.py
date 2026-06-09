"""
Sjekk innsendingsstatus mot offentlige API-er.

Brukes av Wenche UI for å vise om frister er innfridd:
  - Skattemelding: Skatteetatens API (krever Maskinporten-token)
  - Årsregnskap:   Brønnøysundregistrenes åpne Regnskapsregister-API
  - Aksjonærregisteroppgave: Ingen offentlig status-API tilgjengelig

Skattemelding-sjekken bruker endepunktet GET /api/skattemelding/v2/{aar}/{orgnr}
som returnerer en XML-wrapper med <type>-element. Verdiene er definert i
Skatteetatens offisielle XSD-skjema (Dokumenttype):
  - skattemeldingUpersonligUtkast    → forhåndsutfylt, ikke innsendt
  - skattemeldingUpersonligFastsatt  → innsendt og fastsatt

Kilde: https://github.com/Skatteetaten/skattemeldingen/blob/master/src/resources/
       xsd/skattemeldingognaeringsspesifikasjonforespoerselresponse_v2_kompakt.xsd
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
from dotenv import load_dotenv

# Last fra ~/.wenche/.env først (fast lokasjon), så cwd/.env som fallback.
# Matcher load-rekkefølgen i wenche.auth.
_BRUKER_ENV_FIL = Path.home() / ".wenche" / ".env"
if _BRUKER_ENV_FIL.is_file():
    load_dotenv(_BRUKER_ENV_FIL)
load_dotenv()


def neste_frist(maaned: int, dag: int) -> date:
    """Neste forekomst av (maaned, dag) fra og med i dag."""
    today = date.today()
    frist = date(today.year, maaned, dag)
    if frist < today:
        frist = date(today.year + 1, maaned, dag)
    return frist


def regnskapsaar_for_frist(maaned: int, dag: int) -> int:
    """
    Regnskapsåret som neste frist gjelder for.

    Frister leveres i året etter regnskapsårets slutt, så regnskapsår = frist.year - 1.
    F.eks. frist 31. juli 2026 → regnskapsår 2025.
    """
    return neste_frist(maaned, dag).year - 1

# Basis-URL-er for Skatteetatens API — samme som i skd_skattemelding_client.py.
_SKD_BASES = {
    "test": "https://api-test.sits.no",
    "prod": "https://api.skatteetaten.no",
}

# Brønnøysundregistrenes Regnskapsregister-API.
# Åpent API uten autentisering.
# Dokumentasjon: https://data.brreg.no/regnskapsregisteret/openapi/index.html
_BRG_REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap"

# Eksakte verdier fra Dokumenttype-enum i Skatteetatens XSD (se modul-docstring).
# Utvid settet hvis XSDen får nye verdier som indikerer "innsendt og fastsatt".
_FASTSATT_DOKUMENTTYPER = {"skattemeldingUpersonligFastsatt"}


@dataclass
class FristStatus:
    innfridd: bool = False
    tidspunkt: str | None = None
    beskrivelse: str = ""
    brukertekst: str = ""
    lenke: str | None = None
    # Saksreferanse fra myndighetenes register (f.eks. Brønnøysunds journalnr),
    # vist på det innfridde kortet. referanse_etikett gir riktig ledetekst siden
    # ulike etater bruker ulike begreper.
    referanse: str | None = None
    referanse_etikett: str = "Referanse"


def sjekk_skattemelding(orgnr: str, aar: int) -> FristStatus:
    """
    Sjekk om skattemelding er fastsatt via Skatteetatens API.

    Hjem-fanen viser alltid reell innsendingsstatus mot prod, uavhengig av
    WENCHE_ENV. Test-API-et kjenner uansett kun syntetiske Tenor-orgnumre.
    Miljøet sendes som eksplisitt parameter til auth-laget i stedet for å
    mutere WENCHE_ENV midlertidig: i en flertrådet server kunne et samtidig
    kall ellers lese 'prod' mens vinduet sto åpent.
    """
    try:
        from wenche.auth import get_skd_skattemelding_maskinporten_token

        token = get_skd_skattemelding_maskinporten_token(env="prod")
    except RuntimeError:
        return FristStatus(beskrivelse="Maskinporten ikke konfigurert for prod")
    return _utfør_skattemelding_sjekk(token, orgnr, aar)


def _utfør_skattemelding_sjekk(token: str, orgnr: str, aar: int) -> FristStatus:
    status, tilgjengelig = _hent_skattemelding_status(token, orgnr, aar)

    # Så snart årets frist har passert ruller Hjem-fanen fram til neste frist og
    # spør om det kommende inntektsåret. Det året har Skatteetaten ennå ikke
    # åpnet (svarer 403/404), så for en bruker som nettopp har levert ville
    # kortet ellers vist en forvirrende "ikke klargjort"-status rett etter
    # innsending. Når det forespurte året ikke er tilgjengelig, sjekk derfor om
    # fjorårets melding er levert og bekreft heller den.
    if not tilgjengelig:
        forrige, _ = _hent_skattemelding_status(token, orgnr, aar - 1)
        if forrige.innfridd:
            return forrige

    return status


def _hent_skattemelding_status(token: str, orgnr: str, aar: int) -> tuple[FristStatus, bool]:
    """Hent skattemeldingstatus for ett konkret år.

    Returnerer (status, tilgjengelig). `tilgjengelig=False` betyr at Skatteetaten
    ikke har en skattemelding å vise for orgnr/år (HTTP 403/404) — da kan
    kalleren trygt falle tilbake til fjoråret. Transiente feil (5xx, nettverk,
    ugyldig svar) gir `tilgjengelig=True` slik at de ikke trigger fallback som
    ville skjult den reelle feilen.
    """
    base = _SKD_BASES["prod"]

    try:
        resp = httpx.get(
            f"{base}/api/skattemelding/v2/{aar}/{orgnr}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/xml",
            },
            timeout=30,
        )
    except httpx.HTTPError:
        return FristStatus(beskrivelse="Kunne ikke kontakte Skatteetaten"), True

    # 404 betyr at ingen skattemelding er klargjort for orgnr/år ennå. 403 får vi
    # når året ikke er åpnet for oppslag (typisk det kommende inntektsåret som
    # ikke er avsluttet). Begge betyr i praksis "ingen melding å vise for {aar}":
    # vis en forklarende status framfor en kryptisk HTTP-kode, og la kalleren
    # falle tilbake til fjoråret.
    if resp.status_code in (403, 404):
        return FristStatus(
            beskrivelse="Ikke klargjort ennå",
            brukertekst=(
                f"Skatteetaten har ikke klargjort skattemelding for {aar} ennå. "
                "Forhåndsutfylt utkast kommer normalt i mars/april."
            ),
        ), False

    if not resp.is_success:
        return FristStatus(beskrivelse=f"Skatteetaten svarte med HTTP {resp.status_code}"), True

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return FristStatus(beskrivelse="Ugyldig svar fra Skatteetaten"), True

    # <type>-elementet i wrapper-XML-en angir dokumentstatus.
    # Sammenlign eksakt mot kjente "fastsatt"-typer fra XSDen — delstreng-match
    # ville falskt slå inn hvis Skatteetaten innfører nye typer som inneholder
    # "Fastsatt" uten å bety "innsendt og godkjent".
    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag == "type" and elem.text and elem.text.strip() in _FASTSATT_DOKUMENTTYPER:
            return FristStatus(
                innfridd=True,
                brukertekst=f"Skattemeldingen for {aar} er sendt inn og godkjent.",
                lenke=f"https://af.altinn.no/?party=urn%3Aaltinn%3Aorganization%3Aidentifier-no%3A{orgnr}",
            ), True

    return FristStatus(
        beskrivelse="Ikke innsendt",
        brukertekst=f"Skattemeldingen for {aar} er ikke innsendt ennå.",
    ), True


def sjekk_aarsregnskap(orgnr: str, aar: int) -> FristStatus:
    """Sjekk om årsregnskap er levert via Brønnøysundregistrenes API."""
    try:
        resp = httpx.get(
            f"{_BRG_REGNSKAP_URL}/{orgnr}",
            headers={"Accept": "application/json"},
            timeout=15,
        )
    except httpx.HTTPError:
        return FristStatus(beskrivelse="Kunne ikke kontakte Regnskapsregisteret")

    # 404 betyr at orgnr ikke har innleverte regnskap i registeret — det er
    # samme tilstand som "ikke synlig ennå" for inneværende regnskapsår.
    if resp.status_code == 404:
        return _aarsregnskap_ikke_synlig(aar)

    if not resp.is_success:
        return FristStatus(
            beskrivelse=f"Regnskapsregisteret svarte med HTTP {resp.status_code}"
        )

    try:
        data = resp.json()
    except ValueError:
        return FristStatus(beskrivelse="Uventet svar fra Regnskapsregisteret")

    if not isinstance(data, list):
        return FristStatus(beskrivelse="Uventet svar fra Regnskapsregisteret")

    for regnskap in data:
        periode = regnskap.get("regnskapsperiode", {})
        fra = periode.get("fraDato", "")
        if fra.startswith(str(aar)):
            mottatt = regnskap.get("mottaksdag")
            journalnr = regnskap.get("journalnr")
            return FristStatus(
                innfridd=True,
                tidspunkt=mottatt,
                brukertekst=f"Brønnøysundregistrene har mottatt årsregnskapet for {aar}.",
                referanse=journalnr,
                referanse_etikett="Journalnr",
            )

    return _aarsregnskap_ikke_synlig(aar)


def _aarsregnskap_ikke_synlig(aar: int) -> FristStatus:
    """
    Status når årsregnskapet ikke (ennå) finnes i Regnskapsregisteret.

    Det åpne API-et viser kun ferdig behandlede, publiserte regnskap. Et
    årsregnskap som nettopp er sendt inn og signert i Altinn er ikke publisert
    umiddelbart, så vi formulerer dette som et publiseringsetterslep, ikke som
    en bekreftet "ikke levert" — sistnevnte er villedende rett etter innsending.
    """
    return FristStatus(
        beskrivelse="Ikke synlig i registeret ennå",
        brukertekst=(
            f"Regnskapsregisteret viser ikke årsregnskapet for {aar} ennå. "
            "Et nylig innsendt regnskap kan ta noen dager før det publiseres."
        ),
    )


def sjekk_aksjonaerregister(orgnr: str, aar: int) -> FristStatus:
    """Aksjonærregister — ingen offentlig status-API tilgjengelig."""
    return FristStatus(
        beskrivelse="Ingen automatisk sjekk tilgjengelig",
        brukertekst="Sjekk status manuelt hos Skatteetaten.",
    )
