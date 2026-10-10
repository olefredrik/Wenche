"""
SAF-T Financial-import (wenche/saft.py).

Verifiserer at parseren mapper SAF-T-kontoer (GroupingCategory/GroupingCode) til
Wenches config-format: årets tall fra sluttsaldoer, foregående års balanse fra
åpningssaldoer, fremførbart underskudd fra åpningssaldoen på konto 2080, og en
stub-noteoppføring for lån fra aksjonær (konto 2250). Dekker også at
importer_bytes() gir samme resultat som importer() (in-memory-stien web-UI-ene bruker).
"""

from pathlib import Path

import pytest

from wenche.saft import importer, importer_bytes

_NS = "urn:StandardAuditFile-Taxation-Financial:NO"


def _konto(kategori, kode, *, ub_debet=0, ub_kredit=0, ib_debet=0, ib_kredit=0):
    """Bygg et <Account>-element. ub = utgående (closing), ib = inngående (opening)."""
    return f"""
    <Account>
      <GroupingCategory>{kategori}</GroupingCategory>
      <GroupingCode>{kode}</GroupingCode>
      <OpeningDebitBalance>{ib_debet}</OpeningDebitBalance>
      <OpeningCreditBalance>{ib_kredit}</OpeningCreditBalance>
      <ClosingDebitBalance>{ub_debet}</ClosingDebitBalance>
      <ClosingCreditBalance>{ub_kredit}</ClosingCreditBalance>
    </Account>"""


def _saft_xml(kontoer: str, *, aar: int = 2024) -> bytes:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<AuditFile xmlns="{_NS}">
  <Header>
    <SelectionCriteria>
      <PeriodStartYear>{aar}</PeriodStartYear>
    </SelectionCriteria>
    <Company>
      <RegistrationNumber>310137715</RegistrationNumber>
      <Name>Testholding AS</Name>
      <Address>
        <StreetName>Storgata 1</StreetName>
        <PostalCode>0001</PostalCode>
        <City>Oslo</City>
      </Address>
      <Contact>
        <Email>post@testholding.no</Email>
      </Contact>
    </Company>
  </Header>
  <MasterFiles>
    <GeneralLedgerAccounts>{kontoer}</GeneralLedgerAccounts>
  </MasterFiles>
