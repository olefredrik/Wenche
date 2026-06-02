import { useEffect, useState } from "react";
import { btnPrimar } from "@wenche/ui";
import { api } from "./api";
import Hjem from "./Hjem";
import Oppsett from "./Oppsett";
import Tall from "./Tall";
import Dokumenter from "./Dokumenter";
import Send from "./Send";

type Fane = "hjem" | "oppsett" | "tall" | "dokumenter" | "send";

// Hjem er dashboardet (oversikt/frister); de fire arbeidsstegene nummereres 1–4 for å vise
// at de gjennomgås i sekvens.
const FANER: { id: Fane; navn: string; steg?: number }[] = [
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
  const [fane, setFane] = useState<Fane>("hjem");
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
  const naviger = (f: Fane) => {
    setFane(f);
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
          <nav className="flex flex-wrap gap-x-5 gap-y-1">
            {FANER.map(({ id, navn, steg }) => {
              const aktiv = fane === id;
              return (
                <button
                  key={id}
                  onClick={() => naviger(id)}
                  aria-current={aktiv ? "page" : undefined}
                  className={`group -mb-px flex items-center gap-2 border-b-2 pb-3 pt-1 transition ${
                    aktiv ? "border-spruce" : "border-transparent"
                  }`}
                >
                  {steg !== undefined && (
                    <span
                      className={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-medium transition ${
                        aktiv ? "bg-spruce text-background" : "bg-border text-muted-foreground group-hover:text-foreground"
                      }`}
                    >
                      {steg}
                    </span>
                  )}
                  <span
                    className={`font-mono text-[11px] uppercase tracking-[0.15em] transition ${
                      aktiv ? "font-medium text-spruce" : "text-muted-foreground group-hover:text-foreground"
                    }`}
                  >
                    {navn}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-10">
        {fane === "hjem" && <Hjem />}
        {fane === "oppsett" && <Oppsett env={env} />}
        {fane === "tall" && <Tall config={config} env={env} onLagret={setConfig} />}
        {fane === "dokumenter" && <Dokumenter config={config} />}
        {fane === "send" && <Send config={config} env={env} />}

        <GaaVidere fane={fane} naviger={naviger} />
      </main>
    </div>
  );
}

// «Gå videre»-knapp som tar brukeren til neste steg, så tab-menyen ikke er eneste vei
// gjennom flyten. Vises på alle faner unntatt den siste (Send er sluttsteget).
function GaaVidere({ fane, naviger }: { fane: Fane; naviger: (f: Fane) => void }) {
  const idx = FANER.findIndex((f) => f.id === fane);
  const neste = FANER[idx + 1];
  if (!neste) return null;
  return (
    <div className="mt-12 flex justify-end border-t border-border pt-6">
      <button className={btnPrimar} onClick={() => naviger(neste.id)}>
        {fane === "hjem" ? "Kom i gang" : "Gå videre"}: {neste.steg ? `${neste.steg}. ` : ""}
        {neste.navn} →
      </button>
    </div>
  );
}
