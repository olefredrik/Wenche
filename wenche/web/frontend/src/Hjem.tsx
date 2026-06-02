import { useEffect, useState } from "react";
import { Kort, monoLabel } from "@wenche/ui";
import { api } from "./api";

interface Frist {
  key: string;
  tittel: string;
  undertittel: string;
  maaned: number;
  dag: number;
  beskrivelse: string;
  auto_sjekk: boolean;
  neste_frist: string;
}
interface FristStatus {
  innfridd: boolean;
  tidspunkt?: string | null;
  beskrivelse?: string;
  brukertekst?: string;
  lenke?: string | null;
  referanse?: string | null;
  referanse_etikett?: string;
}

function dagerTil(iso: string): number {
  const naa = new Date();
  const frist = new Date(iso + "T00:00:00");
  return Math.ceil((frist.getTime() - naa.getTime()) / (1000 * 60 * 60 * 24));
}

function FristKort({ frist, status }: { frist: Frist; status?: FristStatus }) {
  const dager = dagerTil(frist.neste_frist);
  const innfridd = status?.innfridd;
  const fristDato = `${String(frist.dag).padStart(2, "0")}.${String(frist.maaned).padStart(2, "0")}`;
  const overtid = dager < 0;

  return (
    <div
      className={`flex flex-col rounded-sm border p-5 ${innfridd ? "border-spruce/30 bg-spruce-soft" : "border-border bg-paper"}`}
    >
      <h3 className="font-display text-xl font-normal">{frist.tittel}</h3>

      {/* Frist-pille: grønn «Levert» når innfridd, ellers dato + nedtelling. */}
      {innfridd ? (
        <span className="mt-3 inline-flex w-fit items-center rounded-full bg-spruce px-3 py-1 text-xs font-medium text-background">
          ✓ {status?.brukertekst || "Levert"}
        </span>
      ) : (
        <span
          className={`mt-3 inline-flex w-fit items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
            overtid ? "bg-amber-100 text-amber-800" : "border border-spruce/30 bg-spruce-soft text-spruce"
          }`}
        >
          Frist {fristDato}
          <span className="opacity-70">· {overtid ? `${-dager} d på overtid` : `${dager} d igjen`}</span>
        </span>
      )}

      {innfridd ? (
        <div className="mt-3 text-sm">
          {status?.referanse && (
            <p className="text-muted-foreground">
              {status.referanse_etikett || "Referanse"}: <span className="font-mono">{status.referanse}</span>
            </p>
          )}
          {status?.lenke && (
            <a href={status.lenke} target="_blank" rel="noopener noreferrer" className="mt-1 inline-block text-spruce underline-offset-2 hover:underline">
              Åpne i Altinn →
            </a>
          )}
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">{status?.beskrivelse || frist.beskrivelse}</p>
      )}
    </div>
  );
}

export default function Hjem() {
  const [frister, setFrister] = useState<Frist[]>([]);
  const [aktiv, setAktiv] = useState(false);
  const [statuser, setStatuser] = useState<Record<string, FristStatus>>({});
  const [sjekker, setSjekker] = useState(false);
  const [feil, setFeil] = useState<string | null>(null);

  const sjekk = async () => {
    setSjekker(true);
    setFeil(null);
    try {
      const r = await api.sjekkFrister();
      setStatuser(r.statuser ?? {});
    } catch (e) {
      setFeil((e as Error).message);
    } finally {
      setSjekker(false);
    }
  };

  useEffect(() => {
    api
      .frister()
      .then((r) => {
        setFrister(r.frister ?? []);
        setAktiv(!!r.statussjekk_aktiv);
        if (r.statussjekk_aktiv) sjekk();
      })
      .catch((e) => setFeil((e as Error).message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Frister og status</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Wenche ordner årsregnskap, skattemelding og aksjonærregisteroppgave for
          holdingselskapet ditt. Fyll ut tallene under «Tall», og send inn under «Send».
        </p>
      </div>

      <div className="flex items-center gap-3">
        <h3 className="font-display text-lg">Frister</h3>
        {aktiv && (
          <button
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-spruce underline-offset-2 hover:underline disabled:opacity-40"
            onClick={sjekk}
            disabled={sjekker}
          >
            {sjekker ? "Oppdaterer…" : "Oppdater status"}
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {frister.map((f) => (
          <FristKort key={f.key} frist={f} status={statuser[f.key]} />
        ))}
      </div>

      {feil && <p className="text-sm text-red-700">{feil}</p>}

      <Kort>
        <p className={monoLabel}>Ansvarsfraskrivelse</p>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          Wenche er et hjelpeverktøy for enkle holdingselskaper og er i aktiv utvikling. Det er
          ikke en erstatning for profesjonell regnskapsbistand. Kontroller alltid at genererte
          dokumenter er korrekte før innsending. Du er selv ansvarlig for at innsendte
          opplysninger er riktige.
        </p>
      </Kort>
    </div>
  );
}
