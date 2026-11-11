"""
Dokumentgenerering for hostet Wenche: det delte laget i `wenche.web.felles.dokumenter`, bak
invite-vakten.

Genererer lokalt fra config-en i request-body (akkurat som innsending dry-run): ingen nettverk,
ingenting lagres mellom kall. Krever kun gyldig invite, ikke vendor/kunde-org, siden ingenting
sendes inn.
"""

from wenche.web.felles import dokumenter

from .deps import krev_invitert

router = dokumenter.lag_router(vakt=krev_invitert)
