"""
Web-laget hostet og self-hosted deler.

Begge backendene (hosted/api og wenche/web/backend) er tynne skall rundt det samme: config i
request-body, lokal dokumentgenerering, SAF-T-import og innsending via `wenche.innsending`.
Det som skiller dem er auth (invite + vendor-creds mot brukerens egen Maskinporten-innlogging)
og test-org-byttet i self-hosted. Rutefabrikkene her tar nettopp det som parametre, så hver
regel finnes ett sted:

- `dokumenter.lag_router(vakt=..., transform=...)`
- `saft.lag_router(vakt=...)`
- `innsending.lag_router(tokens=..., env=..., vakt=..., transform=..., forbered=..., hint_403=...)`
- `kropp.Kroppsgrense`: størrelsesgrense på request-kropper, før noe parses
- `svar`: pydantic-modellene for svarene (kontrakten mot SPA-ene)
"""
