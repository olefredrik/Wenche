"""
Hent den forhåndsutfylte skattemeldingen for én org og skriv ut det rå svaret fra
Skatteetaten. Operatør-verktøy: kjøres lokalt og leser Maskinporten-credsene rett fra .env
(MASKINPORTEN_*_PROD), samme nøkkelpar som prod, så svaret er autoritativt.

Bakgrunn: den ekte skattemelding-innsendingen (dry_run=false) gjør som aller første steg
en GET mot Skatteetatens forhåndsutfylt-API for å utlede partsnummer og
dokumentreferanseTilGjeldendeDokument (se wenche/innsending.py send_skattemelding og
wenche/skd_skattemelding_client.py hent_forhåndsutfylt_med_id). Feiler den GET-en, stopper
innsendingen før tallene i det hele tatt brukes, og hostet-API-et pakker det som en HTTP 502
med Skatteetatens statuskode i teksten («Feil ved henting av forhåndsutfylt skattemelding:
400»). Dette skriptet gjør nøyaktig den GET-en og viser hele svaret, så vi ser den eksakte
400-årsaken uten å vente på at brukeren melder fra.

  WENCHE_ENV=prod ./.venv/bin/python hosted/hent_forhandsutfylt.py 999999999 2025

Argumenter: <orgnr> [inntektsår].  Standard inntektsår: 2025.  Credsene leses fra .env
(MASKINPORTEN_CLIENT_ID_PROD / _KID_PROD / MASKINPORTEN_PRIVAT_NOKKEL), valgt av WENCHE_ENV.

Read-only: gjør kun en GET (henting/visning), sender ingenting inn og endrer ingenting hos
Skatteetaten.
"""
import os
import sys

from wenche import auth as wauth
from wenche.auth import SKD_SKATTEMELDING_SCOPE
from wenche.skd_skattemelding_client import SkdSkattemeldingClient


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Bruk: hent_forhandsutfylt.py <orgnr> [inntektsår]")
    org = sys.argv[1].strip()
    inntektsaar = int(sys.argv[2]) if len(sys.argv) > 2 else 2025

    env = os.getenv("WENCHE_ENV", "prod")
    creds = wauth._les_cli_credentials(env)  # leser MASKINPORTEN_*_{ENV} fra .env
    print(f"Miljø: {env}   org: {org}   inntektsår: {inntektsaar}\n")

    # Maskinporten-token på vegne av kunde-orgen, akkurat slik innsendingsruten gjør.
    token = wauth.hent_tokens_for(creds, org, SKD_SKATTEMELDING_SCOPE)["maskinporten_token"]

    with SkdSkattemeldingClient(token, env=env) as skd:
        url = f"{skd._base}/api/skattemelding/v2/{inntektsaar}/{org}"
        print(f"GET {url}\n")
        resp = skd._http.get(url, headers={"Accept": "application/xml"})
        print(f"HTTP {resp.status_code}   Content-Type: {resp.headers.get('content-type', '?')}")
        print("--- svar fra Skatteetaten ---")
        print(resp.text or "(tom kropp)")
        print("--- slutt ---")

        if resp.is_success:
            # Samme tolkning som hent_forhåndsutfylt_med_id, for å se om partsnummer finnes.
            try:
                _, dok_id = skd.hent_forhåndsutfylt_med_id(inntektsaar, org)
                print(f"\nForhåndsutfylt hentet OK. dokument-id: {dok_id or '(ikke funnet)'}")
            except Exception as e:  # noqa: BLE001
                print(f"\nKunne ikke tolke forhåndsutfylt-svaret: {e}")


if __name__ == "__main__":
    main()
