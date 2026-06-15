"""
FastAPI-app for den hostede Wenche-tjenesten.

Importerer `wenche` som bibliotek og gjenbruker domene-, auth- og klientlaget. Server-side
ephemeral sesjon, ingen database. Onboarding: per-org invite-lenke + Altinn systembruker-
godkjenning (BankID). Serverer også den bygde SPA-en (web/dist) på samme origin i prod.
Self-hosted-appen (`wenche.web`) er upåvirket. Se hosted/README.md.
"""
import html
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from wenche import __version__ as WENCHE_VERSJON

from .auth import router as auth_router
from .config import settings
from .dokumenter import router as dokumenter_router
from .idporten import router as idporten_router
from .innsending import router as innsending_router
from .saft import router as saft_router
from .selskap import router as selskap_router
from .systembruker import router as systembruker_router

s = settings()

# API-dokumentasjonen (/docs, /redoc, /openapi.json) er slått av: tjenesten har én kjent
# klient (SPA-en på samme origin), og et åpent skjema gjør rekognosering unødvendig lett.
app = FastAPI(
    title="Wenche hosted",
    version=WENCHE_VERSJON,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Signert sesjonscookie for identitet (e-post, kunde-org). Holder IKKE finansdata.
# max_age er Starlette-defaulten (14 dager), satt eksplisitt som et bevisst valg: verktøyet
# brukes i korte økter rundt årsoppgjøret, og kortere levetid ville tvinge ny invite-lenke
# eller handoff oftere uten reell sikkerhetsgevinst (cookien holder kun identitet).
app.add_middleware(
    SessionMiddleware,
    secret_key=s.session_secret,
    max_age=14 * 24 * 3600,
    https_only=(s.env == "prod"),
    same_site="lax",
)

# Standard sikkerhetsheadere på alle svar. CSP er bevisst utelatt: den krever kartlegging av
# SPA-ens inline styles og den env-styrte Umami-hosten, og en gal CSP knekker appen stille.
class _SikkerhetsHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        respons = await call_next(request)
        respons.headers["X-Frame-Options"] = "DENY"
        respons.headers["X-Content-Type-Options"] = "nosniff"
        respons.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        respons.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if s.env == "prod":
            # Fly tvinger allerede HTTPS på edge (force_https); HSTS lar nettleseren huske det.
            respons.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return respons


app.add_middleware(_SikkerhetsHeaders)

# CORS for SPA-frontenden (egen origin under utvikling).
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(idporten_router)
app.include_router(systembruker_router)
app.include_router(innsending_router)
app.include_router(dokumenter_router)
app.include_router(saft_router)
app.include_router(selskap_router)


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
# I dev finnes ikke dist (Vite serverer SPA-en på 5173), så dette er en no-op da.
_SPA_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
if _SPA_DIST.is_dir():
    # index.html serveres via egen rute så vi kan injisere anonymisert Umami-statistikk
    # (env-styrt, ingen verdier i repoet). data-auto-track="false": SPA-en sporer manuelt
    # FØRST etter at invite-tokenet er fjernet fra URL-en, så tokenet aldri når analytics.
    _index_html = (_SPA_DIST / "index.html").read_text(encoding="utf-8")
    _umami_src = os.getenv("HOSTED_UMAMI_SRC")
    _umami_id = os.getenv("HOSTED_UMAMI_WEBSITE_ID")
    if _umami_src and _umami_id:
        # html.escape som defense-in-depth: verdiene er operatørstyrte env-vars, men de skal
        # uansett aldri kunne bryte ut av attributtene de interpoleres inn i.
        _tag = (
            f'<script defer src="{html.escape(_umami_src, quote=True)}" '
            f'data-website-id="{html.escape(_umami_id, quote=True)}" '
            'data-auto-track="false"></script>'
        )
        _index_html = _index_html.replace("</head>", _tag + "</head>")

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def spa_index() -> HTMLResponse:
        return HTMLResponse(_index_html)

    # Resten (assets m.m.) serveres statisk. Montert SIST, så /api/* + "/" matcher først.
    app.mount("/", StaticFiles(directory=_SPA_DIST, html=True), name="spa")
