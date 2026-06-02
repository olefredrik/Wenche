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

# Dev-standarder som ligger i åpen kildekode. De er KUN for lokal dev (WENCHE_ENV=test).
# I prod fail-closes vi hvis de ikke er overstyrt, ellers kunne hvem som helst som leser
# repoet lage gyldige invite-lenker og forfalske sesjonscookies.
_DEV_SESSION_SECRET = "dev-secret-bytt-i-prod"
_DEV_INVITE_SECRET = "dev-invite-secret-bytt-i-prod"


class Settings:
    def __init__(self) -> None:
        # Miljø pinnes til prod i hostet drift; kan settes til test for verifisering.
        self.env: str = os.getenv("WENCHE_ENV", "prod")
        # Signering av sesjonscookie.
        self.session_secret: str = os.getenv("HOSTED_SESSION_SECRET", _DEV_SESSION_SECRET)
        # Invite-only: signert invite-lenke. Roter ved å bytte denne (ugyldiggjør
        # alle utdelte lenker).
        self.invite_secret: str = os.getenv("HOSTED_INVITE_SECRET", _DEV_INVITE_SECRET)
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("HOSTED_CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        # Brukes til å bygge invite-lenken (peker på app-en der invitten løses inn).
        self.public_url: str = os.getenv("HOSTED_PUBLIC_URL", "http://localhost:5173")
        # Demo-modus: viser en «dette er en demo mot tt02»-banner i SPA-en. Rent informativt,
        # endrer ikke funksjonalitet. Settes kun på demo-appen (aldri i prod).
        self.demo_mode: bool = os.getenv("HOSTED_DEMO_MODE", "").lower() in ("1", "true", "yes")
        self.vendor_orgnr = os.getenv("HOSTED_VENDOR_ORGNR")
        self._vendor_client_id = os.getenv("HOSTED_VENDOR_CLIENT_ID")
        self._vendor_kid = os.getenv("HOSTED_VENDOR_KID")
        # Privat nøkkel: enten som PEM-innhold rett i en env-variabel (foretrukket i
        # container/Fly, holder nøkkelen unna disk), eller som sti til en PEM-fil (dev).
        self._vendor_key_pem = os.getenv("HOSTED_VENDOR_KEY_PEM")
        self._vendor_key_path = os.getenv("HOSTED_VENDOR_KEY_PATH")
        self._fail_closed_i_prod()

    def _fail_closed_i_prod(self) -> None:
        """Nekt oppstart i prod hvis hemmelighetene ikke er overstyrt fra dev-standardene."""
        if self.env != "prod":
            return
        usikre = [
            navn
            for navn, verdi, dev in (
                ("HOSTED_SESSION_SECRET", self.session_secret, _DEV_SESSION_SECRET),
                ("HOSTED_INVITE_SECRET", self.invite_secret, _DEV_INVITE_SECRET),
            )
            if not verdi or verdi == dev
        ]
        if usikre:
            raise RuntimeError(
                "Hostet Wenche kjører i prod uten egne hemmeligheter: "
                + ", ".join(usikre)
                + ". Sett dem fra secret manager/KMS før oppstart. Dev-standardene "
                "ligger i åpen kildekode og ville latt hvem som helst lage gyldige "
                "invite-lenker og forfalske sesjonscookies."
            )

    def vendor_credentials(self) -> VendorCredentials | None:
        """
        Operatørens Maskinporten-credentials, eller None hvis ikke konfigurert.

        Nøkkelen tas fra HOSTED_VENDOR_KEY_PEM (PEM-innhold, foretrukket i prod/container,
        f.eks. fra KMS/Fly-secret) eller HOSTED_VENDOR_KEY_PATH (fil, dev).
        """
        if not (self._vendor_client_id and self._vendor_kid):
            return None
        if self._vendor_key_pem:
            pem = self._vendor_key_pem.encode()
        elif self._vendor_key_path:
            pem = Path(self._vendor_key_path).read_bytes()
        else:
            return None
        return VendorCredentials(
            client_id=self._vendor_client_id,
            kid=self._vendor_kid,
            private_key_pem=pem,
        )


@lru_cache
def settings() -> Settings:
    return Settings()
