// Delte UI-primitiver for Wenche (hostet + self-hosted).
import { monoLabel, input } from "./styles";

export function Kort({
  children,
  accent,
}: {
  children: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-sm border border-border p-8 ${accent ? "bg-spruce-soft" : "bg-paper"}`}
    >
      {children}
    </div>
  );
}

export function Panel({
  tone,
  tittel,
  children,
}: {
  tone: "ok" | "advarsel" | "feil";
  tittel: string;
  children?: React.ReactNode;
}) {
  const toner: Record<string, string> = {
    ok: "border-spruce/30 bg-spruce-soft text-spruce",
    advarsel: "border-amber-300 bg-amber-50 text-amber-800",
    feil: "border-red-300 bg-red-50 text-red-800",
  };
  return (
    <div className={`mt-6 rounded-sm border p-5 ${toner[tone]}`}>
      <p className="font-display text-lg">{tittel}</p>
      <div className="mt-2 text-sm text-foreground/80">{children}</div>
    </div>
  );
}

export function Liste({ tittel, items }: { tittel?: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mt-2">
      {tittel && <p className={`${monoLabel} mb-1`}>{tittel}</p>}
      <ul className="list-disc space-y-1 pl-5">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

export function Inn({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string | number;
  onChange: (v: string) => void;
  type?: "text" | "number";
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <input
        className={input}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

// Sticky innholds-navigasjon over skjema/send-seksjonene. `top` lar hver app
// plassere den under sin egen header-høyde.
export function SeksjonsNav({
  lenker,
  top = "top-16",
}: {
  lenker: [string, string][];
  top?: string;
}) {
  return (
    <nav
      className={`sticky ${top} z-40 -mx-6 border-b border-border bg-background/85 px-6 py-3 backdrop-blur-sm`}
    >
      <div className="flex flex-wrap gap-x-5 gap-y-1">
        {lenker.map(([h, navn]) => (
          <a
            key={h}
            href={h}
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground transition hover:text-spruce"
          >
            {navn}
          </a>
        ))}
      </div>
    </nav>
  );
}
