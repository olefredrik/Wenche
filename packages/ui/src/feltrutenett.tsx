// Generisk renderer for en liste felter (felter.ts) mot config-objektet.
import { TallInput } from "./komponenter";
import type { Felt } from "./felter";
import { hent } from "./skjemadata";
import { input } from "./styles";
import type { Config } from "./typer";

export function Feltrutenett({
  felter,
  config,
  oppdater,
  laasteFelter = [],
}: {
  felter: Felt[];
  config: Config;
  oppdater: (key: string, val: unknown) => void;
  laasteFelter?: string[];
}) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      {felter.map((f) => {
        const laast = laasteFelter.includes(f.key);
        const verdi = hent(config, f.key);
        return f.type === "checkbox" ? (
          <label key={f.key} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="h-4 w-4 accent-[oklch(0.46_0.08_155)]"
              checked={!!verdi}
              onChange={(e) => oppdater(f.key, e.target.checked)}
            />
            {f.label}
          </label>
        ) : (
          <label key={f.key} className="block">
            <span className="mb-1 block text-xs text-muted-foreground">
              {f.label}
              {f.help ? ` (${f.help})` : ""}
            </span>
            {f.type === "number" ? (
              // Tallfelt: tusenskille i visningen, rent number i config (se TallInput).
              <TallInput
                className={`${input} ${laast ? "cursor-not-allowed opacity-60" : ""}`}
                value={(verdi as number | "" | undefined) ?? ""}
                disabled={laast}
                title={laast ? "Låst til selskapet i invitasjonen" : undefined}
                onChange={(v) => oppdater(f.key, v)}
              />
            ) : (
              <input
                className={`${input} ${laast ? "cursor-not-allowed opacity-60" : ""}`}
                type={f.type === "date" ? "date" : "text"}
                value={(verdi as string | undefined) ?? ""}
                disabled={laast}
                title={laast ? "Låst til selskapet i invitasjonen" : undefined}
                onChange={(e) => oppdater(f.key, e.target.value)}
              />
            )}
          </label>
        );
      })}
    </div>
  );
}
