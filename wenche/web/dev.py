"""
Lokal dev-backend for self-hosted SPA-en (mot tt02).

Kjør sammen med Vite-dev-serveren i en egen terminal:

    ./.venv/bin/python -m wenche.web.dev          # ren API på http://127.0.0.1:8080
    cd wenche/web/frontend && npm run dev          # SPA m/ hot reload på http://localhost:5174

Åpne http://localhost:5174 — Vite serverer SPA-en med hot reload og proxer /api hit. Denne
backenden serverer KUN /api (serve_spa=False), så den ikke kolliderer med Vite, og auto-
reloader ved Python-endringer.
"""
import os

os.environ.setdefault("WENCHE_ENV", "test")

from wenche.web.backend.app import lag_app


def lag_dev_app():
    return lag_app("test", serve_spa=False)


if __name__ == "__main__":
    import uvicorn

    print("Self-hosted dev-API -> http://127.0.0.1:8080  (åpne SPA-en på http://localhost:5174)")
    uvicorn.run(
        "wenche.web.dev:lag_dev_app",
        factory=True,
        host="127.0.0.1",
        port=8080,
        reload=True,
        reload_dirs=["wenche"],
    )
