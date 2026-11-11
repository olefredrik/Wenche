import {
  IngenDataPanel,
  SeksjonsNav,
  SendSeksjon,
  StegTittel,
  oppsummer,
  type Config,
  type InnsendingFn,
} from "@wenche/ui";
import { api } from "./api";

const SAMTYKKE = (
  <span>
    Jeg bekrefter at jeg har fullmakt til å sende på vegne av selskapet og at tallene er
    korrekte. Jeg sender på eget ansvar.
  </span>
);

export default function Send({ config, env }: { config: Config | null; env: string }) {
  if (!config) {
    return <IngenDataPanel>Fyll inn og lagre tallene under «Tall» før du sender inn.</IngenDataPanel>;
  }

  const innsending: InnsendingFn = (type, dryRun, cfg, bekreftKlage) =>
    api.innsending(type, dryRun, cfg, bekreftKlage);
  const o = oppsummer(config);

  return (
    <div className="space-y-6">
      <StegTittel tittel="Send inn">
        Wenche kontrollerer tallene (dry-run) og viser en oppsummering før noe sendes til
        myndighetene. Du bekrefter selv før innsending.
      </StegTittel>
      <SeksjonsNav lenker={[["#send", "Send"]]} top="top-0" />
      <SendSeksjon config={config} innsending={innsending} env={env} org={o.org} samtykke={SAMTYKKE} />
    </div>
  );
}
