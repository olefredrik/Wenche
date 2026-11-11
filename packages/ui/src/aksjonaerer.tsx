// Aksjonærlista i skjemaet. Nøklene kommer fra kalleren (stabile per rad, ikke indeks), så
// React ikke blander innholdet i tallfeltene når en rad midt i lista fjernes.
import { Inn, TallFelt } from "./komponenter";
import type { Aksjonaer } from "./skjemadata";
import { btnOutlineLett as btnOutline } from "./styles";

export function AksjonaerListe({
  aksjonaerer,
  nokler,
  onEndre,
  onFjern,
  onLeggTil,
}: {
  aksjonaerer: Aksjonaer[];
  nokler: number[];
  onEndre: (i: number, felt: keyof Aksjonaer, val: string | number) => void;
  onFjern: (i: number) => void;
  onLeggTil: () => void;
}) {
  return (
    <>
      <div className="space-y-4">
        {aksjonaerer.map((a, i) => (
          <div key={nokler[i] ?? i} className="rounded-sm border border-border bg-background p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Inn label="Navn" value={a.navn} onChange={(v) => onEndre(i, "navn", v)} />
              <Inn label="Fødselsnummer" value={a.fodselsnummer} onChange={(v) => onEndre(i, "fodselsnummer", v)} />
              <TallFelt label="Antall aksjer" value={a.antall_aksjer} onChange={(v) => onEndre(i, "antall_aksjer", v)} />
              <Inn label="Aksjeklasse" value={a.aksjeklasse} onChange={(v) => onEndre(i, "aksjeklasse", v)} />
              <TallFelt label="Utbytte utbetalt (kr)" value={a.utbytte_utbetalt} onChange={(v) => onEndre(i, "utbytte_utbetalt", v)} />
              <TallFelt label="Innbetalt kapital per aksje (kr)" value={a.innbetalt_kapital_per_aksje} onChange={(v) => onEndre(i, "innbetalt_kapital_per_aksje", v)} />
            </div>
            {aksjonaerer.length > 1 && (
              <button
                className="mt-3 text-xs text-muted-foreground underline-offset-2 hover:text-red-700 hover:underline"
                onClick={() => onFjern(i)}
              >
                Fjern aksjonær
              </button>
            )}
          </div>
        ))}
      </div>
      <button className={`${btnOutline} mt-4`} onClick={onLeggTil}>
        + Legg til aksjonær
      </button>
    </>
  );
}
