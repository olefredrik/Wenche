"""
Server-konfig for hostet Wenche.

Alle hemmeligheter kommer fra miljøvariabler (i prod: fra KMS/secret manager),
aldri fra koden. Vendor-credentials tilhører operatørselskapet og lastes én gang;
kunde-org kommer per sesjon (ikke herfra).
"""
import os
from functools import lru_cache
from pathlib import Path

from wenche.auth import VendorCredentials


class Settings:
    def __init__(self) -> None:
        # Miljø pinnes til prod i hostet drift; kan settes til test for verifisering.
        self.env: str = os.getenv("WENCHE_ENV", "prod")
        self.session_secret: str = os.getenv(
            "HOSTED_SESSION_SECRET", "dev-secret-bytt-i-prod"
        )
        # Invite-allowlist (e-poster). MVP: komma-separert env-variabel.
        self.allowlist: set[str] = {
            e.strip().lower()
            for e in os.getenv("HOSTED_ALLOWLIST", "").split(",")
            if e.strip()
        }
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("HOSTED_CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        # Magic-link-innlogging
        self.public_url: str = os.getenv("HOSTED_PUBLIC_URL", "http://localhost:8000")
        self.link_max_age_sec: int = int(os.getenv("HOSTED_LINK_MAX_AGE_SEC", "900"))
        self.expose_dev_link: bool = self.env != "prod"
        self.vendor_orgnr = os.getenv("HOSTED_VENDOR_ORGNR")
        self._vendor_client_id = os.getenv("HOSTED_VENDOR_CLIENT_ID")
        self._vendor_kid = os.getenv("HOSTED_VENDOR_KID")
        self._vendor_key_path = os.getenv("HOSTED_VENDOR_KEY_PATH")

    def vendor_credentials(self) -> VendorCredentials | None:
        """
        Operatørens Maskinporten-credentials, eller None hvis ikke konfigurert.

        I prod bør den private nøkkelen hentes fra KMS i stedet for fil.
        """
        if not (self._vendor_client_id and self._vendor_kid and self._vendor_key_path):
            return None
        return VendorCredentials(
            client_id=self._vendor_client_id,
            kid=self._vendor_kid,
            private_key_pem=Path(self._vendor_key_path).read_bytes(),
        )


@lru_cache
def settings() -> Settings:
    return Settings()
