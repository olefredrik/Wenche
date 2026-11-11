import { useEffect, useState } from "react";
import {
  AppHeader,
  Banner,
  Dokumenter,
  GaaVidere,
  StegNav,
  harMinimumsdata,
  useUlagretVakt,
  type Config,
} from "@wenche/ui";
import { api } from "./api";
import Hjem from "./Hjem";
import Oppsett from "./Oppsett";
import Send from "./Send";
import Tall from "./Tall";
import { FANER, type FaneId, type UpdateInfo } from "./typer";

function Oppdateringsbanner({ info }: { info: UpdateInfo }) {
  const kommando = info.fra_git ? "git pull" : "pip install --upgrade wenche";
  return (
    <Banner>
      Ny versjon av Wenche er tilgjengelig ({info.naavaerende} → {info.siste}). Oppdater med{" "}
      <code className="font-mono">{kommando}</code>.
    </Banner>
  );
}

export default function App() {
  const [env, setEnv] = useState<string>("prod");
  const [versjon, setVersjon] = useState<string>("");
  const [fane, setFane] = useState<FaneId>("hjem");
  const [config, setConfig] = useState<Config | null>(null);
  const [oppdatering, setOppdatering] = useState<UpdateInfo | null>(null);
  const [ulagret, setUlagret] = useState(false);
  const [feil, setFeil] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setEnv(h.env);
        setVersjon(h.wenche);
      })
      .catch(() => setFeil("Fikk ikke kontakt med den lokale Wenche-serveren. Start `wenche` på nytt."));
    api
      .hentConfig()
      .then((r) => setConfig(r.config))
      .catch(() => {});
    api
      .updateCheck()
      .then(setOppdatering)
      .catch(() => {});
  }, []);

  // Bytt fane og rull til toppen, så brukeren alltid starter øverst i det nye steget.
  const naviger = (id: string) => {
    setFane(id as FaneId);
    window.scrollTo({ top: 0 });
  };
  // Fanebytte avmonterer skjemaet, så ulagrede endringer må bekreftes først.
  const { forsoekNaviger, dialog: ulagretDialog } = useUlagretVakt(ulagret, naviger);

  return (
    <div className="min-h-screen">
      {oppdatering?.nyere && <Oppdateringsbanner info={oppdatering} />}
      <AppHeader
        env={env}
        hoyre={versjon ? <span className="font-mono text-[11px] text-muted-foreground">v{versjon}</span> : undefined}
        nav={<StegNav faner={FANER} aktiv={fane} onNaviger={forsoekNaviger} />}
      />

      <main className="mx-auto max-w-3xl px-6 py-10">
        {feil && (
          <p role="alert" className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {feil}
          </p>
        )}
        {fane === "hjem" && <Hjem />}
        {fane === "oppsett" && <Oppsett env={env} />}
        {fane === "tall" && <Tall config={config} env={env} onLagret={setConfig} onUlagret={setUlagret} />}
        {fane === "dokumenter" && <Dokumenter config={config} dokument={api.dokument} />}
        {fane === "send" && <Send config={config} env={env} />}

        <GaaVidere
          faner={FANER}
          aktiv={fane}
          onNaviger={forsoekNaviger}
          disabled={fane === "tall" && !harMinimumsdata(config)}
          disabledHint="Trykk «Lagre data» for å gå videre. (Krever selskapsnavn, org.nr. og minst daglig leder eller styreleder.)"
        />
      </main>
      {ulagretDialog}
    </div>
  );
}
