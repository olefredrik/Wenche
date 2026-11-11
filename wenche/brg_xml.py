"""
Generering av BRG XML-dokumenter for årsregnskap.

Brønnøysundregistrene krever to separate XML-dokumenter ved innsending via Altinn:
  - Hovedskjema (RR-0002): selskapsinfo, regnskapsperiode, prinsipper, fastsettelse
  - Underskjema (RR-0002U): selve tallene, resultatregnskap og balanse

Namespace og orid-verdier er hentet fra BRGs offisielle Postman-eksempler:
https://brreg.github.io/docs/apidokumentasjon/regnskapsregisteret/maskinell-innrapportering/
"""

import uuid
from datetime import date
from xml.sax.saxutils import escape

from wenche.models import Aarsregnskap, Balanse, Resultatregnskap
from wenche.xml_hjelp import heltall

# ---------------------------------------------------------------------------
# Valg som følger av scopet: passive holdingselskaper og små AS uten drift (se «Scope-rekkverk»
# i CLAUDE.md). Skal Wenche en gang støtte andre selskapsformer, autorisert regnskapsfører
# eller ansatte, er det disse som må bli config-felt.
# ---------------------------------------------------------------------------
SCOPE_ORGANISASJONSFORM = "AS"
SCOPE_SMAA_FORETAK = "ja"  # små foretak etter regnskapsloven, med forenklingene det gir
SCOPE_KONSERNREGNSKAP = "nei"  # små foretak kan la være å utarbeide konsernregnskap
SCOPE_REGNSKAPSREGLER_SELSKAP = "nei"  # ikke de ordinære reglene for større selskap
SCOPE_FORENKLET_IFRS = "nei"
SCOPE_AUTORISERT_REGNSKAPSFOERER = "nei"  # Wenche er et innsendingsverktøy, ikke regnskapsfører
SCOPE_BISTAND_REGNSKAPSFOERER = "nei"


def _row_id() -> str:
    return str(uuid.uuid4())


def _t(verdi: object) -> str:
    """Tekst klar for innsetting i XML-malen: &, < og > escapes. Et selskapsnavn som
    «Smith & Sønn AS» ga før ugyldig XML. Tallene i malen er alt heltall og trygge."""
    return escape(str(verdi))


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
    beloep = heltall(regnskap.balanse.eiendeler.anleggsmidler.andre_aksjer)

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
    # Bekreftende selskapsrepresentant som fastsetter regnskapet: daglig leder om den finnes,
    # ellers styrelederen. Passive holdingselskaper har ofte ingen daglig leder (aksjeloven
    # krever det ikke for små AS), og da er det styret som fastsetter.
    signatar = regnskap.signatar or s.daglig_leder or s.styreleder
    ikke_revideres = "ja" if not regnskap.revideres else "nei"
    morselskap = (
        "ja" if regnskap.balanse.eiendeler.anleggsmidler.aksjer_i_datterselskap > 0 else "nei"
    )

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
      <organisasjonsnummer orid="18">{_t(s.org_nummer)}</organisasjonsnummer>
      <organisasjonsform orid="756">{SCOPE_ORGANISASJONSFORM}</organisasjonsform>
      <navn orid="1">{_t(s.navn)}</navn>
    </enhet>
    <opplysningerInnsending>
      <noteMaskinellBehandling orid="37499">10</noteMaskinellBehandling>
      <systemNavn orid="39007">Wenche</systemNavn>
    </opplysningerInnsending>
  </Innsender>
  <Skjemainnhold>
    <regnskapsperiode>
      <regnskapsaar orid="17102">{aar}</regnskapsaar>
      <regnskapsstart orid="17103">{regnskap.periode_start.isoformat()}</regnskapsstart>
      <regnskapsslutt orid="17104">{regnskap.periode_slutt.isoformat()}</regnskapsslutt>
    </regnskapsperiode>
    <konsern>
      <morselskap orid="4168">{morselskap}</morselskap>
      <konsernregnskap orid="25943">{SCOPE_KONSERNREGNSKAP}</konsernregnskap>
    </konsern>
    <regnskapsprinsipper>
      <smaaForetak orid="8079">{SCOPE_SMAA_FORETAK}</smaaForetak>
      <regnskapsreglerSelskap orid="25021">{SCOPE_REGNSKAPSREGLER_SELSKAP}</regnskapsreglerSelskap>
      <forenkletIFRS orid="36639">{SCOPE_FORENKLET_IFRS}</forenkletIFRS>
    </regnskapsprinsipper>
    <fastsettelse>
      <fastsettelsedato orid="17105">{fastsettelsesdato.isoformat()}</fastsettelsedato>
      <bekreftendeSelskapsrepresentant orid="19023">{_t(signatar)}</bekreftendeSelskapsrepresentant>
    </fastsettelse>
    <revisjonRegnskapsfoerer>
      <aarsregnskapIkkeRevideres orid="34669">{ikke_revideres}</aarsregnskapIkkeRevideres>
      <aarsregnskapUtarbeidetAutorisertRegnskapsfoerer orid="34670">{SCOPE_AUTORISERT_REGNSKAPSFOERER}</aarsregnskapUtarbeidetAutorisertRegnskapsfoerer>
      <tjenestebistandEksternAutorisertRegnskapsfoerer orid="34671">{SCOPE_BISTAND_REGNSKAPSFOERER}</tjenestebistandEksternAutorisertRegnskapsfoerer>
    </revisjonRegnskapsfoerer>
    <aarsberetning/>
  </Skjemainnhold>
