// Delt stegvis navigasjon (hostet + self-hosted): nummererte faner med tydelig aktiv-tilstand,
// og en «Gå videre»-knapp som leder til neste steg. Rent presentasjonelt; hver app eier sin
// header og fane-liste.
import { btnPrimar } from "./styles";

export interface Fane {
  id: string;
  navn: string;
  steg?: number; // nummer på arbeidssteg; utelatt for dashboard-faner (f.eks. Hjem)
}

export function StegNav({
  faner,
  aktiv,
  onNaviger,
}: {
  faner: Fane[];
  aktiv: string;
  onNaviger: (id: string) => void;
}) {
  return (
    <nav className="flex flex-wrap gap-x-5 gap-y-1">
      {faner.map(({ id, navn, steg }) => {
        const er = aktiv === id;
        return (
          <button
            key={id}
            onClick={() => onNaviger(id)}
            aria-current={er ? "page" : undefined}
            className={`group -mb-px flex items-center gap-2 border-b-2 pb-3 pt-1 transition ${
              er ? "border-spruce" : "border-transparent"
            }`}
          >
            {steg !== undefined && (
              <span
                className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-medium transition ${
                  er ? "bg-spruce text-background" : "bg-border text-muted-foreground group-hover:text-foreground"
                }`}
              >
                {steg}
              </span>
            )}
            <span
              className={`font-mono text-[11px] uppercase tracking-[0.15em] transition ${
                er ? "font-medium text-spruce" : "text-muted-foreground group-hover:text-foreground"
              }`}
            >
              {navn}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

// «Gå videre»-knapp som leder til neste fane, så tab-menyen ikke er eneste vei gjennom flyten.
// Vises på alle faner unntatt den siste. På første fane står det «Kom i gang».
export function GaaVidere({
  faner,
  aktiv,
  onNaviger,
  disabled = false,
  disabledHint,
}: {
  faner: Fane[];
  aktiv: string;
  onNaviger: (id: string) => void;
  disabled?: boolean;
  disabledHint?: string;
}) {
  const idx = faner.findIndex((f) => f.id === aktiv);
  const neste = faner[idx + 1];
  if (!neste) return null;
  return (
    <div className="mt-12 flex flex-wrap items-center justify-end gap-x-4 gap-y-2 border-t border-border pt-6">
      {disabled && disabledHint && (
        <span className="mr-auto flex items-center gap-1.5 text-sm font-medium text-amber-700">
          <span aria-hidden>⚠</span>
          {disabledHint}
        </span>
      )}
      <button
        className={btnPrimar}
        disabled={disabled}
        onClick={() => !disabled && onNaviger(neste.id)}
      >
        {idx === 0 ? "Kom i gang" : "Gå videre"}: {neste.steg ? `${neste.steg}. ` : ""}
        {neste.navn} →
      </button>
    </div>
  );
}
