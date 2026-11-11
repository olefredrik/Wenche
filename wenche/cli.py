"""
Wenche, kommandolinjegrensesnitt.

Bruk:
  wenche                             Starter webgrensesnittet mot produksjon
  wenche dev                         Starter webgrensesnittet mot testmiljøet (tt02)
  wenche login / logout
  wenche registrer-system
  wenche opprett-systembruker [--org ORGNR]
  wenche valider-aarsregnskap [--config config.yaml]
  wenche send-aarsregnskap [--config config.yaml] [--dry-run] [--ut-mappe MAPPE]
  wenche send-aksjonaerregister [--config config.yaml] [--dry-run] [--ut-mappe MAPPE]
  wenche generer-skattemelding [--config config.yaml] [--ut skattemelding.txt]
  wenche valider-skattemelding [--config config.yaml]
  wenche send-skattemelding [--config config.yaml] [--dry-run] [--ut-mappe MAPPE]
  wenche importer-saft SAF-T-FIL [--ut config.yaml] [--overskriv]

Feil Wenche selv melder (WencheFeil fra wenche.feil) blir én lesbar melding på stderr og
exit-kode 1; valideringsfeil listes opp. Fremdrift fra kjernen logges til stderr, så stdout er
ren (generer-skattemelding skriver sammendraget dit).
"""

import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import click
import yaml

from wenche import (
    __version__,
    aarsregnskap,
    aksjonaerregister,
    auth,
    configfelt,
    miljoer,
    skattemelding,
    systembruker,
)
from wenche import innsending as tjeneste
from wenche import skd_skattemelding_client as skd_modul
from wenche.altinn_client import AltinnClient
from wenche.feil import KonfigFeil, ValideringsFeil, WencheFeil
from wenche.filer import skriv_privat
from wenche.skattemelding_konvolutt import generer_konvolutt
from wenche.skd_client import SkdAksjonaerClient

T = TypeVar("T")

_MANGLER_CONFIG = "Kopier config.example.yaml til config.yaml og fyll inn dine verdier."
_TRYGGE_TEGN = re.compile(r"[^A-Za-z0-9._-]+")


class _KlikkHandler(logging.Handler):
    """Skriver kjernens loggmeldinger til stderr via click, så de også fanges av CliRunner."""

    def emit(self, record: logging.LogRecord) -> None:
        click.echo(self.format(record), err=True)


def _sett_opp_logging() -> None:
    """Kjernen logger fremdrift og advarsler; i CLI-en skal de vises, som linjer på stderr."""
    logger = logging.getLogger("wenche")
    if not any(isinstance(h, _KlikkHandler) for h in logger.handlers):
        handler = _KlikkHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


class _Gruppe(click.Group):
    """Gjør Wenches egne feil om til en lesbar melding og exit-kode 1, i stedet for en traceback."""

    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except ValideringsFeil as e:
            click.echo("Validering mislyktes:", err=True)
            for f in e.feil:
                click.echo(f"  - {f}", err=True)
            ctx.exit(1)
        except WencheFeil as e:
            click.echo(f"Feil: {e}", err=True)
            ctx.exit(1)