</melding>"""
    return xml.encode("utf-8")


def _linje(
    tag: str,
    verdi: float,
    besk: str,
    orid_besk: str,
    orid_aarets: str,
    orid_fjor: str,
    fjor_verdi: float = 0.0,
) -> str:
    """
    Linjeelement med altinnRowId og beskrivelse, for elementene XSD-en lar gjenta
    (unbounded). Utelates når både årets og fjorårets verdi er 0.
    """
    iv, ifv = heltall(verdi), heltall(fjor_verdi)
    if iv == 0 and ifv == 0:
        return ""
    return (
        f'<{tag} altinnRowId="{_row_id()}">'
        f'<beskrivelse orid="{orid_besk}">{besk}</beskrivelse>'
        f'<aarets orid="{orid_aarets}">{iv}</aarets>'
        f'<fjoraarets orid="{orid_fjor}">{ifv}</fjoraarets>'
        f"</{tag}>"
    )


def _linje_enkel(
    tag: str, verdi: float, orid_aarets: str, orid_fjor: str, fjor_verdi: float = 0.0
) -> str:
    """
    Linjeelement for elementer som bare kan forekomme én gang. Utelater altinnRowId og
    <beskrivelse> med vilje: XSD-en definerer disse (f.eks. rentekostnad, overkursfond,
    utbytte) uten dem, i motsetning til de gjentakbare elementene i _linje(). Utelates når
    både årets og fjorårets verdi er 0.
    """
    iv, ifv = heltall(verdi), heltall(fjor_verdi)
    if iv == 0 and ifv == 0:
        return ""
    return (
        f"<{tag}>"
        f'<aarets orid="{orid_aarets}">{iv}</aarets>'
        f'<fjoraarets orid="{orid_fjor}">{ifv}</fjoraarets>'
        f"</{tag}>"
    )


def _sumlinje(tag: str, verdi: float, orid_aarets: str, orid_fjor: str, fjor_verdi: float) -> str:
    """Sum- og resultatelement. Sendes alltid, også når begge verdiene er 0."""
    return (
        f"<{tag}>"
        f'<aarets orid="{orid_aarets}">{heltall(verdi)}</aarets>'
        f'<fjoraarets orid="{orid_fjor}">{heltall(fjor_verdi)}</fjoraarets>'
        f"</{tag}>"
    )


def _resultatregnskap_xml(r: Resultatregnskap, fr: Resultatregnskap) -> str:
    """Resultatregnskapet i underskjemaet: drift, finans og resultat, med fjorårets tall."""
    di, dk, fp = r.driftsinntekter, r.driftskostnader, r.finansposter
    fdi, fdk, ffp = fr.driftsinntekter, fr.driftskostnader, fr.finansposter
    # Gevinst ved realisasjon av aksjer er en annen finansinntekt (annenFinansinntekt), ikke
    # en renteinntekt, og rapporteres på egen linje. Tap rapporteres sammen med andre
    # finanskostnader, der det hører hjemme.
    andre_finanskostnader = fp.andre_finanskostnader + fp.tap_ved_realisasjon_av_aksjer
    f_andre_finanskostnader = ffp.andre_finanskostnader + ffp.tap_ved_realisasjon_av_aksjer
    return f"""
    <resultatregnskapDriftsresultat>
      {_sumlinje("driftsresultat", r.driftsresultat, "146", "7026", fr.driftsresultat)}
      <inntekt>
        {_linje("salgsinntekt", di.salgsinntekter, "Salgsinntekter", "28998", "1340", "7965", fdi.salgsinntekter)}
        {_linje("driftsinntekt", di.andre_driftsinntekter, "Andre driftsinntekter", "28999", "7709", "7966", fdi.andre_driftsinntekter)}
        {_sumlinje("driftsinntektSum", di.sum, "72", "6972", fdi.sum)}
      </inntekt>
      <kostnad>
        {_linje("loennskostnad", dk.loennskostnader, "Lønnskostnader", "29001", "81", "6979", fdk.loennskostnader)}
        {_linje("avskrivning", dk.avskrivninger, "Avskrivninger", "29002", "2139", "10181", fdk.avskrivninger)}
        {_linje("annenDriftskostnad", dk.andre_driftskostnader, "Andre driftskostnader", "29003", "82", "7023", fdk.andre_driftskostnader)}
        {_sumlinje("sumDriftskostnad", dk.sum, "17126", "17127", fdk.sum)}
      </kostnad>
    </resultatregnskapDriftsresultat>

    <resultatregnskapFinansinntekt>
      {_sumlinje("nettoFinans", fp.sum_inntekter - fp.sum_kostnader, "158", "7999", ffp.sum_inntekter - ffp.sum_kostnader)}
      <finansinntekt>
        {_linje("investeringDatterforetakTilknyttetSelskap", fp.utbytte_fra_datterselskap, "Utbytte fra datterselskap", "29004", "27934", "27935", ffp.utbytte_fra_datterselskap)}
        {_linje("andreInvesteringer", fp.utbytte_fra_andre_aksjer, "Utbytte fra andre aksjer", "29005", "27936", "27937", ffp.utbytte_fra_andre_aksjer)}
        {_linje_enkel("annenRenteinntekt", fp.andre_finansinntekter, "150", "7030", ffp.andre_finansinntekter)}
        {_linje("annenFinansinntekt", fp.gevinst_ved_realisasjon_av_aksjer, "Gevinst ved realisasjon av aksjer", "29006", "152", "7032", ffp.gevinst_ved_realisasjon_av_aksjer)}
        {_sumlinje("sumFinansinntekter", fp.sum_inntekter, "153", "7993", ffp.sum_inntekter)}
      </finansinntekt>
      <finanskostnad>
        {_linje_enkel("rentekostnad", fp.rentekostnader, "7037", "7038", ffp.rentekostnader)}
        {_linje("annenFinanskostnad", andre_finanskostnader, "Andre finanskostnader", "29011", "156", "7041", f_andre_finanskostnader)}
        {_sumlinje("sumFinanskostnader", fp.sum_kostnader, "17130", "17131", ffp.sum_kostnader)}
      </finanskostnad>
    </resultatregnskapFinansinntekt>

    <resultatregnskapResultat>
      <resultat>
        {_sumlinje("resultatFoerSkattekostnad", r.resultat_foer_skatt, "167", "7042", fr.resultat_foer_skatt)}
        {_linje("skattekostnad", r.skattekostnad, "Skattekostnad på ordinært resultat", "29013", "11835", "11836", fr.skattekostnad)}
        {_sumlinje("aarsresultat", r.aarsresultat, "172", "7054", fr.aarsresultat)}
      </resultat>
      <overfoeringer>
        {_sumlinje("sumOverfoeringerOgDisponeringer", r.aarsresultat, "7071", "7072", fr.aarsresultat)}
      </overfoeringer>
    </resultatregnskapResultat>