</AuditFile>""".encode("utf-8")


# Et lite, men representativt holdingselskap-regnskap.
KONTOER = (
    _konto("salgsinntekt", "3000", ub_kredit=100000)
    + _konto("finansinntekt", "8090", ub_kredit=50000)          # utbytte fra datterselskap
    + _konto("finansinntekt", "8050", ub_kredit=5000)           # andre finansinntekter
    + _konto("finanskostnad", "8150", ub_debet=2000)            # rentekostnader
    + _konto("balanseverdiForAnleggsmiddel", "1313",
             ub_debet=1000000, ib_debet=900000)                 # aksjer i datterselskap
    + _konto("balanseverdiForOmloepsmiddel", "1920",
             ub_debet=200000, ib_debet=150000)                  # bankinnskudd
    + _konto("egenkapital", "2000", ub_kredit=30000, ib_kredit=30000)   # aksjekapital
    + _konto("egenkapital", "2080", ib_debet=40000)             # udekket tap (åpning)
    + _konto("langsiktigGjeld", "2250", ub_kredit=200000)       # lån fra aksjonær
)


@pytest.fixture
def cfg():
    return importer_bytes(_saft_xml(KONTOER))


def test_selskapsopplysninger(cfg):
    s = cfg["selskap"]
    assert s["navn"] == "Testholding AS"
    assert s["org_nummer"] == "310137715"
    assert s["forretningsadresse"] == "Storgata 1, 0001 Oslo"
    assert s["kontakt_epost"] == "post@testholding.no"
    assert s["aksjekapital"] == 30000
    # Felter som ikke finnes i SAF-T skal være tomme/0.
    assert s["daglig_leder"] == ""
    assert s["styreleder"] == ""
    assert cfg["aksjonaerer"] == []


def test_regnskapsaar(cfg):
    assert cfg["regnskapsaar"] == 2024


def test_resultatregnskap_aarets_tall(cfg):
    r = cfg["resultatregnskap"]
    assert r["driftsinntekter"]["salgsinntekter"] == 100000
    assert r["finansposter"]["utbytte_fra_datterselskap"] == 50000
    assert r["finansposter"]["andre_finansinntekter"] == 5000
    assert r["finansposter"]["rentekostnader"] == 2000


def test_balanse_aarets_tall(cfg):
    b = cfg["balanse"]
    assert b["eiendeler"]["anleggsmidler"]["aksjer_i_datterselskap"] == 1000000
    assert b["eiendeler"]["omloepmidler"]["bankinnskudd"] == 200000
    assert b["egenkapital_og_gjeld"]["egenkapital"]["aksjekapital"] == 30000
    assert b["egenkapital_og_gjeld"]["langsiktig_gjeld"]["laan_fra_aksjonaer"] == 200000


def test_foregaaende_aar_balanse_fra_aapningssaldo(cfg):
    """Foregående års balanse hentes fra åpningssaldoene (inngående balanse)."""
    fa = cfg["foregaaende_aar"]["balanse"]
    assert fa["eiendeler"]["anleggsmidler"]["aksjer_i_datterselskap"] == 900000
    assert fa["eiendeler"]["omloepmidler"]["bankinnskudd"] == 150000
    # Foregående års resultatregnskap finnes ikke i SAF-T → skal være 0.
    assert cfg["foregaaende_aar"]["resultatregnskap"]["driftsinntekter"]["salgsinntekter"] == 0


def test_fremfoerbart_underskudd_fra_konto_2080(cfg):
    """Åpningssaldoen (debet) på 2080 estimerer fremførbart underskudd."""
    assert cfg["skattemelding"]["underskudd_til_fremfoering"] == 40000


def test_laan_fra_aksjonaer_gir_note_stub(cfg):
    laan = cfg["noter"]["laan_til_naerstaaende"]
    assert len(laan) == 1
    assert laan[0]["saldo"] == 200000
    assert laan[0]["retning"] == "låntaker"
    # Motpart/rente/sikkerhet finnes ikke i SAF-T og fylles inn manuelt.
    assert laan[0]["motpart"] == ""


def test_ingen_laan_gir_tom_note():
    cfg = importer_bytes(_saft_xml(_konto("salgsinntekt", "3000", ub_kredit=100000)))
    assert cfg["noter"]["laan_til_naerstaaende"] == []


def test_importer_bytes_samme_som_importer(tmp_path: Path):
    """In-memory-stien (web-UI) skal gi identisk resultat som fil-stien (CLI)."""
    xml = _saft_xml(KONTOER)
    fil = tmp_path / "saft.xml"
    fil.write_bytes(xml)
    assert importer_bytes(xml) == importer(fil)


def test_manglende_header_gir_feil():
    xml = f'<?xml version="1.0"?><AuditFile xmlns="{_NS}"></AuditFile>'.encode("utf-8")
    with pytest.raises(ValueError, match="Header"):
        importer_bytes(xml)


def test_xml_med_entitetsdefinisjoner_avvises():
    """
    Opplastet XML med entitetsdefinisjoner (billion laughs / XXE) skal avvises av
    defusedxml før ekspansjon, ikke parses med stdlib-ET. Feilen er en ValueError-
    subklasse, så web-flytenes eksisterende feilhåndtering (rettbart avvik) gjelder.
    """
    ondsinnet = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE AuditFile [<!ENTITY a "x"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>'
        f'<AuditFile xmlns="{_NS}"><Header>&b;</Header></AuditFile>'
    ).encode("utf-8")
    with pytest.raises(ValueError):
        importer_bytes(ondsinnet)


def test_skattekostnad_importeres():
    # Skattekostnaden har egen kategori i SAF-T. Uten mapping falt den ut av importen, og
    # balansen gikk ikke opp for et selskap med skattepliktig inntekt.
    cfg = importer_bytes(
        _saft_xml(
            _konto("finansinntekt", "8050", ub_kredit=50000)
            + _konto("skattekostnad", "8300", ub_debet=11000)
        )
    )
    assert cfg["resultatregnskap"]["skattekostnad"] == 11000


def test_skattekostnad_paa_kode_alene():
    # Fallback: 83-serien er skatt uansett hva kategorien sier.
    cfg = importer_bytes(_saft_xml(_konto("ukjentKategori", "8300", ub_debet=11000)))
    assert cfg["resultatregnskap"]["skattekostnad"] == 11000


def test_betalbar_skatt_egen_linje():
    # 2500 lå tidligere i skyldige offentlige avgifter. Den er motposten til skattekostnaden,
    # og har nå egen linje (rskl. § 6-2).
    cfg = importer_bytes(
        _saft_xml(
            _konto("kortsiktigGjeld", "2500", ub_kredit=11000)
            + _konto("kortsiktigGjeld", "2700", ub_kredit=3000)
        )
    )
    kg = cfg["balanse"]["egenkapital_og_gjeld"]["kortsiktig_gjeld"]
    assert kg["betalbar_skatt"] == 11000
    assert kg["skyldige_offentlige_avgifter"] == 3000


def test_saft_import_gir_balanse_som_gaar_opp_med_skatt():
    # Ende-til-ende for caset i rapporten: renteinntekt, skattekostnad og skattegjeld.
    cfg = importer_bytes(
        _saft_xml(
            _konto("finansinntekt", "8050", ub_kredit=50000)
            + _konto("skattekostnad", "8300", ub_debet=11000)
            + _konto("balanseverdiForOmloepsmiddel", "1920", ub_debet=189000)
            + _konto("egenkapital", "2000", ub_kredit=30000)
            + _konto("egenkapital", "2050", ub_kredit=148000)
            + _konto("kortsiktigGjeld", "2500", ub_kredit=11000)
        )
    )
    from wenche import aarsregnskap as ar

    regnskap = ar.les_config(
        {**cfg, "selskap": {**cfg["selskap"], "daglig_leder": "D L", "styreleder": "D L",
                            "stiftelsesaar": 2020, "aksjekapital": 30000}}
    )
    assert regnskap.resultatregnskap.resultat_foer_skatt == 50000
    assert regnskap.resultatregnskap.aarsresultat == 39000
    assert ar.valider(regnskap) == []


# ---------------------------------------------------------------------------
# Anleggsmidler Wenche ikke har en egen linje for
# ---------------------------------------------------------------------------

def test_immaterielle_eiendeler_gir_advarsel_om_koden_de_faar():
    """
    Immaterielle eiendeler og driftsmidler samles i langsiktige fordringer og rapporteres
    som kode 1390, siden modellen ikke har egne linjer for dem. Beløpet skal fortsatt komme
    med (balansen må gå opp), men brukeren skal få vite hvilken kode det får.
    """
    cfg = importer_bytes(
        _saft_xml(
            KONTOER
            + _konto("balanseverdiForAnleggsmiddel", "1070", ub_debet=45000)  # utsatt skattefordel
            + _konto("balanseverdiForAnleggsmiddel", "1105", ub_debet=12000)  # driftsmiddel
        )
    )

    assert cfg["balanse"]["eiendeler"]["anleggsmidler"]["langsiktige_fordringer"] == 57000
    assert len(cfg["_advarsler"]) == 1
    advarsel = cfg["_advarsler"][0]
    assert "1070, 1105" in advarsel
    assert "57,000" in advarsel
    assert "1390" in advarsel


def test_fordringskodene_gir_ingen_advarsel():
    """1370 og 1390 hører faktisk hjemme i langsiktige fordringer."""
    cfg = importer_bytes(
        _saft_xml(
            KONTOER
            + _konto("balanseverdiForAnleggsmiddel", "1370", ub_debet=25000)
            + _konto("balanseverdiForAnleggsmiddel", "1390", ub_debet=5000)
        )
    )

    assert cfg["balanse"]["eiendeler"]["anleggsmidler"]["langsiktige_fordringer"] == 30000
    assert "_advarsler" not in cfg


def test_vanlig_import_har_ingen_advarselsnoekkel():
    """Nøkkelen utelates helt når det ikke er noe å advare om, så configen er som før."""
    assert "_advarsler" not in importer_bytes(_saft_xml(KONTOER))


def test_advarselsnoekkelen_skrives_ikke_til_config_yaml(tmp_path):
    """_advarsler er ikke et config-felt: CLI-en skal si det, ikke lagre det."""
    from click.testing import CliRunner

    from wenche.cli import main

    saft_fil = tmp_path / "saft.xml"
    saft_fil.write_bytes(
        _saft_xml(KONTOER + _konto("balanseverdiForAnleggsmiddel", "1080", ub_debet=90000))
    )
    ut_fil = tmp_path / "config.yaml"

    resultat = CliRunner().invoke(
        main, ["importer-saft", str(saft_fil), "--ut", str(ut_fil)]
    )

    assert resultat.exit_code == 0
    assert "Advarsel:" in resultat.output
    assert "1080" in resultat.output
    assert "_advarsler" not in ut_fil.read_text(encoding="utf-8")


def test_avsatt_utbytte_konto_2800_faar_egen_linje():
    """
    Konto 2800 havnet før i annen kortsiktig gjeld og ble rapportert som kode 2990.
    Avsatt utbytte har egen linje i årsregnskapet og egen kode (2800).
    """
    cfg = importer_bytes(
        _saft_xml(KONTOER + _konto("kortsiktigGjeld", "2800", ub_kredit=80000))
    )
    kg = cfg["balanse"]["egenkapital_og_gjeld"]["kortsiktig_gjeld"]

    assert kg["avsatt_utbytte"] == 80000
    assert kg["annen_kortsiktig_gjeld"] == 0


def test_utbytte_konto_8090_er_utbytte_fra_datterselskap():
    """
    8090 er Skatteetatens grupperingskode for utbytte, og den næringsspesifikasjonen bruker.
    Før ble utbyttet lest fra 8040, som ikke finnes, og havnet i andre finansinntekter,
    der fritaksmetoden ikke virker.
    """
    cfg = importer_bytes(_saft_xml(_konto("finansinntekt", "8090", ub_kredit=70000)))
    fp = cfg["resultatregnskap"]["finansposter"]

    assert fp["utbytte_fra_datterselskap"] == 70000
    assert fp["andre_finansinntekter"] == 0


def test_aksjer_konto_1313_er_aksjer_i_datterselskap():
    """1313 er aksjer i datterselskap. Før ble 1300 lest, og 1313 havnet i fordringene."""
    cfg = importer_bytes(
        _saft_xml(
            _konto("balanseverdiForAnleggsmiddel", "1313", ub_debet=400000, ib_debet=300000)
        )
    )
    am = cfg["balanse"]["eiendeler"]["anleggsmidler"]
    fam = cfg["foregaaende_aar"]["balanse"]["eiendeler"]["anleggsmidler"]

    assert am["aksjer_i_datterselskap"] == 400000
    assert am["langsiktige_fordringer"] == 0
    assert fam["aksjer_i_datterselskap"] == 300000


def test_konsernlaan_konto_1320_er_langsiktig_fordring():
    """
    1320 er lån til foretak i samme konsern, en fordring. Før ble lånet lest som aksjer i
    datterselskap, og selskapet ble merket som morselskap i årsregnskapet.
    """
    cfg = importer_bytes(
        _saft_xml(
            _konto("balanseverdiForAnleggsmiddel", "1320", ub_debet=250000, ib_debet=200000)
        )
    )
    am = cfg["balanse"]["eiendeler"]["anleggsmidler"]
    fam = cfg["foregaaende_aar"]["balanse"]["eiendeler"]["anleggsmidler"]

    assert am["langsiktige_fordringer"] == 250000
    assert am["aksjer_i_datterselskap"] == 0
    assert fam["langsiktige_fordringer"] == 200000
    assert fam["aksjer_i_datterselskap"] == 0
    assert "_advarsler" not in cfg


def test_investeringer_uten_egen_linje_gir_advarsel():
    """
    Tilknyttede selskap, deltakerlignede datterselskap og obligasjoner har ingen egen linje.
    Beløpet havner i langsiktige fordringer som før, men ikke lenger i stillhet.
    """
    cfg = importer_bytes(
        _saft_xml(
            KONTOER
            + _konto("balanseverdiForAnleggsmiddel", "1312", ub_debet=10000)
            + _konto("balanseverdiForAnleggsmiddel", "1331", ub_debet=20000)
            + _konto("balanseverdiForAnleggsmiddel", "1332", ub_debet=30000)
            + _konto("balanseverdiForAnleggsmiddel", "1360", ub_debet=40000)
        )
    )

    assert cfg["balanse"]["eiendeler"]["anleggsmidler"]["langsiktige_fordringer"] == 100000
    assert len(cfg["_advarsler"]) == 1
    advarsel = cfg["_advarsler"][0]
    assert "1312, 1331, 1332, 1360" in advarsel
    assert "100,000" in advarsel


def test_overkurs_konto_2020_er_overkursfond():
    """2020 er overkurs. Før havnet den i annen egenkapital, altså opptjent egenkapital."""
    cfg = importer_bytes(
        _saft_xml(
            _konto("egenkapital", "2000", ub_kredit=30000)
            + _konto("egenkapital", "2020", ub_kredit=120000)
            + _konto("egenkapital", "2050", ub_kredit=15000)
        )
    )
    ek = cfg["balanse"]["egenkapital_og_gjeld"]["egenkapital"]

    assert ek["overkursfond"] == 120000
    assert ek["annen_egenkapital"] == 15000


# ---------------------------------------------------------------------------
# Sumkontroll: saldo som ikke blir fordelt på noen linje
# ---------------------------------------------------------------------------

def _konto_med_id(konto_id, kategori=None, kode=None, *, ub_debet=0, ub_kredit=0,
                  ib_debet=0, ib_kredit=0, standard_konto=None):
    """Som _konto, men med AccountID og valgfrie grupperingsfelt (eldre SAF-T-filer)."""
    gruppering = ""
    if standard_konto:
        gruppering += f"<StandardAccountID>{standard_konto}</StandardAccountID>"
    if kategori:
        gruppering += f"<GroupingCategory>{kategori}</GroupingCategory>"
    if kode:
        gruppering += f"<GroupingCode>{kode}</GroupingCode>"
    return f"""
    <Account>
      <AccountID>{konto_id}</AccountID>
      {gruppering}
      <OpeningDebitBalance>{ib_debet}</OpeningDebitBalance>
      <OpeningCreditBalance>{ib_kredit}</OpeningCreditBalance>
      <ClosingDebitBalance>{ub_debet}</ClosingDebitBalance>
      <ClosingCreditBalance>{ub_kredit}</ClosingCreditBalance>
    </Account>"""


def test_ukjent_kategori_gir_advarsel_med_konto_og_sum():
    """
    En kategori importen ikke håndterer (her varekostnad) forsvant før uten et ord.
    Beløpet skal fortsatt ikke legges noe sted, men brukeren skal få vite hvilke kontoer
    og hvor mye det gjelder.
    """
    cfg = importer_bytes(
        _saft_xml(
            KONTOER
            + _konto_med_id("4000", "varekostnad", "4005", ub_debet=10000)
            + _konto_med_id("4300", "varekostnad", "4300", ub_debet=2500, ib_debet=1000)
        )
    )

    assert len(cfg["_advarsler"]) == 1
    advarsel = cfg["_advarsler"][0]
    assert "konto 4000, 4300" in advarsel
    assert "12,500 NOK i utgående saldo" in advarsel
    assert "1,000 NOK i inngående saldo" in advarsel
    # Ingen av beløpene er gjettet inn på en linje.
    assert cfg["resultatregnskap"]["driftskostnader"]["andre_driftskostnader"] == 0


def test_sumkontrollen_teller_kredit_og_debet_uten_aa_nulle_dem_ut():
    """En debet- og en kreditkonto som ikke fordeles, skal ikke se ut som null til sammen."""
    cfg = importer_bytes(
        _saft_xml(
            KONTOER
            + _konto_med_id("4000", "varekostnad", "4005", ub_debet=7000)
            + _konto_med_id("9000", "ukjentKategori", "9000", ub_kredit=7000)
        )
    )

    assert "14,000 NOK i utgående saldo" in cfg["_advarsler"][0]


def test_konto_uten_grupperingskode_gir_advarsel():
    """Enkeltkontoer uten GroupingCategory/GroupingCode nevnes særskilt i advarselen."""
    cfg = importer_bytes(
        _saft_xml(KONTOER + _konto_med_id("1500", standard_konto="15", ub_debet=8000))
    )

    advarsel = cfg["_advarsler"][0]
    assert "konto 1500" in advarsel
    assert "8,000 NOK" in advarsel
    assert "mangler GroupingCategory og GroupingCode" in advarsel


def test_ufordelte_kontoer_uten_saldo_gir_ingen_advarsel():
    """En tom konto med ukjent kategori påvirker ikke tallene, og er ikke verdt en advarsel."""
    cfg = importer_bytes(_saft_xml(KONTOER + _konto_med_id("4000", "varekostnad", "4005")))
    assert "_advarsler" not in cfg


def test_resultatdisponering_gir_ingen_advarsel():
    """
    NA og resultatDisponeringForSAF-T (8800) er disponering av årsresultatet. Motposten står i
    egenkapitalen, så det er riktig at de ikke får noen linje, og ingen grunn til å advare.
    """
    cfg = importer_bytes(
        _saft_xml(
            KONTOER
            + _konto_med_id("8800", "resultatDisponeringForSAF-T", "8800", ub_debet=50000)
            + _konto_med_id("8960", "NA", "NA", ub_kredit=50000)
        )
    )
    assert "_advarsler" not in cfg


def test_lang_kontoliste_kortes_ned():
    kontoer = "".join(
        _konto_med_id(str(4000 + i), "varekostnad", "4005", ub_debet=100) for i in range(12)
    )
    advarsel = importer_bytes(_saft_xml(KONTOER + kontoer))["_advarsler"][0]

    assert "12 konto(er)" in advarsel
    assert "4009 og 2 til" in advarsel
    assert "4011" not in advarsel


def test_fil_helt_uten_grupperingskoder_avvises():
    """
    En SAF-T 1.10/1.20-fil med bare StandardAccountID ga før et nullregnskap uten advarsel.
    Nå stopper importen med en forklaring, som web-flytene viser som en rettbar feil.
    """
    xml = _saft_xml(
        _konto_med_id("1920", standard_konto="19", ub_debet=200000)
        + _konto_med_id("2000", standard_konto="20", ub_kredit=30000)
    )
    with pytest.raises(ValueError, match="GroupingCategory og GroupingCode"):
        importer_bytes(xml)


def test_tom_kontoplan_avvises_ikke():
    """Ingen kontoer er ikke det samme som kontoer uten grupperingskoder."""
    cfg = importer_bytes(_saft_xml(""))
    assert cfg["resultatregnskap"]["driftsinntekter"]["salgsinntekter"] == 0


# ---------------------------------------------------------------------------
# AuditFileVersion og SAF-T 1.40
# ---------------------------------------------------------------------------

def _med_versjon(xml: bytes, versjon: str) -> bytes:
    return xml.replace(
        b"<Header>", f"<Header><AuditFileVersion>{versjon}</AuditFileVersion>".encode(), 1
    )


@pytest.mark.parametrize("versjon", ["1.10", "1.20", "1.30", "1.40", "1.4"])
def test_kjente_versjoner_gir_ingen_advarsel(versjon):
    assert "_advarsler" not in importer_bytes(_med_versjon(_saft_xml(KONTOER), versjon))


def test_ukjent_versjon_gir_advarsel_men_leses():
    cfg = importer_bytes(_med_versjon(_saft_xml(KONTOER), "2.00"))

    assert len(cfg["_advarsler"]) == 1
    assert "versjon 2.00" in cfg["_advarsler"][0]
    assert cfg["resultatregnskap"]["driftsinntekter"]["salgsinntekter"] == 100000


def test_saft_versjon_140_leses():
    """
    SAF-T 1.40 er påkrevd fra regnskapsår som starter 1. januar 2027, og er bakoverkompatibel
    med samme namespace. Fixturen validerer mot Skatteetatens 1.40-skjema (men ikke mot 1.30),
    og bruker de nye elementene: flere AccountID per eier, VirtualCurrencyType og Country i
    beløp, lange desimalbeløp og DebitNOKTaxAmount.
    """
    cfg = importer(Path(__file__).parent / "fixtures" / "saft_financial_v140.xml")

    assert cfg["selskap"]["org_nummer"] == "310137715"
    assert cfg["selskap"]["kontakt_epost"] == "post@testholding.no"
    assert cfg["regnskapsaar"] == 2027
    assert cfg["resultatregnskap"]["finansposter"]["utbytte_fra_datterselskap"] == 50000
    b = cfg["balanse"]
    assert b["eiendeler"]["anleggsmidler"]["aksjer_i_datterselskap"] == 1000000
    assert b["eiendeler"]["omloepmidler"]["bankinnskudd"] == 200000
    assert b["egenkapital_og_gjeld"]["langsiktig_gjeld"]["laan_fra_aksjonaer"] == 200000
    fa = cfg["foregaaende_aar"]["balanse"]
    assert fa["eiendeler"]["anleggsmidler"]["aksjer_i_datterselskap"] == 900000
    # Alt er fordelt, og versjonen er kjent.
    assert "_advarsler" not in cfg
