import { useState } from "react";
import { btnPrimar, btnOutline, monoLabel } from "./styles";
import { Kort, Panel, Liste, SeksjonsNav } from "./komponenter";
import { kr, oppsummer } from "./skjema";

// Delt se-over-og-send-flyt: dry-run-kontroll i en bekreft-modal, deretter ekte innsending.
// Auth/onboarding holdes utenfor: hver app injiserer `innsending`-funksjonen (hostet legger
// f.eks. inn 409-rebind av systembruker; self-hosted gjør et rett kall).

export interface Utfall {
  dryRun: boolean;
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any;
  feil?: string;
}

export interface Validering {
  laster: boolean;
  ok?: boolean;
  feil?: string[];
  advarsler?: string[];
  melding?: string;
}

export type InnsendingFn = (
  type: string,
  dryRun: boolean,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any,
) => Promise<any>;

const KVITTERING_ETIKETT: Record<string, string> = {
  forsendelseId: "Forsendelse-ID",
  dialogId: "Dialog-ID",
  instans_id: "Instans-ID",
  oppgavegiversLeveranseReferanse: "Leveranse-referanse",
};

const STANDARD_TYPER: [string, string][] = [
  ["aarsregnskap", "Årsregnskap"],
  ["aksjonaer", "Aksjonærregister"],
  ["skattemelding", "Skattemelding"],
];

const STANDARD_SAMTYKKE = (
  <span>
    Jeg bekrefter at jeg har fullmakt til å sende på vegne av selskapet og at tallene er
    korrekte. Jeg sender på eget ansvar.
  </span>
);

export function Resultatpanel({
  utfall,
  env,
  org,
}: {
  utfall: Utfall;
  env?: string;
  org?: string;
}) {
  const { dryRun, data, feil } = utfall;
  if (feil) {
    return (
      <Panel tone="feil" tittel="Noe gikk galt">
        {feil}
      </Panel>
    );
  }
  if (!data) return null;

  if (dryRun) {
    const feilListe: string[] = data.feil ?? [];
    const advarsler: string[] = data.advarsler ?? [];
    if (data.ok && feilListe.length === 0) {
      return (
        <Panel tone="ok" tittel="Validering OK, klar til innsending">
          <Liste tittel="Merknader" items={advarsler} />
        </Panel>
      );
    }
    return (
      <Panel tone="advarsel" tittel="Avvik som må rettes">
        <Liste items={feilListe} />
        <Liste tittel="Merknader" items={advarsler} />
      </Panel>
    );
  }

  if (data.sendt) {
    const lenkeKlasse =
      "mt-3 inline-block font-medium text-spruce underline-offset-2 hover:underline";
    // Årsregnskap: send_inn returnerer en signeringslenke (streng) — signering i Altinn
    // med BankID kan ikke gjøres maskinelt.
    const signeringsUrl = typeof data.resultat === "string" ? data.resultat : null;
    if (signeringsUrl) {
      return (
        <Panel tone="ok" tittel="Sendt inn">
          <p>Dokumentet er lastet opp og venter på din signatur i Altinn.</p>
          <a href={signeringsUrl} target="_blank" rel="noopener noreferrer" className={lenkeKlasse}>
            Signer i Altinn →
          </a>
        </Panel>
      );
    }
    // Aksjonær (forsendelse-ID) / skattemelding (instans): kvittering + lenke til meldingsboks.
    const kvittering: Record<string, unknown> =
      data.resultat && typeof data.resultat === "object" ? data.resultat : {};
    const linjer: [string, unknown][] = Object.entries(kvittering).filter(
      ([, v]) => typeof v === "string" || typeof v === "number",
    );
    if (data.instans_id) linjer.unshift(["instans_id", data.instans_id]);
    const altinnBase = env === "test" ? "https://tt02.altinn.no" : "https://af.altinn.no";
    const meldingsboksUrl = org
      ? `${altinnBase}/?party=urn%3Aaltinn%3Aorganization%3Aidentifier-no%3A${org}`
      : null;
    return (
      <Panel tone="ok" tittel="Sendt inn">
        <p>Innsendingen er levert. Kvittering og status finner du i Altinn.</p>
        {linjer.length > 0 && (
          <dl className="mt-3 space-y-1">
            {linjer.map(([k, v]) => (
              <div key={k} className="flex gap-2 font-mono text-xs">
                <dt className="text-muted-foreground">{KVITTERING_ETIKETT[k] ?? k}:</dt>
                <dd className="break-all">{String(v)}</dd>
              </div>
            ))}
          </dl>
        )}
        {meldingsboksUrl && (
          <a href={meldingsboksUrl} target="_blank" rel="noopener noreferrer" className={lenkeKlasse}>
            Åpne Altinn meldingsboks →
          </a>
        )}
      </Panel>
    );
  }

  return (
    <Panel tone="advarsel" tittel="Uventet svar">
      {JSON.stringify(data)}
    </Panel>
  );
}

