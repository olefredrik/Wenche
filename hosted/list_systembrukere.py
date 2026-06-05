"""
List alle systembrukere som er koblet til den hostede Wenche-deployen, og sjekk hvilke
rettigheter hver av dem faktisk kan bruke. Operatør-verktøy: kjøres lokalt med de samme
HOSTED_VENDOR_*-creds som prod-appen, så svaret er autoritativt for den kjørende tjenesten
(ikke din personlige self-hosted .env).

Bakgrunn: en systembrukers rettigheter fryses ved kundens samtykke. Utvider du
rettighetspakken senere (f.eks. da skattemelding ble lagt til 2026-03-27), får kunder som
allerede har koblet seg på den IKKE automatisk. De feiler da på nettopp det skjemaet, mens
de skjemaene de samtykket til virker. Dette skriptet finner dem uten å vente på at de melder
fra: for hver tilkoblede org prøver det å hente token for hvert skjema, akkurat slik
innsendingsruten gjør. Feiler token-hentingen, ville innsendingen gitt samme feil.

  WENCHE_ENV=prod \
  HOSTED_VENDOR_ORGNR=... HOSTED_VENDOR_CLIENT_ID=... HOSTED_VENDOR_KID=... \
  HOSTED_VENDOR_KEY_PEM="$(cat vendor.pem)" \
      ./.venv/bin/python hosted/list_systembrukere.py

Read-only: henter kun tokens og lister systembrukere, sender ingenting inn og endrer
ingen rettigheter. Fiks for berørte: systembruker.opprett_endringsforespørsel(...) med
[systembruker._SKATTEMELDING_RETT], som kunden så godkjenner i Altinn.
"""
import os
from pathlib import Path

from wenche import auth as wauth
from wenche import systembruker as sb
from wenche.auth import (
    ADMIN_SCOPES,
    SCOPES,
    SKD_AKSJONAER_SCOPE,
    SKD_SKATTEMELDING_SCOPE,
    VendorCredentials,
)

# Skjemaene en tilkoblet org kan sende inn, med scopene innsendingsruten faktisk ber om.
SKJEMAER = [
    ("aarsregnskap", SCOPES, True),
    ("aksjonaer", SKD_AKSJONAER_SCOPE, False),
    ("skattemelding", SKD_SKATTEMELDING_SCOPE, True),
]


def _org_av(systembruker: dict) -> str | None:
    for nokkel in ("reporteeOrgNo", "partyOrgNo", "orgNo", "partyId"):
        if systembruker.get(nokkel):
            return str(systembruker[nokkel])
    return None


def _creds_fra_env() -> tuple[VendorCredentials, str]:
    """Bygg vendor-creds rett fra HOSTED_VENDOR_*-env, uten å dra inn app-konfig.

    Diagnostikk trenger bare vendor-nøkkelen, ikke session-/invite-hemmelighetene som
    api.config fail-closer på i prod.
    """
    orgnr = os.getenv("HOSTED_VENDOR_ORGNR")
    client_id = os.getenv("HOSTED_VENDOR_CLIENT_ID")
    kid = os.getenv("HOSTED_VENDOR_KID")
    pem = os.getenv("HOSTED_VENDOR_KEY_PEM")
    pem_path = os.getenv("HOSTED_VENDOR_KEY_PATH")
    if not (orgnr and client_id and kid and (pem or pem_path)):
        raise SystemExit(
            "Mangler vendor-creds. Sett HOSTED_VENDOR_ORGNR/CLIENT_ID/KID og "
            "HOSTED_VENDOR_KEY_PEM (eller _PATH), og WENCHE_ENV."
        )
    pem_bytes = pem.encode() if pem else Path(pem_path).read_bytes()
    return VendorCredentials(client_id=client_id, kid=kid, private_key_pem=pem_bytes), orgnr


def main() -> None:
    creds, vendor_orgnr = _creds_fra_env()
    env = os.getenv("WENCHE_ENV", "prod")

    print(f"Miljø: {env}   vendor: {vendor_orgnr}   system: {sb.system_id(vendor_orgnr)}\n")

    admin_token = wauth.hent_tokens_for(creds, scopes=ADMIN_SCOPES)["maskinporten_token"]
    brukere = sb.hent_systembrukere(admin_token, vendor_orgnr)
    if not brukere:
        print("Ingen systembrukere koblet til.")
        return

    print(f"{len(brukere)} tilkoblede systembrukere:\n")
    for b in brukere:
        org = _org_av(b)
        if not org:
            print(f"  ? ukjent org i objekt: {b}")
            continue
        status = []
        for navn, scope, veksle in SKJEMAER:
            try:
                wauth.hent_tokens_for(creds, org, scope, veksle_altinn=veksle)
                status.append(f"{navn}=OK")
            except Exception as e:  # noqa: BLE001 - vil se hvilket skjema som feiler og hvorfor
                kort = str(e).splitlines()[0][:80]
                status.append(f"{navn}=FEIL ({kort})")
        print(f"  {org}: " + "  ".join(status))


if __name__ == "__main__":
    main()
