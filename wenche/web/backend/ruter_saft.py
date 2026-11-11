"""
SAF-T-import for self-hosted Wenche: det delte laget i `wenche.web.felles.saft`. Ingen
invite/auth lokalt; vakten mot fremmede nettsteder ligger som middleware (vakt.py).
"""

from wenche.web.felles import saft

router = saft.lag_router()
