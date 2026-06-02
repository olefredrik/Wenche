"""FastAPI-backend for self-hosted Wenche. Se `app.lag_app` / `app.kjor`."""
from .app import kjor, lag_app

__all__ = ["lag_app", "kjor"]
