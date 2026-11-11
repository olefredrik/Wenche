import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useUlagretVakt } from "./ulagret";

function Testapp({ ulagret, naviger }: { ulagret: boolean; naviger: (id: string) => void }) {
  const { forsoekNaviger, dialog } = useUlagretVakt(ulagret, naviger);
  return (
    <>
      <button onClick={() => forsoekNaviger("send")}>Gå til Send</button>
      {dialog}
    </>
  );
}

describe("useUlagretVakt", () => {
  it("navigerer rett fram uten ulagrede endringer", () => {
    const naviger = vi.fn();
    render(<Testapp ulagret={false} naviger={naviger} />);
    fireEvent.click(screen.getByText("Gå til Send"));
    expect(naviger).toHaveBeenCalledWith("send");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("spør først når skjemaet har ulagrede endringer", () => {
    const naviger = vi.fn();
    render(<Testapp ulagret naviger={naviger} />);
    fireEvent.click(screen.getByText("Gå til Send"));
    expect(naviger).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Forlate uten å lagre?" })).toBeTruthy();
    fireEvent.click(screen.getByText("Bli på siden"));
    expect(naviger).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByText("Gå til Send"));
    fireEvent.click(screen.getByText("Forlat uten å lagre"));
    expect(naviger).toHaveBeenCalledWith("send");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
