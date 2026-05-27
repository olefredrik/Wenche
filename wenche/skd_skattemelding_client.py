"""
Skatteetaten API-klient for skattemelding (upersonlig/AS).

Innsendingsflyt for AS via Maskinporten:
  1. GET  /api/skattemelding/v2/{år}/{orgnr}          — hent forhåndsutfylt melding
  2. POST /api/skattemelding/v2/valider/{år}/{orgnr}  — valider konvolutten (valgfritt)
  3. POST Altinn3: opprett instans
  4. POST Altinn3: last opp konvolutt (text/xml, ingen anførselstegn i Content-Disposition)
  5. Returner Altinn-inbox-URL der brukeren bekrefter med BankID

Selve bekreftelsessteget kan ikke kjøres av systembrukeren. Skatteetaten
krever personlig pålogging via ID-porten for å bekrefte innsendingen,
bekreftet i SSV-5129 (2026-05-20). Brukeren logger inn i Altinn etter
opplasting og klikker «Send inn» for å fullføre.

Autentisering: Maskinporten-token veksles mot Altinn-token for Altinn3-kallene.
Scope: skatteetaten:formueinntekt/skattemelding, altinn:instances.read/write
"""

from __future__ import annotations

import base64
import binascii
import json
from xml.etree.ElementTree import ParseError, fromstring

import httpx

from wenche.altinn_client import AltinnClient
from wenche.skattemelding_konvolutt import generer_konvolutt

_BASES = {
    "test": "https://api-test.sits.no",
    "prod": "https://api.skatteetaten.no",
}


