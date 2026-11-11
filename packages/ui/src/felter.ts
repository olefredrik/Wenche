// Feltstrukturen i datainntastingsskjemaet. Feltene er data: én generisk renderer
// (feltrutenett.tsx) bygger config-objektet (samme form som config.yaml) ut fra denne lista.
// tests/test_configfelt.py leser `key:`-stiene her og sjekker at kjernen kjenner hvert felt.

export type FeltType = "number" | "text" | "checkbox" | "date";

export interface Felt {
  key: string; // punkt-sti inn i config, f.eks. "selskap.navn"
  label: string;
  type?: FeltType;
  help?: string;
  valgfri?: boolean; // utelates fra config med mindre brukeren fyller den inn
}

export interface Seksjon {
  id: string;
  tittel: string;
  felter: Felt[];
}

export const RESULTAT_FELTER: Felt[] = [
  { key: "resultatregnskap.driftsinntekter.salgsinntekter", label: "Salgsinntekter", type: "number" },
  { key: "resultatregnskap.driftsinntekter.andre_driftsinntekter", label: "Andre driftsinntekter", type: "number" },
  { key: "resultatregnskap.driftskostnader.loennskostnader", label: "Lønnskostnader", type: "number" },
  { key: "resultatregnskap.driftskostnader.avskrivninger", label: "Avskrivninger", type: "number" },
  { key: "resultatregnskap.driftskostnader.andre_driftskostnader", label: "Andre driftskostnader", type: "number" },
  { key: "resultatregnskap.finansposter.utbytte_fra_datterselskap", label: "Utbytte fra datterselskap", type: "number" },
  {
    key: "resultatregnskap.finansposter.utbytte_fra_andre_aksjer",
    label: "Utbytte fra andre aksjer",
    type: "number",
    valgfri: true,
    help: "Eierandel under 20 %: verken datterselskap eller tilknyttet selskap. 3 % skattepliktig etter fritaksmetoden",
  },
  { key: "resultatregnskap.finansposter.andre_finansinntekter", label: "Andre finansinntekter", type: "number" },
  { key: "resultatregnskap.finansposter.rentekostnader", label: "Rentekostnader", type: "number" },
  { key: "resultatregnskap.finansposter.andre_finanskostnader", label: "Andre finanskostnader", type: "number" },
  {
    key: "resultatregnskap.finansposter.gevinst_ved_realisasjon_av_aksjer",
    label: "Gevinst ved salg av aksjer",
    type: "number",
    valgfri: true,
    help: "Skattefri etter fritaksmetoden. Ikke rentefond eller aksjer i lavskatteland utenfor EØS",
  },
  {
    key: "resultatregnskap.finansposter.tap_ved_realisasjon_av_aksjer",
    label: "Tap ved salg av aksjer",
    type: "number",
    valgfri: true,
    help: "Gir ikke fradrag etter fritaksmetoden",
  },
  {
    key: "resultatregnskap.skattekostnad",
    label: "Skattekostnad",
    type: "number",
    help: "Egen linje før årsresultatet (rskl. § 6-1). 0 uten skattepliktig inntekt",
  },
];

export const BALANSE_FELTER: Felt[] = [
  { key: "balanse.eiendeler.anleggsmidler.aksjer_i_datterselskap", label: "Aksjer i datterselskap", type: "number" },
  { key: "balanse.eiendeler.anleggsmidler.andre_aksjer", label: "Andre aksjer", type: "number" },
  { key: "balanse.eiendeler.anleggsmidler.langsiktige_fordringer", label: "Langsiktige fordringer", type: "number" },
  { key: "balanse.eiendeler.omloepmidler.kortsiktige_fordringer", label: "Kortsiktige fordringer", type: "number" },
  { key: "balanse.eiendeler.omloepmidler.bankinnskudd", label: "Bankinnskudd", type: "number" },
  { key: "balanse.egenkapital_og_gjeld.egenkapital.aksjekapital", label: "Aksjekapital (EK)", type: "number" },
  { key: "balanse.egenkapital_og_gjeld.egenkapital.overkursfond", label: "Overkursfond", type: "number" },
  { key: "balanse.egenkapital_og_gjeld.egenkapital.annen_egenkapital", label: "Annen egenkapital", type: "number" },
  { key: "balanse.egenkapital_og_gjeld.langsiktig_gjeld.laan_fra_aksjonaer", label: "Lån fra aksjonær", type: "number" },
  { key: "balanse.egenkapital_og_gjeld.langsiktig_gjeld.andre_langsiktige_laan", label: "Andre langsiktige lån", type: "number" },
  { key: "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.leverandoergjeld", label: "Leverandørgjeld", type: "number" },
  {
    key: "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.betalbar_skatt",
    label: "Betalbar skatt",
    type: "number",
    help: "Motposten til skattekostnaden (konto 2500), hvis skatten ikke er betalt ved årsslutt",
  },
  { key: "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.skyldige_offentlige_avgifter", label: "Skyldige offentlige avgifter", type: "number" },
  {
    key: "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.avsatt_utbytte",
    label: "Avsatt utbytte",
    type: "number",
    help: "Utbytte styret har foreslått for regnskapsåret (konto 2800). Reduserer egenkapitalen i år, ikke i utbetalingsåret",
  },
  { key: "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.annen_kortsiktig_gjeld", label: "Annen kortsiktig gjeld", type: "number" },
];

