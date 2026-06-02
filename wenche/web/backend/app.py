"""
FastAPI-app for det self-hostede Wenche-webgrensesnittet.

`lag_app(env)` bygger appen og låser miljøet (prod/test) for kjøringen. Den serverer JSON-API-et
under /api/* og den ferdigbygde SPA-en (wenche/web/static) på samme origin. `kjor(env)` er
inngangen CLI-en bruker (`wenche` / `wenche dev`): starter uvicorn på 127.0.0.1 og åpner
nettleseren. Enbruker og lokalt — ingen invite/sesjon-auth, bind bevisst til loopback.
"""
from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from wenche import __version__ as WENCHE_VERSJON

from . import miljo
from .oppdatering import er_nyere_versjon, hent_nyeste_pypi_versjon, kjorer_fra_git_klone
from .ruter_config import router as config_router
from .ruter_dokumenter import router as dokumenter_router
from .ruter_frister import router as frister_router
from .ruter_innsending import router as innsending_router
from .ruter_oppsett import router as oppsett_router

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"


def lag_app(env: str = "prod", serve_spa: bool = True) -> FastAPI:
    miljo.sett_env(env)
    app = FastAPI(title="Wenche", version=WENCHE_VERSJON)

    app.include_router(config_router)
    app.include_router(oppsett_router)
    app.include_router(frister_router)
    app.include_router(dokumenter_router)
    app.include_router(innsending_router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "env": miljo.aktiv_env(), "wenche": WENCHE_VERSJON}

    @app.get("/api/update-check")
    def update_check() -> dict:
        """Sjekk om en nyere Wenche finnes på PyPI. Faller stille tilbake ved nettverksfeil."""
        siste = hent_nyeste_pypi_versjon()
        nyere = bool(siste) and er_nyere_versjon(siste, WENCHE_VERSJON)
        return {
            "naavaerende": WENCHE_VERSJON,
            "siste": siste,
            "nyere": nyere,
            "fra_git": kjorer_fra_git_klone(),
        }

    # Server den bygde SPA-en fra samme origin. Vi sjekker på index.html (ikke bare mappen),
    # så en ubygd/tom static-mappe (CI, editable-install) ikke krasjer oppstarten. I dev
    # (serve_spa=False) serverer Vite SPA-en med hot reload, og denne appen er ren API.
    if serve_spa and _INDEX_HTML.is_file():
        _index_html = _INDEX_HTML.read_text(encoding="utf-8")

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        def spa_index() -> HTMLResponse:
            return HTMLResponse(_index_html)

        # Montert sist, så /api/* + "/" matcher først.
        app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="spa")

    return app


def kjor(env: str = "prod", port: int = 8080) -> None:
    """Start det lokale webgrensesnittet og åpne nettleseren (inngang fra CLI-en)."""
    import uvicorn

    app = lag_app(env)
    url = f"http://127.0.0.1:{port}"
    if _INDEX_HTML.is_file():
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    else:
        print(
            "Bygd SPA mangler (wenche/web/static). Kjør utviklingsmodus i stedet:\n"
            "  cd wenche/web/frontend && npm install && npm run dev"
        )
    print(f"Wenche{' [TEST]' if env == 'test' else ''} -> {url}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
