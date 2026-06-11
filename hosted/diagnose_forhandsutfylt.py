"""
Lese-only diagnose: hent SKDs forhåndsutfylte skattemelding for ett orgnr/år og rapporter hva
visnings-API-et faktisk gir tilbake. Operatør-verktøy, kjøres lokalt med de samme
HOSTED_VENDOR_*-creds som prod-appen (samme som list_systembrukere.py), så svaret er
autoritativt for den kjørende tjenesten.

Bakgrunn: skattemelding-innsending bygger på partsnummer hentet fra den forhåndsutfylte
(GET /api/skattemelding/v2/{aar}/{orgnr}). Mangler partsnummer, feiler innsendingen. Dette
skriptet svarer på HVORFOR: kom det et 2xx-svar? finnes <partsnummer>? hva slags dokument er
det (utkast/fastsatt), eller er året ikke klargjort (403/404)?

  WENCHE_ENV=prod \
  HOSTED_VENDOR_ORGNR=... HOSTED_VENDOR_CLIENT_ID=... HOSTED_VENDOR_KID=... \
  HOSTED_VENDOR_KEY_PEM="$(cat vendor.pem)" \
      ./.venv/bin/python hosted/diagnose_forhandsutfylt.py <orgnr> <aar>

Read-only: henter kun, sender ingenting inn. Skriver ikke ut tall-/persondata fra den
forhåndsutfylte, kun struktur (tag-navn), partsnummer (SKDs interne id) og HTTP-status.
"""
import os
import sys
from pathlib import Path
from xml.etree.ElementTree import fromstring

from wenche import auth as wauth
from wenche.auth import SKD_SKATTEMELDING_SCOPE, VendorCredentials
from wenche.skattemelding_xml import hent_partsnummer
from wenche.skd_skattemelding_client import SkdSkattemeldingClient


def _creds_fra_env() -> VendorCredentials:
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
    return VendorCredentials(client_id=client_id, kid=kid, private_key_pem=pem_bytes)


def _lokal(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Bruk: python hosted/diagnose_forhandsutfylt.py <orgnr> <aar>")
    orgnr, aar = sys.argv[1].strip(), int(sys.argv[2])
    env = os.getenv("WENCHE_ENV", "prod")
    creds = _creds_fra_env()

    print(f"Miljø: {env}   org: {orgnr}   inntektsår: {aar}\n")

    # Systembruker-token for kunde-orgen, akkurat som innsendingsruten henter det.
    token = wauth.hent_tokens_for(creds, orgnr, SKD_SKATTEMELDING_SCOPE)["maskinporten_token"]

    with SkdSkattemeldingClient(token, env=env) as skd:
        try:
            forhandsutfylt, dok_id = skd.hent_forhåndsutfylt_med_id(aar, orgnr)
        except RuntimeError as e:
            # Ikke-2xx fra SKD (f.eks. 403/404 = ikke klargjort, eller en feilkode som SMEVB-005).
            print("HENTING FEILET (ikke-2xx fra Skatteetaten):")
            print("  " + str(e).strip()[:800])
            return

    print("Henting OK (HTTP 2xx).")
    print(f"  dokument_id: {dok_id!r}")

    try:
        root = fromstring(forhandsutfylt)
    except Exception as e:  # noqa: BLE001 - vil se at svaret ikke er gyldig XML
        print(f"  Svaret er ikke gyldig XML: {e}")
        print(f"  Første 300 tegn: {forhandsutfylt[:300]!r}")
        return

    print(f"  rot-tag: {_lokal(root.tag)}")
    print(f"  namespace: {root.tag[1:root.tag.rindex('}')] if '}' in root.tag else '(ingen)'}")
    print(f"  barn (struktur, uten verdier): {[_lokal(c.tag) for c in root][:25]}")

    try:
        pn = hent_partsnummer(forhandsutfylt)
        print(f"\n  partsnummer: FUNNET = {pn}  -> innsending ville fått partsnummer")
    except Exception as e:  # noqa: BLE001
        print(f"\n  partsnummer: MANGLER -> {str(e).splitlines()[0]}")
        print("  Dette er årsaken til at skattemelding-innsending feiler.")


if __name__ == "__main__":
    main()
