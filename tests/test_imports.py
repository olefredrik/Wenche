"""
Røyktester: verifiserer at alle moduler kan importeres uten feil.
Fanger opp manglende avhengigheter og feilstavede importnavn.
"""


def test_importer_models():
    import wenche.models  # noqa: F401


def test_importer_brg_xml():
    import wenche.brg_xml  # noqa: F401


def test_importer_skattemelding():
    import wenche.skattemelding  # noqa: F401


def test_importer_aarsregnskap():
    import wenche.aarsregnskap  # noqa: F401


def test_importer_aksjonaerregister():
    import wenche.aksjonaerregister  # noqa: F401


def test_importer_auth():
    import wenche.auth  # noqa: F401


def test_importer_altinn_client():
    import wenche.altinn_client  # noqa: F401


def test_importer_cli():
    import wenche.cli  # noqa: F401
