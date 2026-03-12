"""
Wenche — kommandolinjegrensesnitt.

Bruk:
  wenche ui
  wenche login
  wenche logout
  wenche send-aarsregnskap [--config config.yaml] [--dry-run]
  wenche send-aksjonaerregister [--config config.yaml] [--dry-run]
  wenche generer-skattemelding [--config config.yaml] [--ut skattemelding.txt]
  wenche send-skattemelding
"""

import click

from wenche import __version__
from wenche import auth, aarsregnskap, aksjonaerregister, skattemelding, systembruker
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
def ui():
    """Start webgrensesnitt i nettleseren (krever pip install wenche[ui])."""
    import subprocess
    import sys
    from pathlib import Path

    app = Path(__file__).parent / "ui.py"
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(app)], check=True
        )
    except FileNotFoundError:
        click.echo(
            "Streamlit er ikke installert. Kjør:\n  pip install wenche[ui]", err=True
        )
        raise SystemExit(1)


@main.command()
def login():
    """Autentiser mot Maskinporten med RSA-nøkkel."""
    auth.login()


@main.command()
def logout():
    """Logg ut og slett lagret token."""
    auth.logout()


@main.command("registrer-system")
def registrer_system():
    """Registrer Wenche i Altinns systemregister (kjøres én gang per miljø)."""
    import os
    client_id = os.getenv("MASKINPORTEN_CLIENT_ID")
    org_nummer = os.getenv("ORG_NUMMER")
    if not client_id or not org_nummer:
        click.echo(
            "Feil: MASKINPORTEN_CLIENT_ID og ORG_NUMMER må være satt i .env.", err=True
        )
        raise SystemExit(1)

    click.echo("Henter Maskinporten admin-token...")
    token = auth.login_admin()
    sid = systembruker.system_id(org_nummer)
    click.echo(f"Registrerer system '{sid}' i Altinn...")
    try:
        svar = systembruker.registrer_system(token, org_nummer, client_id)
        if svar.get("oppdatert"):
            click.echo(f"System '{sid}' oppdatert i Altinn.")
        else:
            click.echo(f"System registrert: {svar}")
    except Exception as e:
        click.echo(f"Feil ved registrering: {e}", err=True)
        raise SystemExit(1)


@main.command("opprett-systembruker")
def opprett_systembruker():
    """Opprett systembrukerforespørsel og få godkjenningslenke."""
    import os
    org_nummer = os.getenv("ORG_NUMMER")
    if not org_nummer:
        click.echo("Feil: ORG_NUMMER må være satt i .env.", err=True)
        raise SystemExit(1)

    click.echo("Henter Maskinporten admin-token...")
    token = auth.login_admin()
    click.echo(f"Oppretter systembrukerforespørsel for {org_nummer}...")
    try:
        svar = systembruker.opprett_forespørsel(token, org_nummer, org_nummer)
        click.echo(f"\nForespørsel opprettet (ID: {svar['id']})")
        click.echo(f"Status: {svar['status']}")
        click.echo(f"\nGodkjenn her:\n  {svar['confirmUrl']}")
    except Exception as e:
        click.echo(f"Feil ved oppretting av systembruker: {e}", err=True)
        raise SystemExit(1)



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
            f"Feil: finner ikke {config_fil}.\n"
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
        sign_url = aksjonaerregister.send_inn(oppgave, klient)
    if sign_url:
        click.echo(f"\nSigner i Altinn: {sign_url}")


# ---------------------------------------------------------------------------
# Skattemelding
# ---------------------------------------------------------------------------

@main.command("generer-skattemelding")
@click.option(
    "--config",
    "config_fil",
    default="config.yaml",
    show_default=True,
    help="Sti til konfigurasjonsfilen.",
)
@click.option(
    "--ut",
    "ut_fil",
    default=None,
    help="Lagre sammendrag til fil i stedet for å skrive til skjermen.",
)
def generer_skattemelding(config_fil: str, ut_fil: str | None):
    """Generer ferdig utfylt RF-1167 og RF-1028 fra config.yaml."""
    click.echo(f"Leser konfigurasjon fra {config_fil}...")
    try:
        regnskap, konfig = skattemelding.les_config(config_fil)
    except FileNotFoundError:
        click.echo(
            f"Feil: finner ikke {config_fil}.\n"
            "Kopier config.example.yaml til config.yaml og fyll inn dine verdier.",
            err=True,
        )
        raise SystemExit(1)

    tekst = skattemelding.generer(regnskap, konfig)

    if ut_fil:
        from pathlib import Path
        Path(ut_fil).write_text(tekst, encoding="utf-8")
        click.echo(f"Skattemelding lagret til {ut_fil}")
    else:
        click.echo(tekst)


@main.command("send-skattemelding")
def send_skattemelding():
    """Send inn skattemelding for AS (ikke implementert ennå)."""
    click.echo(
        "Innsending via API krever registrering som systemleverandør hos Skatteetaten.\n"
        "Bruk 'wenche generer-skattemelding' for å generere et ferdig utfylt sammendrag\n"
        "som du kan sende inn manuelt på https://www.skatteetaten.no/"
    )
    raise SystemExit(1)
