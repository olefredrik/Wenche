"""
Wenche — kommandolinjegrensesnitt.

Bruk:
  wenche                    Starter UI mot produksjon
  wenche dev                Starter UI mot testmiljø (tt02)
  wenche login
  wenche logout
  wenche valider-aarsregnskap [--config config.yaml]
  wenche send-aarsregnskap [--config config.yaml] [--dry-run]
  wenche send-aksjonaerregister [--config config.yaml] [--dry-run]
  wenche generer-skattemelding [--config config.yaml] [--ut skattemelding.txt]
  wenche send-skattemelding
"""

import click

from wenche import __version__
from wenche import auth, aarsregnskap, aksjonaerregister, skattemelding, systembruker
from wenche.altinn_client import AltinnClient
from wenche.skd_client import SkdAksjonaerClient


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="Wenche")
@click.pass_context
def main(ctx: click.Context):
    """Wenche — enkel innsending til Altinn for holdingselskaper.

    Uten argumenter starter webgrensesnittet mot produksjonsmiljøet.
    Bruk `wenche dev` for å åpne UI mot Skatteetatens testmiljø (tt02).
    """
    if ctx.invoked_subcommand is not None:
        return
    from wenche.web.backend import kjor
    kjor(env="prod")


@main.command()
def dev():
    """Start webgrensesnittet mot testmiljøet (tt02) for tørrtrening."""
    from wenche.web.backend import kjor
    kjor(env="test")


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
@click.option(
    "--org",
    default=None,
    help="Org.nr. for systembrukeren. Standard: ORG_NUMMER fra .env. "
         "I SKDs testmiljø skal dette være et syntetisk org.nr. fra Tenor.",
)
def opprett_systembruker(org: str | None):
    """Opprett systembrukerforespørsel og få godkjenningslenke."""
    import os
    vendor_orgnr = os.getenv("ORG_NUMMER")
    if not vendor_orgnr:
        click.echo("Feil: ORG_NUMMER må være satt i .env.", err=True)
        raise SystemExit(1)
    env = os.getenv("WENCHE_ENV", "prod")
    default_org = os.getenv("SKD_TEST_ORG_NUMMER", vendor_orgnr) if env == "test" else vendor_orgnr
    org_nummer = org or default_org

    click.echo("Henter Maskinporten admin-token...")
    token = auth.login_admin()
    click.echo(f"Oppretter systembrukerforespørsel for {org_nummer}...")
    try:
        svar = systembruker.opprett_forespørsel(token, vendor_orgnr, org_nummer)
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


@main.command("valider-aarsregnskap")
@click.option(
    "--config",
    "config_fil",
    default="config.yaml",
    show_default=True,
    help="Sti til konfigurasjonsfilen.",
)
def valider_aarsregnskap(config_fil: str):
    """Valider årsregnskapet lokalt uten å sende inn.

    Kjører de samme sjekkene som innsendingen (balanse, org.nr.) pluss
    ikke-blokkerende advarsler (f.eks. utbytte uten dekning i fri egenkapital).
    Ingenting genereres eller sendes. Avslutter med exit-kode 1 hvis det finnes
    blokkerende feil, ellers 0 (advarsler alene gir ikke feilkode).
    """
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
        f"({regnskap.selskap.org_nummer})\n"
    )

    feil = aarsregnskap.valider(regnskap)
    advarsler = aarsregnskap.advarsler(regnskap)

    for a in advarsler:
        click.echo(f"ADVARSEL: {a}")

    if feil:
        click.echo("\nValidering mislyktes:", err=True)
        for f in feil:
            click.echo(f"  - {f}", err=True)
        raise SystemExit(1)

    if advarsler:
        click.echo("\nValidering OK, men sjekk advarslene over.")
    else:
        click.echo("Validering OK.")


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
    help="Generer og valider XML lokalt uten å sende til SKD.",
)
def send_aksjonaerregister(config_fil: str, dry_run: bool):
    """Send inn aksjonærregisteroppgave (RF-1086) til Skatteetaten."""
    import os
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

    click.echo("Henter Maskinporten-token med SKD-scope...")
    token = auth.get_skd_aksjonaer_token()
    env = os.getenv("WENCHE_ENV", "prod")
    with SkdAksjonaerClient(token, env=env) as klient:
        svar = aksjonaerregister.send_inn(oppgave, klient)
    if svar:
        click.echo(f"\nForsendelse-ID: {svar.get('forsendelseId')}")
        click.echo(f"Dialog-ID:      {svar.get('dialogId')}")


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
    """Generer ferdig utfylt næringsspesifikasjon og skattemelding fra config.yaml."""
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
def importer_saft(saft_fil: str, ut_fil: str):
    """
    Importer SAF-T Financial XML og generer config.yaml.

    SAF-T-FIL er stien til SAF-T-filen eksportert fra regnskapssystemet
    (Fiken, Tripletex, Visma, Uni Micro, PowerOffice Go, etc.).

    Felter som ikke finnes i SAF-T (daglig_leder, styreleder, stiftelsesaar,
    aksjonaerer) må fylles inn manuelt i config.yaml etterpå.
    """
    import yaml
    from wenche.saft import importer

    click.echo(f"Importerer SAF-T-fil: {saft_fil}")
    try:
        data = importer(saft_fil)
    except Exception as e:
        click.echo(f"Feil ved import: {e}", err=True)
        raise SystemExit(1)

    # _advarsler er ikke et config-felt: den bæres fra importen til brukeren og skal ikke
    # skrives til config.yaml.
    saft_advarsler = data.pop("_advarsler", [])

    from pathlib import Path
    Path(ut_fil).write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
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