"""


def _eiendeler_xml(b: Balanse, fb: Balanse) -> str:
    """Balansens eiendelsside: anleggsmidler og omløpsmidler, med fjorårets tall."""
    ei, fei = b.eiendeler, fb.eiendeler
    am, fam = ei.anleggsmidler, fei.anleggsmidler
    om, fom = ei.omloepmidler, fei.omloepmidler
    return f"""
    <balanseAnleggsmidlerOmloepsmidler>
      {_sumlinje("sumEiendeler", ei.sum, "219", "7127", fei.sum)}
      <balanseAnleggsmidler>
        {_sumlinje("sumAnleggsmidler", am.sum, "217", "7108", fam.sum)}
        <balanseFinansielleAnleggsmidler>
          {_sumlinje("investeringDatterselskap", am.aksjer_i_datterselskap, "9686", "10289", fam.aksjer_i_datterselskap)}
          {_linje("investeringAksjerAndeler", am.andre_aksjer, "Andre aksjer", "29024", "7100", "7101", fam.andre_aksjer)}
          {_linje("annenFordring", am.langsiktige_fordringer, "Langsiktige fordringer", "29025", "203", "27585", fam.langsiktige_fordringer)}
          {_sumlinje("sumFinansielleAnleggsmidler", am.sum, "5267", "8014", fam.sum)}
        </balanseFinansielleAnleggsmidler>
      </balanseAnleggsmidler>
      <balanseOmloepsmidler>
        {_sumlinje("sumOmloepsmidler", om.sum, "194", "7126", fom.sum)}
        <balanseOmloepsmidlerVarerFordringer>
          <fordringer>
            {_linje("andreFordringer", om.kortsiktige_fordringer, "Kortsiktige fordringer", "29028", "282", "7112", fom.kortsiktige_fordringer)}
            {_sumlinje("sumFordringer", om.kortsiktige_fordringer, "80", "8015", fom.kortsiktige_fordringer)}
          </fordringer>
        </balanseOmloepsmidlerVarerFordringer>
        <balanseOmloepsmidlerInvesteringerBankinnskuddKontanter>
          <bankinnskuddKontanter>
            {_linje("bankinnskuddKontanter", om.bankinnskudd, "Bankinnskudd", "29031", "786", "8019", fom.bankinnskudd)}
            {_sumlinje("sumBankinnskuddKontanter", om.bankinnskudd, "29042", "29043", fom.bankinnskudd)}
          </bankinnskuddKontanter>
        </balanseOmloepsmidlerInvesteringerBankinnskuddKontanter>
      </balanseOmloepsmidler>
    </balanseAnleggsmidlerOmloepsmidler>
