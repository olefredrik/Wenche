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
    const d = data?.detail;
    let melding = `Feil (HTTP ${res.status})`;
    if (typeof d === "string") melding = d;
    else if (d && typeof d === "object") {
      if (Array.isArray(d.feil)) melding = d.feil.join(" · ");
      else if (d.validering) melding = String(d.validering);
    }
    throw new Error(melding);
  }
  return data;
}

export const api = {
  me: () => req("/api/auth/me"),
  invite: (token: string) =>
    req("/api/auth/invite", { method: "POST", body: JSON.stringify({ token }) }),
  logout: () => req("/api/auth/logout", { method: "POST" }),
  systembrukerRequest: () => req("/api/systembruker/request", { method: "POST" }),
  putData: (config: unknown) =>
    req("/api/data", { method: "PUT", body: JSON.stringify(config) }),
  innsending: (type: string, dryRun: boolean) =>
    req(`/api/innsending/${type}?dry_run=${dryRun}`, { method: "POST" }),
};
