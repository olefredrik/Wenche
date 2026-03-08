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
  </Innsender>
  <Skjemainnhold>
    <regnskapsperiode>
      <regnskapsaar orid="17102">{aar}</regnskapsaar>
      <regnskapsstart orid="17103">{aar}-01-01</regnskapsstart>
      <regnskapsslutt orid="17104">{aar}-12-31</regnskapsslutt>
    </regnskapsperiode>
    <konsern>
      <morselskap orid="4168">nei</morselskap>
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
    """
    r = regnskap.resultatregnskap
    b = regnskap.balanse

    # Hjelpefunksjon: lager linjeelement med altinnRowId kun hvis verdi != 0
    def linje(tag: str, verdi: int, besk: str, orid_besk: str,
              orid_aarets: str, orid_fjor: str) -> str:
        if verdi == 0:
            return ""
        return (
            f'<{tag} altinnRowId="{_row_id()}">'
            f'<beskrivelse orid="{orid_besk}">{besk}</beskrivelse>'
            f'<aarets orid="{orid_aarets}">{verdi}</aarets>'
            f'<fjoraarets orid="{orid_fjor}">0</fjoraarets>'
            f'</{tag}>'
        )

    # Beregnede verdier
    di = r.driftsinntekter
    dk = r.driftskostnader
    fp = r.finansposter
    ei = b.eiendeler
    am = ei.anleggsmidler
    om = ei.omloepmidler
    ek = b.egenkapital_og_gjeld.egenkapital
    lg = b.egenkapital_og_gjeld.langsiktig_gjeld
    kg = b.egenkapital_og_gjeld.kortsiktig_gjeld

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
        <aarets orid="146">{r.driftsresultat}</aarets>
        <fjoraarets orid="7026">0</fjoraarets>
      </driftsresultat>
      <inntekt>
        {linje("salgsinntekt", di.salgsinntekter, "Salgsinntekter", "28998", "1340", "7965")}
        {linje("driftsinntekt", di.andre_driftsinntekter, "Andre driftsinntekter", "28999", "7709", "7966")}
        <driftsinntektSum>
          <aarets orid="72">{di.sum}</aarets>
          <fjoraarets orid="6972">0</fjoraarets>
        </driftsinntektSum>
      </inntekt>
      <kostnad>
        {linje("loennskostnad", dk.loennskostnader, "Lønnskostnader", "29001", "81", "6979")}
        {linje("avskrivning", dk.avskrivninger, "Avskrivninger", "29002", "2139", "10181")}
        {linje("annenDriftskostnad", dk.andre_driftskostnader, "Andre driftskostnader", "29003", "82", "7023")}
        <sumDriftskostnad>
          <aarets orid="17126">{dk.sum}</aarets>
          <fjoraarets orid="17127">0</fjoraarets>
        </sumDriftskostnad>
      </kostnad>
    </resultatregnskapDriftsresultat>

    <resultatregnskapFinansinntekt>
      <nettoFinans>
        <aarets orid="158">{netto_finans}</aarets>
        <fjoraarets orid="7999">0</fjoraarets>
      </nettoFinans>
      <finansinntekt>
        {linje("investeringDatterforetakTilknyttetSelskap", fp.utbytte_fra_datterselskap, "Utbytte fra datterselskap", "29004", "27934", "27935")}
        {linje("annenRenteinntekt", fp.andre_finansinntekter, "Andre finansinntekter", "29006", "152", "7032")}
        <sumFinansinntekter>
          <aarets orid="153">{fp.sum_inntekter}</aarets>
          <fjoraarets orid="7993">0</fjoraarets>
        </sumFinansinntekter>
      </finansinntekt>
      <finanskostnad>
        {linje("rentekostnad", fp.rentekostnader, "Rentekostnader", "29009", "7037", "7038")}
        {linje("annenFinanskostnad", fp.andre_finanskostnader, "Andre finanskostnader", "29011", "156", "7041")}
        <sumFinanskostnader>
          <aarets orid="17130">{fp.sum_kostnader}</aarets>
          <fjoraarets orid="17131">0</fjoraarets>
        </sumFinanskostnader>
      </finanskostnad>
    </resultatregnskapFinansinntekt>

    <resultatregnskapResultat>
      <resultat>
        <resultatFoerSkattekostnad>
          <aarets orid="167">{r.resultat_foer_skatt}</aarets>
          <fjoraarets orid="7042">0</fjoraarets>
        </resultatFoerSkattekostnad>
        <aarsresultat>
          <aarets orid="172">{r.aarsresultat}</aarets>
          <fjoraarets orid="7054">0</fjoraarets>
        </aarsresultat>
      </resultat>
      <overfoeringer>
        <sumOverfoeringerOgDisponeringer>
          <aarets orid="7067">0</aarets>
          <fjoraarets orid="7068">0</fjoraarets>
        </sumOverfoeringerOgDisponeringer>
      </overfoeringer>
    </resultatregnskapResultat>

    <balanseAnleggsmidlerOmloepsmidler>
      <sumEiendeler>
        <aarets orid="219">{ei.sum}</aarets>
        <fjoraarets orid="7127">0</fjoraarets>
      </sumEiendeler>
      <balanseAnleggsmidler>
        <sumAnleggsmidler>
          <aarets orid="217">{am.sum}</aarets>
          <fjoraarets orid="7108">0</fjoraarets>
        </sumAnleggsmidler>
        <balanseFinansielleAnleggsmidler>
          {linje("investeringDatterselskap", am.aksjer_i_datterselskap, "Aksjer i datterselskap", "29017", "9686", "10289")}
          {linje("investeringAnnetForetakSammeKonsern", am.andre_aksjer, "Andre aksjer", "29018", "7727", "8012")}
          {linje("laanForetakSammeKonsern", am.langsiktige_fordringer, "Langsiktige fordringer", "29019", "6500", "7093")}
          <sumFinansielleAnleggsmidler>
            <aarets orid="5267">{am.sum}</aarets>
            <fjoraarets orid="8014">0</fjoraarets>
          </sumFinansielleAnleggsmidler>
        </balanseFinansielleAnleggsmidler>
      </balanseAnleggsmidler>
      <balanseOmloepsmidler>
        <sumOmloepsmidler>
          <aarets orid="194">{om.sum}</aarets>
          <fjoraarets orid="7126">0</fjoraarets>
        </sumOmloepsmidler>
        <balanseOmloepsmidlerVarerFordringer>
          <fordringer>
            {linje("andreFordringer", om.kortsiktige_fordringer, "Kortsiktige fordringer", "29028", "282", "7112")}
            <sumFordringer>
              <aarets orid="80">{om.kortsiktige_fordringer}</aarets>
              <fjoraarets orid="8015">0</fjoraarets>
            </sumFordringer>
          </fordringer>
        </balanseOmloepsmidlerVarerFordringer>
        <balanseOmloepsmidlerInvesteringerBankinnskuddKontanter>
          <bankinnskuddKontanter>
            {linje("bankinnskuddKontanter", om.bankinnskudd, "Bankinnskudd", "29031", "786", "8019")}
            <sumBankinnskuddKontanter>
              <aarets orid="29042">{om.bankinnskudd}</aarets>
              <fjoraarets orid="29043">0</fjoraarets>
            </sumBankinnskuddKontanter>
          </bankinnskuddKontanter>
        </balanseOmloepsmidlerInvesteringerBankinnskuddKontanter>
      </balanseOmloepsmidler>
    </balanseAnleggsmidlerOmloepsmidler>

    <balanseEgenkapitalGjeld>
      <sumEgenkapitalGjeld>
        <aarets orid="251">{b.egenkapital_og_gjeld.sum}</aarets>
        <fjoraarets orid="7185">0</fjoraarets>
      </sumEgenkapitalGjeld>
      <balanseEgenkapitalInnskuttOpptjentEgenkapital>
        <innskuttEgenkapital>
          {linje("selskapskapital", ek.aksjekapital, "Aksjekapital", "29032", "20488", "20489")}
          {linje("overkursfond", ek.overkursfond, "Overkursfond", "29033", "2585", "7135")}
          <sumInnskuttEgenkapital>
            <aarets orid="3730">{sum_innskutt_ek}</aarets>
            <fjoraarets orid="9984">0</fjoraarets>
          </sumInnskuttEgenkapital>
        </innskuttEgenkapital>
        <opptjentEgenkaiptal>
          {linje("annenEgenkapital", ek.annen_egenkapital, "Annen egenkapital", "29034", "3274", "7140")}
          <sumOpptjentEgenkapital>
            <aarets orid="9702">{ek.annen_egenkapital}</aarets>
            <fjoraarets orid="9985">0</fjoraarets>
          </sumOpptjentEgenkapital>
          <sumEgenkapital>
            <aarets orid="250">{ek.sum}</aarets>
            <fjoraarets orid="7142">0</fjoraarets>
          </sumEgenkapital>
        </opptjentEgenkaiptal>
      </balanseEgenkapitalInnskuttOpptjentEgenkapital>
      <balanseGjeldOversikt>
        <sumGjeld>
          <aarets orid="1119">{sum_gjeld}</aarets>
          <fjoraarets orid="7184">0</fjoraarets>
        </sumGjeld>
        <balanseGjeldAvsetningerForpliktelserAnnenLangsiktigGjeld>
          <sumLangsiktigGjeld>
            <aarets orid="86">{lg.sum}</aarets>
            <fjoraarets orid="7156">0</fjoraarets>
          </sumLangsiktigGjeld>
          <annenLangsiktigGjeld>
            {linje("langsiktigKonserngjeld", lg.laan_fra_aksjonaer, "Lån fra aksjonær", "29035", "2256", "7152")}
            {linje("oevrigLangsiktigGjeld", lg.andre_langsiktige_laan, "Andre langsiktige lån", "29036", "242", "7155")}
            <sumAnnenLangsiktigGjeld>
              <aarets orid="25019">{lg.sum}</aarets>
              <fjoraarets orid="25020">0</fjoraarets>
            </sumAnnenLangsiktigGjeld>
          </annenLangsiktigGjeld>
        </balanseGjeldAvsetningerForpliktelserAnnenLangsiktigGjeld>
        <balanseKortsiktigGjeld>
          {linje("leverandoergjeld", kg.leverandoergjeld, "Leverandørgjeld", "29037", "220", "7162")}
          {linje("skyldigeOffentligeAvgifter", kg.skyldige_offentlige_avgifter, "Skyldige offentlige avgifter", "29039", "225", "7170")}
          {linje("annenKortsiktigGjeld", kg.annen_kortsiktig_gjeld, "Annen kortsiktig gjeld", "29040", "236", "7182")}
          <sumKortsiktigGjeld>
            <aarets orid="85">{kg.sum}</aarets>
            <fjoraarets orid="7183">0</fjoraarets>
          </sumKortsiktigGjeld>
        </balanseKortsiktigGjeld>
      </balanseGjeldOversikt>
    </balanseEgenkapitalGjeld>

  </Skjemainnhold-RR0002U>
</melding>"""
    return xml.encode("utf-8")
