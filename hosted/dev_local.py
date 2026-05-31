"""
Lokal dev-kjøring av den hostede appen mot Skatteetatens testmiljø (tt02).
IKKE for produksjon.

Mapper Wenches eksisterende _TEST-credentials (fra ~/.wenche/.env og repoets .env) til
HOSTED_*-variablene appen forventer, så du slipper å sette dem manuelt. Hemmeligheter
leses fra .env-filene ved kjøretid, de hardkodes aldri her.

Bruk:
    ./.venv/bin/python hosted/dev_local.py
    # så, i en egen terminal:
    cd hosted/web && npm run dev      # http://localhost:5173
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_REPO = Path(__file__).resolve().parent.parent
load_dotenv(Path.home() / ".wenche" / ".env")
load_dotenv(_REPO / ".env")


def _krev(navn: str) -> str:
    verdi = os.environ.get(navn)
    if not verdi:
        raise SystemExit(
            f"Mangler {navn} i .env (test-oppsettet). Se docs/avansert/testing.md."
        )
    return verdi


os.environ["HOSTED_VENDOR_CLIENT_ID"] = _krev("MASKINPORTEN_CLIENT_ID_TEST")
os.environ["HOSTED_VENDOR_KID"] = _krev("MASKINPORTEN_KID_TEST")
os.environ["HOSTED_VENDOR_ORGNR"] = _krev("ORG_NUMMER")

_key = os.environ.get("MASKINPORTEN_PRIVAT_NOKKEL", "maskinporten_privat.pem")
_cands = [
    Path(_key),
    Path.home() / ".wenche" / Path(_key).name,
    Path.home() / ".wenche" / "maskinporten_privat.pem",
]
os.environ["HOSTED_VENDOR_KEY_PATH"] = next((str(p) for p in _cands if p.exists()), _key)

os.environ["WENCHE_ENV"] = "test"
os.environ.setdefault("HOSTED_ALLOWLIST", "test@example.no")
os.environ.setdefault("HOSTED_SESSION_SECRET", "dev-local-secret")
os.environ.setdefault("HOSTED_PUBLIC_URL", "http://localhost:5173")
# Hosted bruker org fra dataene/sesjonen (som i prod), ikke self-hosted sin globale
# test-override. Sett tomme (ikke pop, da ville wenche.auth sin load_dotenv re-lese
# repoets .env) så aksjonær/skattemelding bruker config-orgen = kunde-org.
os.environ["SKD_TEST_ORG_NUMMER"] = ""
os.environ["SKD_TEST_PARTSNUMMER"] = ""

if __name__ == "__main__":
    import uvicorn

    print("Hosted Wenche (dev/test) -> http://127.0.0.1:8077")
    print("Logg inn i SPA-en med allowlist-epost:", os.environ["HOSTED_ALLOWLIST"])
    uvicorn.run("hosted.api.main:app", host="127.0.0.1", port=8077, reload=True)
