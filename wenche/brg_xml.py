"""
Generering av BRG XML-dokumenter for årsregnskap.

Brønnøysundregistrene krever to separate XML-dokumenter ved innsending via Altinn:
  - Hovedskjema (RR-0002): selskapsinfo, regnskapsperiode, prinsipper, fastsettelse
  - Underskjema (RR-0002U): selve tallene — resultatregnskap og balanse

Namespace og orid-verdier er hentet fra BRGs offisielle Postman-eksempler:
https://brreg.github.io/docs/apidokumentasjon/regnskapsregisteret/maskinell-innrapportering/
"""

import uuid
from datetime import date

from wenche.models import Aarsregnskap


def _row_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Minimal PDF-generator (ingen eksterne avhengigheter)
# ---------------------------------------------------------------------------

def _lag_pdf(linjer: list[str]) -> bytes:
    """
    Bygger en minimal men gyldig PDF med gitt tekstinnhold.
    Bruker WinAnsiEncoding (latin-1) som dekker norske tegn (æ, ø, å).
    """
    def _pdf_str(s: str) -> bytes:
        enc = s.encode("cp1252", errors="replace")
        escaped = enc.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
        return b"(" + escaped + b")"

    stream_parts: list[bytes] = [b"BT", b"/F1 11 Tf", b"50 790 Td", b"16 TL"]
    for linje in linjer:
        stream_parts.append(_pdf_str(linje) + b" Tj T*")
    stream_parts.append(b"ET")
    stream = b"\n".join(stream_parts)

    obj1 = b"<</Type /Catalog /Pages 2 0 R>>"
    obj2 = b"<</Type /Pages /Kids [3 0 R] /Count 1>>"
    obj3 = b"<</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 595 842] /Contents 5 0 R>>"
    obj4 = b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding>>"
    obj5 = f"<</Length {len(stream)}>>\nstream\n".encode() + stream + b"\nendstream"

    objects = [obj1, obj2, obj3, obj4, obj5]
    pdf = b"%PDF-1.4\n"
    offsets: list[int] = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += b"xref\n"
    pdf += f"0 {len(objects) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += f"trailer\n<</Size {len(objects) + 1} /Root 1 0 R>>\n".encode()
    pdf += f"startxref\n{xref_offset}\n%%EOF\n".encode()
    return pdf


def generer_aksjenote_vedlegg(regnskap: Aarsregnskap) -> bytes:
    """
    Genererer aksjenote som PDF-vedlegg (dataType=Vedlegg).

    BRG krever Vedlegg når selskapet har andre aksjer og andeler
    (investeringAksjerAndeler > 0) i Underskjema-XML.
    Noten dokumenterer investeringen etter rskl. § 7-36.
    """
    s = regnskap.selskap
    aar = regnskap.regnskapsaar
    beloep = round(regnskap.balanse.eiendeler.anleggsmidler.andre_aksjer)

    linjer = [
        f"Note til årsregnskap — {s.navn}",
        f"Organisasjonsnummer: {s.org_nummer}",
        f"Regnskapsår: {aar}",
        "",
        "Note — Andre aksjer og andeler (rskl. § 7-36)",
        "",
        "Selskapet eier aksjer og andeler i andre foretak.",
        f"Bokført verdi per 31.12.{aar}: {beloep:,} kr".replace(",", " "),
        "",
        "Investeringene er vurdert til kostpris.",
        "Fritaksmetoden (sktl. § 2-38) vurderes for mottatt utbytte.",
    ]
    return _lag_pdf(linjer)


