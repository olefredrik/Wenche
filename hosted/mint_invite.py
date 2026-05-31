"""
Skriv ut Wenches invite-lenke. Del den ut manuelt til inviterte (e-post, Signal, ...).
Roter ved å bytte HOSTED_INVITE_SECRET, det ugyldiggjør alle tidligere utdelte lenker.

  HOSTED_INVITE_SECRET=... HOSTED_PUBLIC_URL=https://wenche... ./.venv/bin/python hosted/mint_invite.py

Uten satte variabler brukes dev-standardene (samme som dev_local.py).
"""
import os

from itsdangerous import URLSafeSerializer

secret = os.getenv("HOSTED_INVITE_SECRET", "dev-invite-secret-bytt-i-prod")
public = os.getenv("HOSTED_PUBLIC_URL", "http://localhost:5173")
token = URLSafeSerializer(secret, salt="invite").dumps("wenche-invite")
print(f"{public}/?invite={token}")
