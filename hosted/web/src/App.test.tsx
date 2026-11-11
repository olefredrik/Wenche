import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Me } from "./typer";

// Appen røyktestes mot et mocket API: gaten uten invitasjon, tilkoblingsskjermen med, og
// et lesbart varsel når tjenesten ikke svarer.
const me = vi.fn<() => Promise<Me>>();
vi.mock("./api", () => ({
  api: {
    me: () => me(),
    invite: vi.fn(),
    handoffUse: vi.fn(),
    logout: vi.fn(),
  },
}));

import App from "./App";

beforeEach(() => {
  me.mockReset();
  window.history.replaceState({}, "", "/");
});

describe("hostet App", () => {
  it("viser gaten med kontaktvei når økten ikke er invitert og ID-porten er av", async () => {
    me.mockResolvedValue({ invited: false, idporten: false, kontakt: "mailto:hei@eksempel.no" });
    render(<App />);
    await screen.findByText("Logg inn");
    expect(screen.getByText("hei@eksempel.no")).toBeTruthy();
    expect(screen.queryByText("Hjem")).toBeNull();
  });

  it("viser tilkoblingsskjermen for en invitert, ukoblet økt", async () => {
    me.mockResolvedValue({ invited: true, invite_org: "312463938", env: "test", demo: true });
    render(<App />);
    await screen.findByText("Koble til selskapet ditt");
    expect(screen.getByText("312463938")).toBeTruthy();
    expect(screen.getByText(/Demo mot Altinns testmiljø/)).toBeTruthy();
  });

  it("sier fra når tjenesten ikke svarer, i stedet for å late som om ingen er invitert", async () => {
    me.mockRejectedValue(new Error("nede"));
    render(<App />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Fikk ikke kontakt med Wenche");
  });
});
