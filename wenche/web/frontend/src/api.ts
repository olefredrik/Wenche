// Endepunkt-bindinger for self-hosted Wenche oppå den delte fetch-wrapperen.
import { req } from "@wenche/ui";

export const api = {
  health: () => req("/api/health"),
  updateCheck: () => req("/api/update-check"),

  hentConfig: () => req("/api/config"),
  lagreConfig: (config: unknown) =>
    req("/api/config", { method: "PUT", body: JSON.stringify(config) }),

  oppsettStatus: () => req("/api/oppsett/status"),
  lagreCredentials: (body: { client_id: string; kid: string; orgnr: string }) =>
    req("/api/oppsett/credentials", { method: "PUT", body: JSON.stringify(body) }),
  lagreNokkel: (pem: string) =>
    req("/api/oppsett/nokkel", { method: "POST", body: JSON.stringify({ pem }) }),
  testTilkobling: () => req("/api/oppsett/test-tilkobling", { method: "POST" }),
  registrerSystem: () => req("/api/oppsett/registrer-system", { method: "POST" }),
  opprettSystembruker: () => req("/api/oppsett/systembruker", { method: "POST" }),
  systembrukerStatus: () => req("/api/oppsett/systembruker/status", { method: "POST" }),
  oppdaterSystembruker: () => req("/api/oppsett/systembruker/oppdater", { method: "POST" }),

  frister: () => req("/api/frister"),
  sjekkFrister: () => req("/api/frister/sjekk", { method: "POST" }),

  dokument: (type: string, config: unknown) =>
    req(`/api/dokumenter/${type}`, { method: "POST", body: JSON.stringify(config) }),

  importerSaft: (file: File, foregaaende: boolean) =>
    req(`/api/saft/import?foregaaende=${foregaaende}`, {
      method: "POST",
      headers: { "Content-Type": "application/xml" },
      body: file,
    }),

  innsending: (type: string, dryRun: boolean, config: unknown) =>
    req(`/api/innsending/${type}?dry_run=${dryRun}`, {
      method: "POST",
      body: JSON.stringify(config),
    }),
};
