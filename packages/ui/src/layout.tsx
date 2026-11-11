// Delte app-rammer: header med Test-merke, varselbanner og steg-overskrifter. Hver app eier
// innholdet (høyre del av headeren, fanelista), rammen er lik.
import { Panel } from "./komponenter";

export function AppHeader({
  env,
  hoyre,
  nav,
  bredde = "max-w-3xl",
}: {
  env?: string;
  hoyre?: React.ReactNode;
  nav?: React.ReactNode;
  bredde?: string;
}) {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-sm">
      <div className={`mx-auto ${bredde} px-6`}>
        <div className="flex items-center justify-between py-4">
          <div className="flex items-baseline gap-2">
            <h1 className="font-display text-2xl font-medium tracking-tight">Wenche</h1>
            {env === "test" && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-amber-800">
                Test
              </span>
            )}
          </div>
          {hoyre}
        </div>
        {nav && <div className="pb-1">{nav}</div>}
      </div>
    </header>
  );
}

// Gult banner øverst (demo-modus, ny versjon tilgjengelig).
export function Banner({ children }: { children: React.ReactNode }) {
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-6 py-2 text-center text-sm text-amber-900">
      {children}
    </div>
  );
}

// Overskrift og ingress øverst i et steg.
export function StegTittel({ tittel, children }: { tittel: string; children?: React.ReactNode }) {
  return (
    <div>
      <h2 className="font-display text-2xl font-normal">{tittel}</h2>
      {children && <p className="mt-1 text-sm text-muted-foreground">{children}</p>}
    </div>
  );
}

// Vises i Dokumenter og Send før det finnes lagrede tall.
export function IngenDataPanel({ children }: { children: React.ReactNode }) {
  return (
    <Panel tone="advarsel" tittel="Ingen data ennå">
      {children}
    </Panel>
  );
}