"""


def _egenkapital_og_gjeld_xml(b: Balanse, fb: Balanse) -> str:
    """Balansens finansieringsside: innskutt og opptjent egenkapital, langsiktig og kortsiktig gjeld."""
    eg, feg = b.egenkapital_og_gjeld, fb.egenkapital_og_gjeld
    ek, fek = eg.egenkapital, feg.egenkapital
    lg, flg = eg.langsiktig_gjeld, feg.langsiktig_gjeld
    kg, fkg = eg.kortsiktig_gjeld, feg.kortsiktig_gjeld
    # «opptjentEgenkaiptal» er elementnavnet i BRGs skjema, med skrivefeilen.
    return f"""
    <balanseEgenkapitalGjeld>
      {_sumlinje("sumEgenkapitalGjeld", eg.sum, "251", "7185", feg.sum)}
      <balanseEgenkapitalInnskuttOpptjentEgenkapital>
        <innskuttEgenkapital>
          {_linje("selskapskapital", ek.aksjekapital, "Aksjekapital", "29032", "20488", "20489", fek.aksjekapital)}
          {_linje_enkel("overkursfond", ek.overkursfond, "2585", "7135", fek.overkursfond)}
          {_sumlinje("sumInnskuttEgenkapital", ek.aksjekapital + ek.overkursfond, "3730", "9984", fek.aksjekapital + fek.overkursfond)}
        </innskuttEgenkapital>
        <opptjentEgenkaiptal>
          {_linje("annenEgenkapital", ek.annen_egenkapital, "Annen egenkapital", "29034", "3274", "7140", fek.annen_egenkapital)}
          {_sumlinje("sumOpptjentEgenkapital", ek.annen_egenkapital, "9702", "9985", fek.annen_egenkapital)}
          {_sumlinje("sumEgenkapital", ek.sum, "250", "7142", fek.sum)}
        </opptjentEgenkaiptal>
      </balanseEgenkapitalInnskuttOpptjentEgenkapital>
      <balanseGjeldOversikt>
        {_sumlinje("sumGjeld", lg.sum + kg.sum, "1119", "7184", flg.sum + fkg.sum)}
        <balanseGjeldAvsetningerForpliktelserAnnenLangsiktigGjeld>
          {_sumlinje("sumLangsiktigGjeld", lg.sum, "86", "7156", flg.sum)}
          <annenLangsiktigGjeld>
            {_linje("oevrigLangsiktigGjeld", lg.laan_fra_aksjonaer, "Lån fra aksjonær", "29036", "242", "7155", flg.laan_fra_aksjonaer)}
            {_linje("oevrigLangsiktigGjeld", lg.andre_langsiktige_laan, "Andre langsiktige lån", "29036", "242", "7155", flg.andre_langsiktige_laan)}
            {_sumlinje("sumAnnenLangsiktigGjeld", lg.sum, "25019", "25020", flg.sum)}
          </annenLangsiktigGjeld>
        </balanseGjeldAvsetningerForpliktelserAnnenLangsiktigGjeld>
        <balanseKortsiktigGjeld>
          {_linje_enkel("leverandoergjeld", kg.leverandoergjeld, "220", "7162", fkg.leverandoergjeld)}
          {_linje("betalbarSkatt", kg.betalbar_skatt, "Betalbar skatt", "29038", "2483", "10293", fkg.betalbar_skatt)}
          {_linje("skyldigeOffentligeAvgifter", kg.skyldige_offentlige_avgifter, "Skyldige offentlige avgifter", "29039", "225", "7170", fkg.skyldige_offentlige_avgifter)}
          {_linje_enkel("utbytte", kg.avsatt_utbytte, "235", "7171", fkg.avsatt_utbytte)}
          {_linje("annenKortsiktigGjeld", kg.annen_kortsiktig_gjeld, "Annen kortsiktig gjeld", "29040", "236", "7182", fkg.annen_kortsiktig_gjeld)}
          {_sumlinje("sumKortsiktigGjeld", kg.sum, "85", "7183", fkg.sum)}
        </balanseKortsiktigGjeld>
      </balanseGjeldOversikt>
    </balanseEgenkapitalGjeld>
