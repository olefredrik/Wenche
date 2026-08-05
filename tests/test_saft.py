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
    + _konto("finansinntekt", "8040", ub_kredit=50000)          # utbytte fra datterselskap
    + _konto("finansinntekt", "8050", ub_kredit=5000)           # andre finansinntekter
    + _konto("finanskostnad", "8150", ub_debet=2000)            # rentekostnader
    + _konto("balanseverdiForAnleggsmiddel", "1300",
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
