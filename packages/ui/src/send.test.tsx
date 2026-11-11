import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { EKSEMPEL } from "./eksempel";
import { Resultatpanel, SendSeksjon, type InnsendingFn } from "./send";

describe("Resultatpanel", () => {
  it("viser dry-run-resultatet som OK eller avvik", () => {
    const { rerender } = render(
      <Resultatpanel utfall={{ dryRun: true, type: "aarsregnskap", data: { dry_run: true, ok: true, feil: [], advarsler: ["En merknad"] } }} />,
    );
    expect(screen.getByText("Validering OK, klar til innsending")).toBeTruthy();
    expect(screen.getByText("En merknad")).toBeTruthy();
    rerender(
      <Resultatpanel utfall={{ dryRun: true, type: "aarsregnskap", data: { dry_run: true, ok: false, feil: ["Balansen går ikke opp"], advarsler: [] } }} />,
    );
    expect(screen.getByText("Avvik som må rettes")).toBeTruthy();
    expect(screen.getByText("Balansen går ikke opp")).toBeTruthy();
  });

  it("viser signeringslenke for Altinn-instanser og kvittering for RF-1086", () => {
    const { rerender } = render(
      <Resultatpanel utfall={{ dryRun: false, type: "skattemelding", data: { sendt: true, resultat: "https://af.tt02.altinn.no/inbox", klage: true } }} />,
    );
    expect(screen.getByText("Venter på signatur")).toBeTruthy();
    expect(screen.getByText(/sendes som klage/)).toBeTruthy();
    expect((screen.getByText("Signer i Altinn →") as HTMLAnchorElement).href).toBe("https://af.tt02.altinn.no/inbox");
    rerender(
      <Resultatpanel
        utfall={{ dryRun: false, type: "aksjonaer", data: { sendt: true, resultat: { forsendelseId: "abc-123" } } }}
        env="test"
        org="312463938"
      />,
    );
    expect(screen.getByText("Sendt inn")).toBeTruthy();
    expect(screen.getByText("abc-123")).toBeTruthy();
    expect((screen.getByText("Åpne Altinn meldingsboks →") as HTMLAnchorElement).href).toContain("tt02.altinn.no");
  });

  it("viser feil som alert", () => {
    render(<Resultatpanel utfall={{ dryRun: false, type: "aarsregnskap", feil: "Altinn svarte 502" }} />);
    expect(screen.getByRole("alert").textContent).toContain("Altinn svarte 502");
  });
});

describe("SendSeksjon", () => {
  it("kontrollerer først, krever samtykke, og sender så på ekte", async () => {
    const innsending = vi.fn<InnsendingFn>(async (_type, dryRun) =>
      dryRun
        ? { dry_run: true, ok: true, feil: [], advarsler: [] }
        : { sendt: true, resultat: "https://af.tt02.altinn.no/inbox" },
    );
    render(<SendSeksjon config={EKSEMPEL} innsending={innsending} env="test" org="312463938" />);
    fireEvent.click(screen.getAllByText("Fortsett til innsending")[0]);
    expect(innsending).toHaveBeenLastCalledWith("aarsregnskap", true, EKSEMPEL);
    await screen.findByText(/Alt ser bra ut/);

    const send = screen.getByText("Bekreft og send inn") as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(send.disabled).toBe(false);
    fireEvent.click(send);
    await waitFor(() => expect(innsending).toHaveBeenLastCalledWith("aarsregnskap", false, EKSEMPEL, false));
    await screen.findByText("Venter på signatur");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("viser avvik fra kontrollen og lar ikke brukeren sende", async () => {
    const innsending = vi.fn<InnsendingFn>(async () => ({ dry_run: true, ok: false, feil: ["Balansen går ikke opp"], advarsler: [] }));
    render(<SendSeksjon config={EKSEMPEL} innsending={innsending} />);
    fireEvent.click(screen.getAllByText("Fortsett til innsending")[1]);
    await screen.findByText("Balansen går ikke opp");
    expect((screen.getByText("Bekreft og send inn") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("checkbox")).toBeNull();
  });
});
