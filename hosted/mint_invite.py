"""
Skriv ut Wenches per-org invite-lenke. Del den ut manuelt til en kjent, verifisert person
(e-post, Signal, ...). Lenken er knyttet til ETT organisasjonsnummer, så mottakeren kan
kun koble og sende inn for det selskapet. Roter ved å bytte HOSTED_INVITE_SECRET, det
ugyldiggjør alle tidligere utdelte lenker.

  HOSTED_INVITE_SECRET=... HOSTED_PUBLIC_URL=https://wenche... \
      ./.venv/bin/python hosted/mint_invite.py <orgnr>

Begge variablene må være satt. På Fly-maskinen er de det alt (secrets), så kjør skriptet der
(`flyctl ssh console`). Uten dem stopper skriptet i stedet for å falle stille tilbake til
dev-verdiene, som ville gitt en lenke prod avviser.
"""

import os
import sys
from pathlib import Path

# Kjøres som `python hosted/mint_invite.py`, så repo-roten (der `hosted`-pakken ligger) må på
# stien selv; sys.path[0] er skriptets egen mappe.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hosted.api.auth import lag_invite_token  # noqa: E402

if len(sys.argv) < 2 or not sys.argv[1].strip():
    raise SystemExit("Bruk: python hosted/mint_invite.py <orgnr>")

org = sys.argv[1].strip()
secret = os.environ.get("HOSTED_INVITE_SECRET", "")
public = os.environ.get("HOSTED_PUBLIC_URL", "")
if not secret or not public:
    raise SystemExit(
        "Sett HOSTED_INVITE_SECRET og HOSTED_PUBLIC_URL (samme verdier som appen kjører med). "
        "Lokalt mot dev_local.py: bruk verdiene den setter."
    )
# Fragment (#), ikke query (?): fragmentet sendes aldri til serveren, så tokenet havner ikke i
# noen access-logg. Eldre lenker med ?invite= godtas fortsatt av SPA-en.
print(f"{public.rstrip('/')}/#invite={lag_invite_token(org, secret=secret)}")