export const SEKSJONER: Seksjon[] = [
  {
    id: "selskap",
    tittel: "Selskap",
    felter: [
      { key: "selskap.navn", label: "Selskapsnavn", type: "text" },
      { key: "selskap.org_nummer", label: "Organisasjonsnummer", type: "text", help: "9 siffer" },
      { key: "selskap.daglig_leder", label: "Daglig leder", type: "text" },
      { key: "selskap.styreleder", label: "Styreleder", type: "text" },
      { key: "selskap.forretningsadresse", label: "Forretningsadresse", type: "text" },
      { key: "selskap.stiftelsesaar", label: "Stiftelsesår", type: "number" },
      {
        key: "selskap.stiftelsesdato",
        label: "Stiftelsesdato",
        type: "date",
        valgfri: true,
        help: "Hentes fra Enhetsregisteret. Brukes i aksjonærregisteroppgaven",
      },
      { key: "selskap.aksjekapital", label: "Aksjekapital (kr)", type: "number" },
      {
        key: "selskap.tinginnskudd_ved_stiftelse",
        label: "Tinginnskudd ved stiftelse (kr)",
        type: "number",
        valgfri: true,
        help: "Kun i første regnskapsår, hvis selskapet ble stiftet med annet enn penger (typisk aksjer). Tom = alt innskutt kontant",
      },
      { key: "selskap.kontakt_epost", label: "Kontakt-e-post", type: "text" },
      { key: "regnskapsaar", label: "Regnskapsår", type: "number" },
      {
        key: "regnskapsstart",
        label: "Regnskapsperiode fra",
        type: "date",
        valgfri: true,
        help: "Kun i første regnskapsår, fra stiftelsesdatoen. Tom = 1. januar",
      },
      {
        key: "regnskapsslutt",
        label: "Regnskapsperiode til",
        type: "date",
        valgfri: true,
        help: "Kan stå tom. Regnskapsåret slutter alltid 31. desember",
      },
    ],
  },
  { id: "resultatregnskap", tittel: "Resultatregnskap", felter: RESULTAT_FELTER },
  { id: "balanse", tittel: "Balanse", felter: BALANSE_FELTER },
  {
    id: "skattemelding",
    tittel: "Skattemelding",
    felter: [
      { key: "skattemelding.underskudd_til_fremfoering", label: "Underskudd til fremføring", type: "number" },
      { key: "skattemelding.formuesverdi_aksjer", label: "Formuesverdi aksjer", type: "number" },
      { key: "skattemelding.anvend_fritaksmetoden", label: "Anvend fritaksmetoden", type: "checkbox" },
      { key: "skattemelding.boersnotert", label: "Børsnotert", type: "checkbox" },
      {
        key: "skattemelding.eierandel_for_fritaksmetoden",
        label: "Eierandel for fritaksmetoden (%)",
        type: "number",
        valgfri: true,
        help: "Brukes når fritaksmetoden er valgt. Over 90 % gir helt skattefritt utbytte. Tom = 100 %",
      },
      {
        key: "skattemelding.samlet_verdi_bak_aksjene",
        label: "Samlet verdi bak aksjene (kr)",
        type: "number",
        valgfri: true,
        help: "Valgfri overstyring; ellers beregnes den fra formuesverdi + balanse",
      },
    ],
  },
];

// Fjorårets sammenligningstall: samme felter, prefikset foregaaende_aar, alle valgfrie.
export const FJORARET_FELTER: Felt[] = [...RESULTAT_FELTER, ...BALANSE_FELTER].map((f) => ({
  ...f,
  key: `foregaaende_aar.${f.key}`,
  valgfri: true,
}));

export const BALANSE_EIENDELER = BALANSE_FELTER.filter((f) => f.key.includes(".eiendeler.")).map((f) => f.key);
export const BALANSE_EK_GJELD = BALANSE_FELTER.filter((f) => f.key.includes(".egenkapital_og_gjeld.")).map((f) => f.key);

// Skatteetaten krever vedtakstidspunktet når det er utdelt utbytte (RF-1086 post 8 og 21).
// Vises derfor bare når minst én aksjonær har fått utbytte, eller datoen alt er fylt inn.
export const UTBYTTE_VEDTAKSDATO_FELT: Felt = {
  key: "utbytte_vedtaksdato",
  label: "Vedtaksdato for utbytte",
  type: "date",
  valgfri: true,
  help: "Datoen generalforsamlingen vedtok utbyttet. Påkrevd i aksjonærregisteroppgaven",
};

// Alle ikke-valgfrie tallfelt (kostnader, balanse, årstall, aksjekapital osv.). Disse står
// tomme under redigering, men må være tall i payloaden.
export const PAAKREVDE_TALLFELT: string[] = SEKSJONER.flatMap((s) =>
  s.felter.filter((f) => f.type === "number" && !f.valgfri).map((f) => f.key),
);
