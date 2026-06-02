// Delt noter-redigering (antall ansatte + lån til nærstående). Notene sendes ikke inn, men
// brukes til å generere notedokumentet under «Dokumenter» og lagres i config under `noter`.
// Rendres som en seksjon (ikke eget kort) slik at den passer sist i datainntastings-skjemaet.
import { Inn } from "./komponenter";
import { btnOutlineLett } from "./styles";

export interface Laan {
  motpart: string;
  saldo: number;
  retning: string;
  rente_prosent: number;
  sikkerhet: string;
}
export interface NoterData {
  antall_ansatte: number;
  laan_til_naerstaaende: Laan[];
}

export function tomtLaan(): Laan {
  return { motpart: "", saldo: 0, retning: "långiver", rente_prosent: 0, sikkerhet: "" };
}

// Bygg NoterData fra en config-dict (tåler manglende/delvise felt).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function noterFraConfig(config: any): NoterData {
  return {
    antall_ansatte: config?.noter?.antall_ansatte ?? 0,
    laan_til_naerstaaende: (config?.noter?.laan_til_naerstaaende ?? []).map((l: Partial<Laan>) => ({
      ...tomtLaan(),
      ...l,
    })),
  };
}

export function NoterSeksjon({
  noter,
  setNoter,
}: {
  noter: NoterData;
  setNoter: (n: NoterData) => void;
}) {
  const settLaan = (i: number, felt: keyof Laan, val: string | number) =>
    setNoter({
      ...noter,
      laan_til_naerstaaende: noter.laan_til_naerstaaende.map((l, j) =>
        j === i ? { ...l, [felt]: val } : l,
      ),
    });
  return (
    <section className="border-t border-border pt-6">
      <h3 className="mb-1 font-display text-xl font-normal">Obligatoriske noter</h3>
      <p className="mb-4 text-sm text-muted-foreground">
        Regnskapsloven krever noter til årsregnskapet. De sendes ikke inn digitalt, men kan
        lastes ned under «Dokumenter», undertegnes av styret og oppbevares av selskapet.
      </p>
      <div className="max-w-xs">
        <Inn
          label="Antall ansatte i regnskapsåret"
          type="number"
          value={noter.antall_ansatte}
          onChange={(v) => setNoter({ ...noter, antall_ansatte: Number(v) || 0 })}
        />
      </div>

      <div className="mt-6 space-y-4">
        {noter.laan_til_naerstaaende.map((l, i) => (
          <div key={i} className="rounded-sm border border-border bg-background p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Inn label="Motpart (nærstående)" value={l.motpart} onChange={(v) => settLaan(i, "motpart", v)} />
              <Inn label="Saldo per 31.12 (kr)" type="number" value={l.saldo} onChange={(v) => settLaan(i, "saldo", Number(v) || 0)} />
              <label className="block">
                <span className="mb-1 block text-xs text-muted-foreground">Retning</span>
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-spruce"
                  value={l.retning}
                  onChange={(e) => settLaan(i, "retning", e.target.value)}
                >
                  <option value="långiver">Selskapet har lånt ut til nærstående</option>
                  <option value="låntaker">Nærstående har lånt til selskapet</option>
                </select>
              </label>
              <Inn label="Rente (%)" type="number" value={l.rente_prosent} onChange={(v) => settLaan(i, "rente_prosent", Number(v) || 0)} />
              <Inn label="Sikkerhet" value={l.sikkerhet} onChange={(v) => settLaan(i, "sikkerhet", v)} />
            </div>
            <button
              className="mt-3 text-xs text-muted-foreground underline-offset-2 hover:text-red-700 hover:underline"
              onClick={() =>
                setNoter({ ...noter, laan_til_naerstaaende: noter.laan_til_naerstaaende.filter((_, j) => j !== i) })
              }
            >
              Fjern lån
            </button>
          </div>
        ))}
      </div>
      <button
        className={`${btnOutlineLett} mt-4`}
        onClick={() => setNoter({ ...noter, laan_til_naerstaaende: [...noter.laan_til_naerstaaende, tomtLaan()] })}
      >
        + Legg til lån til nærstående
      </button>
    </section>
  );
}
