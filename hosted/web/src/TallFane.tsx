// Tall: skjema + noter. Klienten er fasit (ingen disk); lagring setter App-config-en.
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

export function TallFane({
  config,
  env,
  org,
  onLagret,
  onUlagret,
}: {
  config: Config | null;
  env?: string;
  org?: string | null;
  onLagret: (c: Config) => void;
  onUlagret: (ulagret: boolean) => void;
}) {
  const [noter, setNoter] = useState<NoterData>(() => noterFraConfig(config));
  const [lagret, setLagret] = useState(false);

  const lagre = async (formConfig: Config) => {
    onLagret({ ...formConfig, noter });
    setLagret(true);
  };

  return (
    <div className="space-y-6">
      <StegTittel tittel="Tall">
        Fyll inn selskapsopplysninger, regnskap, balanse, skattemelding og aksjonærer. Trykk
        «Lagre data», så kan du se over dokumentene og sende inn.
      </StegTittel>
      <Kort>
        <DataSkjema
          onLagre={lagre}
          visEksempel={env === "test"}
          initial={config ?? undefined}
          laastOrg={org ?? undefined}
          stegEtikett="Steg 1 · Årets tall"
          importerSaft={api.importerSaft}
          prefillSelskap={api.selskap}
          beregnSkatt={api.skatteberegning}
          saftMerknad="SAF-T-filen behandles i minnet i EØS og lagres ikke."
          ekstraSeksjon={<NoterSeksjon noter={noter} setNoter={setNoter} />}
          onUlagret={onUlagret}
        />
      </Kort>
      {lagret && (
        <p role="status" className="text-sm text-spruce">
          ✓ Lagret. Gå videre til «Dokumenter» eller «Send».
        </p>
      )}
    </div>
  );
}
