import { useState } from "react";
import {
  DataSkjema,
  Kort,
  NoterSeksjon,
  StegTittel,
  noterFraConfig,
  type Config,
  type NoterData,
} from "@wenche/ui";
import { api } from "./api";

export default function Tall({
  config,
  env,
  onLagret,
  onUlagret,
}: {
  config: Config | null;
  env: string;
  onLagret: (c: Config) => void;
  onUlagret: (ulagret: boolean) => void;
}) {
  const [noter, setNoter] = useState<NoterData>(() => noterFraConfig(config));
  const [kvittering, setKvittering] = useState<string | null>(null);

  const lagre = async (formConfig: Config) => {
    const full = { ...formConfig, noter };
    const r = await api.lagreConfig(full);
    onLagret(full);
    setKvittering(`Lagret til ${r.fil}`);
  };

  return (
    <div className="space-y-6">
      <StegTittel tittel="Tall">
        Fyll inn selskapsopplysninger, regnskap, balanse, skattemelding og aksjonærer. Trykk
        «Lagre data» for å skrive til {env === "test" ? "config.dev.yaml" : "config.yaml"}.
      </StegTittel>

      <Kort>
        <DataSkjema
          onLagre={lagre}
          visEksempel={env === "test"}
          initial={config ?? undefined}
          stegEtikett="Steg 2 · Årets tall"
          importerSaft={api.importerSaft}
          beregnSkatt={api.skatteberegning}
          saftMerknad="SAF-T-filen behandles lokalt på din egen maskin og lagres ikke."
          ekstraSeksjon={<NoterSeksjon noter={noter} setNoter={setNoter} />}
          onUlagret={onUlagret}
        />
      </Kort>

      {kvittering && (
        <p role="status" className="text-sm text-spruce">
          ✓ {kvittering}
        </p>
      )}
    </div>
  );
}
