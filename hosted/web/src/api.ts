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
  // Fortsett på en annen enhet: en koblet økt lager en kortvarig overføringslenke (QR),
  // den nye enheten løser den inn og arver bindingen.
  handoffCreate: () => req("/api/auth/handoff/create", { method: "POST" }),
  handoffUse: (token: string) =>
    req("/api/auth/handoff/use", { method: "POST", body: JSON.stringify({ token }) }),
  logout: () => req("/api/auth/logout", { method: "POST" }),
  systembrukerRequest: () => req("/api/systembruker/request", { method: "POST" }),
  systembrukerStatus: () => req("/api/systembruker/status", { method: "POST" }),
  // Forhåndsfyll: daglig leder, styreleder og stiftelsesår fra Enhetsregisteret for den koblede
  // orgen (offentlige data, lagres ikke). SAF-T bærer ikke disse feltene, så uten dette må de
  // skrives manuelt etter import.
  selskap: () => req("/api/selskap"),
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