@main.command("send-skattemelding")
@click.option(
    "--config",
    "config_fil",
    default="config.yaml",
    show_default=True,
    help="Sti til konfigurasjonsfil.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Hent forhåndsutfylt og generer XML lokalt uten å sende til Altinn.",
)
def send_skattemelding(config_fil: str, dry_run: bool):
    """Send inn skattemelding for AS til Skatteetaten via Altinn3."""
    import os
    from pathlib import Path
    from wenche.skattemelding import les_config
    from wenche.skattemelding_xml import generer_skattemelding_fra_konfig, hent_partsnummer
    from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
    from wenche.skd_skattemelding_client import (
        SkattemeldingValideringsfeil,
        SkdSkattemeldingClient,
    )

    click.echo(f"Leser konfigurasjon fra {config_fil}...")
    try:
        regnskap, konfig = les_config(config_fil)
    except FileNotFoundError:
        click.echo(
            f"Feil: finner ikke {config_fil}.\n"
            "Kopier config.example.yaml til config.yaml og fyll inn selskapets opplysninger."
        )
        raise SystemExit(1)

    env = os.getenv("WENCHE_ENV", "prod")
    orgnr = os.getenv("SKD_TEST_ORG_NUMMER", regnskap.selskap.org_nummer) if env == "test" else regnskap.selskap.org_nummer

    click.echo("Henter tokens for skattemelding...")
    tokens = auth.get_skd_skattemelding_tokens()

    with SkdSkattemeldingClient(tokens["maskinporten_token"], env=env) as skd:
        test_partsnummer = os.getenv("SKD_TEST_PARTSNUMMER") if env == "test" else None
        gjeldende_dokument_id: str | None = None
        if test_partsnummer:
            click.echo(f"Bruker SKD_TEST_PARTSNUMMER={test_partsnummer} (hopper over forhåndsutfylt)")
            partsnummer = int(test_partsnummer)
        else:
            click.echo("Henter forhåndsutfylt skattemelding...")
            forhåndsutfylt, gjeldende_dokument_id = skd.hent_forhåndsutfylt_med_id(
                regnskap.regnskapsaar, orgnr
            )
            partsnummer = hent_partsnummer(forhåndsutfylt)
        click.echo(f"Partsnummer: {partsnummer}")

        skattemelding_xml = generer_skattemelding_fra_konfig(regnskap, konfig, partsnummer)
        naeringsspesifikasjon_xml = generer_naeringsspesifikasjon(regnskap, partsnummer, konfig)

        if dry_run:
            ut_fil = Path("skattemelding.xml")
            ut_fil.write_bytes(skattemelding_xml)
            ns_fil = Path("naeringsspesifikasjon.xml")
            ns_fil.write_bytes(naeringsspesifikasjon_xml)
            click.echo(
                f"Dry-run: skattemelding XML lagret til {ut_fil}\n"
                f"Dry-run: naeringsspesifikasjon XML lagret til {ns_fil}\n"
                "Ingenting sendt."
            )
            return

        try:
            instans_id = skd.send(
                inntektsaar=regnskap.regnskapsaar,
                orgnr=orgnr,
                skattemelding_xml=skattemelding_xml,
                altinn_token=tokens["altinn_token"],
                naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
                gjeldende_dokument_id=gjeldende_dokument_id,
            )
        except SkattemeldingValideringsfeil as e:
            click.echo(f"\n{e}")
            click.echo("\nRett feilene over og kjør på nytt. Kjør «wenche valider-skattemelding» for å sjekke uten å sende.")
            raise SystemExit(1)

    click.echo(f"\nSkattemelding sendt. Instans-ID: {instans_id}")


