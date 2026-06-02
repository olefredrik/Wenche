import { SendSeksjon, SeksjonsNav, Panel, oppsummer, type InnsendingFn } from "@wenche/ui";
import { api } from "./api";

const SAMTYKKE = (
  <span>
    Jeg bekrefter at jeg har fullmakt til å sende på vegne av selskapet og at tallene er
    korrekte. Jeg sender på eget ansvar.
  </span>
);

export default function Send({ config, env }: { config: any; env: string }) {
  if (!config) {
    return (
      <Panel tone="advarsel" tittel="Ingen data ennå">
        Fyll inn og lagre tallene under «Tall» før du sender inn.
      </Panel>
    );
  }

  const innsending: InnsendingFn = (type, dryRun, cfg) => api.innsending(type, dryRun, cfg);
  const o = oppsummer(config);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Send inn</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Wenche kontrollerer tallene (dry-run) og viser en oppsummering før noe sendes til
          myndighetene. Du bekrefter selv før innsending.
        </p>
      </div>
      <SeksjonsNav lenker={[["#send", "Send"]]} top="top-0" />
      <SendSeksjon config={config} innsending={innsending} env={env} org={o.org} samtykke={SAMTYKKE} />
    </div>
  );
}
