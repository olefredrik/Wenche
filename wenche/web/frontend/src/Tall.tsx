import { useState } from "react";
import { DataSkjema, Kort, Inn, monoLabel, btnOutlineLett } from "@wenche/ui";
import { api } from "./api";

interface Laan {
  motpart: string;
  saldo: number;
  retning: string;
  rente_prosent: number;
  sikkerhet: string;
}
interface NoterData {
  antall_ansatte: number;
  laan_til_naerstaaende: Laan[];
}

function tomtLaan(): Laan {
  return { motpart: "", saldo: 0, retning: "långiver", rente_prosent: 0, sikkerhet: "" };
}

// Noter-redigering (antall ansatte + lån til nærstående). Sendes ikke inn, men brukes til å
// generere notedokumentet under «Dokumenter» og lagres i config under `noter`.
function NoterSeksjon({ noter, setNoter }: { noter: NoterData; setNoter: (n: NoterData) => void }) {
  const settLaan = (i: number, felt: keyof Laan, val: string | number) =>
    setNoter({
      ...noter,
      laan_til_naerstaaende: noter.laan_til_naerstaaende.map((l, j) =>
        j === i ? { ...l, [felt]: val } : l,
      ),
    });
  return (
    <Kort>
      <p className={monoLabel}>Noter</p>
      <h3 className="mt-2 font-display text-xl font-normal">Obligatoriske noter</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Regnskapsloven krever noter til årsregnskapet. De sendes ikke inn digitalt, men kan
        lastes ned under «Dokumenter», undertegnes av styret og oppbevares av selskapet.
      </p>
      <div className="mt-4 max-w-xs">
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
    </Kort>
  );
}

export default function Tall({
  config,
  env,
  onLagret,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  env: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onLagret: (c: any) => void;
}) {
  const [noter, setNoter] = useState<NoterData>(() => ({
    antall_ansatte: config?.noter?.antall_ansatte ?? 0,
    laan_til_naerstaaende: (config?.noter?.laan_til_naerstaaende ?? []).map((l: Partial<Laan>) => ({
      ...tomtLaan(),
      ...l,
    })),
  }));
  const [kvittering, setKvittering] = useState<string | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const lagre = async (formConfig: any) => {
    const full = { ...formConfig, noter };
    const r = await api.lagreConfig(full);
    onLagret(full);
    setKvittering(`Lagret til ${r.fil}`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Tall</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Fyll inn selskapsopplysninger, regnskap, balanse, skattemelding og aksjonærer. Trykk
          «Lagre data» for å skrive til {env === "test" ? "config.dev.yaml" : "config.yaml"}.
        </p>
      </div>

      <NoterSeksjon noter={noter} setNoter={setNoter} />

      <Kort>
        <DataSkjema onLagre={lagre} visEksempel={env === "test"} initial={config ?? undefined} />
      </Kort>

      {kvittering && <p className="text-sm text-spruce">✓ {kvittering}</p>}
    </div>
  );
}
