// Rene funksjoner over config-objektet: lese og skrive punkt-stier, normalisere før lagring,
// oppsummere til bekreft-modalen. Ingen React her, så de kan testes rett fram (vitest).
import {
  BALANSE_EIENDELER,
  BALANSE_EK_GJELD,
  PAAKREVDE_TALLFELT,
  SEKSJONER,
} from "./felter";
import type { Config } from "./typer";

export interface Aksjonaer {
  navn: string;
  fodselsnummer: string;
  // Tallfeltene kan stå tomme ("") under redigering, så brukeren slipper å slette en ledende 0.
  // Normaliseres til tall ved lagring (se normaliserForLagring).
  antall_aksjer: number | "";
  aksjeklasse: string;
  utbytte_utbetalt: number | "";
  innbetalt_kapital_per_aksje: number | "";
}

export const AKSJONAER_TALLFELT = [
  "antall_aksjer",
  "utbytte_utbetalt",
  "innbetalt_kapital_per_aksje",
] as const;

export function tomAksjonaer(): Aksjonaer {
  return {
    navn: "",
    fodselsnummer: "",
    antall_aksjer: "",
    aksjeklasse: "ordinære",
    utbytte_utbetalt: "",
    innbetalt_kapital_per_aksje: "",
  };
}

export function hent(obj: Config | null | undefined, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o == null ? undefined : (o as Config)[k]), obj);
}

export function sett(obj: Config, path: string, value: unknown): Config {
  const keys = path.split(".");
  const ny: Config = { ...obj };
  let cur: Config = ny;
  for (let i = 0; i < keys.length - 1; i++) {
    cur[keys[i]] = { ...(cur[keys[i]] ?? {}) };
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
  return ny;
}

// Tomt tallfelt ("", null, NaN) → true. Valgfrie felt får stå tomme (kjernen tolererer dem),
// men påkrevde felt og aksjonær-tall må gjøres om til 0 før innsending.
export function erTomtTall(v: unknown): boolean {
  return v === "" || v == null || (typeof v === "number" && Number.isNaN(v));
}

// Gjør blanke påkrevde tallfelt om til 0 rett før lagring/innsending, slik at payloaden er
// identisk med den gamle (der feltene alltid var 0). Rører ikke valgfrie felt eller tekst.
export function normaliserForLagring(config: Config): Config {
  let c = config;
  for (const key of PAAKREVDE_TALLFELT) if (erTomtTall(hent(c, key))) c = sett(c, key, 0);
  const aksjonaerer = ((config?.aksjonaerer ?? []) as Aksjonaer[]).map((a) => {
    const na: Aksjonaer = { ...a };
    for (const f of AKSJONAER_TALLFELT) if (erTomtTall(na[f])) na[f] = 0;
    return na;
  });
  return { ...c, aksjonaerer };
}

// Tomt skjema: tallfelt starter tomme ("") slik at brukeren slipper å slette en ledende 0.
// De normaliseres tilbake til tall ved lagring (normaliserForLagring).
export function grunnConfig(): Config {
  let c: Config = {};
  for (const s of SEKSJONER)
    for (const f of s.felter)
      if (!f.valgfri) c = sett(c, f.key, f.type === "checkbox" ? false : "");
  c.aksjonaerer = [tomAksjonaer()];
  return c;
}

// Tving org til det låste selskapet (hostet: org fra invitasjonen).
export function medLaastOrg(c: Config, laastOrg?: string): Config {
  return laastOrg ? { ...c, selskap: { ...(c?.selskap ?? {}), org_nummer: laastOrg } } : c;
}

// SAF-T mangler styringsdata (daglig leder, styreleder, stiftelsesår, aksjonærer). Behold
// det brukeren allerede har fylt inn (eller hentet fra Bodil) i stedet for å blanke det.
export function flettStyring(saft: Config, eks: Config | null | undefined): Config {
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
}

export function kr(n: number): string {
  return (Number(n) || 0).toLocaleString("nb-NO") + " kr";
}

export interface Oppsummering {
  navn: string;
  org: string;
  aar: string | number;
  balanseDiff: number;
  balansererOk: boolean;
  antallAksjonaerer: number;
}

export function sumBalanse(config: Config | null | undefined): { eiendeler: number; ekGjeld: number } {
  const eiendeler = BALANSE_EIENDELER.reduce((s, k) => s + (Number(hent(config, k)) || 0), 0);
  const ekGjeld = BALANSE_EK_GJELD.reduce((s, k) => s + (Number(hent(config, k)) || 0), 0);
  return { eiendeler, ekGjeld };
}

export function oppsummer(config: Config): Oppsummering {
  const { eiendeler, ekGjeld } = sumBalanse(config);
  return {
    navn: String(hent(config, "selskap.navn") || ""),
    org: String(hent(config, "selskap.org_nummer") || ""),
    aar: (hent(config, "regnskapsaar") as string | number) || "",
    balanseDiff: eiendeler - ekGjeld,
    balansererOk: Math.abs(eiendeler - ekGjeld) < 0.01,
    antallAksjonaerer: (config.aksjonaerer ?? []).length,
  };
}

// Sann når de grunnleggende selskapsopplysningene er fylt inn. Brukes til å gate «Gå videre»
// fra Tall-steget, så man ikke havner på en tom Dokumenter-/Send-side.
export function harMinimumsdata(config: Config | null | undefined): boolean {
  if (!config) return false;
  const s = config.selskap ?? {};
  const utfylt = (k: string) => String(s[k] ?? "").trim() !== "";
  // Navn + org alltid; daglig leder ELLER styreleder. Passive holdingselskaper har ofte ingen
  // daglig leder, og da står styrelederen som bekreftende representant i årsregnskapet.
  return utfylt("navn") && utfylt("org_nummer") && (utfylt("daglig_leder") || utfylt("styreleder"));
}