class SkdSkattemeldingClient:
    """
    Klient for Skatteetatens skattemelding-API (upersonlig/AS).

    Instansieres med et gyldig Maskinporten-token. For Altinn3-operasjoner
    trengs i tillegg et Altinn-token (oppnås via auth.veksle_til_altinn_token).
    """

    def __init__(self, maskinporten_token: str, env: str = "prod"):
        if env not in _BASES:
            raise ValueError(f"Ugyldig env: {env!r}. Bruk 'prod' eller 'test'.")
        self._base = _BASES[env]
        self._env = env
        self._token = maskinporten_token
        self._http = httpx.Client(
            headers={
                "Authorization": f"Bearer {maskinporten_token}",
                "Accept": "application/json",
            },
            timeout=60,
        )

    def hent_forhåndsutfylt(self, inntektsaar: int, orgnr: str) -> bytes:
        """
        Henter forhåndsutfylt skattemelding fra Skatteetaten.

        Returnerer rå XML-bytes (skattemeldingUpersonlig v5).
        Inneholder partsnummer som trengs for innsending — bruk
        skattemelding_xml.hent_partsnummer() for å hente det ut.

        API-et returnerer en wrapper-XML med base64-kodet innhold i <content>.
        Denne metoden dekoder automatisk hvis wrapper-format oppdages.
        For å hente ID-en på forhåndsutfylt-dokumentet (kreves for
        dokumentreferanseTilGjeldendeDokument i innsending), bruk
        hent_forhåndsutfylt_med_id() i stedet.
        """
        xml, _ = self.hent_forhåndsutfylt_med_id(inntektsaar, orgnr)
        return xml

    def hent_forhåndsutfylt_med_id(
        self, inntektsaar: int, orgnr: str
    ) -> tuple[bytes, str | None]:
        """
        Henter forhåndsutfylt skattemelding og dens dokument-ID.

        Returnerer (skattemelding_xml, dokument_id). Dokument-ID-en er
        identifikatoren Skatteetaten genererer for forhåndsutfylt-dokumentet.
        Inkluderes som dokumentreferanseTilGjeldendeDokument i konvolutten
        ved innsending, slik at Skatteetaten kan koble innsendingen til
        det opprinnelige dokumentet (visning-API-et bruker dette feltet).

        dokument_id er None hvis responsen ikke følger forventet wrapper-format.
        """
        url = f"{self._base}/api/skattemelding/v2/{inntektsaar}/{orgnr}"
        resp = self._http.get(url, headers={"Accept": "application/xml"})
        if not resp.is_success:
            raise RuntimeError(
                f"Feil ved henting av forhåndsutfylt skattemelding: "
                f"{resp.status_code}\n{resp.text}"
            )
        raw = resp.content

        try:
            root = fromstring(raw)
            ns = (
                "no:skatteetaten:fastsetting:formueinntekt:"
                "skattemeldingognaeringsspesifikasjon:forespoersel:response:v2"
            )
            dok_el = root.find(f".//{{{ns}}}skattemeldingdokument")
            if dok_el is None:
                # Fallback: tolerér ukjent eller endret namespace
                dok_el = root.find(".//{*}skattemeldingdokument")
            if dok_el is not None:
                content_el = dok_el.find(f"{{{ns}}}content")
                if content_el is None:
                    content_el = dok_el.find("{*}content")
                id_el = dok_el.find(f"{{{ns}}}id")
                if id_el is None:
                    id_el = dok_el.find("{*}id")
                if content_el is not None and content_el.text:
                    dok_id = id_el.text.strip() if id_el is not None and id_el.text else None
                    return base64.b64decode(content_el.text), dok_id
        except (ParseError, binascii.Error):
            pass

        return raw, None

    def valider(
        self,
        inntektsaar: int,
        orgnr: str,
        konvolutt: bytes,
    ) -> dict:
        """
        Validerer skattemelding-konvolutten mot Skatteetatens API.

        Returnerer et strukturert valideringsresultat:
            {
                "resultat": "validertOK" | "validertMedFeil" | ...,
                "aarsak": str | None,
                "avvik_ved_validering": [ {avvikstype, sti, ...}, ... ],
                "avvik_etter_beregning": [ ... ],
                "veiledning": [ {veiledningstype, hjelpetekst, ...}, ... ],
            }

        Validering lagrer ikke data hos Skatteetaten — det er ikke en innsending.

        NB: endepunktet svarer kun med application/xml. Accept: application/json
        gir HTTP 406.
        """
        url = f"{self._base}/api/skattemelding/v2/valider/{inntektsaar}/{orgnr}"
        resp = self._http.post(
            url,
            content=konvolutt,
            headers={"Content-Type": "application/xml", "Accept": "application/xml"},
        )
        if not resp.is_success:
            raise RuntimeError(
                f"Valideringsfeil: {resp.status_code}\n{resp.text}"
            )
        return _parse_valideringsrespons(resp.content)

    def send(
        self,
        inntektsaar: int,
        orgnr: str,
        skattemelding_xml: bytes,
        altinn_token: str,
        naeringsspesifikasjon_xml: bytes | None = None,
        gjeldende_dokument_id: str | None = None,
    ) -> str:
        """
        Klargjør skattemelding for innsending via Altinn3.

        Flyt:
          1. Generer konvolutt
          2. Opprett Altinn3-instans
          3. Sett inntektsaar i Skattemeldingsapp_v2
          4. Last opp konvolutt
          5. Returner Altinn-inbox-URL

        Brukeren må deretter logge inn i Altinn med BankID og klikke
        «Send inn» for å fullføre. Selve bekreftelsessteget kan ikke
        kjøres av systembrukeren (SSV-5129, 2026-05-20).

        Args:
            skattemelding_xml:        XML fra generer_skattemelding_upersonlig().
            altinn_token:             Token fra auth.get_skd_skattemelding_tokens().
            naeringsspesifikasjon_xml: Valgfri næringsoppgave-XML.

        Returns:
            URL til Altinn-inboksen der brukeren fullfører innsendingen.
        """
        konvolutt = generer_konvolutt(
            skattemelding_xml=skattemelding_xml,
            inntektsaar=inntektsaar,
            orgnr=orgnr,
            naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
            gjeldende_dokument_id=gjeldende_dokument_id,
        )

        with AltinnClient(altinn_token, env=self._env) as altinn:
            print("Oppretter Altinn3-instans...")
            instans = altinn.opprett_instans("skattemelding", orgnr)

            print("Setter inntektsaar i Skattemeldingsapp_v2-modellen...")
            altinn.oppdater_data_element(
                "skattemelding",
                instans,
                "Skattemeldingsapp_v2",
                json.dumps({"inntektsaar": inntektsaar}).encode(),
                "application/json",
            )

            print("Laster opp skattemelding-konvolutt...")
            altinn.last_opp_skattemelding_data(instans, konvolutt)

            # Avanser ett prosesssteg slik at instansen havner i bekreftelses-
            # tasken og dukker opp som en oppgave i brukerens Altinn-innboks.
            # Selve bekreftelsen (siste prosesssteg) gjøres av brukeren via
            # BankID i Altinn-UI — det kan ikke kjøres av systembrukeren
            # (SSV-5129, 2026-05-20).
            return altinn.fullfoor_instans("skattemelding", instans)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _tekst(el, tag: str) -> str | None:
    """Henter teksten i barneelementet `tag` (namespace-agnostisk)."""
    funnet = el.findtext(f"{{*}}{tag}")
    return funnet.strip() if funnet else None


