"""Self-hosted webgrensesnitt for Wenche (FastAPI + React/Tailwind SPA).

Erstatter det tidligere NiceGUI-laget. Backend-en (`backend/`) gjenbruker domene-, auth- og
klientlaget i `wenche`-pakken; den bygde SPA-en serveres fra `static/` på samme origin.
"""
