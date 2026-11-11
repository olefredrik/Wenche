import { afterEach, describe, expect, it, vi } from "vitest";
import { feilmelding, lagFellesApi, meldingFraFeilsvar, req, type ApiFeil } from "./api";

function svar(status: number, kropp: string) {
  return { ok: status >= 200 && status < 300, status, text: async () => kropp };
}

type Fetch = (url: string, init?: RequestInit) => Promise<ReturnType<typeof svar>>;
const fetchSom = (status: number, kropp: string) => vi.fn<Fetch>(async () => svar(status, kropp));

afterEach(() => vi.unstubAllGlobals());

describe("meldingFraFeilsvar", () => {
  it("plukker teksten ut av FastAPI-formene backendene svarer med", () => {
    expect(meldingFraFeilsvar({ detail: "Wenche er kun for inviterte." }, 401)).toBe(
      "Wenche er kun for inviterte.",
    );
    expect(meldingFraFeilsvar({ detail: { feil: ["a", "b"] } }, 422)).toBe("a · b");
    expect(meldingFraFeilsvar({ detail: { validering: "validertMedFeil" } }, 422)).toBe("validertMedFeil");
    expect(meldingFraFeilsvar(null, 500)).toBe("Feil (HTTP 500)");
    expect(meldingFraFeilsvar({ detail: { noe: 1 } }, 418)).toBe("Feil (HTTP 418)");
  });
});

describe("req", () => {
  it("sender klientheaderen, JSON-typen og egne headere, og parser svaret", async () => {
    const fetchMock = fetchSom(200, '{"ok": true}');
    vi.stubGlobal("fetch", fetchMock);
    const data = await req<{ ok: boolean }>("/api/x", {
      method: "POST",
      headers: { "Content-Type": "application/xml" },
    });
    expect(data).toEqual({ ok: true });
    const init = fetchMock.mock.calls[0][1]!;
    expect(init.credentials).toBe("same-origin");
    expect(init.headers).toMatchObject({
      "X-Wenche-Klient": "1",
      "Content-Type": "application/xml", // egne headere vinner, klientheaderen beholdes
    });
  });

  it("kaster ApiFeil med lesbar melding og status ved feilsvar, også uten JSON", async () => {
    vi.stubGlobal("fetch", fetchSom(422, '{"detail": {"feil": ["Balansen går ikke opp"]}}'));
    await expect(req("/api/x")).rejects.toMatchObject({ message: "Balansen går ikke opp", status: 422 });

    vi.stubGlobal("fetch", fetchSom(502, "Bad Gateway"));
    const e = (await req("/api/x").catch((e: ApiFeil) => e)) as ApiFeil;
    expect(e.message).toBe("Feil (HTTP 502)");
    expect(e.status).toBe(502);
  });

  it("tåler tomt svar", async () => {
    vi.stubGlobal("fetch", fetchSom(200, ""));
    expect(await req("/api/x")).toBeNull();
  });
});

describe("lagFellesApi", () => {
  it("treffer de delte endepunktene med riktige parametre", async () => {
    const fetchMock = fetchSom(200, '{"dry_run": true, "ok": true, "feil": [], "advarsler": []}');
    vi.stubGlobal("fetch", fetchMock);
    const api = lagFellesApi();
    await api.innsending("skattemelding", false, { a: 1 }, true);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/innsending/skattemelding?dry_run=false&bekreft_klage=true");
    await api.dokument("noter", { a: 1 });
    expect(fetchMock.mock.calls[1][0]).toBe("/api/dokumenter/noter");
    await api.importerSaft(new File(["<x/>"], "saft.xml"), true);
    expect(fetchMock.mock.calls[2][0]).toBe("/api/saft/import?foregaaende=true");
    expect(fetchMock.mock.calls[2][1]!.headers).toMatchObject({
      "Content-Type": "application/xml",
    });
  });
});

describe("feilmelding", () => {
  it("bruker meldingen fra Error og standardteksten ellers", () => {
    expect(feilmelding(new Error("x"))).toBe("x");
    expect(feilmelding("rar feil")).toBe("Noe gikk galt");
    expect(feilmelding(new Error(""), "Tomt")).toBe("Tomt");
  });
});
