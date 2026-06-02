# Container for den HOSTEDE Wenche-tjenesten (hosted/), ikke for self-hosted CLI.
# Multi-stage: bygg SPA-ene med Node i npm-workspacet, kjør FastAPI som serverer API + SPA.

# ---- Stage 1: bygg SPA-ene i workspace ----
FROM node:20-slim AS web
WORKDIR /repo
# Workspace-manifester først for god lag-caching.
COPY package.json package-lock.json ./
COPY packages/ui/package.json packages/ui/package.json
COPY hosted/web/package.json hosted/web/package.json
COPY wenche/web/frontend/package.json wenche/web/frontend/package.json
RUN npm ci
# Kildekode for det delte designsystemet + begge appene.
COPY packages ./packages
COPY hosted/web ./hosted/web
COPY wenche/web/frontend ./wenche/web/frontend
# Hostet SPA (-> hosted/web/dist) og self-hosted SPA (-> wenche/web/static).
# Self-hosted static bygges fordi `pip install .` force-includer den i wheelen.
RUN npm run build --workspace hosted/web
RUN npm run build --workspace wenche/web/frontend

# ---- Stage 2: Python-app ----
FROM python:3.11-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Installer wenche-kjernen (fra pyproject) + hosted-avhengighetene.
COPY pyproject.toml README.md LICENSE ./
COPY wenche/ ./wenche/
# Den bygde self-hosted SPA-en må finnes ved install (force-include i pyproject).
COPY --from=web /repo/wenche/web/static ./wenche/web/static
RUN pip install .
COPY hosted/requirements.txt ./hosted/requirements.txt
RUN pip install -r hosted/requirements.txt

# App-koden + det ferdigbygde hostede SPA-et (FastAPI monterer hosted/web/dist på "/").
COPY hosted/ ./hosted/
COPY --from=web /repo/hosted/web/dist ./hosted/web/dist

EXPOSE 8080
# ÉN worker med vilje: in-memory-sesjonen forutsetter én prosess.
CMD ["uvicorn", "hosted.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
