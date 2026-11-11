#!/usr/bin/env python3
"""
Regenerer det som utledes av config-skjemaet i wenche/models.py:

  - packages/ui/src/config.generert.ts  (TypeScript-typen SPA-ene bruker)
  - docs/referanse.md                   (tabellene mellom <!-- skjema: ... --> og <!-- /skjema -->)

Kjør etter en endring i modellen: `./.venv/bin/python scripts/generer_skjema.py`.
tests/test_skjema.py feiler til filene er à jour. `--sjekk` endrer ingenting og gir exit 1 ved
avvik (for CI eller pre-commit).
"""

import sys
from pathlib import Path

ROT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROT))

from wenche import skjema  # noqa: E402

FILER = {
    ROT / "packages/ui/src/config.generert.ts": lambda gammel: skjema.typescript(),
    ROT / "docs/referanse.md": skjema.oppdater_referanse,
}


def main(argv: list[str]) -> int:
    sjekk = "--sjekk" in argv
    avvik = 0
    for fil, lag in FILER.items():
        gammel = fil.read_text(encoding="utf-8") if fil.exists() else ""
        ny = lag(gammel)
        if ny == gammel:
            print(f"  {fil.relative_to(ROT)}: à jour")
            continue
        avvik += 1
        if sjekk:
            print(f"  {fil.relative_to(ROT)}: AVVIKER fra modellen")
        else:
            fil.write_text(ny, encoding="utf-8")
            print(f"  {fil.relative_to(ROT)}: oppdatert")
    if sjekk and avvik:
        print("Kjør scripts/generer_skjema.py og commit resultatet.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
