// Vakt mot å bytte fane med ulagrede endringer i skjemaet. Fanebytte avmonterer skjemaet, så
// uten denne forsvant utfyllingen stille; beforeunload-vakten dekker bare sidelukking.
import { useState } from "react";
import { Modal } from "./modal";
import { btnOutline, btnPrimar } from "./styles";

export function useUlagretVakt(ulagret: boolean, naviger: (id: string) => void) {
  const [ventende, setVentende] = useState<string | null>(null);
  const forsoekNaviger = (id: string) => {
    if (ulagret) setVentende(id);
    else naviger(id);
  };
  const dialog = ventende ? (
    <Modal etikett="Ulagrede endringer" tittel="Forlate uten å lagre?" onLukk={() => setVentende(null)}>
      <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
        Du har endringer i skjemaet som ikke er lagret. Går du videre nå, mister du dem. Trykk
        «Lagre data» nederst i skjemaet for å beholde dem.
      </p>
      <div className="mt-5 flex items-center justify-end gap-3">
        <button className={btnOutline} onClick={() => setVentende(null)}>
          Bli på siden
        </button>
        <button
          className={btnPrimar}
          onClick={() => {
            const id = ventende;
            setVentende(null);
            naviger(id);
          }}
        >
          Forlat uten å lagre
        </button>
      </div>
    </Modal>
  ) : null;
  return { forsoekNaviger, dialog };
}
