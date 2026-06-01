import { useEffect, useState } from "react";
import { api } from "./api";
import { DataSkjema, kr, oppsummer } from "./skjema";

interface Me {
  invited: boolean;
  invite_org?: string | null;
  kunde_org?: string | null;
  env?: string;
}

const monoLabel = "font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground";
const btnPrimar =
  "rounded-full bg-spruce px-5 py-2.5 text-sm font-medium text-background transition hover:brightness-110 disabled:opacity-40";
const btnOutline =
  "rounded-full border border-foreground px-5 py-2.5 text-sm font-medium transition hover:bg-foreground hover:text-background disabled:opacity-40";

function Skall({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-6 py-4">
          <span className="font-display text-2xl font-medium tracking-tight">Wenche</span>
          <span className="hidden text-xs text-muted-foreground sm:inline">Enkel innsending for holdingselskap</span>
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-6 py-12">{children}</main>
    </div>
  );
}

function Kort({ children, accent }: { children: React.ReactNode; accent?: boolean }) {
  return (
    <div
      className={`rounded-sm border border-border p-8 ${accent ? "bg-spruce-soft" : "bg-paper"}`}
    >
      {children}
    </div>
  );
}

function KunInviterte() {
  return (
    <Kort>
      <p className={monoLabel}>Tilgang</p>
      <h1 className="mt-3 font-display text-3xl font-normal">Wenche er kun for inviterte</h1>
      <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
        Har du en invite-lenke, åpne den for å komme i gang. Ellers er tjenesten foreløpig
        lukket.
      </p>
    </Kort>
  );
}

function Onboarding({ org, onApproved }: { org?: string | null; onApproved: () => void }) {
  const [confirmUrl, setConfirmUrl] = useState<string | null>(null);
  const [feil, setFeil] = useState<string | null>(null);
  const [kobler, setKobler] = useState(false);

  const koble = async () => {
    setFeil(null);
    setConfirmUrl(null);
    setKobler(true);
    try {
      const r = await api.systembrukerRequest();
      if (r.godkjent || r.status === "AlreadyApproved") {
        onApproved();
      } else {
        setConfirmUrl(r.confirm_url ?? null);
      }
    } catch (e) {
      setFeil((e as Error).message);
    } finally {
      setKobler(false);
    }
  };

  return (
    <Kort>
      <p className={monoLabel}>Steg 1 · Koble selskap</p>
      <h2 className="mt-3 font-display text-2xl font-normal">Koble til selskapet ditt</h2>
      {org ? (
        <>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Invitasjonen din gjelder selskapet under. Første gang må daglig leder eller
            styreleder godkjenne Wenche i Altinn med BankID. Har selskapet allerede godkjent,
            kobles du til direkte.
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="rounded-md border border-border bg-background px-4 py-2.5 text-sm">
              <span className={monoLabel}>Org</span> <span className="font-mono">{org}</span>
            </div>
            <button className={btnPrimar} onClick={koble} disabled={kobler}>
              {kobler ? "Kobler…" : "Koble systembruker"}
            </button>
          </div>
        </>
      ) : (
        <p className="mt-4 text-sm text-red-700">
          Invite-lenken er ikke knyttet til et selskap. Be om en ny lenke.
        </p>
      )}
      {confirmUrl && (
        <div className="mt-5 rounded-sm border border-border bg-background p-4 text-sm">
          <p className="text-muted-foreground">Godkjenn i Altinn, så kom tilbake:</p>
          <a className="mt-1 block break-all text-spruce underline-offset-2 hover:underline" href={confirmUrl} target="_blank">
            {confirmUrl}
          </a>
          <button className={`${btnOutline} mt-4`} onClick={onApproved}>
            Jeg har godkjent, sjekk på nytt
          </button>
        </div>
      )}
      {feil && <p className="mt-4 text-sm text-red-700">{feil}</p>}
    </Kort>
  );
}

interface Utfall {
  dryRun: boolean;
  type: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data?: any;
  feil?: string;
}

const KVITTERING_ETIKETT: Record<string, string> = {
  forsendelseId: "Forsendelse-ID",
  dialogId: "Dialog-ID",
  instans_id: "Instans-ID",
  oppgavegiversLeveranseReferanse: "Leveranse-referanse",
};

function SeksjonsNav({ visSend }: { visSend: boolean }) {
  const lenker: [string, string][] = [
    ["#selskap", "Selskap"],
    ["#resultatregnskap", "Regnskap"],
    ["#skattemelding", "Skattemelding"],
    ["#aksjonaerer", "Aksjonærer"],
  ];
  if (visSend) lenker.push(["#send", "Send"]);
  return (
    <nav className="sticky top-16 z-40 -mx-6 border-b border-border bg-background/85 px-6 py-3 backdrop-blur-sm">
      <div className="flex flex-wrap gap-x-5 gap-y-1">
        {lenker.map(([h, navn]) => (
          <a
            key={h}
            href={h}
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground transition hover:text-spruce"
          >
            {navn}
          </a>
        ))}
      </div>
    </nav>
  );
}

interface Validering {
  laster: boolean;
  ok?: boolean;
  feil?: string[];
  advarsler?: string[];
  melding?: string;
}

