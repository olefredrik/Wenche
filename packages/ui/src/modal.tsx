// Én modal for hele Wenche: dialog-semantikk (role, aria-modal, tittel), Escape lukker,
// fokus holdes inne i dialogen og går tilbake dit det var når den lukkes. Klikk utenfor lukker.
import { useEffect, useId, useRef } from "react";
import { monoLabel } from "./styles";

const FOKUSERBAR =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
  'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Modal({
  etikett,
  tittel,
  onLukk,
  children,
  bredde = "max-w-md",
}: {
  etikett?: string;
  tittel: string;
  onLukk: () => void;
  children: React.ReactNode;
  bredde?: string;
}) {
  const boksRef = useRef<HTMLDivElement>(null);
  const tittelId = useId();
  // Lukkeren leses via ref, så en ny inline-funksjon per render ikke flytter fokus på nytt.
  const lukkRef = useRef(onLukk);
  useEffect(() => {
    lukkRef.current = onLukk;
  });

  useEffect(() => {
    const boks = boksRef.current;
    const forrige = document.activeElement as HTMLElement | null;
    const foerste = boks?.querySelector<HTMLElement>(FOKUSERBAR);
    (foerste ?? boks)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        lukkRef.current();
        return;
      }
      if (e.key !== "Tab" || !boks) return;
      const alle = Array.from(boks.querySelectorAll<HTMLElement>(FOKUSERBAR));
      if (alle.length === 0) {
        e.preventDefault();
        boks.focus();
        return;
      }
      const first = alle[0];
      const last = alle[alle.length - 1];
      const aktiv = document.activeElement;
      if (e.shiftKey && (aktiv === first || aktiv === boks)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && aktiv === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      forrige?.focus?.();
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 p-4"
      onClick={onLukk}
    >
      <div
        ref={boksRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={tittelId}
        tabIndex={-1}
        className={`w-full ${bredde} rounded-sm border border-border bg-background p-6 shadow-2xl outline-none`}
        onClick={(e) => e.stopPropagation()}
      >
        {etikett && <p className={monoLabel}>{etikett}</p>}
        <h3 id={tittelId} className="mt-2 font-display text-xl font-normal">
          {tittel}
        </h3>
        {children}
      </div>
    </div>
  );
}