@click.group(cls=_Gruppe, invoke_without_command=True)
@click.version_option(__version__, prog_name="Wenche")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Wenche, enkel innsending til Altinn for holdingselskaper.

    Uten argumenter starter webgrensesnittet mot produksjonsmiljøet.
    Bruk `wenche dev` for å åpne UI mot Skatteetatens testmiljø (tt02).
    """
    miljoer.last_env_filer()
    _sett_opp_logging()
    if ctx.invoked_subcommand is not None:
        return
    from wenche.web.backend import kjor

    kjor(env="prod")


# ---------------------------------------------------------------------------
# Felles hjelpere
# ---------------------------------------------------------------------------


def _config_option(f):
    return click.option(
        "--config",
        "config_fil",
        default="config.yaml",
        show_default=True,
        help="Sti til konfigurasjonsfilen.",
    )(f)


def _ut_mappe_option(f):
    return click.option(
        "--ut-mappe",
        "ut_mappe",
        default=".",
        show_default=True,
        help="Mappe for filene en dry-run skriver.",
    )(f)


def _les(leser: Callable[[str], T], config_fil: str) -> T:
    """Les config med lesbar feil: manglende fil, manglende felt eller ugyldig verdi blir KonfigFeil."""
    click.echo(f"Leser konfigurasjon fra {config_fil}...")
    try:
        return leser(config_fil)
    except FileNotFoundError:
        raise KonfigFeil(f"finner ikke {config_fil}.\n{_MANGLER_CONFIG}") from None
    except KeyError as e:
        raise KonfigFeil(f"feltet {e.args[0]!r} mangler i {config_fil}.") from e
    except (ValueError, yaml.YAMLError) as e:
        raise KonfigFeil(f"kunne ikke lese {config_fil}: {e}") from e


def _advar_om_ukjente_felt(config_fil: str) -> None:
    """Advarer om felt i configen Wenche ikke kjenner, og som derfor ikke kommer med.

    Skrives til stderr, så det generer-skattemelding skriver til stdout forblir rent.
    """
    for a in configfelt.advarsel_om_ukjente_felt(config_fil):
        click.echo(f"ADVARSEL: {a}", err=True)


def _krev_gyldig(feil: list[str]) -> None:
    if feil:
        raise ValideringsFeil(feil)


def _skriv_dry_run(filer: dict[str, bytes], ut_mappe: str) -> list[Path]:
    """
    Skriv filene en dry-run lager. Rettigheter 0600, siden aksjonærregisteroppgaven inneholder
    fødselsnummer, og filnavn renset for alt annet enn bokstaver, sifre, punktum, bindestrek og
    understrek (navnet bygges av verdier fra configen).
    """
    mappe = Path(ut_mappe)
    stier = []
    for navn, innhold in filer.items():
        sti = mappe / _TRYGGE_TEGN.sub("_", navn)
        skriv_privat(sti, innhold)
        stier.append(sti)
    return stier


# ---------------------------------------------------------------------------
# Oppsett og innlogging
# ---------------------------------------------------------------------------


@main.command()
def dev() -> None:
    """Start webgrensesnittet mot testmiljøet (tt02) for tørrtrening."""
    from wenche.web.backend import kjor

    kjor(env="test")


@main.command()
def login() -> None:
    """Autentiser mot Maskinporten med RSA-nøkkel."""
    auth.login()


@main.command()
def logout() -> None:
    """Logg ut og slett lagret token."""
    auth.logout()


@main.command("registrer-system")
def registrer_system() -> None:
    """Registrer Wenche i Altinns systemregister (kjøres én gang per miljø)."""
    env = miljoer.gjeldende_navn()
    creds = auth.les_cli_credentials(env)
    org_nummer = auth.les_vendor_orgnr()
    click.echo("Henter Maskinporten admin-token...")
    token = auth.login_admin()
    sid = systembruker.system_id(org_nummer)
    click.echo(f"Registrerer system '{sid}' i Altinn...")
    svar = systembruker.registrer_system(token, org_nummer, creds.client_id)
    if svar.get("oppdatert"):
        click.echo(f"System '{sid}' oppdatert i Altinn.")
    else:
        click.echo(f"System registrert: {svar}")


@main.command("opprett-systembruker")
@click.option(
    "--org",
    default=None,
    help="Org.nr. for systembrukeren. Standard: ORG_NUMMER fra .env. "
    "I SKDs testmiljø skal dette være et syntetisk org.nr. fra Tenor.",
)
def opprett_systembruker(org: str | None) -> None:
    """Opprett systembrukerforespørsel og få godkjenningslenke."""
    vendor_orgnr = auth.les_vendor_orgnr()
    org_nummer = org or auth._les_systembruker_org(miljoer.gjeldende_navn())
    click.echo("Henter Maskinporten admin-token...")
    token = auth.login_admin()
    click.echo(f"Oppretter systembrukerforespørsel for {org_nummer}...")
    svar = systembruker.opprett_forespoersel(token, vendor_orgnr, org_nummer)
    click.echo(f"\nForespørsel opprettet (ID: {svar['id']})")
    click.echo(f"Status: {svar['status']}")
    click.echo(f"\nGodkjenn her:\n  {svar['confirmUrl']}")


# ---------------------------------------------------------------------------
# Årsregnskap
# ---------------------------------------------------------------------------


@main.command("send-aarsregnskap")
@_config_option
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generer og valider dokumentene uten å sende til Altinn.",
)
@_ut_mappe_option
def send_aarsregnskap(config_fil: str, dry_run: bool, ut_mappe: str) -> None:
    """Send inn årsregnskap til Brønnøysundregistrene."""
    regnskap = _les(aarsregnskap.les_config, config_fil)
    _advar_om_ukjente_felt(config_fil)
    click.echo(
        f"Aarsregnskap {regnskap.regnskapsaar} for {regnskap.selskap.navn} "
        f"({regnskap.selskap.org_nummer})"
    )

    if dry_run:
        _krev_gyldig(aarsregnskap.valider(regnskap))
        click.echo("Validering OK.")
        for a in aarsregnskap.advarsler(regnskap):
            click.echo(f"ADVARSEL: {a}", err=True)
        stier = _skriv_dry_run(aarsregnskap.bygg_filer(regnskap), ut_mappe)
        click.echo(
            "Dry-run: XML lagret til " + ", ".join(str(s) for s in stier) + ". "
            "Ingenting sendt til Altinn."
        )
        return

    token = auth.get_altinn_token()
    with AltinnClient(token) as klient:
        inbox_url = aarsregnskap.send_inn(regnskap, klient)
    click.echo(
        "\nÅrsregnskapet er lastet opp og klart for signering. "
        f"Finn skjemaet i Altinn-innboksen og signer der:\n  {inbox_url}"
    )


@main.command("valider-aarsregnskap")
@_config_option
def valider_aarsregnskap(config_fil: str) -> None:
    """Valider årsregnskapet lokalt uten å sende inn.

    Kjører de samme sjekkene som innsendingen (balanse, org.nr.) pluss
    ikke-blokkerende advarsler (f.eks. utbytte uten dekning i fri egenkapital).
    Ingenting genereres eller sendes. Avslutter med exit-kode 1 hvis det finnes
    blokkerende feil, ellers 0 (advarsler alene gir ikke feilkode).
    """
    regnskap = _les(aarsregnskap.les_config, config_fil)
    click.echo(
        f"Aarsregnskap {regnskap.regnskapsaar} for {regnskap.selskap.navn} "
        f"({regnskap.selskap.org_nummer})\n"
    )

    feil = aarsregnskap.valider(regnskap)
    advarsler = aarsregnskap.advarsler(regnskap) + configfelt.advarsel_om_ukjente_felt(config_fil)
    for a in advarsler:
        click.echo(f"ADVARSEL: {a}")
    _krev_gyldig(feil)
    if advarsler:
        click.echo("\nValidering OK, men sjekk advarslene over.")
    else:
        click.echo("Validering OK.")


# ---------------------------------------------------------------------------
# Aksjonærregisteroppgave
# ---------------------------------------------------------------------------


@main.command("send-aksjonaerregister")
@_config_option
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generer og valider XML lokalt uten å sende til SKD.",
)
@_ut_mappe_option
def send_aksjonaerregister(config_fil: str, dry_run: bool, ut_mappe: str) -> None:
    """Send inn aksjonærregisteroppgave (RF-1086) til Skatteetaten."""
    oppgave = _les(aksjonaerregister.les_config, config_fil)
    _advar_om_ukjente_felt(config_fil)
    click.echo(
        f"Aksjonaerregisteroppgave {oppgave.regnskapsaar} for {oppgave.selskap.navn} "
        f"({oppgave.selskap.org_nummer}), {len(oppgave.aksjonaerer)} aksjonaer(er)"
    )

    if dry_run:
        _krev_gyldig(aksjonaerregister.valider(oppgave))
        click.echo("Validering OK.")
        filer = aksjonaerregister.bygg_filer(oppgave, aksjonaerregister.innsending_org_for_test())
        stier = _skriv_dry_run(filer, ut_mappe)
        click.echo(
            "Dry-run: XML lagret til " + ", ".join(str(s) for s in stier) + ". "
            "Ingenting sendt til SKD."
        )
        return

    click.echo("Henter Maskinporten-token med SKD-scope...")
    token = auth.get_skd_aksjonaer_token()
    with SkdAksjonaerClient(token, env=miljoer.gjeldende_navn()) as klient:
        svar = aksjonaerregister.send_inn(oppgave, klient)
    click.echo(f"\nForsendelse-ID: {svar.get('forsendelseId')}")
    click.echo(f"Dialog-ID:      {svar.get('dialogId')}")


# ---------------------------------------------------------------------------
# Skattemelding
# ---------------------------------------------------------------------------


@main.command("generer-skattemelding")
@_config_option
@click.option(
    "--ut",
    "ut_fil",
    default=None,
    help="Lagre sammendrag til fil i stedet for å skrive til skjermen.",
)
def generer_skattemelding(config_fil: str, ut_fil: str | None) -> None:
    """Generer ferdig utfylt næringsspesifikasjon og skattemelding fra config.yaml."""
    regnskap, konfig = _les(skattemelding.les_config, config_fil)
    _advar_om_ukjente_felt(config_fil)
    tekst = skattemelding.generer(regnskap, konfig)
    if ut_fil:
        Path(ut_fil).write_text(tekst, encoding="utf-8")
        click.echo(f"Skattemelding lagret til {ut_fil}")
    else:
        click.echo(tekst)


def _skattemelding_forberedelser(config_fil: str) -> tuple[str, str, int | None]:
    """
    Felles for send- og valider-skattemelding: les config, stopp ved periodefeil FØR noe
    hentes eller sendes, og finn org.nr. og eventuelt test-partsnummer for miljøet.

    Returnerer (env, orgnr, partsnummer). Partsnummer er bare satt i testmiljø med
    SKD_TEST_PARTSNUMMER (SKDs testmiljø har ikke alltid en forhåndsutfylt melding å hente).
    """
    regnskap, _ = _les(skattemelding.les_config, config_fil)
    _advar_om_ukjente_felt(config_fil)
    # Skattemeldingen leveres per kalenderår, og Wenche bygger den fra samme periode som
    # årsregnskapet. En periode over to kalenderår ville gitt en skattemelding for feil periode.
    _krev_gyldig(aarsregnskap.valider_periode(regnskap))
    env = miljoer.gjeldende_navn()
    orgnr = regnskap.selskap.org_nummer
    partsnummer: int | None = None
    if env == "test":
        orgnr = os.getenv("SKD_TEST_ORG_NUMMER", orgnr)
        test_partsnummer = os.getenv("SKD_TEST_PARTSNUMMER")
        if test_partsnummer:
            try:
                partsnummer = int(test_partsnummer)
            except ValueError:
                raise KonfigFeil(
                    f"SKD_TEST_PARTSNUMMER må være et heltall, ikke {test_partsnummer!r}."
                ) from None
    return env, orgnr, partsnummer


@main.command("send-skattemelding")
@_config_option
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Hent forhåndsutfylt og generer XML lokalt uten å sende til Altinn.",
)
@_ut_mappe_option
def send_skattemelding(config_fil: str, dry_run: bool, ut_mappe: str) -> None:
    """Send inn skattemelding for AS til Skatteetaten via Altinn3."""
    env, orgnr, test_partsnummer = _skattemelding_forberedelser(config_fil)

    click.echo("Henter tokens for skattemelding...")
    tokens = auth.get_skd_skattemelding_tokens()

    with skd_modul.SkdSkattemeldingClient(tokens["maskinporten_token"], env=env) as skd:
        if test_partsnummer:
            click.echo(
                f"Bruker SKD_TEST_PARTSNUMMER={test_partsnummer} (hopper over forhåndsutfylt)"
            )
        else:
            click.echo("Henter forhåndsutfylt skattemelding...")
        bygg = tjeneste.bygg_skattemelding(
            config_fil, skd, orgnr=orgnr, partsnummer=test_partsnummer
        )
        click.echo(f"Partsnummer: {bygg.partsnummer}")

        if bygg.skjoennsfastsatt:
            click.echo(
                "\n"
                + tjeneste.SKJOENN_KLAGE_FORKLARING.format(aar=bygg.regnskap.regnskapsaar)
                + "\n"
            )
            if not dry_run:
                svar = click.prompt(
                    "Vil du sende skattemeldingen som klage på skjønnsfastsettingen? [j/N]",
                    default="n",
                    show_default=False,
                )
                if svar.strip().lower() not in {"j", "ja"}:
                    click.echo("Avbrutt. Ingenting er sendt.")
                    raise SystemExit(1)

        if dry_run:
            stier = _skriv_dry_run(
                {
                    "skattemelding.xml": bygg.skattemelding_xml,
                    "naeringsspesifikasjon.xml": bygg.naeringsspesifikasjon_xml,
                },
                ut_mappe,
            )
            click.echo(
                "Dry-run: XML lagret til " + ", ".join(str(s) for s in stier) + ". Ingenting sendt."
            )
            return

        try:
            signeringslenke = skd.send(
                inntektsaar=bygg.regnskap.regnskapsaar,
                orgnr=orgnr,
                skattemelding_xml=bygg.skattemelding_xml,
                altinn_token=tokens["altinn_token"],
                naeringsspesifikasjon_xml=bygg.naeringsspesifikasjon_xml,
                gjeldende_dokument_id=bygg.gjeldende_dokument_id,
                innsendingsformaal=bygg.innsendingsformaal,
            )
        except skd_modul.SkattemeldingValideringsfeil as e:
            click.echo(f"\n{e}", err=True)
            click.echo(
                "\nRett feilene over og kjør på nytt. Kjør «wenche valider-skattemelding» for å "
                "sjekke uten å sende.",
                err=True,
            )
            raise SystemExit(1) from None

    click.echo(
        "\nSkattemeldingen er lastet opp og venter på signering. Den er ikke levert før du "
        f"signerer med BankID i Altinn:\n  {signeringslenke}"
    )


@main.command("valider-skattemelding")
@_config_option
def valider_skattemelding(config_fil: str) -> None:
    """Valider skattemelding-konvolutten mot Skatteetaten uten å sende inn.

    Kaller Skatteetatens valider-tjeneste og skriver ut eventuelle avvik og
    veiledning. Validering lagrer ikke data og er ikke en innsending.
    """
    env, orgnr, test_partsnummer = _skattemelding_forberedelser(config_fil)

    click.echo("Henter tokens for skattemelding...")
    tokens = auth.get_skd_skattemelding_tokens()

    with skd_modul.SkdSkattemeldingClient(tokens["maskinporten_token"], env=env) as skd:
        if not test_partsnummer:
            click.echo("Henter forhåndsutfylt skattemelding...")
        bygg = tjeneste.bygg_skattemelding(
            config_fil, skd, orgnr=orgnr, partsnummer=test_partsnummer
        )
        click.echo(f"Partsnummer: {bygg.partsnummer}")
        if bygg.skjoennsfastsatt:
            click.echo(
                "Skattemeldingen er skjønnsfastsatt. Validerer som klage på "
                "skjønnsfastsettingen, slik den vil bli sendt."
            )
        konvolutt = generer_konvolutt(
            skattemelding_xml=bygg.skattemelding_xml,
            inntektsaar=bygg.regnskap.regnskapsaar,
            orgnr=orgnr,
            naeringsspesifikasjon_xml=bygg.naeringsspesifikasjon_xml,
            gjeldende_dokument_id=bygg.gjeldende_dokument_id,
            innsendingsformaal=bygg.innsendingsformaal,
        )
        click.echo("Validerer mot Skatteetaten (lagrer ikke data)...\n")
        resultat = skd.valider(bygg.regnskap.regnskapsaar, orgnr, konvolutt)

    click.echo(skd_modul.formater_valideringsresultat(resultat))


# ---------------------------------------------------------------------------
# SAF-T import
# ---------------------------------------------------------------------------


@main.command("importer-saft")
@click.argument("saft_fil", metavar="SAF-T-FIL")
@click.option(
    "--ut",
    "ut_fil",
    default="config.yaml",
    show_default=True,
    help="Sti til config.yaml-filen som skal skrives.",
)
@click.option(
    "--overskriv",
    is_flag=True,
    help="Erstatt en config-fil som alt finnes.",
)
def importer_saft(saft_fil: str, ut_fil: str, overskriv: bool) -> None:
    """
    Importer SAF-T Financial XML og generer config.yaml.

    SAF-T-FIL er stien til SAF-T-filen eksportert fra regnskapssystemet
    (Fiken, Tripletex, Visma, Uni Micro, PowerOffice Go, etc.).

    Felter som ikke finnes i SAF-T (daglig_leder, styreleder, stiftelsesaar,
    aksjonaerer) må fylles inn manuelt i config.yaml etterpå. En fil som alt finnes røres ikke
    uten --overskriv, siden det er nettopp de manuelle feltene som ville gått tapt.
    """
    from wenche.saft import importer

    ut = Path(ut_fil)
    if ut.exists() and not overskriv:
        raise KonfigFeil(
            f"{ut_fil} finnes alt. Bruk --overskriv for å erstatte den, eller --ut for et annet filnavn."
        )
    click.echo(f"Importerer SAF-T-fil: {saft_fil}")
    try:
        data = importer(saft_fil)
    except FileNotFoundError:
        raise KonfigFeil(f"finner ikke {saft_fil}.") from None
    except Exception as e:
        raise KonfigFeil(f"kunne ikke lese SAF-T-filen: {e}") from e

    # _advarsler er ikke et config-felt: den bæres fra importen til brukeren og skal ikke
    # skrives til config.yaml.
    saft_advarsler = data.pop("_advarsler", [])

    # 0600: configen får etter hvert fødselsnummer, samme regel som webgrensesnittet bruker.
    skriv_privat(ut, yaml.dump(data, allow_unicode=True, sort_keys=False))
    click.echo(f"config.yaml skrevet til {ut_fil}")

    for advarsel in saft_advarsler:
        click.echo(f"\nAdvarsel: {advarsel}")
    click.echo(
        "\nHusk å fylle inn følgende manuelt i config.yaml:\n"
        "  - selskap.daglig_leder\n"
        "  - selskap.styreleder\n"
        "  - selskap.stiftelsesaar\n"
        "  - aksjonaerer (navn, fødselsnummer, antall aksjer, utbytte)\n"
        "  - foregaaende_aar.resultatregnskap (er ikke tilgjengelig i SAF-T)"
    )
