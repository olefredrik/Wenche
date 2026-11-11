// Hjem: tilkoblingsstatus. Koblet → bekreftelse + «sjekk tilkobling». Ikke koblet → onboarding.
import { useState } from "react";
import { Kort, StegTittel, feilmelding, monoLabel } from "@wenche/ui";
import { api } from "./api";
import { FortsettAnnenEnhet } from "./FortsettAnnenEnhet";
import { Onboarding } from "./Onboarding";
import type { Me } from "./typer";

export function HjemFane({ me, onChange }: { me: Me; onChange: () => void }) {
  const [sjekker, setSjekker] = useState(false);
  const [melding, setMelding] = useState<string | null>(null);

  // Bekreft at en godkjent systembruker fortsatt finnes for selskapet. Bruker `request`
  // (ikke `status`): en allerede godkjent kunde har ingen ventende forespørsel, så `status`
  // ville svart «ingen aktiv forespørsel» selv om tilkoblingen er aktiv. `request` sjekker
  // eksisterende systembrukere og returnerer «AlreadyApproved» uten å lage en ny forespørsel.
  const sjekk = async () => {
    setSjekker(true);
    setMelding(null);
    try {
      const r = await api.systembrukerRequest();
      if (r.godkjent || r.status === "AlreadyApproved") {
        setMelding("✓ Tilkoblingen er aktiv.");
      } else {
        setMelding("Tilkoblingen er ikke lenger aktiv. Last siden på nytt for å koble på nytt.");
      }
    } catch (e) {
      setMelding(feilmelding(e));
    } finally {
      setSjekker(false);
    }
  };

  if (!me.kunde_org) {
    return (
      <div className="space-y-6">
        <StegTittel tittel="Velkommen">
          Koble selskapet ditt til Altinn for å komme i gang. Maskinporten-oppsettet er allerede
          gjort for deg.
        </StegTittel>
        <Onboarding org={me.invite_org} onApproved={onChange} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <StegTittel tittel="Hjem">
        Fyll inn tallene under «Tall», se over dokumentene, og send inn under «Send».
      </StegTittel>
      <Kort accent>
        <p className={monoLabel}>Tilkobling</p>
        <p className="mt-2 font-display text-lg text-spruce">
          ✓ Selskapet ditt (org {me.kunde_org}) er koblet til Altinn
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Wenche kan sende inn på vegne av selskapet. Du kan når som helst kontrollere at
          tilkoblingen fortsatt er aktiv.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-spruce underline-offset-2 hover:underline disabled:opacity-40"
            onClick={sjekk}
            disabled={sjekker}
          >
            {sjekker ? "Sjekker…" : "Sjekk tilkobling"}
          </button>
          {melding && (
            <span role="status" className="text-sm text-muted-foreground">
              {melding}
            </span>
          )}
        </div>
      </Kort>
      {/* Handoff er bare relevant for invite-baserte økter (f.eks. demo, eller fallback-brukere
          uten ID-porten-rolletreff): de kan ikke logge inn på nytt på en ny enhet uten lenken.
          ID-porten-brukere logger bare inn på nytt på enhet to (og treffer AlreadyApproved), så
          handoff er overflødig for dem. Skjules derfor for ID-porten-økter. */}
      {!me.via_idporten && (
        <Kort>
          <p className={monoLabel}>Flere enheter</p>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Tilkoblingen gjelder denne nettleseren.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            Vil du bruke Wenche på telefonen eller en annen maskin, lag en lenke her og åpne den
            der, så kobles den enheten til i tillegg, uten ny godkjenning. Begge forblir koblet.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            En enhet du ikke vil bruke lenger, logger du ut med «Logg ut».
          </p>
          <div className="mt-4">
            <FortsettAnnenEnhet />
          </div>
        </Kort>
      )}
    </div>
  );
}
