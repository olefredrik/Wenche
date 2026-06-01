# Container for den HOSTEDE Wenche-tjenesten (hosted/), ikke for self-hosted CLI/NiceGUI.
# Multi-stage: bygg SPA-en med Node, kjør FastAPI som serverer både API og SPA på samme origin.

# ---- Stage 1: bygg SPA-en ----
FROM node:20-slim AS web
WORKDIR /web
COPY hosted/web/package.json hosted/web/package-lock.json ./
RUN npm ci
COPY hosted/web/ ./
RUN npm run build

# ---- Stage 2: Python-app ----
FROM python:3.11-slim AS app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Installer wenche-kjernen (fra pyproject) + hosted-avhengighetene.
COPY pyproject.toml README.md LICENSE ./
COPY wenche/ ./wenche/
RUN pip install .
COPY hosted/requirements.txt ./hosted/requirements.txt
RUN pip install -r hosted/requirements.txt

# App-koden + det ferdigbygde SPA-et (FastAPI monterer hosted/web/dist på "/").
COPY hosted/ ./hosted/
COPY --from=web /web/dist ./hosted/web/dist

EXPOSE 8080
# ÉN worker med vilje: in-memory-sesjonen forutsetter én prosess.
CMD ["uvicorn", "hosted.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
