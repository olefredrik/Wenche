import { useEffect, useRef, useState } from "react";
import yaml from "js-yaml";
import { monoLabel, input, btnPrimar, btnOutlineLett as btnOutline } from "./styles";
import { Inn, TallInput, TallFelt } from "./komponenter";

// Skjema-drevet datainntasting. Feltstrukturen er data; én generisk renderer bygger
// config-objektet (samme form som config.yaml) som sendes til backenden.

type FeltType = "number" | "text" | "checkbox" | "date";
interface Felt {
  key: string; // punkt-sti inn i config, f.eks. "selskap.navn"
  label: string;
  type?: FeltType;
  help?: string;
  valgfri?: boolean; // utelates fra config med mindre brukeren fyller den inn
}
interface Seksjon {
  id: string;
  tittel: string;
  felter: Felt[];
}

const RESULTAT_FELTER: Felt[] = [
  { key: "resultatregnskap.driftsinntekter.salgsinntekter", label: "Salgsinntekter", type: "number" },
  { key: "resultatregnskap.driftsinntekter.andre_driftsinntekter", label: "Andre driftsinntekter", type: "number" },
  { key: "resultatregnskap.driftskostnader.loennskostnader", label: "Lønnskostnader", type: "number" },
  { key: "resultatregnskap.driftskostnader.avskrivninger", label: "Avskrivninger", type: "number" },
  { key: "resultatregnskap.driftskostnader.andre_driftskostnader", label: "Andre driftskostnader", type: "number" },
  { key: "resultatregnskap.finansposter.utbytte_fra_datterselskap", label: "Utbytte fra datterselskap", type: "number" },
  { key: "resultatregnskap.finansposter.andre_finansinntekter", label: "Andre finansinntekter", type: "number" },
  { key: "resultatregnskap.finansposter.rentekostnader", label: "Rentekostnader", type: "number" },
  { key: "resultatregnskap.finansposter.andre_finanskostnader", label: "Andre finanskostnader", type: "number" },
  {
    key: "resultatregnskap.skattekostnad",
    label: "Skattekostnad",
    type: "number",
    help: "Egen linje før årsresultatet (rskl. § 6-1). 0 uten skattepliktig inntekt",
  },
];

const BALANSE_FELTER: Felt[] = [
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
  { key: "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.annen_kortsiktig_gjeld", label: "Annen kortsiktig gjeld", type: "number" },
];

