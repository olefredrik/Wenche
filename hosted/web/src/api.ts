// Hostet-spesifikke endepunkt-bindinger oppå den delte fetch-wrapperen. Same-origin i dev
// via Vite-proxy, så cookies (sesjon) følger med uten CORS-styr.
import { req } from "@wenche/ui";

export const api = {
  me: () => req("/api/auth/me"),
  invite: (token: string) =>
    req("/api/auth/invite", { method: "POST", body: JSON.stringify({ token }) }),
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
};
