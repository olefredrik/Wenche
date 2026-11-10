# Container for den HOSTEDE Wenche-tjenesten (hosted/), ikke for self-hosted CLI.
# Multi-stage: bygg SPA-ene med Node i npm-workspacet, kjør FastAPI som serverer API + SPA.

# ---- Stage 1: bygg SPA-ene i workspace ----
FROM node:22-slim AS web
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

# Låste avhengigheter først, som eget lag (endres sjeldnere enn koden). hosted/requirements.txt
# er generert fra pyproject (kjerne + hosted-extra) med uv, se toppen av fila, så imaget bygges
# likt hver gang i stedet for å løse nyeste versjon ved hvert bygg.
COPY hosted/requirements.txt ./hosted/requirements.txt
RUN pip install -r hosted/requirements.txt
# Så wenche selv, uten at pip løser avhengigheter på nytt (alt ligger alt i låsen).
COPY pyproject.toml README.md LICENSE ./
COPY wenche/ ./wenche/
# Den bygde self-hosted SPA-en må finnes ved install (force-include i pyproject).
COPY --from=web /repo/wenche/web/static ./wenche/web/static
RUN pip install --no-deps .

# Bare det imaget bruker: API-et, operatørskriptet som kjøres via `fly ssh console`
# (hosted/invite.sh), og det ferdigbygde hostede SPA-et (FastAPI monterer dist på "/").
COPY hosted/api/ ./hosted/api/
COPY hosted/mint_invite.py ./hosted/mint_invite.py
COPY --from=web /repo/hosted/web/dist ./hosted/web/dist

# Kjør som ikke-root (laveste privilegium). Appen skriver ikke til disk i drift (session-only),
# og mint_invite.py leser kun env, så brukeren trenger bare lesetilgang til /app, som alle har.
RUN adduser --disabled-password --gecos "" wenche
USER wenche

EXPOSE 8080
# ÉN worker med vilje (sesjonen ligger i cookien, men rate-limit og caches er per prosess).
# Access-loggen er av: den ville logget hver URL med query-streng, der ID-porten-callbackens
# code/state står, og der eldre invite-/handoff-lenker bar tokenet. Feil logges fortsatt.
# --forwarded-allow-ips="*": bare Fly-proxyen når porten, så X-Forwarded-For kan stoles på og
# request.client.host blir sluttbrukerens adresse (rate-limit-fallback i auth.py).
CMD ["uvicorn", "hosted.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "*"]
