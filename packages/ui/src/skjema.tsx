import { useEffect, useRef, useState } from "react";
import yaml from "js-yaml";
import { monoLabel, input, btnPrimar, btnOutlineLett as btnOutline } from "./styles";
import { Inn } from "./komponenter";

// Skjema-drevet datainntasting. Feltstrukturen er data; én generisk renderer bygger
// config-objektet (samme form som config.yaml) som sendes til backenden.

type FeltType = "number" | "text" | "checkbox";
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
      { key: "selskap.aksjekapital", label: "Aksjekapital (kr)", type: "number" },
      { key: "selskap.kontakt_epost", label: "Kontakt-e-post", type: "text" },
      { key: "regnskapsaar", label: "Regnskapsår", type: "number" },
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
  antall_aksjer: number;
  aksjeklasse: string;
  utbytte_utbetalt: number;
  innbetalt_kapital_per_aksje: number;
}

function tomAksjonaer(): Aksjonaer {
  return {
    navn: "",
    fodselsnummer: "",
    antall_aksjer: 0,
    aksjeklasse: "ordinære",
    utbytte_utbetalt: 0,
    innbetalt_kapital_per_aksje: 0,
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function grunnConfig(): any {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let c: any = {};
  for (const s of SEKSJONER)
    for (const f of s.felter)
      if (!f.valgfri)
        c = sett(c, f.key, f.type === "checkbox" ? false : f.type === "text" ? "" : 0);
  c.aksjonaerer = [tomAksjonaer()];
  return c;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const EKSEMPEL: any = {
  selskap: {
    navn: "KORREKT FRISK TIGER AS",
    org_nummer: "314273818",
    daglig_leder: "Daglig Leder",
    styreleder: "Daglig Leder",
    forretningsadresse: "Bergveien 23, 1890 RAKKESTAD",
    stiftelsesaar: 2018,
    aksjekapital: 30000,
    kontakt_epost: "test@example.no",
  },
  regnskapsaar: 2024,
  resultatregnskap: {
    driftsinntekter: { salgsinntekter: 0, andre_driftsinntekter: 0 },
    driftskostnader: { loennskostnader: 0, avskrivninger: 0, andre_driftskostnader: 0 },
    finansposter: {
      utbytte_fra_datterselskap: 0,
      andre_finansinntekter: 0,
      rentekostnader: 0,
      andre_finanskostnader: 0,
    },
  },
  balanse: {
    eiendeler: {
      anleggsmidler: { aksjer_i_datterselskap: 0, andre_aksjer: 0, langsiktige_fordringer: 0 },
      omloepmidler: { kortsiktige_fordringer: 0, bankinnskudd: 30000 },
    },
    egenkapital_og_gjeld: {
      egenkapital: { aksjekapital: 30000, overkursfond: 0, annen_egenkapital: 0 },
      langsiktig_gjeld: { laan_fra_aksjonaer: 0, andre_langsiktige_laan: 0 },
      kortsiktig_gjeld: {
        leverandoergjeld: 0,
        skyldige_offentlige_avgifter: 0,
        annen_kortsiktig_gjeld: 0,
      },
    },
  },
  skattemelding: {
    underskudd_til_fremfoering: 0,
    anvend_fritaksmetoden: false,
    boersnotert: false,
    formuesverdi_aksjer: 0,
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

function Feltrutenett({
  felter,
  config,
  oppdater,
}: {
  felter: Felt[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  oppdater: (key: string, val: any) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {felter.map((f) =>
        f.type === "checkbox" ? (
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
            <input
              className={input}
              type={f.type === "number" ? "number" : "text"}
              value={hent(config, f.key) ?? ""}
              onChange={(e) =>
                oppdater(f.key, f.type === "number" ? Number(e.target.value) || 0 : e.target.value)
              }
            />
          </label>
        ),
      )}
    </div>
  );
}

export function DataSkjema({
  onLagre,
  visEksempel = false,
  initial,
  lagreEtikett = "Lagre data",
}: {
  onLagre: (config: unknown) => Promise<void>;
  visEksempel?: boolean;
  // Startverdi (self-hosted laster eksisterende config.yaml fra disk; hostet starter tomt).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  initial?: any;
  lagreEtikett?: string;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [config, setConfig] = useState<any>(() => initial ?? grunnConfig());
  const [lagrer, setLagrer] = useState(false);
  const [visBodil, setVisBodil] = useState(false);
  const [importMelding, setImportMelding] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const filRef = useRef<HTMLInputElement>(null);

  // Advar mot å forlate siden (logo-/tilbake-klikk, nettleser-tilbake, lukke fane) hvis
  // skjemaet har ulagret innhold, så en bruker ikke mister utfyllingen ved et uhell.
  // Baseline er startverdien (lastet config regnes ikke som «ulagret»).
  const pristine = useRef(JSON.stringify(initial ?? grunnConfig()));
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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const oppdater = (key: string, val: any) => setConfig((c: any) => sett(c, key, val));

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
      await onLagre(config);
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
      setConfig(parsed);
      setVisBodil(false);
    } catch (e) {
      setImportMelding("Kunne ikke lese filen: " + (e as Error).message);
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
          {visEksempel && (
            <button
              className="text-xs text-muted-foreground underline-offset-2 hover:text-spruce hover:underline"
              onClick={() => setConfig(structuredClone(EKSEMPEL))}
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

      {SEKSJONER.map((s) => (
        <section key={s.tittel} id={s.id} className="scroll-mt-32">
          <h3 className="mb-4 font-display text-xl font-normal">{s.tittel}</h3>
          <Feltrutenett felter={s.felter} config={config} oppdater={oppdater} />
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
                <Inn label="Antall aksjer" type="number" value={a.antall_aksjer} onChange={(v) => settAksj(i, "antall_aksjer", Number(v) || 0)} />
                <Inn label="Aksjeklasse" value={a.aksjeklasse} onChange={(v) => settAksj(i, "aksjeklasse", v)} />
                <Inn label="Utbytte utbetalt (kr)" type="number" value={a.utbytte_utbetalt} onChange={(v) => settAksj(i, "utbytte_utbetalt", Number(v) || 0)} />
                <Inn label="Innbetalt kapital per aksje (kr)" type="number" value={a.innbetalt_kapital_per_aksje} onChange={(v) => settAksj(i, "innbetalt_kapital_per_aksje", Number(v) || 0)} />
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

      <button className={btnPrimar} onClick={lagre} disabled={lagrer}>
        {lagrer ? "Lagrer…" : lagreEtikett}
      </button>
    </div>
  );
}
