"""
Feiltypene Wenche selv melder, med struktur i stedet for tekst.

Før bar klientene feil som `RuntimeError(f"{status}\\n{svarkropp}")`, og mottakerne måtte tolke
teksten: regex på «Maskinporten svarte», `"AUTH-00004" in str(e)` og `str(e).split("\\n")[0]`
for å holde svarkroppen unna brukeren. Her får hver feil felt kalleren kan lese direkte.
Svarkroppen følger med i `kropp` til loggen, men aldri i meldingen.

- WencheFeil          basis. Arver RuntimeError, så eldre kallsteder med `except RuntimeError`
                      fortsetter å virke.
  - KonfigFeil        config eller oppsett: manglende felt, ugyldig verdi, manglende credentials.
                      Brukeren kan rette det selv.
  - ValideringsFeil   blokkerende valideringsfeil funnet lokalt før innsending. Bærer listen.
  - MyndighetsFeil    et kall mot Altinn, Skatteetaten, Maskinporten eller Enhetsregisteret
                      feilet: tjeneste, steg, status, kode, kropp, url.
    - AuthFeil        Maskinporten avviste innloggingen: kode og beskrivelse fra svaret.
"""

from __future__ import annotations

import json
import re

import httpx

TJENESTENAVN = {
    "altinn": "Altinn",
    "skatteetaten": "Skatteetaten",
    "maskinporten": "Maskinporten",
    "brreg": "Enhetsregisteret",
}

# Feilkoder myndighetene bruker i svarkropper, f.eks. AUTH-00004 (Altinn) og MP-100 (Maskinporten).
_KODEMONSTER = re.compile(r"\b[A-Z]{2,6}-\d{3,6}\b")

# Koden for «fikk ikke svar»: tidsavbrudd, brutt forbindelse, DNS-feil.
NETTVERK = "nettverk"

# Feilkoder brukeren kan gjøre noe med, eller som ellers ser ut som en feil i Wenche. Teksten
# legges til i meldingen (CLI og web) ved siden av steg og status.
KJENTE_KODER: dict[str, str] = {
    # Altinn avviser en ny systembruker-forespørsel når selskapet allerede har en systembruker
    # for systemet (verifisert i tt02).
    "AUTH-00004": (
        "Selskapet har allerede en systembruker for Wenche i Altinn, så det trengs ingen ny "
        "forespørsel."
    ),
}


class WencheFeil(RuntimeError):
    """Basisklasse for feil Wenche selv melder (ikke programmeringsfeil)."""


class KonfigFeil(WencheFeil):
    """Feil i config eller oppsett som brukeren kan rette selv."""

    def __init__(self, melding: str, *, felt: str | None = None) -> None:
        super().__init__(melding)
        self.felt = felt


class ValideringsFeil(WencheFeil):
    """Blokkerende valideringsfeil oppdaget lokalt før innsending. Bærer feillisten."""

    def __init__(self, feil: list[str]) -> None:
        self.feil = list(feil)
        super().__init__("; ".join(self.feil))


class MyndighetsFeil(WencheFeil):
    """
    Et kall mot en myndighet feilet.

    `steg` er det kalleren forsøkte, i brukerens språk («oppretting av innsending i Altinn»),
    `status` HTTP-koden (None ved nettverksfeil), `kode` tjenestens egen feilkode når den
    finnes i svaret, og `kropp` den rå svarkroppen, som logges men aldri vises.
    """

    def __init__(
        self,
        tjeneste: str,
        steg: str,
        *,
        status: int | None = None,
        kode: str | None = None,
        kropp: str | None = None,
        url: str | None = None,
        beskrivelse: str | None = None,
    ) -> None:
        self.tjeneste = tjeneste
        self.steg = steg
        self.status = status
        self.kode = kode
        self.kropp = kropp
        self.url = url
        self.beskrivelse = beskrivelse
        super().__init__(self.melding)

    @property
    def navn(self) -> str:
        return TJENESTENAVN.get(self.tjeneste, self.tjeneste)

    @property
    def melding(self) -> str:
        """Lesbar melding uten svarkropp: tjeneste, steg, status og kode."""
        hva = f"{self.steg} feilet" if self.steg else "kallet feilet"
        if self.kode == NETTVERK:
            tekst = f"{self.navn}: {hva} (nettverksfeil eller tidsavbrudd)"
        elif self.status is not None:
            kode = f", {self.kode}" if self.kode else ""
            tekst = f"{self.navn}: {hva} (HTTP {self.status}{kode})"
        else:
            kode = f" ({self.kode})" if self.kode else ""
            tekst = f"{self.navn}: {hva}{kode}"
        if self.beskrivelse:
            tekst += f". {self.beskrivelse}"
        if self.kode in KJENTE_KODER:
            tekst += f". {KJENTE_KODER[self.kode]}"
        return tekst

    @classmethod
    def fra_svar(
        cls, tjeneste: str, steg: str, resp: httpx.Response, *, beskrivelse: str | None = None
    ) -> MyndighetsFeil:
        """Feil fra et HTTP-svar: status fra svaret, kode plukket ut av kroppen hvis den finnes."""
        kropp = resp.text
        return cls(
            tjeneste,
            steg,
            status=resp.status_code,
            kode=finn_feilkode(kropp),
            kropp=kropp,
            url=url_fra_svar(resp),
            beskrivelse=beskrivelse,
        )

    @classmethod
    def fra_nettverksfeil(
        cls, tjeneste: str, steg: str, feil: httpx.RequestError
    ) -> MyndighetsFeil:
        """Feil uten HTTP-svar: tidsavbrudd, brutt forbindelse, DNS-feil."""
        return cls(
            tjeneste,
            steg,
            kode=NETTVERK,
            kropp=f"{type(feil).__name__}: {feil}",
            url=url_fra_unntak(feil),
        )


