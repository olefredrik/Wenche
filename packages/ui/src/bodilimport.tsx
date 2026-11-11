// «Hent tall fra Bodil»: last opp config.yaml fra følgeverktøyet og forhåndsfyll skjemaet.
import { useRef, useState } from "react";
// js-yaml 5 fjernet default-eksporten, så navngitt import er eneste vei inn.
import { load as lesYaml, CORE_SCHEMA } from "js-yaml";
import { Modal } from "./modal";
import { btnOutlineLett as btnOutline } from "./styles";
import type { Config } from "./typer";
import { feilmelding } from "./api";

// Leser en Bodil/Wenche config.yaml til et config-objekt, eller kaster med lesbar melding.
export function lesBodilConfig(tekst: string): Config {
  // CORE_SCHEMA, ikke standardskjemaet, av to grunner. (1) Datoer: js-yaml 4 gjorde en
  // naken YYYY-MM-DD om til et JS Date, som serialiseres til "2025-10-24T00:00:00.000Z".
  // Det avvises av <input type="date"> (feltet ble blankt) og av backend, så en importert
  // regnskapsperiode brakk innsendingen med en feilmelding om en dato brukeren aldri skrev.
  // js-yaml 5 droppet timestamp fra standardskjemaet, så oppgraderingen alene retter det,
  // men da avhenger oppførselen av bibliotekets standardvalg. De har endret seg én gang og
  // kan endre seg igjen; et eksplisitt skjema låser den fast. (2) Sikkerhet: !!omap har hatt
  // kvadratisk parsetid (GHSA-5p4m-2wfm-xmqj). CORE_SCHEMA har ikke taggen i det hele tatt.
  const parsed = lesYaml(tekst, { schema: CORE_SCHEMA });
  if (!parsed || typeof parsed !== "object" || !("selskap" in parsed)) {
    throw new Error("Dette ser ikke ut som en Wenche/Bodil config.yaml.");
  }
  return parsed as Config;
}

export function BodilImportModal({
  onImportert,
  onLukk,
}: {
  onImportert: (config: Config) => void;
  onLukk: () => void;
}) {
  const [melding, setMelding] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const filRef = useRef<HTMLInputElement>(null);

  const importer = async (file: File) => {
    setMelding(null);
    try {
      onImportert(lesBodilConfig(await file.text()));
      onLukk();
    } catch (e) {
      setMelding("Kunne ikke lese filen: " + feilmelding(e));
    }
  };

  return (
    <Modal etikett="Hent tall fra Bodil" tittel="Fører du regnskapet i Bodil?" onLukk={onLukk}>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Bodil er følgeverktøyet som fører regnskapet for passive holdingselskaper og lager en{" "}
        <code className="font-mono">config.yaml</code> med årets tall. Last den opp her, så
        fyller vi inn regnskapet for deg. Du ser over alt og sender som vanlig.
      </p>
      <div
        role="button"
        tabIndex={0}
        className={`mt-5 flex flex-col items-center justify-center rounded-sm border-2 border-dashed px-6 py-8 text-center transition ${
          dragOver ? "border-spruce bg-spruce-soft" : "border-border hover:border-spruce/60"
        }`}
        onClick={() => filRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            filRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) importer(f);
        }}
      >
        <svg
          className="h-7 w-7 text-spruce"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16V4m0 0L8 8m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
          />
        </svg>
        <p className="mt-3 text-sm font-medium">
          Dra og slipp <code className="font-mono">config.yaml</code> her
        </p>
        <p className="mt-1 text-xs text-muted-foreground">eller</p>
        <button
          type="button"
          className={`${btnOutline} mt-2`}
          onClick={(e) => {
            e.stopPropagation();
            filRef.current?.click();
          }}
        >
          Velg fil
        </button>
        <input
          ref={filRef}
          type="file"
          accept=".yaml,.yml,.json"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) importer(f);
          }}
        />
      </div>
      {melding && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {melding}
        </p>
      )}
      <div className="mt-6 flex items-center justify-between">
        <a
          href="https://github.com/olefredrik/Bodil"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-spruce underline-offset-2 hover:underline"
        >
          Hva er Bodil?
        </a>
        <button className={btnOutline} onClick={onLukk}>
          Lukk
        </button>
      </div>
    </Modal>
  );
}
