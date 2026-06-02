// Hostet-spesifikke endepunkt-bindinger oppå den delte fetch-wrapperen. Same-origin i dev
// via Vite-proxy, så cookies (sesjon) følger med uten CORS-styr.
import { req } from "@wenche/ui";

export const api = {
  me: () => req("/api/auth/me"),
  invite: (token: string) =>
    req("/api/auth/invite", { method: "POST", body: JSON.stringify({ token }) }),
  // Selvbetjent tilgang: navn + orgnr verifiseres mot Enhetsregisteret. Navnet lagres ikke.
  beOmTilgang: (navn: string, org: string) =>
    req("/api/auth/be-om-tilgang", { method: "POST", body: JSON.stringify({ navn, org }) }),
  logout: () => req("/api/auth/logout", { method: "POST" }),
  systembrukerRequest: () => req("/api/systembruker/request", { method: "POST" }),
  systembrukerStatus: () => req("/api/systembruker/status", { method: "POST" }),
  // Config sendes i body (klienten er fasit), så en sovende/restartende server ikke kan
  // miste utfyllingen. Ingen server-side datalagring mellom kall.
  innsending: (type: string, dryRun: boolean, config: unknown) =>
    req(`/api/innsending/${type}?dry_run=${dryRun}`, {
      method: "POST",
      body: JSON.stringify(config),
    }),
  // Genererer dokumenter for nedlasting/gjennomgang (ingenting sendes inn).
  dokument: (type: string, config: unknown) =>
    req(`/api/dokumenter/${type}`, { method: "POST", body: JSON.stringify(config) }),
  // Parser en opplastet SAF-T i minnet (lagres ikke) og returnerer config for forhåndsfylling.
  importerSaft: (file: File, foregaaende: boolean) =>
    req(`/api/saft/import?foregaaende=${foregaaende}`, {
      method: "POST",
      headers: { "Content-Type": "application/xml" },
      body: file,
    }),
};
