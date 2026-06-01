"""
Skriv ut Wenches per-org invite-lenke. Del den ut manuelt til en kjent, verifisert person
(e-post, Signal, ...). Lenken er knyttet til ETT organisasjonsnummer, så mottakeren kan
kun koble og sende inn for det selskapet. Roter ved å bytte HOSTED_INVITE_SECRET, det
ugyldiggjør alle tidligere utdelte lenker.

  HOSTED_INVITE_SECRET=... HOSTED_PUBLIC_URL=https://wenche... \
      ./.venv/bin/python hosted/mint_invite.py <orgnr>

Uten satte variabler brukes dev-standardene (samme som dev_local.py).
"""
import os
import sys

from itsdangerous import URLSafeSerializer

if len(sys.argv) < 2 or not sys.argv[1].strip():
    raise SystemExit("Bruk: python hosted/mint_invite.py <orgnr>")

org = sys.argv[1].strip()
secret = os.getenv("HOSTED_INVITE_SECRET", "dev-invite-secret-bytt-i-prod")
public = os.getenv("HOSTED_PUBLIC_URL", "http://localhost:5173")
token = URLSafeSerializer(secret, salt="invite").dumps({"org": org})
print(f"{public}/?invite={token}")
