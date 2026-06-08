import { useEffect, useState } from "react";
import { StegNav, GaaVidere, Dokumenter, harMinimumsdata, type Fane } from "@wenche/ui";
import { api } from "./api";
import Hjem from "./Hjem";
import Oppsett from "./Oppsett";
import Tall from "./Tall";
import Send from "./Send";

type FaneId = "hjem" | "oppsett" | "tall" | "dokumenter" | "send";

// Hjem er dashboardet (oversikt/frister); de fire arbeidsstegene nummereres 1-4 for å vise
// at de gjennomgås i sekvens.
const FANER: Fane[] = [
  { id: "hjem", navn: "Hjem" },
  { id: "oppsett", navn: "Oppsett", steg: 1 },
  { id: "tall", navn: "Tall", steg: 2 },
  { id: "dokumenter", navn: "Dokumenter", steg: 3 },
  { id: "send", navn: "Send", steg: 4 },
];

interface UpdateInfo {
  naavaerende: string;
  siste: string | null;
  nyere: boolean;
  fra_git: boolean;
}

function Oppdateringsbanner({ info }: { info: UpdateInfo }) {
  const kommando = info.fra_git ? "git pull" : "pip install --upgrade wenche";
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-6 py-2 text-center text-sm text-amber-900">
      Ny versjon av Wenche er tilgjengelig ({info.naavaerende} → {info.siste}). Oppdater med{" "}
      <code className="font-mono">{kommando}</code>.
    </div>
  );
}

export default function App() {
  const [env, setEnv] = useState<string>("prod");
  const [versjon, setVersjon] = useState<string>("");
  const [fane, setFane] = useState<FaneId>("hjem");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [config, setConfig] = useState<any | null>(null);
  const [oppdatering, setOppdatering] = useState<UpdateInfo | null>(null);

  useEffect(() => {
    api.health().then((h) => {
      setEnv(h.env);
      setVersjon(h.wenche);
    }).catch(() => {});
    api.hentConfig().then((r) => setConfig(r.config)).catch(() => {});
    api.updateCheck().then(setOppdatering).catch(() => {});
  }, []);

  // Bytt fane og rull til toppen, så brukeren alltid starter øverst i det nye steget.
  const naviger = (id: string) => {
    setFane(id as FaneId);
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="min-h-screen">
      {oppdatering?.nyere && <Oppdateringsbanner info={oppdatering} />}
      <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="mx-auto max-w-3xl px-6">
          <div className="flex items-center justify-between py-4">
            <div className="flex items-baseline gap-2">
              <span className="font-display text-2xl font-medium tracking-tight">Wenche</span>
              {env === "test" && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-amber-800">
                  Test
                </span>
              )}
            </div>
            {versjon && <span className="font-mono text-[11px] text-muted-foreground">v{versjon}</span>}
          </div>
          <StegNav faner={FANER} aktiv={fane} onNaviger={naviger} />
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        {fane === "hjem" && <Hjem />}
        {fane === "oppsett" && <Oppsett env={env} />}
        {fane === "tall" && <Tall config={config} env={env} onLagret={setConfig} />}
        {fane === "dokumenter" && <Dokumenter config={config} dokument={api.dokument} />}
        {fane === "send" && <Send config={config} env={env} />}

        <GaaVidere
          faner={FANER}
          aktiv={fane}
          onNaviger={naviger}
          disabled={fane === "tall" && !harMinimumsdata(config)}
          disabledHint="Fyll inn selskapsnavn, org.nr. og minst daglig leder eller styreleder, og trykk «Lagre data»."
        />
      </main>
    </div>
  );
}