def generer_hovedskjema(regnskap: Aarsregnskap) -> bytes:
    """
    Genererer Hovedskjema XML (dataType=Hovedskjema, dataFormatId=1266).
    Inneholder selskapsinfo, regnskapsperiode, prinsipper og fastsettelse.
    """
    s = regnskap.selskap
    aar = regnskap.regnskapsaar
    fastsettelsesdato = regnskap.fastsettelsesdato or date.today()
    signatar = regnskap.signatar or s.daglig_leder
    revideres = "nei" if not regnskap.revideres else "ja"
    ikke_revideres = "ja" if not regnskap.revideres else "nei"
    morselskap = "ja" if regnskap.balanse.eiendeler.anleggsmidler.aksjer_i_datterselskap > 0 else "nei"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<melding xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns:xsd="http://www.w3.org/2001/XMLSchema"
         xmlns="http://schema.brreg.no/regnsys/aarsregnskap_vanlig"
         dataFormatId="1266"
         dataFormatVersion="51820"
         tjenestehandling="aarsregnskap_vanlig"
         tjeneste="regnskap">
  <Innsender>
    <enhet>
      <organisasjonsnummer orid="18">{s.org_nummer}</organisasjonsnummer>
      <organisasjonsform orid="756">AS</organisasjonsform>
      <navn orid="1">{s.navn}</navn>
    </enhet>
    <opplysningerInnsending>
      <noteMaskinellBehandling orid="37499">Maskinell innsending</noteMaskinellBehandling>
      <systemNavn orid="39007">Wenche</systemNavn>
    </opplysningerInnsending>
  </Innsender>
  <Skjemainnhold>
    <regnskapsperiode>
      <regnskapsaar orid="17102">{aar}</regnskapsaar>
      <regnskapsstart orid="17103">{aar}-01-01</regnskapsstart>
      <regnskapsslutt orid="17104">{aar}-12-31</regnskapsslutt>
    </regnskapsperiode>
    <konsern>
      <morselskap orid="4168">{morselskap}</morselskap>
      <konsernregnskap orid="25943">nei</konsernregnskap>
    </konsern>
    <regnskapsprinsipper>
      <smaaForetak orid="8079">ja</smaaForetak>
      <regnskapsreglerSelskap orid="25021">nei</regnskapsreglerSelskap>
      <forenkletIFRS orid="36639">nei</forenkletIFRS>
    </regnskapsprinsipper>
    <fastsettelse>
      <fastsettelsedato orid="17105">{fastsettelsesdato.isoformat()}</fastsettelsedato>
      <bekreftendeSelskapsrepresentant orid="19023">{signatar}</bekreftendeSelskapsrepresentant>
    </fastsettelse>
    <revisjonRegnskapsfoerer>
      <aarsregnskapIkkeRevideres orid="34669">{ikke_revideres}</aarsregnskapIkkeRevideres>
      <aarsregnskapUtarbeidetAutorisertRegnskapsfoerer orid="34670">nei</aarsregnskapUtarbeidetAutorisertRegnskapsfoerer>
      <tjenestebistandEksternAutorisertRegnskapsfoerer orid="34671">nei</tjenestebistandEksternAutorisertRegnskapsfoerer>
    </revisjonRegnskapsfoerer>
    <aarsberetning/>
  </Skjemainnhold>
