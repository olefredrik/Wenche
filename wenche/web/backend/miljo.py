"""
Miljø- og konfig-tilstand for det self-hostede webgrensesnittet.

Miljøet (prod/test) låses per kjøring (slik `wenche` vs `wenche dev` gjorde det i NiceGUI),
og settes også i `WENCHE_ENV` slik at hele kjernen (auth, klienter, fristsjekk) peker mot
riktig miljø. Credentials og oppsett bor i `~/.wenche/.env` + `~/.wenche/maskinporten_privat.pem`,
nøyaktig som før — porten fra `wenche/ui.py`.
"""
from __future__ import annotations

import os
from pathlib import Path

_WENCHE_DIR = Path.home() / ".wenche"
_BRUKER_ENV_FIL = _WENCHE_DIR / ".env"
_PRIVAT_NOKKEL_FIL = _WENCHE_DIR / "maskinporten_privat.pem"

# Aktivt miljø for hele kjøringen. Settes av sett_env() ved app-oppstart.
_AKTIV_ENV: str = "prod"


def sett_env(env: str) -> None:
    """Lås miljøet for kjøringen og speil det til WENCHE_ENV for hele kjernen."""
    global _AKTIV_ENV
    if env not in ("prod", "test"):
        raise ValueError(f"Ukjent miljø: {env!r}. Bruk 'prod' eller 'test'.")
    _AKTIV_ENV = env
    os.environ["WENCHE_ENV"] = env


def aktiv_env() -> str:
    return _AKTIV_ENV


def er_test() -> bool:
    return _AKTIV_ENV == "test"


def config_fil() -> Path:
    """Aktiv config-fil: `config.yaml` (prod) eller `config.dev.yaml` (test).

    Skiller test-data fra ekte selskapsinformasjon slik at Tenor-orgnumre ikke
    overskriver din virkelige config (samme regel som NiceGUI-en brukte).
    """
    return Path("config.dev.yaml" if _AKTIV_ENV == "test" else "config.yaml")


def orgnr_var() -> str:
    """Navnet på env-variabelen som holder orgnr for aktivt miljø."""
    return "SKD_TEST_ORG_NUMMER" if _AKTIV_ENV == "test" else "ORG_NUMMER"


def aktiv_orgnr() -> str:
    return os.getenv(orgnr_var(), "").strip()


def med_test_org(config: dict) -> dict:
    """
    I testmiljø: bytt selskapets `org_nummer` til Tenor-test-orgnr-et du har systembruker for
    (`SKD_TEST_ORG_NUMMER`), uavhengig av hva som står i config. Det gjør at hele kjeden (XML,
    Altinn-instans, validering) bruker samme org som systembrukeren er godkjent for, så org-
    mismatch (403) ikke kan oppstå når man tørrtrener med eksempeldata. No-op i prod.
    """
    if not er_test():
        return config
    test_org = os.getenv("SKD_TEST_ORG_NUMMER", "").strip()
    if not test_org:
        return config
    return {**config, "selskap": {**(config.get("selskap") or {}), "org_nummer": test_org}}


def les_konfig_for_milj(navn: str, env: str | None = None, default: str = "") -> str:
    """
    Les credential-verdi for gitt miljø.

    Prøver først miljø-spesifikk variant ({navn}_{TEST|PROD}). Hvis den er eksplisitt satt
    (selv som tom streng) er den autoritativ. Faller tilbake til generisk variabelnavn kun
    når miljø-spesifikk variabel ikke er definert i det hele tatt.
    """
    if env is None:
        env = _AKTIV_ENV
    env_key = f"{navn}_{env.upper()}"
    if env_key in os.environ:
        return os.environ[env_key] or default
    return os.getenv(navn) or default


def privat_nokkel_sti() -> str:
    return os.getenv("MASKINPORTEN_PRIVAT_NOKKEL", "maskinporten_privat.pem")


# --- Systembruker-tilstand persistert per miljø (request-id + sist mottatt godkjenningslenke) ---

def _request_id_fil(env: str) -> Path:
    return _WENCHE_DIR / f"systembruker_request_id_{env}.txt"


def _confirm_url_fil(env: str) -> Path:
    return _WENCHE_DIR / f"systembruker_confirm_url_{env}.txt"


def lagre_request_id(request_id: str, env: str | None = None) -> None:
    _WENCHE_DIR.mkdir(exist_ok=True)
    _request_id_fil(env or _AKTIV_ENV).write_text(request_id, encoding="utf-8")


def les_request_id(env: str | None = None) -> str:
    fil = _request_id_fil(env or _AKTIV_ENV)
    return fil.read_text(encoding="utf-8").strip() if fil.exists() else ""


def lagre_confirm_url(url: str, env: str | None = None) -> None:
    if not url:
        return
    _WENCHE_DIR.mkdir(exist_ok=True)
    _confirm_url_fil(env or _AKTIV_ENV).write_text(url, encoding="utf-8")


def les_confirm_url(env: str | None = None) -> str:
    fil = _confirm_url_fil(env or _AKTIV_ENV)
    return fil.read_text(encoding="utf-8").strip() if fil.exists() else ""


def sikre_bruker_env_fil() -> bool:
    """
    Sørg for at ~/.wenche/.env eksisterer og er trygt rettighetssatt. Migrerer en eventuell
    cwd/.env (oppsett fra eldre Wenche-versjoner) inn. Returnerer True hvis migrering skjedde.
    """
    _WENCHE_DIR.mkdir(exist_ok=True)
    if _BRUKER_ENV_FIL.exists():
        return False
    migrert = False
    cwd_env = Path(".env")
    if cwd_env.is_file():
        _BRUKER_ENV_FIL.write_text(cwd_env.read_text(encoding="utf-8"), encoding="utf-8")
        migrert = True
    else:
        _BRUKER_ENV_FIL.touch()
    try:
        _BRUKER_ENV_FIL.chmod(0o600)
    except OSError:
        pass
    return migrert
