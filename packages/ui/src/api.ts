// Delt, tynn fetch-wrapper mot en same-origin JSON-backend, pluss endepunkt-bindingene begge
// appene har felles (dokumenter, SAF-T, innsending). Hver app legger sine egne oppå
// (hostet: invite/systembruker; self-hosted: oppsett/frister).
import type {
  Config,
  FilerSvar,
  InnsendingResultat,
  SaftImportSvar,
  SkatteberegningSvar,
} from "./typer";

export interface ApiFeil extends Error {
  status?: number;
}

// Meldingen fra et kastet unntak, til visning. Alt vi kaster selv er Error, men en
// tredjepartsfeil kan være hva som helst.
export function feilmelding(e: unknown, standard = "Noe gikk galt"): string {
  return e instanceof Error && e.message ? e.message : standard;
}

export async function req<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...opts,
    headers: {
      "Content-Type": "application/json",
      // Self-hosted-backenden krever denne på alle endringskall (wenche/web/backend/vakt.py):
      // en egendefinert header tvinger CORS-preflight, så et fremmed nettsted ikke kan kalle den
      // lokale serveren. Hostet ignorerer den. Må stå etter ...opts, ellers ville et opts.headers
      // erstatte hele objektet og miste både Content-Type og denne.
      "X-Wenche-Klient": "1",
      ...(opts.headers || {}),
    },
  });
  const tekst = await res.text();
  // Tål ikke-JSON-svar (f.eks. en 500 «Internal Server Error» eller en proxy-feilside),
  // ellers ville JSON.parse kastet en kryptisk «Unexpected identifier»-feil til brukeren.
  let data: unknown = null;
  try {
    data = tekst ? JSON.parse(tekst) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const err = new Error(meldingFraFeilsvar(data, res.status)) as ApiFeil;
    err.status = res.status;
    throw err;
  }
  return data as T;
}

// Backendens feilsvar er {"detail": tekst | {"feil": [...]} | {"validering": tekst}} (FastAPI
// HTTPException). Uten noe lesbart faller vi tilbake på statuskoden.
export function meldingFraFeilsvar(data: unknown, status: number): string {
  const d = (data as { detail?: unknown } | null)?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    const o = d as { feil?: unknown; validering?: unknown };
    if (Array.isArray(o.feil)) return o.feil.map(String).join(" · ");
    if (o.validering) return String(o.validering);
  }
  return `Feil (HTTP ${status})`;
}

// Endepunktene begge appene deler (samme URL-er i begge backendene, via wenche/web/felles).
export function lagFellesApi() {
  return {
    // Config sendes i body (klienten er fasit). bekreftKlage: brukeren har bekreftet at
    // skattemeldingen sendes som klage på skjønnsfastsetting (backend svarer
    // krever_bekreftelse uten å sende før det).
    innsending: (type: string, dryRun: boolean, config: Config, bekreftKlage = false) =>
      req<InnsendingResultat>(
        `/api/innsending/${type}?dry_run=${dryRun}${bekreftKlage ? "&bekreft_klage=true" : ""}`,
        { method: "POST", body: JSON.stringify(config) },
      ),
    // Genererer dokumenter for nedlasting/gjennomgang (ingenting sendes inn).
    dokument: (type: string, config: Config) =>
      req<FilerSvar>(`/api/dokumenter/${type}`, { method: "POST", body: JSON.stringify(config) }),
    // Forslag til skattekostnad, beregnet av kjernen fra tallene i skjemaet.
    skatteberegning: (config: Config) =>
      req<SkatteberegningSvar>("/api/dokumenter/skatteberegning", {
        method: "POST",
        body: JSON.stringify(config),
      }),
    // Parser en opplastet SAF-T i minnet (lagres ikke) og returnerer config for forhåndsfylling.
    importerSaft: (file: File, foregaaende: boolean) =>
      req<SaftImportSvar>(`/api/saft/import?foregaaende=${foregaaende}`, {
        method: "POST",
        headers: { "Content-Type": "application/xml" },
        body: file,
      }),
  };
}

export type FellesApi = ReturnType<typeof lagFellesApi>;
