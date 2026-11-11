// Eksempeldata for testmiljøet: demo-selskapet i tt02 (Tenor-org med systembruker for demoen).
// Vises bare når appen kjører mot test (knappen «Fyll inn eksempeldata»).
import type { Config } from "./typer";

export const EKSEMPEL: Config = {
  selskap: {
    navn: "FORSIKTIG MINKENDE TIGER AS",
    org_nummer: "312463938",
    daglig_leder: "Daglig Leder",
    styreleder: "Daglig Leder",
    forretningsadresse: "J. M. Uglands vei 20, 4878 GRIMSTAD",
    stiftelsesaar: 2001,
    aksjekapital: 100000,
    kontakt_epost: "test@example.no",
  },
  regnskapsaar: 2025,
  resultatregnskap: {
    driftsinntekter: { salgsinntekter: 0, andre_driftsinntekter: 0 },
    driftskostnader: { loennskostnader: 0, avskrivninger: 0, andre_driftskostnader: 0 },
    finansposter: {
      utbytte_fra_datterselskap: 0,
      andre_finansinntekter: 0,
      rentekostnader: 0,
      andre_finanskostnader: 0,
    },
    skattekostnad: 0,
  },
  balanse: {
    eiendeler: {
      anleggsmidler: { aksjer_i_datterselskap: 100000, andre_aksjer: 0, langsiktige_fordringer: 0 },
      omloepmidler: { kortsiktige_fordringer: 0, bankinnskudd: 30000 },
    },
    egenkapital_og_gjeld: {
      egenkapital: { aksjekapital: 100000, overkursfond: 0, annen_egenkapital: 30000 },
      langsiktig_gjeld: { laan_fra_aksjonaer: 0, andre_langsiktige_laan: 0 },
      kortsiktig_gjeld: {
        leverandoergjeld: 0,
        betalbar_skatt: 0,
        skyldige_offentlige_avgifter: 0,
        annen_kortsiktig_gjeld: 0,
      },
    },
  },
  // Fjorårets balanse er identisk (passivt holding uten bevegelse i året), så
  // egenkapitalavstemmingen går i null mot årsresultat 0. Uten foregående år
  // ville hele utgående EK telt som «årets overskudd» og gitt avvik mot SKD.
  foregaaende_aar: {
    resultatregnskap: {
      driftsinntekter: { salgsinntekter: 0, andre_driftsinntekter: 0 },
      driftskostnader: { loennskostnader: 0, avskrivninger: 0, andre_driftskostnader: 0 },
      finansposter: {
        utbytte_fra_datterselskap: 0,
        andre_finansinntekter: 0,
        rentekostnader: 0,
        andre_finanskostnader: 0,
      },
      skattekostnad: 0,
    },
    balanse: {
      eiendeler: {
        anleggsmidler: { aksjer_i_datterselskap: 100000, andre_aksjer: 0, langsiktige_fordringer: 0 },
        omloepmidler: { kortsiktige_fordringer: 0, bankinnskudd: 30000 },
      },
      egenkapital_og_gjeld: {
        egenkapital: { aksjekapital: 100000, overkursfond: 0, annen_egenkapital: 30000 },
        langsiktig_gjeld: { laan_fra_aksjonaer: 0, andre_langsiktige_laan: 0 },
        kortsiktig_gjeld: {
          leverandoergjeld: 0,
          betalbar_skatt: 0,
          skyldige_offentlige_avgifter: 0,
          annen_kortsiktig_gjeld: 0,
        },
      },
    },
  },
  skattemelding: {
    underskudd_til_fremfoering: 0,
    anvend_fritaksmetoden: true,
    boersnotert: false,
    // Formuesverdi av aksjene i datterselskapet (RF-1088S), erstatter bokført
    // verdi i formuesgrunnlaget. Gir skattemeldingen formue-innhold så den ikke
    // er «tom» mot næringsspesifikasjonen (UP_HAR_NÆRINGSSPESIFIKASJON_MANGLER_SKATTEMELDING).
    formuesverdi_aksjer: 1200000,
  },
  aksjonaerer: [
    {
      navn: "Daglig Leder",
      fodselsnummer: "24847799354",
      antall_aksjer: 100,
      aksjeklasse: "ordinære",
      utbytte_utbetalt: 0,
      innbetalt_kapital_per_aksje: 1000,
    },
  ],
};