@main.command("valider-skattemelding")
@click.option(
    "--config",
    "config_fil",
    default="config.yaml",
    show_default=True,
    help="Sti til konfigurasjonsfil.",
)
def valider_skattemelding(config_fil: str):
    """Valider skattemelding-konvolutten mot Skatteetaten uten å sende inn.

    Kaller Skatteetatens valider-tjeneste og skriver ut eventuelle avvik og
    veiledning. Validering lagrer ikke data og er ikke en innsending.
    """
    import os
    from wenche.skattemelding import les_config
    from wenche.skattemelding_xml import generer_skattemelding_fra_konfig, hent_partsnummer
    from wenche.naeringsspesifikasjon_xml import generer_naeringsspesifikasjon
    from wenche.skattemelding_konvolutt import generer_konvolutt
    from wenche.skd_skattemelding_client import (
        SkdSkattemeldingClient,
        formater_valideringsresultat,
    )

    click.echo(f"Leser konfigurasjon fra {config_fil}...")
    try:
        regnskap, konfig = les_config(config_fil)
    except FileNotFoundError:
        click.echo(
            f"Feil: finner ikke {config_fil}.\n"
            "Kopier config.example.yaml til config.yaml og fyll inn selskapets opplysninger."
        )
        raise SystemExit(1)

    env = os.getenv("WENCHE_ENV", "prod")
    orgnr = (
        os.getenv("SKD_TEST_ORG_NUMMER", regnskap.selskap.org_nummer)
        if env == "test"
        else regnskap.selskap.org_nummer
    )

    click.echo("Henter tokens for skattemelding...")
    tokens = auth.get_skd_skattemelding_tokens()

    with SkdSkattemeldingClient(tokens["maskinporten_token"], env=env) as skd:
        test_partsnummer = os.getenv("SKD_TEST_PARTSNUMMER") if env == "test" else None
        gjeldende_dokument_id = None
        if test_partsnummer:
            partsnummer = int(test_partsnummer)
        else:
            click.echo("Henter forhåndsutfylt skattemelding...")
            forhåndsutfylt, gjeldende_dokument_id = skd.hent_forhåndsutfylt_med_id(
                regnskap.regnskapsaar, orgnr
            )
            partsnummer = hent_partsnummer(forhåndsutfylt)
        click.echo(f"Partsnummer: {partsnummer}")

        skattemelding_xml = generer_skattemelding_fra_konfig(regnskap, konfig, partsnummer)
        naeringsspesifikasjon_xml = generer_naeringsspesifikasjon(regnskap, partsnummer, konfig)
        konvolutt = generer_konvolutt(
            skattemelding_xml=skattemelding_xml,
            inntektsaar=regnskap.regnskapsaar,
            orgnr=orgnr,
            naeringsspesifikasjon_xml=naeringsspesifikasjon_xml,
            gjeldende_dokument_id=gjeldende_dokument_id,
        )

        click.echo("Validerer mot Skatteetaten (lagrer ikke data)...\n")
        resultat = skd.valider(regnskap.regnskapsaar, orgnr, konvolutt)

    click.echo(formater_valideringsresultat(resultat))
