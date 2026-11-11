import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DataSkjema } from "./skjema";
import type { Config } from "./typer";

describe("DataSkjema", () => {
  it("viser feilen når lagringen feiler, i stedet for å svelge den", async () => {
    render(<DataSkjema onLagre={async () => { throw new Error("Disken er full"); }} />);
    fireEvent.click(screen.getByText("Lagre data"));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Kunne ikke lagre");
    expect(alert.textContent).toContain("Disken er full");
  });

  it("melder ulagrede endringer, og nullstiller dem etter lagring", async () => {
    const onUlagret = vi.fn();
    const onLagre = vi.fn<(c: Config) => Promise<void>>(async () => {});
    render(<DataSkjema onLagre={onLagre} onUlagret={onUlagret} visEksempel />);
    expect(onUlagret).toHaveBeenLastCalledWith(false);
    fireEvent.click(screen.getByText("Fyll inn eksempeldata (test)"));
    expect(onUlagret).toHaveBeenLastCalledWith(true);
    fireEvent.click(screen.getByText("Lagre data"));
    await waitFor(() => expect(onLagre).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onUlagret).toHaveBeenLastCalledWith(false));
    // Lagret med eksempeldataene, normalisert til tall.
    const lagret = onLagre.mock.calls[0][0];
    expect(lagret.selskap.org_nummer).toBe("312463938");
    expect(lagret.regnskapsaar).toBe(2025);
  });

  it("låser org.nr. til invitasjonen, også når eksempeldata fylles inn", () => {
    render(<DataSkjema onLagre={async () => {}} visEksempel laastOrg="999999999" />);
    const org = screen.getByLabelText(/Organisasjonsnummer/) as HTMLInputElement;
    expect(org.value).toBe("999999999");
    expect(org.disabled).toBe(true);
    fireEvent.click(screen.getByText("Fyll inn eksempeldata (test)"));
    expect(org.value).toBe("999999999");
  });

  it("åpner Bodil-importen som en dialog og lukker den igjen", () => {
    render(<DataSkjema onLagre={async () => {}} />);
    fireEvent.click(screen.getByText("Hent tall fra Bodil"));
    expect(screen.getByRole("dialog", { name: /Fører du regnskapet i Bodil/ })).toBeTruthy();
    fireEvent.click(screen.getByText("Lukk"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("legger til og fjerner aksjonærer med stabile rader", () => {
    render(<DataSkjema onLagre={async () => {}} />);
    fireEvent.click(screen.getByText("+ Legg til aksjonær"));
    const navn = screen.getAllByLabelText("Navn") as HTMLInputElement[];
    expect(navn).toHaveLength(2);
    fireEvent.change(navn[1], { target: { value: "Nummer to" } });
    fireEvent.click(screen.getAllByText("Fjern aksjonær")[0]);
    const igjen = screen.getAllByLabelText("Navn") as HTMLInputElement[];
    expect(igjen).toHaveLength(1);
    expect(igjen[0].value).toBe("Nummer to");
  });
});
