#!/usr/bin/env bash
#
# Mynt en per-org invite-lenke for den HOSTEDE Wenche-tjenesten i prod.
# Lenken er knyttet til ETT organisasjonsnummer.
#
# Scriptet velger metode automatisk:
#   * LOKALT  hvis ~/.wenche/hosted-prod.env finnes (rask; secret ligger lokalt OG paa Fly)
#   * ellers via flyctl ssh paa Fly-maskinen (secret blir kun paa Fly)
#
# Lokal env-fil (utenfor repoet, chmod 600):
#   HOSTED_INVITE_SECRET=...        # SAMME verdi som Fly-secreten, ellers validerer ikke serveren
#   HOSTED_PUBLIC_URL=https://app.wenche.cloud
#
# ssh-fallback krever engangsoppsett:  flyctl ssh issue --agent
#
# Bruk:
#   hosted/invite.sh <orgnr>
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${WENCHE_HOSTED_ENV:-$HOME/.wenche/hosted-prod.env}"
APP="${WENCHE_HOSTED_APP:-wenche-hosted}"
HEALTH_URL="${WENCHE_HOSTED_HEALTH:-https://app.wenche.cloud/api/health}"
ORG="${1:-}"

if [ -z "$ORG" ]; then
  echo "Bruk: $0 <orgnr>" >&2
  exit 1
fi

# Rask vei: mynt lokalt med secret fra den untrackede env-fila.
if [ -f "$ENV_FILE" ]; then
  set -a; . "$ENV_FILE"; set +a
  exec "$ROOT/.venv/bin/python" "$ROOT/hosted/mint_invite.py" "$ORG"
fi

# Fallback: kjoer mint_invite.py inne paa Fly-maskinen (secret forlater aldri serveren).
# Maskinen er scale-to-zero; vekk den foerst saa ssh har noe aa koble til.
curl -fsS "$HEALTH_URL" >/dev/null 2>&1 || true
exec flyctl ssh console --app "$APP" -C "python /app/hosted/mint_invite.py $ORG"
