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
      ./.venv/bin/python hosted/diagnose_forhandsutfylt.py <orgnr> <aar> [--valider]

Read-only: henter kun, sender ingenting inn. Skriver ikke ut tall-/persondata fra den
forhåndsutfylte, kun struktur (tag-navn), partsnummer (SKDs interne id) og HTTP-status.

--valider: i tillegg, bygg en MINIMAL, GENERISK (ikke kundens) v5-skattemelding for orgnr/året
med det ekte partsnummeret, pakk konvolutten som ved ekte innsending, og kjør Skatteetatens
`valider`-tjeneste (IKKE-BINDENDE, sender ingenting inn). Svarer på om v5 godtas for året eller
avvises på skjemaversjon. Generiske tall, så ingen persondata involveres.
"""
import os
import sys
from pathlib import Path
from xml.etree.ElementTree import fromstring

from wenche import auth as wauth
from wenche import skattemelding as sm
from wenche.auth import SKD_SKATTEMELDING_SCOPE, VendorCredentials
from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
from wenche.skattemelding_konvolutt import generer_konvolutt
from wenche.skattemelding_xml import generer_skattemelding_fra_konfig, hent_partsnummer
from wenche.skd_skattemelding_client import SkdSkattemeldingClient


def _minimal_config(orgnr: str, aar: int) -> dict:
    """Minimal, balansert, GENERISK config — kun for å teste skjemaversjon, ikke kundens tall."""
    return {
        "selskap": {"navn": "DIAGNOSE AS", "org_nummer": orgnr, "daglig_leder": "Test Person",
                    "styreleder": "Test Person", "forretningsadresse": "Testveien 1, 0001 OSLO",
                    "stiftelsesaar": 2018, "aksjekapital": 30000, "kontakt_epost": "test@example.no"},
        "regnskapsaar": aar,
        "resultatregnskap": {"driftsinntekter": {"salgsinntekter": 0, "andre_driftsinntekter": 0},
            "driftskostnader": {"loennskostnader": 0, "avskrivninger": 0, "andre_driftskostnader": 0},
            "finansposter": {"utbytte_fra_datterselskap": 0, "andre_finansinntekter": 0,
                             "rentekostnader": 0, "andre_finanskostnader": 0}},
        "balanse": {"eiendeler": {"anleggsmidler": {"aksjer_i_datterselskap": 0, "andre_aksjer": 0, "langsiktige_fordringer": 0},
                        "omloepmidler": {"kortsiktige_fordringer": 0, "bankinnskudd": 30000}},
            "egenkapital_og_gjeld": {"egenkapital": {"aksjekapital": 30000, "overkursfond": 0, "annen_egenkapital": 0},
                "langsiktig_gjeld": {"laan_fra_aksjonaer": 0, "andre_langsiktige_laan": 0},
                "kortsiktig_gjeld": {"leverandoergjeld": 0, "skyldige_offentlige_avgifter": 0, "annen_kortsiktig_gjeld": 0}}},
        "skattemelding": {"anvend_fritaksmetoden": True, "boersnotert": False,
                          "underskudd_til_fremfoering": 0, "formuesverdi_aksjer": 0},
        "aksjonaerer": [],
    }


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
        raise SystemExit("Bruk: python hosted/diagnose_forhandsutfylt.py <orgnr> <aar> [--valider]")
    orgnr, aar = sys.argv[1].strip(), int(sys.argv[2])
    gjor_valider = "--valider" in sys.argv[3:]
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
            print(f"  rot-tag: {_lokal(root.tag)}")
            print(f"  namespace: {root.tag[1:root.tag.rindex('}')] if '}' in root.tag else '(ingen)'}")
            print(f"  barn (struktur, uten verdier): {[_lokal(c.tag) for c in root][:25]}")
        except Exception as e:  # noqa: BLE001 - vil se at svaret ikke er gyldig XML
            print(f"  Svaret er ikke gyldig XML: {e}")
            print(f"  Første 300 tegn: {forhandsutfylt[:300]!r}")
            return

        try:
            pn = hent_partsnummer(forhandsutfylt)
            print(f"\n  partsnummer: FUNNET = {pn}")
        except Exception as e:  # noqa: BLE001
            print(f"\n  partsnummer: MANGLER -> {str(e).splitlines()[0]}")
            print("  Dette er årsaken til at skattemelding-innsending feiler.")
            return

        if not gjor_valider:
            print("\n(Kjør med --valider for ikke-bindende valideringssjekk av v5 mot dette året.)")
            return

        # Ikke-bindende: bygg en MINIMAL, GENERISK v5-skattemelding for året og valider.
        print(f"\n--- Ikke-bindende valider (GENERISKE tall, sender ingenting inn) ---")
        regnskap, konfig = sm.les_config(_minimal_config(orgnr, aar))
        sm_xml = generer_skattemelding_fra_konfig(regnskap, konfig, pn)
        naer_xml = generer_naeringsspesifikasjon(regnskap, pn)
        konvolutt = generer_konvolutt(
            skattemelding_xml=sm_xml, inntektsaar=aar, orgnr=orgnr,
            naeringsspesifikasjon_xml=naer_xml, gjeldende_dokument_id=dok_id,
        )
        try:
            res = skd.valider(aar, orgnr, konvolutt)
        except RuntimeError as e:
            print("  VALIDER FEILET (ikke-2xx) — peker ofte på skjema-/versjonsavvik:")
            print("  " + str(e).strip()[:900])
            return
        print(f"  resultat: {res.get('resultat')}")
        if res.get("aarsak"):
            print(f"  aarsak: {res.get('aarsak')}")
        for nokkel in ("avvik_ved_validering", "avvik_etter_beregning"):
            avvik = res.get(nokkel) or []
            print(f"  {nokkel}: {len(avvik)}")
            for a in avvik[:8]:
                print(f"     - {a.get('avvikstype') or a.get('kode') or a}")


if __name__ == "__main__":
    main()
