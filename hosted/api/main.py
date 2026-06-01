"""
FastAPI-skjelett for hostet Wenche (MVP).

Importerer `wenche` som bibliotek. Server-side ephemeral sesjon, ingen database.
Self-hosted NiceGUI-appen (`wenche/ui.py`) er upåvirket av denne appen.

Faser bygges inkrementelt (se docs/hosted/mvp-plan.md):
  Fase 2 (her): skjelett, helse, sesjon, CORS.
  Fase 3: magic-link-innlogging + invite-allowlist.
  Fase 4: systembruker-onboarding.
  Fase 5: innsendings-endepunkter + SPA.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from wenche import __version__ as WENCHE_VERSJON

from .auth import router as auth_router
from .config import settings
from .innsending import router as innsending_router
from .systembruker import router as systembruker_router

s = settings()

app = FastAPI(title="Wenche hosted (MVP)", version=WENCHE_VERSJON)

# Signert sesjonscookie for identitet (e-post, kunde-org). Holder IKKE finansdata.
app.add_middleware(
    SessionMiddleware,
    secret_key=s.session_secret,
    https_only=(s.env == "prod"),
    same_site="lax",
)

# CORS for SPA-frontenden (egen origin under utvikling).
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(systembruker_router)
app.include_router(innsending_router)


@app.get("/api/health")
def health() -> dict:
    """Helsesjekk. Avslører miljø og om vendor-creds er konfigurert (ikke selve verdiene)."""
    return {
        "status": "ok",
        "env": s.env,
        "wenche": WENCHE_VERSJON,
        "vendor_konfigurert": s.vendor_credentials() is not None,
    }


# Server den bygde SPA-en fra samme origin i prod (slipper CORS/cookie-kryssorigin).
# Monteres SIST, så /api/*-rutene over matcher først; html=True gir index.html på "/".
# I dev finnes ikke dist (Vite serverer SPA-en på 5173), så dette er en no-op da.
_SPA_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _SPA_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_SPA_DIST, html=True), name="spa")
