# Installasjon

## Krav

- Python **3.11 eller nyere**
- OpenSSL (følger med macOS og de fleste Linux-distribusjoner; Python på Windows inkluderer dette automatisk)

### Sjekk Python-versjonen din

=== "macOS / Linux"

    ```bash
    python3 --version
    ```

=== "Windows (PowerShell)"

    ```powershell
    python --version
    ```

    Har du flere Python-versjoner installert, bruk `py`-launcheren for å se alle:

    ```powershell
    py --list
    ```

Viser kommandoen 3.10 eller lavere (eller du får feilmeldingen `command not found`), installer en nyere versjon:

=== "macOS"

    ```bash
    brew install python@3.11
    ```

=== "Linux (Ubuntu/Debian)"

    ```bash
    sudo apt install python3.11 python3.11-venv
    ```

=== "Windows"

    Last ned **Python 3.11** eller nyere fra [python.org](https://www.python.org/downloads/).

    !!! warning "Viktig under installasjonen"
        Huk av **«Add Python to PATH»** nederst i installasjonsvinduet før du klikker *Install Now*.
        Uten dette finner ikke terminalen `python`-kommandoen.

    !!! tip "Unngå Microsoft Store-versjonen"
        Windows kan ha en stubb-versjon av Python installert som åpner Microsoft Store i stedet for å kjøre Python.
        Hvis `python --version` åpner Store, deaktiver dette under **Innstillinger → Apper → Appkjøringsaliaser** og slå av begge Python-oppføringene.

## Installer Wenche

Det anbefales å installere Wenche i et virtuelt miljø for å unngå konflikter med andre Python-pakker.

=== "macOS / Linux — kommandolinje"

    ```bash
    python3.11 -m venv .venv
    source .venv/bin/activate
    pip install wenche
    ```

=== "macOS / Linux — webgrensesnitt"

    ```bash
    python3.11 -m venv .venv
    source .venv/bin/activate
    pip install "wenche[ui]"
    ```

=== "Windows — kommandolinje"

    ```powershell
    py -3.11 -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install wenche
    ```

=== "Windows — webgrensesnitt"

    ```powershell
    py -3.11 -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install "wenche[ui]"
    ```

!!! warning "Windows: PowerShell execution policy"
    Får du feilmeldingen `running scripts is disabled on this system` når du kjører `Activate.ps1`,
    må du tillate kjøring av lokale scripts:

    ```powershell
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    ```

    Kjør så `.venv\Scripts\Activate.ps1` på nytt.

Wenche er nå tilgjengelig som kommandoen `wenche` i terminalen:

```bash
wenche --help
```

!!! tip "Husk å aktivere miljøet"
    Neste gang du åpner et nytt terminalvindu må du aktivere det virtuelle miljøet på nytt:

    === "macOS / Linux"
        ```bash
        source .venv/bin/activate
        ```

    === "Windows"
        ```powershell
        .venv\Scripts\Activate.ps1
        ```

## Start webgrensesnittet

Har du installert `wenche[ui]`, starter du grensesnittet slik:

```bash
wenche ui
```

Streamlit starter og åpner `http://localhost:8501` i nettleseren. Åpnes ikke nettleseren automatisk, kan du lime inn adressen manuelt.

## For utviklere

Vil du bidra til koden eller kjøre siste versjon fra GitHub?

```bash
git clone https://github.com/olefredrik/wenche.git
cd wenche
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Kjør testsuiten:

```bash
pytest tests/ -v
```

[Gå videre til oppsett →](oppsett.md){ .md-button .md-button--primary }