</melding>"""
    return xml.encode("utf-8")


def generer_underskjema(regnskap: Aarsregnskap) -> bytes:
    """
    Genererer Underskjema XML (dataType=Underskjema, dataFormatId=758).
    Inneholder resultatregnskap og balanse med BRGs orid-verdier.
    BRG krever heltall — alle beløp rundes til nærmeste krone.
    """
    r = regnskap.resultatregnskap
    b = regnskap.balanse
    fr = regnskap.foregaaende_aar_resultat
    fb = regnskap.foregaaende_aar_balanse

    # Avrund float til int for BRG XML (registrene aksepterer kun heltall)
    def _i(v: float) -> int:
        return round(v)

    # Hjelpefunksjon: lager linjeelement med altinnRowId kun hvis verdi != 0
    def linje(tag: str, verdi: float, besk: str, orid_besk: str,
              orid_aarets: str, orid_fjor: str, fjor_verdi: float = 0.0) -> str:
        iv, ifv = _i(verdi), _i(fjor_verdi)
        if iv == 0 and ifv == 0:
            return ""
        return (
            f'<{tag} altinnRowId="{_row_id()}">'
            f'<beskrivelse orid="{orid_besk}">{besk}</beskrivelse>'
            f'<aarets orid="{orid_aarets}">{iv}</aarets>'
            f'<fjoraarets orid="{orid_fjor}">{ifv}</fjoraarets>'
            f'</{tag}>'
        )

    # Inneværende år
    di = r.driftsinntekter
    dk = r.driftskostnader
    fp = r.finansposter
    ei = b.eiendeler
    am = ei.anleggsmidler
    om = ei.omloepmidler
    ek = b.egenkapital_og_gjeld.egenkapital
    lg = b.egenkapital_og_gjeld.langsiktig_gjeld
    kg = b.egenkapital_og_gjeld.kortsiktig_gjeld

    # Foregående år
    fdi = fr.driftsinntekter
    fdk = fr.driftskostnader
    ffp = fr.finansposter
    fei = fb.eiendeler
    fam = fei.anleggsmidler
    fom = fei.omloepmidler
    fek = fb.egenkapital_og_gjeld.egenkapital
    flg = fb.egenkapital_og_gjeld.langsiktig_gjeld
    fkg = fb.egenkapital_og_gjeld.kortsiktig_gjeld

    netto_finans = fp.sum_inntekter - fp.sum_kostnader
    sum_gjeld = lg.sum + kg.sum
    sum_innskutt_ek = ek.aksjekapital + ek.overkursfond

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<melding xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns:xsd="http://www.w3.org/2001/XMLSchema"
         xmlns="http://schema.brreg.no/regnsys/aarsregnskap_vanlig/underskjema"
         dataFormatId="758"
         dataFormatVersion="51980"
         tjenestehandling="aarsregnskap_vanlig_underskjema"
         tjeneste="regnskap">
  <Rapport-RR0002U>
    <aarsregnskap>
      <regnskapstype orid="25942">S</regnskapstype>
      <valuta orid="34984">NOK</valuta>
      <valoer orid="28974">H</valoer>
    </aarsregnskap>
  </Rapport-RR0002U>
  <Skjemainnhold-RR0002U>

    <resultatregnskapDriftsresultat>
      <driftsresultat>
        <aarets orid="146">{_i(r.driftsresultat)}</aarets>
        <fjoraarets orid="7026">{_i(fr.driftsresultat)}</fjoraarets>
      </driftsresultat>
      <inntekt>
        {linje("salgsinntekt", di.salgsinntekter, "Salgsinntekter", "28998", "1340", "7965", fdi.salgsinntekter)}
        {linje("driftsinntekt", di.andre_driftsinntekter, "Andre driftsinntekter", "28999", "7709", "7966", fdi.andre_driftsinntekter)}
        <driftsinntektSum>
          <aarets orid="72">{_i(di.sum)}</aarets>
          <fjoraarets orid="6972">{_i(fdi.sum)}</fjoraarets>
        </driftsinntektSum>
      </inntekt>
      <kostnad>
        {linje("loennskostnad", dk.loennskostnader, "Lønnskostnader", "29001", "81", "6979", fdk.loennskostnader)}
        {linje("avskrivning", dk.avskrivninger, "Avskrivninger", "29002", "2139", "10181", fdk.avskrivninger)}
        {linje("annenDriftskostnad", dk.andre_driftskostnader, "Andre driftskostnader", "29003", "82", "7023", fdk.andre_driftskostnader)}
        <sumDriftskostnad>
          <aarets orid="17126">{_i(dk.sum)}</aarets>
          <fjoraarets orid="17127">{_i(fdk.sum)}</fjoraarets>
        </sumDriftskostnad>
      </kostnad>
    </resultatregnskapDriftsresultat>

    <resultatregnskapFinansinntekt>
      <nettoFinans>
        <aarets orid="158">{_i(netto_finans)}</aarets>
        <fjoraarets orid="7999">{_i(ffp.sum_inntekter - ffp.sum_kostnader)}</fjoraarets>
      </nettoFinans>
      <finansinntekt>
        {linje("investeringDatterforetakTilknyttetSelskap", fp.utbytte_fra_datterselskap, "Utbytte fra datterselskap", "29004", "27934", "27935", ffp.utbytte_fra_datterselskap)}
        {linje("annenRenteinntekt", fp.andre_finansinntekter, "Andre finansinntekter", "29006", "152", "7032", ffp.andre_finansinntekter)}
        <sumFinansinntekter>
          <aarets orid="153">{_i(fp.sum_inntekter)}</aarets>
          <fjoraarets orid="7993">{_i(ffp.sum_inntekter)}</fjoraarets>
        </sumFinansinntekter>
      </finansinntekt>
      <finanskostnad>
        {linje("rentekostnad", fp.rentekostnader, "Rentekostnader", "29009", "7037", "7038", ffp.rentekostnader)}
        {linje("annenFinanskostnad", fp.andre_finanskostnader, "Andre finanskostnader", "29011", "156", "7041", ffp.andre_finanskostnader)}
        <sumFinanskostnader>
          <aarets orid="17130">{_i(fp.sum_kostnader)}</aarets>
          <fjoraarets orid="17131">{_i(ffp.sum_kostnader)}</fjoraarets>
        </sumFinanskostnader>
      </finanskostnad>
    </resultatregnskapFinansinntekt>

    <resultatregnskapResultat>
      <resultat>
        <resultatFoerSkattekostnad>
          <aarets orid="167">{_i(r.resultat_foer_skatt)}</aarets>
          <fjoraarets orid="7042">{_i(fr.resultat_foer_skatt)}</fjoraarets>
        </resultatFoerSkattekostnad>
        <aarsresultat>
          <aarets orid="172">{_i(r.aarsresultat)}</aarets>
          <fjoraarets orid="7054">{_i(fr.aarsresultat)}</fjoraarets>
        </aarsresultat>
      </resultat>
      <overfoeringer>
        <sumOverfoeringerOgDisponeringer>
          <aarets orid="7067">{_i(r.aarsresultat)}</aarets>
          <fjoraarets orid="7068">{_i(fr.aarsresultat)}</fjoraarets>
        </sumOverfoeringerOgDisponeringer>
      </overfoeringer>
    </resultatregnskapResultat>

    <balanseAnleggsmidlerOmloepsmidler>
      <sumEiendeler>
        <aarets orid="219">{_i(ei.sum)}</aarets>
        <fjoraarets orid="7127">{_i(fei.sum)}</fjoraarets>
      </sumEiendeler>
      <balanseAnleggsmidler>
        <sumAnleggsmidler>
          <aarets orid="217">{_i(am.sum)}</aarets>
          <fjoraarets orid="7108">{_i(fam.sum)}</fjoraarets>
        </sumAnleggsmidler>
        <balanseFinansielleAnleggsmidler>
          <investeringDatterselskap>
            <aarets orid="9686">{_i(am.aksjer_i_datterselskap)}</aarets>
            <fjoraarets orid="10289">{_i(fam.aksjer_i_datterselskap)}</fjoraarets>
          </investeringDatterselskap>
          {linje("investeringAksjerAndeler", am.andre_aksjer, "Andre aksjer", "29018", "7727", "8012", fam.andre_aksjer)}
          {linje("annenFordring", am.langsiktige_fordringer, "Langsiktige fordringer", "29019", "6500", "7093", fam.langsiktige_fordringer)}
          <sumFinansielleAnleggsmidler>
            <aarets orid="5267">{_i(am.sum)}</aarets>
            <fjoraarets orid="8014">{_i(fam.sum)}</fjoraarets>
          </sumFinansielleAnleggsmidler>
        </balanseFinansielleAnleggsmidler>
      </balanseAnleggsmidler>
      <balanseOmloepsmidler>
        <sumOmloepsmidler>
          <aarets orid="194">{_i(om.sum)}</aarets>
          <fjoraarets orid="7126">{_i(fom.sum)}</fjoraarets>
        </sumOmloepsmidler>
        <balanseOmloepsmidlerVarerFordringer>
          <fordringer>
            {linje("andreFordringer", om.kortsiktige_fordringer, "Kortsiktige fordringer", "29028", "282", "7112", fom.kortsiktige_fordringer)}
            <sumFordringer>
              <aarets orid="80">{_i(om.kortsiktige_fordringer)}</aarets>
              <fjoraarets orid="8015">{_i(fom.kortsiktige_fordringer)}</fjoraarets>
            </sumFordringer>
          </fordringer>
        </balanseOmloepsmidlerVarerFordringer>
        <balanseOmloepsmidlerInvesteringerBankinnskuddKontanter>
          <bankinnskuddKontanter>
            {linje("bankinnskuddKontanter", om.bankinnskudd, "Bankinnskudd", "29031", "786", "8019", fom.bankinnskudd)}
            <sumBankinnskuddKontanter>
              <aarets orid="29042">{_i(om.bankinnskudd)}</aarets>
              <fjoraarets orid="29043">{_i(fom.bankinnskudd)}</fjoraarets>
            </sumBankinnskuddKontanter>
          </bankinnskuddKontanter>
        </balanseOmloepsmidlerInvesteringerBankinnskuddKontanter>
      </balanseOmloepsmidler>
    </balanseAnleggsmidlerOmloepsmidler>

    <balanseEgenkapitalGjeld>
      <sumEgenkapitalGjeld>
        <aarets orid="251">{_i(b.egenkapital_og_gjeld.sum)}</aarets>
        <fjoraarets orid="7185">{_i(fb.egenkapital_og_gjeld.sum)}</fjoraarets>
      </sumEgenkapitalGjeld>
      <balanseEgenkapitalInnskuttOpptjentEgenkapital>
        <innskuttEgenkapital>
          {linje("selskapskapital", ek.aksjekapital, "Aksjekapital", "29032", "20488", "20489", fek.aksjekapital)}
          {linje("overkursfond", ek.overkursfond, "Overkursfond", "29033", "2585", "7135", fek.overkursfond)}
          <sumInnskuttEgenkapital>
            <aarets orid="3730">{_i(sum_innskutt_ek)}</aarets>
            <fjoraarets orid="9984">{_i(fek.aksjekapital + fek.overkursfond)}</fjoraarets>
          </sumInnskuttEgenkapital>
        </innskuttEgenkapital>
        <opptjentEgenkaiptal>
          {linje("annenEgenkapital", ek.annen_egenkapital, "Annen egenkapital", "29034", "3274", "7140", fek.annen_egenkapital)}
          <sumOpptjentEgenkapital>
            <aarets orid="9702">{_i(ek.annen_egenkapital)}</aarets>
            <fjoraarets orid="9985">{_i(fek.annen_egenkapital)}</fjoraarets>
          </sumOpptjentEgenkapital>
          <sumEgenkapital>
            <aarets orid="250">{_i(ek.sum)}</aarets>
            <fjoraarets orid="7142">{_i(fek.sum)}</fjoraarets>
          </sumEgenkapital>
        </opptjentEgenkaiptal>
      </balanseEgenkapitalInnskuttOpptjentEgenkapital>
      <balanseGjeldOversikt>
        <sumGjeld>
          <aarets orid="1119">{_i(sum_gjeld)}</aarets>
          <fjoraarets orid="7184">{_i(flg.sum + fkg.sum)}</fjoraarets>
        </sumGjeld>
        <balanseGjeldAvsetningerForpliktelserAnnenLangsiktigGjeld>
          <sumLangsiktigGjeld>
            <aarets orid="86">{_i(lg.sum)}</aarets>
            <fjoraarets orid="7156">{_i(flg.sum)}</fjoraarets>
          </sumLangsiktigGjeld>
          <annenLangsiktigGjeld>
            {linje("langsiktigKonserngjeld", lg.laan_fra_aksjonaer, "Lån fra aksjonær", "29035", "2256", "7152", flg.laan_fra_aksjonaer)}
            {linje("oevrigLangsiktigGjeld", lg.andre_langsiktige_laan, "Andre langsiktige lån", "29036", "242", "7155", flg.andre_langsiktige_laan)}
            <sumAnnenLangsiktigGjeld>
              <aarets orid="25019">{_i(lg.sum)}</aarets>
              <fjoraarets orid="25020">{_i(flg.sum)}</fjoraarets>
            </sumAnnenLangsiktigGjeld>
          </annenLangsiktigGjeld>
        </balanseGjeldAvsetningerForpliktelserAnnenLangsiktigGjeld>
        <balanseKortsiktigGjeld>
          {linje("leverandoergjeld", kg.leverandoergjeld, "Leverandørgjeld", "29037", "220", "7162", fkg.leverandoergjeld)}
          {linje("skyldigeOffentligeAvgifter", kg.skyldige_offentlige_avgifter, "Skyldige offentlige avgifter", "29039", "225", "7170", fkg.skyldige_offentlige_avgifter)}
          {linje("annenKortsiktigGjeld", kg.annen_kortsiktig_gjeld, "Annen kortsiktig gjeld", "29040", "236", "7182", fkg.annen_kortsiktig_gjeld)}
          <sumKortsiktigGjeld>
            <aarets orid="85">{_i(kg.sum)}</aarets>
            <fjoraarets orid="7183">{_i(fkg.sum)}</fjoraarets>
          </sumKortsiktigGjeld>
        </balanseKortsiktigGjeld>
      </balanseGjeldOversikt>
    </balanseEgenkapitalGjeld>


    <noter>
      <noteAarsverkTjenestePensjon>
        <antallAarsverk orid="37467">0</antallAarsverk>
      </noteAarsverkTjenestePensjon>
    </noter>

  </Skjemainnhold-RR0002U>
</melding>"""
    return xml.encode("utf-8")