function BekreftModal({
  navn,
  o,
  validering,
  sender,
  samtykke,
  onBekreft,
  onAvbryt,
}: {
  navn: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  o: any;
  validering: Validering | null;
  sender: boolean;
  samtykke: React.ReactNode;
  onBekreft: () => void;
  onAvbryt: () => void;
}) {
  const [godtatt, setGodtatt] = useState(false);
  const klar = validering?.ok === true;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/50 p-4"
      onClick={onAvbryt}
    >
      <div
        className="w-full max-w-md rounded-sm border border-border bg-background p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <p className={monoLabel}>Bekreft innsending</p>
        <h3 className="mt-2 font-display text-xl font-normal">{navn}</h3>

        <div className="mt-4 rounded-sm border border-border bg-paper p-4 text-sm">
          <p className="font-medium">
            {o.navn || "Selskap"} · org {o.org}
          </p>
          <p className="mt-1 text-muted-foreground">
            Regnskapsår {o.aar} · {o.antallAksjonaerer} aksjonær(er) ·{" "}
            {o.balansererOk ? "balansen går opp" : `balanse-differanse ${kr(o.balanseDiff)}`}
          </p>
        </div>

        <div className="mt-4 text-sm">
          {validering?.laster && <p className="text-muted-foreground">Kontrollerer tallene…</p>}
          {validering && !validering.laster && klar &&
            ((validering.advarsler?.length ?? 0) > 0 ? (
              <p className="text-spruce">✓ Tallene er gyldige. Les merknadene under før du sender.</p>
            ) : (
              <p className="text-spruce">✓ Alt ser bra ut. Klar til innsending.</p>
            ))}
          {validering && !validering.laster && !klar && (
            <div className="text-amber-800">
              <p className="font-medium">Noen ting bør rettes først:</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {(validering.feil ?? []).map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
                {validering.melding && <li>{validering.melding}</li>}
              </ul>
            </div>
          )}
          {klar && (validering?.advarsler?.length ?? 0) > 0 && (
            <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-800">
              <p className="font-medium">Merknader (ikke-blokkerende):</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {validering!.advarsler!.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          Sendes til myndighetene via Altinn, og er bindende.
        </p>

        {klar && (
          <label className="mt-4 flex items-start gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-[oklch(0.46_0.08_155)]"
              checked={godtatt}
              onChange={(e) => setGodtatt(e.target.checked)}
            />
            {samtykke}
          </label>
        )}

        <div className="mt-5 flex items-center justify-end gap-3">
          <button className={btnOutline} onClick={onAvbryt} disabled={sender}>
            Avbryt
          </button>
          <button
            className={`${btnPrimar} min-w-52 text-center`}
            onClick={onBekreft}
            disabled={!klar || sender || !godtatt}
          >
            {sender ? "Sender…" : "Bekreft og send inn"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Se-over-og-send-seksjonen. `config` er ferdig utfylt (lagret) av DataSkjema.
export function SendSeksjon({
  config,
  innsending,
  env,
  org,
  samtykke = STANDARD_SAMTYKKE,
  typer = STANDARD_TYPER,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  innsending: InnsendingFn;
  env?: string;
  org?: string;
  samtykke?: React.ReactNode;
  typer?: [string, string][];
}) {
  const [bekreft, setBekreft] = useState<{ type: string; navn: string } | null>(null);
  const [validering, setValidering] = useState<Validering | null>(null);
  const [sender, setSender] = useState(false);
  const [utfall, setUtfall] = useState<Utfall | null>(null);

  const o = oppsummer(config);

  // Steg 1 av innsending: åpne bekreft-modal og kontroller tallene (dry-run).
  const aapneBekreft = async (type: string, navn: string) => {
    setUtfall(null);
    setBekreft({ type, navn });
    setValidering({ laster: true });
    try {
      const data = await innsending(type, true, config);
      const feil: string[] = data.feil ?? [];
      setValidering({
        laster: false,
        ok: !!data.ok && feil.length === 0,
        feil,
        advarsler: data.advarsler ?? [],
      });
    } catch (e) {
      setValidering({ laster: false, ok: false, melding: (e as Error).message });
    }
  };

  const lukkBekreft = () => {
    setBekreft(null);
    setValidering(null);
  };

  // Steg 2: brukeren har bekreftet, send inn på ekte.
  const bekreftSend = async () => {
    if (!bekreft) return;
    const { type } = bekreft;
    setSender(true);
    try {
      const data = await innsending(type, false, config);
      setUtfall({ dryRun: false, type, data });
    } catch (e) {
      setUtfall({ dryRun: false, type, feil: (e as Error).message });
    } finally {
      setSender(false);
      lukkBekreft();
    }
  };

  return (
    <Kort>
      <div id="send" className="scroll-mt-32">
        <p className={monoLabel}>Se over og send</p>
        <div className="mt-4 rounded-sm border border-border bg-background p-4 text-sm">
          <p className="font-medium">
            {o.navn || "Selskap"} · org {o.org}
          </p>
          <p className="mt-1 text-muted-foreground">
            Regnskapsår {o.aar} · {o.antallAksjonaerer} aksjonær(er) ·{" "}
            {o.balansererOk ? (
              <span className="text-spruce">balansen går opp</span>
            ) : (
              <span className="text-red-700">balanse-differanse {kr(o.balanseDiff)}</span>
            )}
          </p>
        </div>
        <p className="mt-4 flex items-start gap-2 text-sm text-muted-foreground">
          <span className="text-spruce">✓</span>
          <span>
            Trygt: når du trykker «Fortsett til innsending», kontrollerer Wenche tallene og
            viser deg en oppsummering. Ingenting sendes til myndighetene før du bekrefter.
          </span>
        </p>
        <div className="mt-5 space-y-3">
          {typer.map(([t, navn]) => (
            <div key={t} className="flex flex-wrap items-center gap-3">
              <span className="w-40 text-sm">{navn}</span>
              <button
                className={btnPrimar}
                disabled={bekreft !== null || sender}
                onClick={() => aapneBekreft(t, navn)}
              >
                Fortsett til innsending
              </button>
            </div>
          ))}
        </div>
        {utfall && <Resultatpanel utfall={utfall} env={env} org={org} />}
      </div>

      {bekreft && (
        <BekreftModal
          navn={bekreft.navn}
          o={o}
          validering={validering}
          sender={sender}
          samtykke={samtykke}
          onBekreft={bekreftSend}
          onAvbryt={lukkBekreft}
        />
      )}
    </Kort>
  );
}

export { SeksjonsNav };
