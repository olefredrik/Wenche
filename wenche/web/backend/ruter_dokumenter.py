"""
Dokumentgenerering for self-hosted Wenche: det delte laget i `wenche.web.felles.dokumenter`,
med test-org-byttet (miljo.med_test_org) foran. Genererer lokalt, sender ingenting. Vakten mot
fremmede nettsteder ligger som middleware (vakt.py), så ruteren trenger ingen egen.
"""

from wenche.web.felles import dokumenter

from . import miljo

router = dokumenter.lag_router(transform=miljo.med_test_org)
