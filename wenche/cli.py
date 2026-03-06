"""
Wenche — kommandolinjegrensesnitt.

Bruk:
  wenche login
  wenche logout
  wenche send-aarsregnskap [--config config.yaml] [--dry-run]
  wenche send-aksjonaerregister [--config config.yaml] [--dry-run]
  wenche send-skattemelding
"""

import click

from wenche import __version__
from wenche import auth, aarsregnskap, aksjonaerregister, skattemelding
from wenche.altinn_client import AltinnClient


@click.group()
@click.version_option(__version__, prog_name="Wenche")
def main():
    """Wenche — enkel innsending til Altinn for holdingselskaper."""
    pass


# ---------------------------------------------------------------------------
# Autentisering
# ---------------------------------------------------------------------------

@main.command()
def login():
    """Autentiser mot Maskinporten med RSA-nøkkel."""
    auth.login()


@main.command()
def logout():
    """Logg ut og slett lagret token."""
    auth.logout()


# ---------------------------------------------------------------------------
# Årsregnskap
# ---------------------------------------------------------------------------

@main.command("send-aarsregnskap")
@click.option(
    "--config",
    "config_fil",
    default="config.yaml",
    show_default=True,
    help="Sti til konfigurasjonsfilen.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generer og valider dokument uten å sende til Altinn.",
)
def send_aarsregnskap(config_fil: str, dry_run: bool):
    """Send inn årsregnskap til Brønnøysundregistrene."""
    click.echo(f"Leser konfigurasjon fra {config_fil}...")
    try:
        regnskap = aarsregnskap.les_config(config_fil)
    except FileNotFoundError:
        click.echo(
            f"Feil: finner ikke {config_fil}.\n"
            "Kopier config.example.yaml til config.yaml og fyll inn dine verdier.",
            err=True,
        )
        raise SystemExit(1)

    click.echo(
        f"Aarsregnskap {regnskap.regnskapsaar} for {regnskap.selskap.navn} "
        f"({regnskap.selskap.org_nummer})"
    )

    if dry_run:
        aarsregnskap.send_inn(regnskap, klient=None, dry_run=True)
        return

    token = auth.get_altinn_token()
    with AltinnClient(token) as klient:
        aarsregnskap.send_inn(regnskap, klient)


# ---------------------------------------------------------------------------
# Aksjonærregisteroppgave
# ---------------------------------------------------------------------------

@main.command("send-aksjonaerregister")
@click.option(
    "--config",
    "config_fil",
    default="config.yaml",
    show_default=True,
    help="Sti til konfigurasjonsfilen.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generer og valider XML uten å sende til Altinn.",
)
def send_aksjonaerregister(config_fil: str, dry_run: bool):
    """Send inn aksjonærregisteroppgave (RF-1086) til Altinn."""
    click.echo(f"Leser konfigurasjon fra {config_fil}...")
    try:
        oppgave = aksjonaerregister.les_config(config_fil)
    except FileNotFoundError:
        click.echo(
            f"Wææ - noe gikk galt. Men det er din feil. Du har ikke noe config fil {config_fil}.\n"
            "Kopier config.example.yaml til config.yaml og fyll inn dine verdier.",
            err=True,
        )
        raise SystemExit(1)

    click.echo(
        f"Aksjonaerregisteroppgave {oppgave.regnskapsaar} for {oppgave.selskap.navn} "
        f"({oppgave.selskap.org_nummer}) — "
        f"{len(oppgave.aksjonaerer)} aksjonaer(er)"
    )

    if dry_run:
        aksjonaerregister.send_inn(oppgave, klient=None, dry_run=True)
        return

    token = auth.get_altinn_token()
    with AltinnClient(token) as klient:
        aksjonaerregister.send_inn(oppgave, klient)


# ---------------------------------------------------------------------------
# Skattemelding
# ---------------------------------------------------------------------------

@main.command("send-skattemelding")
def send_skattemelding():
    """Send inn skattemelding for AS (ikke implementert ennå)."""
    try:
        skattemelding.send_inn(None, None)
    except NotImplementedError as e:
        click.echo(str(e))
        raise SystemExit(1)
