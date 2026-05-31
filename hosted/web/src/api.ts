// Tynn API-klient mot den hostede FastAPI-backenden. Same-origin i dev via Vite-proxy,
// så cookies (sesjon) følger med uten CORS-styr.

async function req(path: string, opts: RequestInit = {}): Promise<any> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const tekst = await res.text();
  const data = tekst ? JSON.parse(tekst) : null;
  if (!res.ok) {
    const melding =
      typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`;
    throw new Error(melding);
  }
  return data;
}

export const api = {
  me: () => req("/api/auth/me"),
  requestLink: (epost: string) =>
    req("/api/auth/request-link", { method: "POST", body: JSON.stringify({ epost }) }),
  logout: () => req("/api/auth/logout", { method: "POST" }),
  systembrukerRequest: (org: string) =>
    req("/api/systembruker/request", { method: "POST", body: JSON.stringify({ org }) }),
  putData: (config: unknown) =>
    req("/api/data", { method: "PUT", body: JSON.stringify(config) }),
  innsending: (type: string, dryRun: boolean) =>
    req(`/api/innsending/${type}?dry_run=${dryRun}`, { method: "POST" }),
};
