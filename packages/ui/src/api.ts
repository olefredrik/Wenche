// Delt, tynn fetch-wrapper mot en same-origin JSON-backend. Hver app bygger sine egne
// endepunkt-bindinger oppå denne (hostet: invite/systembruker; self-hosted: oppsett/frister).

export interface ApiFeil extends Error {
  status?: number;
}

export async function req(path: string, opts: RequestInit = {}): Promise<any> {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const tekst = await res.text();
  // Tål ikke-JSON-svar (f.eks. en 500 «Internal Server Error» eller en proxy-feilside),
  // ellers ville JSON.parse kastet en kryptisk «Unexpected identifier»-feil til brukeren.
  let data: any = null;
  try {
    data = tekst ? JSON.parse(tekst) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const d = data?.detail;
    let melding = `Feil (HTTP ${res.status})`;
    if (typeof d === "string") melding = d;
    else if (d && typeof d === "object") {
      if (Array.isArray(d.feil)) melding = d.feil.join(" · ");
      else if (d.validering) melding = String(d.validering);
    }
    const err = new Error(melding) as ApiFeil;
    err.status = res.status;
    throw err;
  }
  return data;
}
