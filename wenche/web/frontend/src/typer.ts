// Typene for den self-hostede appens egne endepunkter (wenche/web/backend/ruter_*.py).
// De delte svarene (innsending, dokumenter, SAF-T) kommer fra @wenche/ui.
import type { Config, Fane } from "@wenche/ui";

export type FaneId = "hjem" | "oppsett" | "tall" | "dokumenter" | "send";

// Hjem er dashboardet (oversikt/frister); de fire arbeidsstegene nummereres 1-4 for å vise
// at de gjennomgås i sekvens.
export const FANER: Fane[] = [
  { id: "hjem", navn: "Hjem" },
  { id: "oppsett", navn: "Oppsett", steg: 1 },
  { id: "tall", navn: "Tall", steg: 2 },
  { id: "dokumenter", navn: "Dokumenter", steg: 3 },
  { id: "send", navn: "Send", steg: 4 },
];

export interface UpdateInfo {
  naavaerende: string;
  siste: string | null;
  nyere: boolean;
  fra_git: boolean;
}

export interface ConfigSvar {
  config: Config | null;
  fil: string;
  env: string;
}

export interface LagreConfigSvar {
  ok: boolean;
  fil: string;
}

export interface OppsettStatus {
  env: string;
  credentials: { client_id: string; kid: string; orgnr: string; mangler: string[]; komplett: boolean };
  nokkel: { ok: boolean; sti: string };
  systembruker: { har_forespoersel: boolean; confirm_url: string | null };
}

// Tilstanden til systembruker-koblingen, utledet av status-kallet mot Altinn.
export type SysState = "laster" | "godkjent" | "venter" | "avvist" | "ikke_opprettet" | "ukjent";

export interface SystembrukerSvar {
  status?: string;
  melding?: string;
  confirm_url?: string | null;
  request_id?: string;
  oppdatert?: boolean;
}

export interface TestTilkoblingSvar {
  auth_ok: boolean;
  melding: string;
  systembruker?: { status?: string; melding?: string };
}

export interface Frist {
  key: string;
  tittel: string;
  undertittel: string;
  maaned: number;
  dag: number;
  beskrivelse: string;
  auto_sjekk: boolean;
  neste_frist: string;
}

export interface FristStatus {
  innfridd: boolean;
  tidspunkt?: string | null;
  beskrivelse?: string;
  brukertekst?: string;
  lenke?: string | null;
  referanse?: string | null;
  referanse_etikett?: string;
}

export interface FristerSvar {
  env: string;
  statussjekk_aktiv: boolean;
  frister: Frist[];
}

export interface SjekkSvar {
  statuser: Record<string, FristStatus>;
}