"""


def generer_underskjema(regnskap: Aarsregnskap) -> bytes:
    """
    Genererer Underskjema XML (dataType=Underskjema, dataFormatId=758).
    Inneholder resultatregnskap og balanse med BRGs orid-verdier, seksjon for seksjon.
    BRG krever heltall, så alle beløp rundes til nærmeste krone.
    """
    # Årsverk settes lik antall ansatte i note 2, så skjemaet og noten sier det samme. Wenche
    # har ingen deltidsbrøk; passive selskap har normalt 0, og dry-run advarer når tallet er
    # over 0 (lønn og a-melding er utenfor det Wenche sender inn).
    aarsverk = regnskap.noter.antall_ansatte
    fr = regnskap.foregaaende_aar_resultat
    fb = regnskap.foregaaende_aar_balanse

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
{_resultatregnskap_xml(regnskap.resultatregnskap, fr)}
{_eiendeler_xml(regnskap.balanse, fb)}
{_egenkapital_og_gjeld_xml(regnskap.balanse, fb)}
    <noter>
      <noteAarsverkTjenestePensjon>
        <antallAarsverk orid="37467">{aarsverk}</antallAarsverk>
      </noteAarsverkTjenestePensjon>
    </noter>
  </Skjemainnhold-RR0002U>
</melding>"""
    return xml.encode("utf-8")
