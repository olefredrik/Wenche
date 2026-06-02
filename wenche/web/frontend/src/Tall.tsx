import { useState } from "react";
import { DataSkjema, Kort, NoterSeksjon, noterFraConfig, type NoterData } from "@wenche/ui";
import { api } from "./api";

export default function Tall({
  config,
  env,
  onLagret,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  env: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onLagret: (c: any) => void;
}) {
  const [noter, setNoter] = useState<NoterData>(() => noterFraConfig(config));
  const [kvittering, setKvittering] = useState<string | null>(null);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const lagre = async (formConfig: any) => {
    const full = { ...formConfig, noter };
    const r = await api.lagreConfig(full);
    onLagret(full);
    setKvittering(`Lagret til ${r.fil}`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Tall</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Fyll inn selskapsopplysninger, regnskap, balanse, skattemelding og aksjonærer. Trykk
          «Lagre data» for å skrive til {env === "test" ? "config.dev.yaml" : "config.yaml"}.
        </p>
      </div>

      <Kort>
        <DataSkjema
          onLagre={lagre}
          visEksempel={env === "test"}
          initial={config ?? undefined}
          importerSaft={api.importerSaft}
          saftMerknad="SAF-T-filen behandles lokalt på din egen maskin og lagres ikke."
          ekstraSeksjon={<NoterSeksjon noter={noter} setNoter={setNoter} />}
        />
      </Kort>

      {kvittering && <p className="text-sm text-spruce">✓ {kvittering}</p>}
    </div>
  );
}
