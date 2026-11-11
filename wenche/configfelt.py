"""
Varsel om felt i config.yaml som Wenche ikke kjenner.

Leserne henter bare feltene de kjenner og ignorerer resten uten varsel. Et beløp i et felt
Wenche ikke kjenner, forsvinner derfor fra innsendingen mens valideringen sier OK. Typisk
er configen laget for en nyere Wenche-versjon, eller feltnavnet er feilstavet (#191).

De gyldige nøklene kommer fra `Konfig` i models.py via wenche.skjema, samme kilde som JSON
Schema og referansen, så listen kan ikke drifte fra modellen. Hele fila kontrolleres, også
toppnivået.

Modulen har bare modeller og skjemaet som avhengighet, så den kan importeres fra alle kallsteder.
"""

import yaml

from wenche import skjema

# Nøkkeltreet for hele config.yaml, fra samme modell som JSON Schema og referansen. Toppnivået
# kontrolleres også; nøkler som begynner med «_» er metadata (som _advarsler fra SAF-T-importen)
# og ikke config-felt.
_KJENTE = skjema.nokkeltre()


def _ukjente(verdi: dict, kjente: dict, sti: str) -> list[str]:
    ukjente = []
    for nokkel, under in verdi.items():
        full = f"{sti}.{nokkel}" if sti else str(nokkel)
        if not sti and str(nokkel).startswith("_"):
            continue
        if nokkel not in kjente:
            ukjente.append(full)
        elif isinstance(kjente[nokkel], dict) and isinstance(under, dict):
            ukjente.extend(_ukjente(under, kjente[nokkel], full))
        elif isinstance(kjente[nokkel], list) and kjente[nokkel] and isinstance(under, list):
            for i, element in enumerate(under):
                if isinstance(element, dict):
                    ukjente.extend(_ukjente(element, kjente[nokkel][0], f"{full}[{i}]"))
    return ukjente


def ukjente_felt(config: str | dict) -> list[str]:
    """Stiene til feltene i config-en som Wenche ikke kjenner, f.eks. `balanse.eiendeler.x`."""
    if isinstance(config, dict):
        raw = config
    else:
        with open(config, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    return _ukjente(raw, _KJENTE, "") if isinstance(raw, dict) else []


def advarsel_om_ukjente_felt(config: str | dict) -> list[str]:
    """Én advarsel som lister de ukjente feltene, eller en tom liste."""
    ukjente = ukjente_felt(config)
    if not ukjente:
        return []
    return [
        f"Wenche kjenner ikke {'disse feltene' if len(ukjente) > 1 else 'feltet'} i configen, "
        f"og ignorerer {'dem' if len(ukjente) > 1 else 'det'}: {', '.join(ukjente)}. "
        "Står det et beløp der, kommer det ikke med i innsendingen. Kontroller stavemåten, "
        "eller oppgrader Wenche hvis configen er laget for en nyere versjon."
    ]