function Innsending({ env }: { env?: string }) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [config, setConfig] = useState<any | null>(null);
  const [lagreFeil, setLagreFeil] = useState<string | null>(null);
  const [bekreft, setBekreft] = useState<{ type: string; navn: string } | null>(null);
  const [validering, setValidering] = useState<Validering | null>(null);
  const [sender, setSender] = useState(false);
  const [utfall, setUtfall] = useState<Utfall | null>(null);

  const lagre = async (c: unknown) => {
    setLagreFeil(null);
    try {
      await api.putData(c);
      setConfig(c);
    } catch (e) {
      setLagreFeil((e as Error).message);
    }
  };

  // Steg 1 av innsending: åpne bekreft-modal og kontroller tallene (dry-run).
  const aapneBekreft = async (type: string, navn: string) => {
    setUtfall(null);
    setBekreft({ type, navn });
    setValidering({ laster: true });
    try {
      const data = await api.innsending(type, true);
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
      const data = await api.innsending(type, false);
      setUtfall({ dryRun: false, type, data });
    } catch (e) {
      setUtfall({ dryRun: false, type, feil: (e as Error).message });
    } finally {
      setSender(false);
      lukkBekreft();
    }
  };

  const typer: [string, string][] = [
    ["aarsregnskap", "Årsregnskap"],
    ["aksjonaer", "Aksjonærregister"],
    ["skattemelding", "Skattemelding"],
  ];

  const o = config ? oppsummer(config) : null;

  return (
    <div className="space-y-6">
      <SeksjonsNav visSend={o !== null} />
      <Kort>
        <DataSkjema onLagre={lagre} visEksempel={env === "test"} />
      </Kort>
      {!o && lagreFeil && <p className="text-sm text-red-700">{lagreFeil}</p>}

      {o && (
        <Kort>
          <div id="send" className="scroll-mt-32">
            <p className={monoLabel}>Steg 3 · Se over og send</p>
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
            {utfall && <Resultatpanel utfall={utfall} />}
          </div>
        </Kort>
      )}

      {bekreft && o && (
        <BekreftModal
          navn={bekreft.navn}
          o={o}
          validering={validering}
          sender={sender}
          onBekreft={bekreftSend}
          onAvbryt={lukkBekreft}
        />
      )}
    </div>
  );
}

function BekreftModal({
  navn,
  o,
  validering,
  sender,
  onBekreft,
  onAvbryt,
}: {
  navn: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  o: any;
  validering: Validering | null;
  sender: boolean;
  onBekreft: () => void;
  onAvbryt: () => void;
}) {
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

        <div className="mt-5 flex items-center justify-end gap-3">
          <button className={btnOutline} onClick={onAvbryt} disabled={sender}>
            Avbryt
          </button>
          <button
            className={`${btnPrimar} min-w-52 text-center`}
            onClick={onBekreft}
            disabled={!klar || sender}
          >
            {sender ? "Sender…" : "Bekreft og send inn"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Panel({
  tone,
  tittel,
  children,
}: {
  tone: "ok" | "advarsel" | "feil";
  tittel: string;
  children?: React.ReactNode;
}) {
  const toner: Record<string, string> = {
    ok: "border-spruce/30 bg-spruce-soft text-spruce",
    advarsel: "border-amber-300 bg-amber-50 text-amber-800",
    feil: "border-red-300 bg-red-50 text-red-800",
  };
  return (
    <div className={`mt-6 rounded-sm border p-5 ${toner[tone]}`}>
      <p className="font-display text-lg">{tittel}</p>
      <div className="mt-2 text-sm text-foreground/80">{children}</div>
    </div>
  );
}

function Liste({ tittel, items }: { tittel?: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mt-2">
      {tittel && <p className={`${monoLabel} mb-1`}>{tittel}</p>}
      <ul className="list-disc space-y-1 pl-5">
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

function Resultatpanel({ utfall }: { utfall: Utfall }) {
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
    const kvittering: Record<string, unknown> =
      data.resultat && typeof data.resultat === "object" ? data.resultat : {};
    const linjer: [string, unknown][] = Object.entries(kvittering).filter(
      ([, v]) => typeof v === "string" || typeof v === "number",
    );
    if (data.instans_id) linjer.unshift(["instans_id", data.instans_id]);
    return (
      <Panel tone="ok" tittel="Sendt inn">
        <p>Innsendingen er levert. Kvittering finner du også i Altinn.</p>
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
      </Panel>
    );
  }

  return (
    <Panel tone="advarsel" tittel="Uventet svar">
      {JSON.stringify(data)}
    </Panel>
  );
}

function Hjem({ me, onChange }: { me: Me; onChange: () => void }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <span className={monoLabel}>
          Innlogget{me.kunde_org ? ` · org ${me.kunde_org}` : ""}
        </span>
        <button
          className="text-sm text-muted-foreground underline-offset-2 hover:text-spruce hover:underline"
          onClick={() => api.logout().then(onChange)}
        >
          Logg ut
        </button>
      </div>
      {me.kunde_org ? <Innsending env={me.env} /> : <Onboarding org={me.invite_org} onApproved={onChange} />}
    </div>
  );
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);

  const refresh = () =>
    api.me().then(setMe).catch(() => setMe({ invited: false }));

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("invite");
    if (token) {
      api
        .invite(token)
        .catch(() => {})
        .finally(() => {
          window.history.replaceState({}, "", window.location.pathname);
          refresh();
        });
    } else {
      refresh();
    }
  }, []);

  // Keep-alive-heartbeat: holder Fly-maskinen våken mens appen er åpen, så scale-to-zero
  // ikke sovner midt i en økt og mister in-memory-tilstanden. Lett GET mot /api/health.
  useEffect(() => {
    const id = setInterval(() => {
      fetch("/api/health").catch(() => {});
    }, 45000);
    return () => clearInterval(id);
  }, []);

  return (
    <Skall>
      {!me ? (
        <p className="text-sm text-muted-foreground">Laster…</p>
      ) : !me.invited ? (
        <KunInviterte />
      ) : (
        <Hjem me={me} onChange={refresh} />
      )}
    </Skall>
  );
}
