"""
Hent den forhåndsutfylte skattemeldingen for én org og skriv ut det rå svaret fra
Skatteetaten. Operatør-verktøy: kjøres lokalt og leser Maskinporten-credsene rett fra .env
(MASKINPORTEN_*_PROD), samme nøkkelpar som prod, så svaret er autoritativt.

Bakgrunn: den ekte skattemelding-innsendingen (dry_run=false) gjør som aller første steg
en GET mot Skatteetatens forhåndsutfylt-API for å utlede partsnummer og
dokumentreferanseTilGjeldendeDokument (se wenche/innsending.py send_skattemelding og
wenche/skd_skattemelding_client.py hent_forhaandsutfylt_med_id). Feiler den GET-en, stopper
innsendingen før tallene i det hele tatt brukes, og hostet-API-et pakker det som en HTTP 502
med Skatteetatens statuskode i teksten («Feil ved henting av forhåndsutfylt skattemelding:
400»). Dette skriptet gjør nøyaktig den GET-en og viser hele svaret, så vi ser den eksakte
400-årsaken uten å vente på at brukeren melder fra.

  WENCHE_ENV=prod ./.venv/bin/python hosted/hent_forhandsutfylt.py 999999999 2025

Argumenter: <orgnr> [inntektsår] [--vis-svar].  Standard inntektsår: 2025.  Credsene leses fra
.env (MASKINPORTEN_CLIENT_ID_PROD / _KID_PROD / MASKINPORTEN_PRIVAT_NOKKEL), valgt av WENCHE_ENV.
Svarkroppen (hele den forhåndsutfylte skattemeldingen) skrives bare ut når kallet feiler, eller
med --vis-svar; ellers vises status, lengde og om partsnummer og dokument-id ble funnet.

Read-only: gjør kun en GET (henting/visning), sender ingenting inn og endrer ingenting hos
Skatteetaten.
"""

import sys

from wenche import auth as wauth
from wenche import miljoer
from wenche.auth import SKD_SKATTEMELDING_SCOPE
from wenche.skd_skattemelding_client import SkdSkattemeldingClient


def main() -> None:
    vis_svar = "--vis-svar" in sys.argv
    argv = [a for a in sys.argv[1:] if a != "--vis-svar"]
    if not argv:
        raise SystemExit("Bruk: hent_forhandsutfylt.py <orgnr> [inntektsår] [--vis-svar]")
    org = argv[0].strip()
    inntektsaar = int(argv[1]) if len(argv) > 1 else 2025

    miljoer.last_env_filer()
    env = miljoer.gjeldende_navn()
    creds = wauth.les_cli_credentials(env)  # leser MASKINPORTEN_*_{ENV} fra miljøet
    print(f"Miljø: {env}   org: {org}   inntektsår: {inntektsaar}\n")

    # Maskinporten-token på vegne av kunde-orgen, akkurat slik innsendingsruten gjør.
    token = wauth.hent_tokens_for(creds, org, SKD_SKATTEMELDING_SCOPE)["maskinporten_token"]

    with SkdSkattemeldingClient(token, env=env) as skd:
        resp = skd.hent_forhaandsutfylt_svar(inntektsaar, org)
        print(f"GET {resp.request.url}\n")
        print(f"HTTP {resp.status_code}   Content-Type: {resp.headers.get('content-type', '?')}")
        if vis_svar or not resp.is_success:
            print("--- svar fra Skatteetaten ---")
            print(resp.text or "(tom kropp)")
            print("--- slutt ---")
        else:
            print(f"Svarkropp: {len(resp.text)} tegn (skjult, --vis-svar viser den)")

        if resp.is_success:
            # Samme tolkning som hent_forhaandsutfylt_med_id, for å se om partsnummer finnes.
            try:
                _, dok_id = skd.hent_forhaandsutfylt_med_id(inntektsaar, org)
                print(f"\nForhåndsutfylt hentet OK. dokument-id: {dok_id or '(ikke funnet)'}")
            except Exception as e:  # noqa: BLE001
                print(f"\nKunne ikke tolke forhåndsutfylt-svaret: {e}")


if __name__ == "__main__":
    main()
