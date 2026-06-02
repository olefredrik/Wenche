// Delt dokument-nedlasting (hostet + self-hosted). Generer dokumentene for gjennomgang før
// innsending; ingenting sendes inn her. Hver app injiserer sin `dokument`-binding.
import { useState } from "react";
import { Kort, Panel } from "./komponenter";
import { monoLabel, btnOutlineLett } from "./styles";
import { lastNed, type NedlastFil } from "./nedlasting";

export type DokumentFn = (
  type: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any,
) => Promise<{ filer: NedlastFil[] }>;

const STANDARD_DOKUMENTER: { type: string; navn: string; beskrivelse: string }[] = [
  { type: "skattemelding", navn: "Skattemelding", beskrivelse: "Tekstsammendrag av skattemelding og næringsspesifikasjon." },
  { type: "aarsregnskap", navn: "Årsregnskap (XML)", beskrivelse: "Hoved- og underskjema slik de sendes til Brønnøysund." },
  { type: "aksjonaer", navn: "Aksjonærregister (XML)", beskrivelse: "RF-1086 hovedskjema + ett underskjema per aksjonær." },
  { type: "noter", navn: "Noter", beskrivelse: "De obligatoriske notene til årsregnskapet (signeres av styret, sendes ikke inn)." },
];

export function Dokumenter({
  config,
  dokument,
  dokumenter = STANDARD_DOKUMENTER,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  dokument: DokumentFn;
  dokumenter?: { type: string; navn: string; beskrivelse: string }[];
}) {
  const [feil, setFeil] = useState<string | null>(null);
  const [laster, setLaster] = useState<string | null>(null);

  const lastNedDok = async (type: string) => {
    setFeil(null);
    setLaster(type);
    try {
      const r = await dokument(type, config);
      lastNed(r.filer);
    } catch (e) {
      setFeil((e as Error).message);
    } finally {
      setLaster(null);
    }
  };

  if (!config) {
    return (
      <Panel tone="advarsel" tittel="Ingen data ennå">
        Fyll inn tallene under «Tall» før du genererer dokumenter.
      </Panel>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Dokumenter</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Generer og last ned dokumentene for gjennomgang. Ingenting sendes inn her.
        </p>
      </div>
      {feil && (
        <Panel tone="feil" tittel="Kunne ikke generere">
          {feil}
        </Panel>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {dokumenter.map((d) => (
          <Kort key={d.type}>
            <p className={monoLabel}>Dokument</p>
            <h3 className="mt-2 font-display text-lg font-normal">{d.navn}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{d.beskrivelse}</p>
            <button
              className={`${btnOutlineLett} mt-4`}
              onClick={() => lastNedDok(d.type)}
              disabled={laster !== null}
            >
              {laster === d.type ? "Genererer…" : "Last ned"}
            </button>
          </Kort>
        ))}
      </div>
    </div>
  );
}
