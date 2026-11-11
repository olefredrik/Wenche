"""
Innsending for self-hosted Wenche: det delte web-laget (`wenche.web.felles.innsending`) med
lokal auth: brukerens egen Maskinporten-innlogging (egen RSA-nøkkel), ingen vendor/invite.
I testmiljø byttes selskapets org til Tenor-orgen (miljo.med_test_org) før alt annet, så hele
kjeden bruker orgen systembrukeren er godkjent for.
"""

from __future__ import annotations

from wenche import auth
from wenche.web.felles import innsending

from . import miljo


class _LokaleTokens:
    """Tokens fra brukerens egne credentials i ~/.wenche/.env (org følger av miljøet)."""

    def altinn(self, org: str) -> str:
        return auth.get_altinn_token()

    def skd_aksjonaer(self, org: str) -> str:
        return auth.get_skd_aksjonaer_token()

    def skd_skattemelding(self, org: str) -> tuple[str, str]:
        tokens = auth.get_skd_skattemelding_tokens()
        return tokens["maskinporten_token"], tokens["altinn_token"]


def hint_403() -> str | None:
    """I testmiljø er en 403 nesten alltid org-mismatch mot systembrukeren; si det."""
    return innsending.TENOR_HINT if miljo.er_test() else None


router = innsending.lag_router(
    tokens=_LokaleTokens(),
    env=miljo.aktiv_env,
    transform=miljo.med_test_org,
    hint_403=hint_403,
)