const SEKSJONER: Seksjon[] = [
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
      { key: "selskap.kontakt_epost", label: "Kontakt-e-post", type: "text" },
      { key: "regnskapsaar", label: "Regnskapsår", type: "number" },
      {
        key: "regnskapsstart",
        label: "Regnskapsperiode fra",
        type: "date",
        valgfri: true,
        help: "Kun ved forlenget første regnskapsår. Tom = 1. januar",
      },
      {
        key: "regnskapsslutt",
        label: "Regnskapsperiode til",
        type: "date",
        valgfri: true,
        help: "Kun ved forlenget første regnskapsår. Tom = 31. desember",
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
        help: "Brukes når fritaksmetoden er valgt. Tom = 100 % (helt skattefritt)",
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
const FJORARET_FELTER: Felt[] = [...RESULTAT_FELTER, ...BALANSE_FELTER].map((f) => ({
  ...f,
  key: `foregaaende_aar.${f.key}`,
  valgfri: true,
}));

const BALANSE_EIENDELER = BALANSE_FELTER.filter((f) => f.key.includes(".eiendeler.")).map((f) => f.key);
const BALANSE_EK_GJELD = BALANSE_FELTER.filter((f) => f.key.includes(".egenkapital_og_gjeld.")).map((f) => f.key);

interface Aksjonaer {
  navn: string;
  fodselsnummer: string;
  // Tallfeltene kan stå tomme ("") under redigering, så brukeren slipper å slette en ledende 0.
  // Normaliseres til tall ved lagring (se normaliserForLagring).
  antall_aksjer: number | "";
  aksjeklasse: string;
  utbytte_utbetalt: number | "";
  innbetalt_kapital_per_aksje: number | "";
}

const AKSJONAER_TALLFELT = [
  "antall_aksjer",
  "utbytte_utbetalt",
  "innbetalt_kapital_per_aksje",
] as const;

function tomAksjonaer(): Aksjonaer {
  return {
    navn: "",
    fodselsnummer: "",
    antall_aksjer: "",
    aksjeklasse: "ordinære",
    utbytte_utbetalt: "",
    innbetalt_kapital_per_aksje: "",
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function hent(obj: any, path: string): any {
  return path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function sett(obj: any, path: string, value: any): any {
  const keys = path.split(".");
  const ny = { ...obj };
  let cur = ny;
  for (let i = 0; i < keys.length - 1; i++) {
    cur[keys[i]] = { ...(cur[keys[i]] ?? {}) };
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return ny;
}

// Alle ikke-valgfrie tallfelt (kostnader, balanse, årstall, aksjekapital osv.). Disse står
// tomme under redigering, men må være tall i payloaden: flere av dem leses med direkte
// indeksering i kjernen (selskap.stiftelsesaar/aksjekapital, regnskapsaar) og krasjer på "".
const PAAKREVDE_TALLFELT: string[] = SEKSJONER.flatMap((s) =>
  s.felter.filter((f) => f.type === "number" && !f.valgfri).map((f) => f.key),
);

// Tomt tallfelt ("", null, NaN) → true. Valgfrie felt får stå tomme (kjernen tolererer dem),
// men påkrevde felt og aksjonær-tall må gjøres om til 0 før innsending.
function erTomtTall(v: unknown): boolean {
  return v === "" || v == null || (typeof v === "number" && Number.isNaN(v));
}

// Gjør blanke påkrevde tallfelt om til 0 rett før lagring/innsending, slik at payloaden er
// identisk med den gamle (der feltene alltid var 0). Rører ikke valgfrie felt eller tekst.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function normaliserForLagring(config: any): any {
  let c = config;
  for (const key of PAAKREVDE_TALLFELT) if (erTomtTall(hent(c, key))) c = sett(c, key, 0);
  const aksjonaerer = (config?.aksjonaerer ?? []).map((a: Aksjonaer) => {
    const na = { ...a };
    for (const f of AKSJONAER_TALLFELT) if (erTomtTall(na[f])) na[f] = 0;
    return na;
  });
  return { ...c, aksjonaerer };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function grunnConfig(): any {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let c: any = {};
  // Tallfelt starter tomme ("") slik at brukeren slipper å slette en ledende 0.
  // De normaliseres tilbake til tall ved lagring (normaliserForLagring).
  for (const s of SEKSJONER)
    for (const f of s.felter)
      if (!f.valgfri)
        c = sett(c, f.key, f.type === "checkbox" ? false : "");
  c.aksjonaerer = [tomAksjonaer()];
  return c;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const EKSEMPEL: any = {
  selskap: {
    navn: "MOTSTANDSDYKTIG ENTUSIASTISK TIGER AS",
    org_nummer: "310137715",
    daglig_leder: "Daglig Leder",
    styreleder: "Daglig Leder",
    forretningsadresse: "Bergveien 23, 1890 RAKKESTAD",
    stiftelsesaar: 2018,
    aksjekapital: 30000,
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
      egenkapital: { aksjekapital: 30000, overkursfond: 0, annen_egenkapital: 100000 },
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
        egenkapital: { aksjekapital: 30000, overkursfond: 0, annen_egenkapital: 100000 },
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
      antall_aksjer: 300,
      aksjeklasse: "ordinære",
      utbytte_utbetalt: 0,
      innbetalt_kapital_per_aksje: 100,
    },
  ],
};

export function kr(n: number): string {
  return (Number(n) || 0).toLocaleString("nb-NO") + " kr";
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function oppsummer(config: any) {
  const sumE = BALANSE_EIENDELER.reduce((s, k) => s + (Number(hent(config, k)) || 0), 0);
  const sumG = BALANSE_EK_GJELD.reduce((s, k) => s + (Number(hent(config, k)) || 0), 0);
  return {
    navn: hent(config, "selskap.navn") || "",
    org: hent(config, "selskap.org_nummer") || "",
    aar: hent(config, "regnskapsaar") || "",
    balanseDiff: sumE - sumG,
    balansererOk: Math.abs(sumE - sumG) < 0.01,
    antallAksjonaerer: (config.aksjonaerer ?? []).length,
  };
}

// Sann når de grunnleggende selskapsopplysningene er fylt inn. Brukes til å gate «Gå videre»
// fra Tall-steget, så man ikke havner på en tom Dokumenter-/Send-side.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function harMinimumsdata(config: any): boolean {
  if (!config) return false;
  const s = config.selskap ?? {};
  const utfylt = (k: string) => String(s[k] ?? "").trim() !== "";
  // Navn + org alltid; daglig leder ELLER styreleder. Passive holdingselskaper har ofte ingen
  // daglig leder, og da står styrelederen som bekreftende representant i årsregnskapet.
  return utfylt("navn") && utfylt("org_nummer") && (utfylt("daglig_leder") || utfylt("styreleder"));
}

function Feltrutenett({
  felter,
  config,
  oppdater,
  laasteFelter = [],
}: {
  felter: Felt[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  oppdater: (key: string, val: any) => void;
  laasteFelter?: string[];
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {felter.map((f) => {
        const laast = laasteFelter.includes(f.key);
        return f.type === "checkbox" ? (
          <label key={f.key} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 accent-[oklch(0.46_0.08_155)]"
              checked={!!hent(config, f.key)}
              onChange={(e) => oppdater(f.key, e.target.checked)}
            />
            {f.label}
          </label>
        ) : (
          <label key={f.key} className="block">
            <span className="mb-1 block text-xs text-muted-foreground">
              {f.label}
              {f.help ? ` (${f.help})` : ""}
            </span>
            {f.type === "number" ? (
              // Tallfelt: tusenskille i visningen, rent number i config (se TallInput).
              <TallInput
                className={`${input} ${laast ? "cursor-not-allowed opacity-60" : ""}`}
                value={hent(config, f.key) ?? ""}
                disabled={laast}
                title={laast ? "Låst til selskapet i invitasjonen" : undefined}
                onChange={(v) => oppdater(f.key, v)}
              />
            ) : (
              <input
                className={`${input} ${laast ? "cursor-not-allowed opacity-60" : ""}`}
                type={f.type === "date" ? "date" : "text"}
                value={hent(config, f.key) ?? ""}
                disabled={laast}
                title={laast ? "Låst til selskapet i invitasjonen" : undefined}
                onChange={(e) => oppdater(f.key, e.target.value)}
              />
            )}
          </label>
        );
      })}
    </div>
  );
}

export function DataSkjema({
  onLagre,
  visEksempel = false,
  initial,
  lagreEtikett = "Lagre data",
  ekstraSeksjon,
  laastOrg,
  importerSaft,
  saftMerknad,
  prefillSelskap,
  beregnSkatt,
}: {
  onLagre: (config: unknown) => Promise<void>;
  visEksempel?: boolean;
  // Startverdi (self-hosted laster eksisterende config.yaml fra disk; hostet starter tomt).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  initial?: any;
  lagreEtikett?: string;
  // Valgfri tilleggsseksjon (f.eks. noter) som vises sist, rett før «Lagre data», slik at
  // den lagres sammen med resten av skjemaet i ett trykk.
  ekstraSeksjon?: React.ReactNode;
  // Hostet kjenner selskapet fra invitasjonen: org.nr forhåndsutfylles, låses i feltet, og
  // tvinges tilbake ved import/eksempeldata (innsending krever at config-org == kunde-org).
  laastOrg?: string;
  // Valgfri SAF-T-import: parser en opplastet SAF-T Financial-fil til config-form. Hver app
  // injiserer sin binding (self-hosted/hostet backend). Uten denne vises ikke SAF-T-knappen.
  // foregaaende=true => kun fjorårets sammenligningstall hentes (egen fil for fjoråret).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  importerSaft?: (file: File, foregaaende: boolean) => Promise<any>;
  // Valgfri merknad i SAF-T-modalen (hostet bruker den til personvern-info om EØS/ingen lagring).
  saftMerknad?: React.ReactNode;
  // Valgfri forhåndsfylling av styringsdata SAF-T ikke bærer (daglig leder, styreleder,
  // stiftelsesår) fra Enhetsregisteret. Hostet injiserer henteren; self-hosted lar den være.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  prefillSelskap?: () => Promise<any>;
  // Valgfritt forslag til skattekostnad: kjernen beregner 22 % av skattepliktig inntekt fra
  // tallene i skjemaet. Forslag, aldri auto-utfylling: brukeren fører selv tallet han signerer
  // på. Uten denne vises ikke forslags-knappen.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  beregnSkatt?: (config: any) => Promise<any>;
}) {
  const laasteFelter = laastOrg ? ["selskap.org_nummer"] : [];
  // Tving org til det låste selskapet (brukes ved start, Bodil-import og eksempeldata).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const medLaastOrg = (c: any): any =>
    laastOrg ? { ...c, selskap: { ...(c?.selskap ?? {}), org_nummer: laastOrg } } : c;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const startConfig = (): any => medLaastOrg(initial ?? grunnConfig());
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [config, setConfig] = useState<any>(startConfig);
  const [lagrer, setLagrer] = useState(false);
  const [visBodil, setVisBodil] = useState(false);
  const [importMelding, setImportMelding] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const filRef = useRef<HTMLInputElement>(null);
  const [visSaft, setVisSaft] = useState(false);
  const [saftMelding, setSaftMelding] = useState<string | null>(null);
  const [saftFeil, setSaftFeil] = useState(false);
  const [saftLaster, setSaftLaster] = useState(false);
  const [saftDrag, setSaftDrag] = useState<string | null>(null);
  const saftRef = useRef<HTMLInputElement>(null);
  const saftFjorRef = useRef<HTMLInputElement>(null);

  // Advar mot å forlate siden (logo-/tilbake-klikk, nettleser-tilbake, lukke fane) hvis
  // skjemaet har ulagret innhold, så en bruker ikke mister utfyllingen ved et uhell.
  // Baseline er startverdien (lastet config regnes ikke som «ulagret»).
  const pristine = useRef(JSON.stringify(startConfig()));
  const configRef = useRef(config);
  configRef.current = config;
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (JSON.stringify(configRef.current) !== pristine.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  // Forhåndsfyll styringsdata SAF-T ikke bærer (daglig leder, styreleder, stiftelsesår) fra
  // Enhetsregisteret ved kobling, kun der feltet står tomt, så det ikke overskriver noe brukeren
  // (eller en importert config) alt har fylt. Fail-soft: feiler oppslaget, forblir skjemaet tomt.
  // Forhåndsfyll teller ikke som ulagret endring (oppdaterer pristine), men må fortsatt lagres.
  useEffect(() => {
    if (!prefillSelskap) return;
    let avbrutt = false;
    prefillSelskap()
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .then((d: any) => {
        if (avbrutt || !d) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setConfig((c: any) => {
          const s = c.selskap ?? {};
          const oppdatert = {
            ...c,
            selskap: {
              ...s,
              navn: String(s.navn ?? "").trim() || d.navn || "",
              forretningsadresse:
                String(s.forretningsadresse ?? "").trim() || d.forretningsadresse || "",
              daglig_leder: String(s.daglig_leder ?? "").trim() || d.daglig_leder || "",
              styreleder: String(s.styreleder ?? "").trim() || d.styreleder || "",
              stiftelsesaar: Number(s.stiftelsesaar) || d.stiftelsesaar || 0,
              stiftelsesdato: String(s.stiftelsesdato ?? "").trim() || d.stiftelsesdato || "",
            },
          };
          pristine.current = JSON.stringify(oppdatert);
          return oppdatert;
        });
      })
      .catch(() => {});
    return () => {
      avbrutt = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const oppdater = (key: string, val: any) => setConfig((c: any) => sett(c, key, val));

  // Forslag til skattekostnad. Hentes kun når brukeren ber om det, og settes kun inn ved et
  // eksplisitt trykk: Wenche fastsetter ikke tallet, den regner det ut som hjelp.
  const [skattForslag, setSkattForslag] = useState<number | null>(null);
  const [skattLaster, setSkattLaster] = useState(false);
  const [skattFeil, setSkattFeil] = useState<string | null>(null);
  const hentSkattForslag = async () => {
    if (!beregnSkatt) return;
    setSkattLaster(true);
    setSkattFeil(null);
    try {
      const d = await beregnSkatt(normaliserForLagring(config));
      setSkattForslag(Number(d?.beregnet_skatt) || 0);
    } catch (e) {
      setSkattFeil(e instanceof Error ? e.message : "Klarte ikke å beregne skatten");
    } finally {
      setSkattLaster(false);
    }
  };

  const sumEiendeler = BALANSE_EIENDELER.reduce((s, k) => s + (Number(hent(config, k)) || 0), 0);
  const sumEkGjeld = BALANSE_EK_GJELD.reduce((s, k) => s + (Number(hent(config, k)) || 0), 0);
  const diff = sumEiendeler - sumEkGjeld;
  const balansererOk = Math.abs(diff) < 0.01;

  const aksjonaerer: Aksjonaer[] = config.aksjonaerer ?? [];
  const settAksj = (i: number, felt: keyof Aksjonaer, val: string | number) =>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    setConfig((c: any) => ({
      ...c,
      aksjonaerer: c.aksjonaerer.map((a: Aksjonaer, j: number) =>
        j === i ? { ...a, [felt]: val } : a,
      ),
    }));

  const lagre = async () => {
    setLagrer(true);
    try {
      await onLagre(normaliserForLagring(config));
      // Etter vellykket lagring er gjeldende innhold den nye baselinen.
      pristine.current = JSON.stringify(configRef.current);
    } finally {
      setLagrer(false);
    }
  };

  const importerBodil = async (file: File) => {
    setImportMelding(null);
    try {
      const parsed = yaml.load(await file.text());
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      if (!parsed || typeof parsed !== "object" || !(parsed as any).selskap) {
        setImportMelding("Dette ser ikke ut som en Wenche/Bodil config.yaml.");
        return;
      }
      setConfig(medLaastOrg(parsed));
      setVisBodil(false);
    } catch (e) {
      setImportMelding("Kunne ikke lese filen: " + (e as Error).message);
    }
  };

  // SAF-T mangler styringsdata (daglig leder, styreleder, stiftelsesår, aksjonærer). Behold
  // det brukeren allerede har fylt inn (eller hentet fra Bodil) i stedet for å blanke det.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const flettStyring = (saft: any, eks: any): any => {
    const s = eks?.selskap ?? {};
    return {
      ...saft,
      selskap: {
        ...saft.selskap,
        daglig_leder: saft.selskap?.daglig_leder || s.daglig_leder || "",
        styreleder: saft.selskap?.styreleder || s.styreleder || "",
        stiftelsesaar: saft.selskap?.stiftelsesaar || s.stiftelsesaar || 0,
        kontakt_epost: saft.selskap?.kontakt_epost || s.kontakt_epost || "",
      },
      aksjonaerer: saft.aksjonaerer?.length ? saft.aksjonaerer : (eks?.aksjonaerer ?? []),
    };
  };

  const importerSaftFil = async (file: File, foregaaende: boolean) => {
    if (!importerSaft) return;
    setSaftMelding(null);
    setSaftFeil(false);
    setSaftLaster(true);
    try {
      const data = await importerSaft(file, foregaaende);
      const aar = data?.regnskapsaar ? ` ${data.regnskapsaar}` : "";
      if (foregaaende) {
        // Kun fjorårets sammenligningstall: merge inn i gjeldende config, rør ikke resten.
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setConfig((c: any) => ({ ...c, foregaaende_aar: data.foregaaende_aar }));
        setSaftMelding(`Sammenligningstall for fjoråret importert fra SAF-T${aar}.`);
      } else {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setConfig((c: any) => medLaastOrg(flettStyring(data, c)));
        setSaftMelding(`Tall importert fra SAF-T${aar}. Se over og lagre.`);
      }
    } catch (e) {
      setSaftFeil(true);
      setSaftMelding("Kunne ikke importere SAF-T: " + (e as Error).message);
    } finally {
      setSaftLaster(false);
    }
  };

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className={monoLabel}>Steg 2 · Årets tall</p>
        <div className="flex items-center gap-4">
          <button
            className="text-xs font-medium text-spruce underline-offset-2 hover:underline"
            onClick={() => {
              setImportMelding(null);
              setVisBodil(true);
            }}
          >
            Hent tall fra Bodil
          </button>
          {importerSaft && (
            <button
              className="text-xs font-medium text-spruce underline-offset-2 hover:underline"
              onClick={() => {
                setSaftMelding(null);
                setSaftFeil(false);
                setVisSaft(true);
              }}
            >
              Importer fra SAF-T
            </button>
          )}
          {visEksempel && (
            <button
              className="text-xs text-muted-foreground underline-offset-2 hover:text-spruce hover:underline"
              onClick={() => setConfig(medLaastOrg(structuredClone(EKSEMPEL)))}
            >
              Fyll inn eksempeldata (test)
            </button>
          )}
        </div>
      </div>

      {visBodil && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 p-4"
          onClick={() => setVisBodil(false)}
        >
          <div
            className="w-full max-w-md rounded-sm border border-border bg-background p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <p className={monoLabel}>Hent tall fra Bodil</p>
            <h3 className="mt-2 font-display text-xl font-normal">Fører du regnskapet i Bodil?</h3>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Bodil er følgeverktøyet som fører regnskapet for passive holdingselskaper og lager
              en <code className="font-mono">config.yaml</code> med årets tall. Last den opp her,
              så fyller vi inn regnskapet for deg. Du ser over alt og sender som vanlig.
            </p>
            <div
              role="button"
              tabIndex={0}
              className={`mt-5 flex flex-col items-center justify-center rounded-sm border-2 border-dashed px-6 py-8 text-center transition ${
                dragOver ? "border-spruce bg-spruce-soft" : "border-border hover:border-spruce/60"
              }`}
              onClick={() => filRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  filRef.current?.click();
                }
              }}
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = e.dataTransfer.files?.[0];
                if (f) importerBodil(f);
              }}
            >
              <svg
                className="h-7 w-7 text-spruce"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 16V4m0 0L8 8m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                />
              </svg>
              <p className="mt-3 text-sm font-medium">
                Dra og slipp <code className="font-mono">config.yaml</code> her
              </p>
              <p className="mt-1 text-xs text-muted-foreground">eller</p>
              <button
                type="button"
                className={`${btnOutline} mt-2`}
                onClick={(e) => {
                  e.stopPropagation();
                  filRef.current?.click();
                }}
              >
                Velg fil
              </button>
              <input
                ref={filRef}
                type="file"
                accept=".yaml,.yml,.json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) importerBodil(f);
                }}
              />
            </div>
            {importMelding && <p className="mt-3 text-sm text-red-700">{importMelding}</p>}
            <div className="mt-6 flex items-center justify-between">
              <a
                href="https://github.com/olefredrik/Bodil"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-spruce underline-offset-2 hover:underline"
              >
                Hva er Bodil?
              </a>
              <button className={btnOutline} onClick={() => setVisBodil(false)}>
                Lukk
              </button>
            </div>
          </div>
        </div>
      )}

      {visSaft && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 p-4"
          onClick={() => setVisSaft(false)}
        >
          <div
            className="w-full max-w-md rounded-sm border border-border bg-background p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <p className={monoLabel}>Importer fra SAF-T</p>
            <h3 className="mt-2 font-display text-xl font-normal">Hent tall fra regnskapssystemet</h3>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
              Eksporter en SAF-T Financial-fil fra regnskapssystemet ditt (Fiken, Tripletex,
              Visma, PowerOffice m.fl.), så fyller jeg inn regnskap og balanse for deg. Du ser
              over alt og sender som vanlig.
            </p>

            {[
              {
                id: "naa",
                ref: saftRef,
                foregaaende: false,
                tittel: "Inneværende år",
                beskrivelse: "Fyller selskap, resultat og balanse for regnskapsåret.",
              },
              {
                id: "fjor",
                ref: saftFjorRef,
                foregaaende: true,
                tittel: "Foregående år (valgfritt)",
                beskrivelse:
                  "Egen SAF-T for fjoråret. Fyller kun sammenligningstallene (fjorårets resultatregnskap finnes ikke i årets fil).",
              },
            ].map((sone) => (
              <div key={sone.id} className="mt-5">
                <p className="text-sm font-medium">{sone.tittel}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{sone.beskrivelse}</p>
                <div
                  role="button"
                  tabIndex={0}
                  className={`mt-2 flex flex-col items-center justify-center rounded-sm border-2 border-dashed px-6 py-6 text-center transition ${
                    saftDrag === sone.id ? "border-spruce bg-spruce-soft" : "border-border hover:border-spruce/60"
                  } ${saftLaster ? "pointer-events-none opacity-60" : ""}`}
                  onClick={() => sone.ref.current?.click()}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      sone.ref.current?.click();
                    }
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setSaftDrag(sone.id);
                  }}
                  onDragLeave={() => setSaftDrag(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    setSaftDrag(null);
                    const f = e.dataTransfer.files?.[0];
                    if (f) importerSaftFil(f, sone.foregaaende);
                  }}
                >
                  <p className="text-sm">
                    Dra og slipp <code className="font-mono">.xml</code> her, eller{" "}
                    <span className="text-spruce underline-offset-2 hover:underline">velg fil</span>
                  </p>
                  <input
                    ref={sone.ref}
                    type="file"
                    accept=".xml,text/xml,application/xml"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) importerSaftFil(f, sone.foregaaende);
                      e.target.value = "";
                    }}
                  />
                </div>
              </div>
            ))}

            {saftLaster && <p className="mt-3 text-sm text-muted-foreground">Importerer…</p>}
            {saftMelding && (
              <p className={`mt-3 text-sm ${saftFeil ? "text-red-700" : "text-spruce"}`}>{saftMelding}</p>
            )}
            {saftMerknad && (
              <p className="mt-4 text-xs leading-relaxed text-muted-foreground">{saftMerknad}</p>
            )}
            <div className="mt-6 flex justify-end">
              <button className={btnOutline} onClick={() => setVisSaft(false)}>
                Lukk
              </button>
            </div>
          </div>
        </div>
      )}

      {SEKSJONER.map((s) => (
        <section key={s.tittel} id={s.id} className="scroll-mt-32">
          <h3 className="mb-4 font-display text-xl font-normal">{s.tittel}</h3>
          <Feltrutenett felter={s.felter} config={config} oppdater={oppdater} laasteFelter={laasteFelter} />
          {s.id === "resultatregnskap" && beregnSkatt && (
            <div className="mt-4 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <button className={btnOutline} onClick={hentSkattForslag} disabled={skattLaster}>
                  {skattLaster ? "Beregner…" : "Foreslå skattekostnad"}
                </button>
                {skattForslag !== null && (
                  <>
                    <span className="text-muted-foreground">
                      Beregnet skatt (22 %): {kr(skattForslag)}
                    </span>
                    <button
                      className="text-spruce underline underline-offset-2"
                      onClick={() => oppdater("resultatregnskap.skattekostnad", skattForslag)}
                    >
                      Sett inn
                    </button>
                  </>
                )}
              </div>
              {skattFeil && <p className="mt-2 text-red-700">{skattFeil}</p>}
              {skattForslag !== null && (
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  Forslaget er 22 % av skattepliktig inntekt slik Wenche beregner den, etter
                  fritaksmetoden og fremført underskudd. Det dekker ikke utsatt skatt eller andre
                  permanente forskjeller, så kontroller tallet før du fører det. Husk «Betalbar
                  skatt» under kortsiktig gjeld hvis skatten ikke er betalt ved årsslutt.
                </p>
              )}
            </div>
          )}
          {s.id === "balanse" && (
            <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
              <span className="text-muted-foreground">Sum eiendeler: {kr(sumEiendeler)}</span>
              <span className="text-muted-foreground">Sum EK + gjeld: {kr(sumEkGjeld)}</span>
              <span className={balansererOk ? "text-spruce" : "text-red-700"}>
                {balansererOk ? "Balansen går opp" : `Differanse: ${kr(diff)}`}
              </span>
            </div>
          )}
        </section>
      ))}

      <details id="fjoraaret" className="scroll-mt-32 border-t border-border pt-6">
        <summary className="cursor-pointer font-display text-xl font-normal">
          Fjorårets tall
        </summary>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Sammenligningstall for fjoråret, påkrevd etter regnskapsloven. Kan stå tomt kun
          hvis selskapet ble stiftet i dette regnskapsåret og ikke har et fjorår å
          sammenligne med. Importerer du fra Bodil, er disse allerede fylt inn.
        </p>
        <div className="mt-4">
          <Feltrutenett felter={FJORARET_FELTER} config={config} oppdater={oppdater} />
        </div>
      </details>

      <section id="aksjonaerer" className="scroll-mt-32">
        <h3 className="mb-4 font-display text-xl font-normal">Aksjonærer</h3>
        <div className="space-y-4">
          {aksjonaerer.map((a, i) => (
            <div key={i} className="rounded-sm border border-border bg-background p-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Inn label="Navn" value={a.navn} onChange={(v) => settAksj(i, "navn", v)} />
                <Inn label="Fødselsnummer" value={a.fodselsnummer} onChange={(v) => settAksj(i, "fodselsnummer", v)} />
                <TallFelt label="Antall aksjer" value={a.antall_aksjer} onChange={(v) => settAksj(i, "antall_aksjer", v)} />
                <Inn label="Aksjeklasse" value={a.aksjeklasse} onChange={(v) => settAksj(i, "aksjeklasse", v)} />
                <TallFelt label="Utbytte utbetalt (kr)" value={a.utbytte_utbetalt} onChange={(v) => settAksj(i, "utbytte_utbetalt", v)} />
                <TallFelt label="Innbetalt kapital per aksje (kr)" value={a.innbetalt_kapital_per_aksje} onChange={(v) => settAksj(i, "innbetalt_kapital_per_aksje", v)} />
              </div>
              {aksjonaerer.length > 1 && (
                <button
                  className="mt-3 text-xs text-muted-foreground underline-offset-2 hover:text-red-700 hover:underline"
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  onClick={() => setConfig((c: any) => ({ ...c, aksjonaerer: c.aksjonaerer.filter((_: Aksjonaer, j: number) => j !== i) }))}
                >
                  Fjern aksjonær
                </button>
              )}
            </div>
          ))}
        </div>
        <button
          className={`${btnOutline} mt-4`}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          onClick={() => setConfig((c: any) => ({ ...c, aksjonaerer: [...c.aksjonaerer, tomAksjonaer()] }))}
        >
          + Legg til aksjonær
        </button>
      </section>

      {ekstraSeksjon}

      <button className={btnPrimar} onClick={lagre} disabled={lagrer}>
        {lagrer ? "Lagrer…" : lagreEtikett}
      </button>
    </div>
  );
}
