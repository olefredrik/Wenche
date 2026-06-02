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