class AuthFeil(MyndighetsFeil):
    """Maskinporten avviste innloggingen. `kode` er OAuth-feilkoden (invalid_grant, ...)."""

    def __init__(
        self,
        *,
        status: int | None = None,
        kode: str | None = None,
        beskrivelse: str | None = None,
        kropp: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(
            "maskinporten",
            "innlogging mot Maskinporten",
            status=status,
            kode=kode,
            kropp=kropp,
            url=url,
            beskrivelse=beskrivelse,
        )

    @property
    def melding(self) -> str:
        tekst = "Maskinporten avviste innloggingen"
        if self.status is not None:
            kode = f", {self.kode}" if self.kode else ""
            tekst += f" (HTTP {self.status}{kode})"
        elif self.kode:
            tekst += f" ({self.kode})"
        if self.beskrivelse:
            tekst += f": {self.beskrivelse}"
        return tekst

    @classmethod
    def fra_maskinporten_svar(cls, resp: httpx.Response) -> AuthFeil:
        """Maskinportens feilsvar er JSON med `error` og `error_description` (RFC 6749)."""
        kropp = resp.text
        kode: str | None = None
        beskrivelse: str | None = None
        try:
            data = json.loads(kropp)
        except ValueError:
            data = None
        if isinstance(data, dict):
            kode = str(data.get("error") or "") or None
            beskrivelse = str(data.get("error_description") or "") or None
        return cls(
            status=resp.status_code,
            kode=kode or finn_feilkode(kropp),
            beskrivelse=beskrivelse,
            kropp=kropp,
            url=url_fra_svar(resp),
        )


def finn_feilkode(kropp: str | None) -> str | None:
    """Tjenestens feilkode fra en svarkropp: JSON-feltene code/kode/errorCode/error, ellers et
    mønster som AUTH-00004 i teksten. None når ingen kode finnes."""
    if not kropp:
        return None
    try:
        data = json.loads(kropp)
    except ValueError:
        data = None
    if isinstance(data, dict):
        for nokkel in ("code", "kode", "errorCode", "error"):
            verdi = data.get(nokkel)
            if isinstance(verdi, str) and verdi.strip():
                return verdi.strip()
    treff = _KODEMONSTER.search(kropp)
    return treff.group(0) if treff else None


def url_fra_svar(resp: httpx.Response) -> str | None:
    try:
        return str(resp.request.url)
    except RuntimeError:  # httpx: svar uten request
        return None


def url_fra_unntak(feil: Exception) -> str | None:
    """URL-en fra en httpx-feil, trygt: `.request` kaster RuntimeError når den ikke er satt."""
    try:
        return str(feil.request.url)  # type: ignore[attr-defined]
    except (RuntimeError, AttributeError):
        return None


def brukermelding(e: MyndighetsFeil) -> str:
    """
    Meldingen sluttbrukeren ser når en innsending stopper hos en myndighet.

    Navngir steget og statuskoden, så et skjermbilde fra brukeren alene peker på riktig sted,
    men aldri svarkroppen (den kan inneholde interne detaljer og logges i stedet).
    """
    if isinstance(e, AuthFeil):
        return e.melding
    hvor = f" under {e.steg}" if e.steg else ""
    if e.kode == NETTVERK:
        return (
            f"Fikk ikke fullført forespørselen mot {e.navn}{hvor} (nettverksfeil eller "
            "tidsavbrudd). Det er som regel midlertidig. Sjekk i Altinn eller hos Skatteetaten "
            "før du prøver på nytt, i tilfelle forespørselen likevel gikk gjennom."
        )
    status = e.status
    if status == 403:
        tekst = (
            f"Tilgangen ble avslått (HTTP 403){hvor}. Vanligste årsak: systembrukeren er ikke "
            "lenger godkjent for selskapet, eller tjenesten mangler nødvendig rettighet."
        )
    elif status == 401:
        tekst = (
            f"Tokenet ble avvist (HTTP 401){hvor}. Prøv igjen, eller koble systembrukeren på nytt."
        )
    elif status is not None and status >= 500:
        tekst = (
            f"{e.navn} svarte med en serverfeil (HTTP {status}){hvor}. Dette er som regel "
            "midlertidig hos myndighetene. Ingenting er sendt inn. Prøv igjen om litt."
        )
    elif status is not None:
        kode = f", {e.kode}" if e.kode else ""
        tekst = (
            f"{e.navn} avviste forespørselen (HTTP {status}{kode}){hvor}. Ingenting er sendt "
            "inn. Detaljene er logget; prøv igjen eller ta kontakt."
        )
    else:
        tekst = f"{e.navn}: {e.steg or 'kallet'} feilet. Ingenting er sendt inn."
    if e.beskrivelse:
        tekst += f" {e.beskrivelse}"
    if e.kode in KJENTE_KODER:
        tekst += f" {KJENTE_KODER[e.kode]}"
    return tekst
