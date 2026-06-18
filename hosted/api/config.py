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
        # Kontaktvei som vises når ID-porten-rollesjekken ikke gir treff (skjermet person,
        # navneavvik, selskap uten registrert rolleinnehaver) og som operatør-fallback.
        # mailto:- eller https-URL.
        self.kontakt: str = os.getenv("HOSTED_KONTAKT", "mailto:hello@olefredrik.com")
        self.vendor_orgnr = os.getenv("HOSTED_VENDOR_ORGNR")
        self._vendor_client_id = os.getenv("HOSTED_VENDOR_CLIENT_ID")
        self._vendor_kid = os.getenv("HOSTED_VENDOR_KID")
        # Privat nøkkel: enten som PEM-innhold rett i en env-variabel (foretrukket i
        # container/Fly, holder nøkkelen unna disk), eller som sti til en PEM-fil (dev).
        self._vendor_key_pem = os.getenv("HOSTED_VENDOR_KEY_PEM")
        self._vendor_key_path = os.getenv("HOSTED_VENDOR_KEY_PATH")
        # ID-porten-innlogging (OIDC). Primær onboarding-port i prod: brukeren logger inn med
        # BankID, og vi får et verifisert navn (+ fødselsnummer som transient `pid`) som
        # rollesjekken mot Enhetsregisteret bygger på. Utelates config (som på demo), er
        # ID-porten av og invite-lenken er eneste port. Samme nøkkelmønster som vendor-creds.
        self._idporten_client_id = os.getenv("HOSTED_IDPORTEN_CLIENT_ID")
        self._idporten_kid = os.getenv("HOSTED_IDPORTEN_KID")
        self._idporten_key_pem = os.getenv("HOSTED_IDPORTEN_KEY_PEM")
        self._idporten_key_path = os.getenv("HOSTED_IDPORTEN_KEY_PATH")
        self.idporten_redirect_uri = os.getenv("HOSTED_IDPORTEN_REDIRECT_URI")
        # Be om Altinn-scopet altinn:accessmanagement/authorizedparties (for å hente selskapslista fra autoriserte parter)
        # KUN når operatøren har fått scopet tildelt klienten i Samarbeidsportalen. Ber vi om et
        # ikke-tildelt scope, avviser ID-porten hele innloggingen (invalid_scope). Av som standard:
        # da logger man inn med bare openid+profile, og selskap velges ved manuell orgnr-inntasting.
        self._idporten_reportees = os.getenv("HOSTED_IDPORTEN_REPORTEES", "").lower() in (
            "1", "true", "yes",
        )
        self._fail_closed_i_prod()

    @property
    def kontakt_tekst(self) -> str:
        """Kontaktverdien uten URL-skjema, for innfelling i ren tekst. `kontakt` lagres med
        skjema (mailto:/https://) fordi den brukes som href; skjemaet skal ikke leses av en
        bruker. Speiler KontaktLenke i frontend."""
        if self.kontakt.startswith("mailto:"):
            return self.kontakt[len("mailto:") :]
        return self.kontakt.removeprefix("https://").removeprefix("http://")

    @property
    def idporten_client_id(self) -> str | None:
        return self._idporten_client_id

    @property
    def idporten_reportees(self) -> bool:
        """
        Om vi skal be om altinn:accessmanagement/authorizedparties og tilby selskapsvalg fra Altinn autoriserte parter.

        Krever at ID-porten er aktivert og at scopet faktisk er tildelt klienten (env-flagget
        settes da av operatøren). Er det av, hoppes auto-lista over og brukeren taster orgnr selv.
        """
        return self.idporten_aktivert and self._idporten_reportees

    @property
    def idporten_aktivert(self) -> bool:
        """
        Om ID-porten-innlogging er konfigurert (og dermed primær port).

        Krever client-ID, nøkkel-ID, en privat nøkkel (PEM eller filsti) og redirect-URI.
        Mangler alt, er ID-porten av og invite-lenken er eneste port (slik demo kjører).
        """
        return bool(
            self._idporten_client_id
            and self._idporten_kid
            and (self._idporten_key_pem or self._idporten_key_path)
            and self.idporten_redirect_uri
        )

    @property
    def idporten_kid(self) -> str | None:
        return self._idporten_kid

    def idporten_key(self) -> bytes | None:
        """Privat ID-porten-nøkkel (client_assertion), fra PEM-env eller filsti. None om ukonfigurert."""
        if self._idporten_key_pem:
            return self._idporten_key_pem.encode()
        if self._idporten_key_path:
            return Path(self._idporten_key_path).read_bytes()
        return None

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
        # Delvis ID-porten-config i prod er nesten alltid en feil (glemt secret), og en
        # halvkonfigurert OIDC-klient feiler stille ved innlogging. Krev enten alt eller intet.
        idp = {
            "HOSTED_IDPORTEN_CLIENT_ID": self._idporten_client_id,
            "HOSTED_IDPORTEN_KID": self._idporten_kid,
            "HOSTED_IDPORTEN_KEY_PEM/_PATH": self._idporten_key_pem or self._idporten_key_path,
            "HOSTED_IDPORTEN_REDIRECT_URI": self.idporten_redirect_uri,
        }
        satt = {k for k, v in idp.items() if v}
        if satt and satt != set(idp):
            mangler = ", ".join(sorted(set(idp) - satt))
            raise RuntimeError(
                "Hostet Wenche har delvis ID-porten-config i prod. Mangler: "
                + mangler
                + ". Sett alle eller ingen (uten = invite-only)."
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