def _avvik_liste(root, container_tag: str) -> list[dict]:
    avvik = []
    container = root.find(f"{{*}}{container_tag}")
    if container is None:
        return avvik
    for a in container.findall("{*}avvik"):
        avvik.append(
            {
                "avvikstype": _tekst(a, "avvikstype"),
                "sti": _tekst(a, "sti"),
                "oevrigInformasjon": _tekst(a, "oevrigInformasjon"),
                "mottattVerdi": _tekst(a, "mottattVerdi"),
                "beregnetVerdi": _tekst(a, "beregnetVerdi"),
                "forekomstidentifikator": _tekst(a, "forekomstidentifikator"),
            }
        )
    return avvik


def _parse_valideringsrespons(raw: bytes) -> dict:
    """Parser Skatteetatens valider-respons (XML) til en strukturert dict."""
    root = fromstring(raw)
    veiledning = []
    cont = root.find("{*}veiledningEtterKontroll")
    if cont is not None:
        for v in cont.findall("{*}veiledning"):
            veiledning.append(
                {
                    "veiledningstype": _tekst(v, "veiledningstype"),
                    "hjelpetekst": _tekst(v, "hjelpetekst"),
                    "betjeningsstrategi": _tekst(v, "betjeningsstrategi"),
                }
            )
    return {
        "resultat": _tekst(root, "resultatAvValidering"),
        "aarsak": _tekst(root, "aarsakTilValidertMedFeil"),
        "avvik_ved_validering": _avvik_liste(root, "avvikVedValidering"),
        "avvik_etter_beregning": _avvik_liste(root, "avvikEtterBeregning"),
        "veiledning": veiledning,
    }


def formater_valideringsresultat(res: dict) -> str:
    """Formaterer et valideringsresultat fra valider() til lesbar tekst."""
    linjer = [f"resultatAvValidering: {res.get('resultat')}"]
    if res.get("aarsak"):
        linjer.append(f"aarsak: {res['aarsak']}")

    blokkerende = res.get("avvik_ved_validering") or []
    if blokkerende:
        linjer.append(f"\nBlokkerende avvik ({len(blokkerende)}):")
        for a in blokkerende:
            detalj = a.get("oevrigInformasjon") or a.get("sti") or ""
            linjer.append(f"  - {a.get('avvikstype')}: {detalj}".rstrip(": "))

    etter = res.get("avvik_etter_beregning") or []
    if etter:
        linjer.append(f"\nAvvik etter beregning ({len(etter)}, ikke-blokkerende):")
        for a in etter:
            linjer.append(
                f"  - {a.get('avvikstype')} @ {a.get('sti')}"
                + (f" (beregnet={a['beregnetVerdi']})" if a.get("beregnetVerdi") else "")
            )

    veil = res.get("veiledning") or []
    if veil:
        linjer.append(f"\nVeiledning/merknader ({len(veil)}):")
        for v in veil:
            linjer.append(f"  - {v.get('veiledningstype')}: {v.get('hjelpetekst')}")

    return "\n".join(linjer)


def bygg_og_valider_konvolutt(
    skattemelding_xml: bytes,
    inntektsaar: int,
    orgnr: str,
    naeringsspesifikasjon_xml: bytes | None = None,
) -> bytes:
    """
    Hjelpefunksjon: bygger konvolutten uten å sende den.

    Nyttig for lokal testing og for å inspisere XML-strukturen
    før API-tilgang er på plass.
    """
    return generer_konvolutt(
        skattemelding_xml=skattemelding_xml,
        inntektsaar=inntektsaar,
        orgnr=orgnr,
        naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
    )
