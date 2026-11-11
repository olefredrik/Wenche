"""
Innsending for hostet Wenche: det delte web-laget (`wenche.web.felles.innsending`) med
hostet-auth oppå: invite-vakt, vendor-creds og den økt-bundne kunde-orgen.

- POST /api/innsending/{type}?dry_run=...   -> config sendes i request-body (klienten er
    fasit), ingen server-side lagring av kundedata mellom kall.
    dry_run: lokal bygging/validering, ingen nettverk, ingen disk, ingen binding kreves.
    ekte: vendor-creds + godkjent kunde-org; tokens hentes med kunde-org som systembruker-claim.

Sikkerhet: ekte innsending krever at data-org == godkjent systembruker-org (kunde_org), så vi
aldri sender på vegne av feil org. Personvern: innsendingsdata (inkl. fødselsnummer) lever kun
i minnet i det ene kallet som behandler det, aldri lagret mellom requester.
"""

from fastapi import HTTPException, Request

from wenche import auth as wauth
from wenche.auth import SCOPES, SKD_AKSJONAER_SCOPE, SKD_SKATTEMELDING_SCOPE
from wenche.web.felles import innsending

from .config import settings
from .deps import krev_invitert, krev_kunde_org, krev_vendor


def _sjekk_org(cfg: dict, kunde_org: str) -> None:
    """Hindrer innsending på vegne av en annen org enn den med godkjent systembruker."""
    cfg_org = str((cfg.get("selskap") or {}).get("org_nummer", "")).strip()
    if cfg_org != str(kunde_org):
        raise HTTPException(
            status_code=409,
            detail=f"Data-org ({cfg_org or 'tom'}) matcher ikke godkjent systembruker-org ({kunde_org}).",
        )


def _forbered(request: Request, config: dict) -> str:
    """Før ekte innsending: vendor konfigurert (503), økt bundet (409) og data-org lik bundet org (409)."""
    krev_vendor()
    org = krev_kunde_org(request)
    _sjekk_org(config, org)
    return org


class _VendorTokens:
    """Tokens med operatørens creds og kundens org som systembruker-claim."""

    def altinn(self, org: str) -> str:
        creds, _ = krev_vendor()
        return wauth.hent_tokens_for(creds, org, SCOPES, veksle_altinn=True)["altinn_token"]

    def skd_aksjonaer(self, org: str) -> str:
        creds, _ = krev_vendor()
        return wauth.hent_tokens_for(creds, org, SKD_AKSJONAER_SCOPE)["maskinporten_token"]

    def skd_skattemelding(self, org: str) -> tuple[str, str]:
        creds, _ = krev_vendor()
        tokens = wauth.hent_tokens_for(creds, org, SKD_SKATTEMELDING_SCOPE, veksle_altinn=True)
        return tokens["maskinporten_token"], tokens["altinn_token"]


router = innsending.lag_router(
    tokens=_VendorTokens(),
    env=lambda: settings().env,
    vakt=krev_invitert,
    forbered=_forbered,
)
