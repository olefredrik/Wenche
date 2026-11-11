// Send: dry-run + bekreft + ekte innsending, med selvhelende 409-rebind.
import {
  IngenDataPanel,
  Panel,
  SendSeksjon,
  StegTittel,
  oppsummer,
  type ApiFeil,
  type Config,
  type InnsendingFn,
} from "@wenche/ui";
import { api } from "./api";
import { HOSTET_SAMTYKKE } from "./felles";
import { sporHendelse } from "./sporing";
import type { Me } from "./typer";

export function SendFane({ config, me }: { config: Config | null; me: Me }) {
  if (!me.kunde_org) {
    return (
      <Panel tone="advarsel" tittel="Ikke koblet ennå">
        Koble selskapet ditt til Altinn på «Hjem» før du sender inn.
      </Panel>
    );
  }
  if (!config) {
    return <IngenDataPanel>Fyll inn og lagre tallene under «Tall» før du sender inn.</IngenDataPanel>;
  }

  // Selvhelende systembruker-binding: en 409 betyr at bindingen gikk tapt (serveren sov/
  // restartet). Den reises FØR innsending, så det er trygt å rebinde og prøve én gang til.
  const innsending: InnsendingFn = async (type, dryRun, cfg, bekreftKlage) => {
    if (dryRun) sporHendelse("send-start", { type });
    try {
      const data = await api.innsending(type, dryRun, cfg, bekreftKlage);
      if (!dryRun && "sendt" in data && data.sendt) sporHendelse("send-ok", { type });
      return data;
    } catch (e) {
      if (!dryRun && (e as ApiFeil).status === 409) {
        await api.systembrukerRequest();
        const data = await api.innsending(type, dryRun, cfg, bekreftKlage);
        if ("sendt" in data && data.sendt) sporHendelse("send-ok", { type });
        return data;
      }
      throw e;
    }
  };

  const o = oppsummer(config);
  return (
    <div className="space-y-6">
      <StegTittel tittel="Send inn">
        Wenche kontrollerer tallene og viser en oppsummering før noe sendes til myndighetene.
      </StegTittel>
      <SendSeksjon
        config={config}
        innsending={innsending}
        env={me.env}
        org={o.org}
        samtykke={HOSTET_SAMTYKKE}
      />
    </div>
  );
}
