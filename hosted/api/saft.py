"""
SAF-T-import for hostet Wenche: det delte laget i `wenche.web.felles.saft`, bak invite-vakten.

Krever gyldig invite, ikke vendor/kunde-org, siden ingenting sendes inn. Personvern: bytene
leses inn i minnet, parses og forkastes. Ingenting skrives til disk eller lagres (sesjonen er
fasit). Behandlingen skjer i EØS. Org-låsen i klienten gjør at SAF-T-ens org ikke endrer
kundeidentitet.
"""

from wenche.web.felles import saft

from .deps import krev_invitert

router = saft.lag_router(vakt=krev_invitert)
