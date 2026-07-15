// Delte UI-primitiver for Wenche (hostet + self-hosted).
import { useState } from "react";
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

// Grupperer heltallsdelen med hardt mellomrom (nb-NO-stil), bevarer fortegn og desimaler.
// 1000 -> "1\u00A0000", 1000000 -> "1\u00A0000\u00A0000", -2500.5 -> "-2\u00A0500,5". Ren visning;
// tallet i config r\u00f8res ikke. Hardt mellomrom (\u00A0) matcher kr()/toLocaleString("nb-NO").
export function grupperTusen(n: number): string {
  if (!Number.isFinite(n)) return "";
  const neg = n < 0;
  const [heltall, desimal] = String(Math.abs(n)).split(".");
  const gruppert = heltall.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00A0");
  return (neg ? "-" : "") + gruppert + (desimal ? "," + desimal : "");
}

// Tolker en skrevet streng (mellomrom og komma tillatt) til number | "". Tomt/ufullstendig
// ("", "-", ".") og ugyldig blir "", s\u00e5 feltet kan st\u00e5 tomt under redigering.
export function tolkTall(s: string): number | "" {
  const r = s.replace(/[\s\u00A0]/g, "").replace(",", ".");
  if (r === "" || r === "-" || r === "." || r === "-.") return "";
  const n = Number(r);
  return Number.isNaN(n) ? "" : n;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formaterVerdi(v: any): string {
  if (v === "" || v == null) return "";
  const n = typeof v === "number" ? v : Number(String(v).replace(/[\s\u00A0]/g, "").replace(",", "."));
  return Number.isFinite(n) ? grupperTusen(n) : "";
}

// Tallfelt med tusenskille i visningen. Lagrer alltid et rent number (eller "" når tomt) via
// onChange, så SAF-T/Bodil-import, skjembygging og innsending ser samme verdier som før.
// Formaterer først når feltet mister fokus; viser rene sifre mens du skriver (ingen markør-hopp).
export function TallInput({
  value,
  onChange,
  className = input,
  disabled,
  title,
}: {
  value: number | "";
  onChange: (v: number | "") => void;
  className?: string;
  disabled?: boolean;
  title?: string;
}) {
  const [fokus, setFokus] = useState(false);
  const [tekst, setTekst] = useState("");
  const vis = fokus ? tekst : formaterVerdi(value);
  return (
    <input
      className={className}
      type="text"
      inputMode="decimal"
      value={vis}
      disabled={disabled}
      title={title}
      onFocus={() => {
        setTekst(value === "" || value == null ? "" : String(value));
        setFokus(true);
      }}
      onChange={(e) => {
        // Behold bare sifre, mellomrom, komma/punktum og minus mens brukeren skriver.
        const rå = e.target.value.replace(/[^\d\s.,-]/g, "");
        setTekst(rå);
        onChange(tolkTall(rå));
      }}
      onBlur={() => setFokus(false)}
    />
  );
}

// Etikettert tallfelt (samme oppsett som Inn), for aksjonær-tallene o.l.
export function TallFelt({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | "";
  onChange: (v: number | "") => void;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-muted-foreground">{label}</span>
      <TallInput value={value} onChange={onChange} />
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
