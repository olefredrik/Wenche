// «Importer fra SAF-T»: last opp SAF-T Financial for årets tall, og eventuelt en egen fil for
// fjorårets sammenligningstall. Selve parsingen gjør backenden (wenche.saft) i minnet.
import { useRef, useState } from "react";
import { feilmelding } from "./api";
import { Modal } from "./modal";
import { btnOutlineLett as btnOutline } from "./styles";
import type { SaftImportSvar } from "./typer";

export type SaftImporter = (file: File, foregaaende: boolean) => Promise<SaftImportSvar>;

export function SaftImportModal({
  importerSaft,
  onImportert,
  merknad,
  onLukk,
}: {
  importerSaft: SaftImporter;
  // Kalles med svaret (uten _advarsler) og om det bare gjaldt fjoråret. Kalleren fletter det
  // inn i skjemaet.
  onImportert: (data: SaftImportSvar, foregaaende: boolean) => void;
  merknad?: React.ReactNode;
  onLukk: () => void;
}) {
  const [melding, setMelding] = useState<string | null>(null);
  const [feil, setFeil] = useState(false);
  const [laster, setLaster] = useState(false);
  const [drag, setDrag] = useState<string | null>(null);
  const naaRef = useRef<HTMLInputElement>(null);
  const fjorRef = useRef<HTMLInputElement>(null);

  const importer = async (file: File, foregaaende: boolean) => {
    setMelding(null);
    setFeil(false);
    setLaster(true);
    try {
      const svar = await importerSaft(file, foregaaende);
      // _advarsler er ikke et config-felt: den skilles ut her, slik at den aldri havner i
      // configen brukeren lagrer, men fortsatt blir sagt.
      const { _advarsler: advarsler, ...data } = svar ?? {};
      const aar = data?.regnskapsaar ? ` ${data.regnskapsaar}` : "";
      const advarsel = Array.isArray(advarsler) && advarsler.length ? " " + advarsler.join(" ") : "";
      onImportert(data, foregaaende);
      setMelding(
        foregaaende
          ? `Sammenligningstall for fjoråret importert fra SAF-T${aar}.${advarsel}`
          : `Tall importert fra SAF-T${aar}. Se over og lagre.${advarsel}`,
      );
    } catch (e) {
      setFeil(true);
      setMelding("Kunne ikke importere SAF-T: " + feilmelding(e));
    } finally {
      setLaster(false);
    }
  };

  const soner = [
    {
      id: "naa",
      ref: naaRef,
      foregaaende: false,
      tittel: "Inneværende år",
      beskrivelse: "Fyller selskap, resultat og balanse for regnskapsåret.",
    },
    {
      id: "fjor",
      ref: fjorRef,
      foregaaende: true,
      tittel: "Foregående år (valgfritt)",
      beskrivelse:
        "Egen SAF-T for fjoråret. Fyller kun sammenligningstallene (fjorårets resultatregnskap finnes ikke i årets fil).",
    },
  ];

  return (
    <Modal etikett="Importer fra SAF-T" tittel="Hent tall fra regnskapssystemet" onLukk={onLukk}>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Eksporter en SAF-T Financial-fil fra regnskapssystemet ditt (Fiken, Tripletex, Visma,
        PowerOffice m.fl.), så fyller jeg inn regnskap og balanse for deg. Du ser over alt og
        sender som vanlig.
      </p>

      {soner.map((sone) => (
        <div key={sone.id} className="mt-5">
          <p className="text-sm font-medium">{sone.tittel}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{sone.beskrivelse}</p>
          <div
            role="button"
            tabIndex={0}
            className={`mt-2 flex flex-col items-center justify-center rounded-sm border-2 border-dashed px-6 py-6 text-center transition ${
              drag === sone.id ? "border-spruce bg-spruce-soft" : "border-border hover:border-spruce/60"
            } ${laster ? "pointer-events-none opacity-60" : ""}`}
            onClick={() => sone.ref.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                sone.ref.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(sone.id);
            }}
            onDragLeave={() => setDrag(null)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(null);
              const f = e.dataTransfer.files?.[0];
              if (f) importer(f, sone.foregaaende);
            }}
          >
            <p className="text-sm">
              Dra og slipp <code className="font-mono">.xml</code> her, eller{" "}
              <span className="text-spruce underline-offset-2 hover:underline">velg fil</span>
            </p>
            <input
              ref={sone.ref}
              type="file"
              accept=".xml,text/xml,application/xml"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) importer(f, sone.foregaaende);
                e.target.value = "";
              }}
            />
          </div>
        </div>
      ))}

      {laster && <p className="mt-3 text-sm text-muted-foreground">Importerer…</p>}
      {melding && (
        <p
          role={feil ? "alert" : "status"}
          className={`mt-3 text-sm ${feil ? "text-red-700" : "text-spruce"}`}
        >
          {melding}
        </p>
      )}
      {merknad && <p className="mt-4 text-xs leading-relaxed text-muted-foreground">{merknad}</p>}
      <div className="mt-6 flex justify-end">
        <button className={btnOutline} onClick={onLukk}>
          Lukk
        </button>
      </div>
    </Modal>
  );
}
