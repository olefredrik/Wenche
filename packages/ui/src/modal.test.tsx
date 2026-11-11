import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./modal";

describe("Modal", () => {
  it("er en dialog med tittel som navn, og får fokus når den åpnes", () => {
    render(
      <Modal etikett="Etikett" tittel="Bekreft noe" onLukk={() => {}}>
        <button>Første</button>
        <button>Siste</button>
      </Modal>,
    );
    const dialog = screen.getByRole("dialog", { name: "Bekreft noe" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement?.textContent).toBe("Første");
  });

  it("lukker på Escape og ved klikk utenfor, ikke ved klikk inni", () => {
    const onLukk = vi.fn();
    render(
      <Modal tittel="Tittel" onLukk={onLukk}>
        <button>Inni</button>
      </Modal>,
    );
    fireEvent.click(screen.getByText("Inni"));
    expect(onLukk).not.toHaveBeenCalled();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onLukk).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("dialog").parentElement!);
    expect(onLukk).toHaveBeenCalledTimes(2);
  });

  it("holder Tab innenfor dialogen", () => {
    render(
      <Modal tittel="Tittel" onLukk={() => {}}>
        <button>Første</button>
        <button>Siste</button>
      </Modal>,
    );
    screen.getByText("Siste").focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement?.textContent).toBe("Første");
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement?.textContent).toBe("Siste");
  });

  it("gir fokus tilbake dit det var når den lukkes", () => {
    const Knapp = () => {
      return <button>Åpne</button>;
    };
    const { unmount } = render(<Knapp />);
    screen.getByText("Åpne").focus();
    const modal = render(
      <Modal tittel="Tittel" onLukk={() => {}}>
        <button>Inni</button>
      </Modal>,
    );
    expect(document.activeElement?.textContent).toBe("Inni");
    modal.unmount();
    expect(document.activeElement?.textContent).toBe("Åpne");
    unmount();
  });
});
