// Koble systembruker (BankID i Altinn). Vises på Hjem når selskapet ikke er koblet ennå.
import { useEffect, useState } from "react";
import { Kort, btnOutline, btnPrimar, feilmelding, monoLabel } from "@wenche/ui";
import { api } from "./api";

// Pollingen mot Altinn stopper av seg selv etter dette (4 s mellom hver), så en fane som
// står åpen og glemt ikke spør i det uendelige. Brukeren kan alltid sjekke manuelt.
const POLL_INTERVALL_MS = 4000;
const MAKS_POLL = 225; // 15 minutter

export function Onboarding({ org, onApproved }: { org?: string | null; onApproved: () => void }) {
  const [confirmUrl, setConfirmUrl] = useState<string | null>(null);
  const [feil, setFeil] = useState<string | null>(null);
  const [kobler, setKobler] = useState(false);
  const [venter, setVenter] = useState(false);

  const koble = async () => {
    setFeil(null);
    setConfirmUrl(null);
    setKobler(true);
    try {
      const r = await api.systembrukerRequest();
      if (r.godkjent || r.status === "AlreadyApproved") onApproved();
      else {
        setConfirmUrl(r.confirm_url ?? null);
        setVenter(true);
      }
    } catch (e) {
      setFeil(feilmelding(e));
    } finally {
      setKobler(false);
    }
  };

  const sjekkNaa = async () => {
    setFeil(null);
    try {
      const r = await api.systembrukerStatus();
      if (r.godkjent) onApproved();
      else setFeil("Ikke godkjent ennå. Fullfør i Altinn og prøv igjen om litt.");
    } catch (e) {
      setFeil(feilmelding(e));
    }
  };

  // Poll status mens vi venter, så UI-et går videre av seg selv når daglig leder/styreleder
  // har godkjent i Altinn.
  useEffect(() => {
    if (!venter) return;
    let forsok = 0;
    const id = setInterval(async () => {
      forsok += 1;
      if (forsok > MAKS_POLL) {
        clearInterval(id);
        setVenter(false);
        setFeil("Venter ikke lenger automatisk. Trykk «Jeg har godkjent, sjekk nå» når godkjenningen er gjort.");
        return;
      }
      try {
        const r = await api.systembrukerStatus();
        if (r.godkjent) {
          clearInterval(id);
          onApproved();
        }
      } catch {
        /* nettverksglipp e.l.: prøver igjen ved neste intervall */
      }
    }, POLL_INTERVALL_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [venter]);

  return (
    <Kort>
      <p className={monoLabel}>Tilkobling</p>
      <h2 className="mt-3 font-display text-2xl font-normal">Koble til selskapet ditt</h2>
      {org ? (
        <>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Invitasjonen din gjelder selskapet under. Første gang må daglig leder eller
            styreleder godkjenne Wenche i Altinn med BankID. Har selskapet allerede godkjent,
            kobles du til direkte.
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="rounded-md border border-border bg-background px-4 py-2.5 text-sm">
              <span className={monoLabel}>Org</span> <span className="font-mono">{org}</span>
            </div>
            <button className={btnPrimar} onClick={koble} disabled={kobler}>
              {kobler ? "Kobler…" : "Koble systembruker"}
            </button>
          </div>
        </>
      ) : (
        <p role="alert" className="mt-4 text-sm text-red-700">
          Invite-lenken er ikke knyttet til et selskap. Be om en ny lenke.
        </p>
      )}
      {confirmUrl && (
        <div className="mt-5 rounded-sm border border-border bg-background p-4 text-sm">
          <p className="text-muted-foreground">
            Daglig leder eller styreleder må godkjenne Wenche i Altinn med BankID. Åpne lenken,
            godkjenn, så kommer du videre automatisk her:
          </p>
          <a
            className="mt-2 block break-all text-spruce underline-offset-2 hover:underline"
            href={confirmUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            {confirmUrl}
          </a>
          <div className="mt-4 flex items-center gap-3">
            <button className={btnOutline} onClick={sjekkNaa}>
              Jeg har godkjent, sjekk nå
            </button>
            {venter && <span className="text-xs text-muted-foreground">Venter på godkjenning…</span>}
          </div>
        </div>
      )}
      {feil && (
        <p role="alert" className="mt-4 text-sm text-red-700">
          {feil}
        </p>
      )}
    </Kort>
  );
}
