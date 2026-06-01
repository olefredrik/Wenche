import { useEffect, useState } from "react";
import { api } from "./api";

interface Me {
  invited: boolean;
  kunde_org?: string | null;
}

const monoLabel = "font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground";
const btnPrimar =
  "rounded-full bg-spruce px-5 py-2.5 text-sm font-medium text-background transition hover:brightness-110 disabled:opacity-40";
const btnOutline =
  "rounded-full border border-foreground px-5 py-2.5 text-sm font-medium transition hover:bg-foreground hover:text-background disabled:opacity-40";
const input =
  "w-full rounded-md border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-spruce";

function Skall({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-6 py-4">
          <span className="font-display text-2xl font-medium tracking-tight">Wenche</span>
          <span className="hidden text-xs text-muted-foreground sm:inline">Årsoppgjøret, rolig sortert</span>
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

function Onboarding({ onApproved }: { onApproved: () => void }) {
  const [org, setOrg] = useState("");
  const [confirmUrl, setConfirmUrl] = useState<string | null>(null);
  const [feil, setFeil] = useState<string | null>(null);

  const koble = async () => {
    setFeil(null);
    setConfirmUrl(null);
    try {
      const r = await api.systembrukerRequest(org.trim());
      if (r.godkjent || r.status === "AlreadyApproved") {
        onApproved();
      } else {
        setConfirmUrl(r.confirm_url ?? null);
      }
    } catch (e) {
      setFeil((e as Error).message);
    }
  };

  return (
    <Kort>
      <p className={monoLabel}>Steg 1 · Koble selskap</p>
      <h2 className="mt-3 font-display text-2xl font-normal">Koble til selskapet ditt</h2>
      <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
        Oppgi organisasjonsnummeret. Første gang må daglig leder eller styreleder godkjenne
        Wenche i Altinn med BankID. Har selskapet allerede godkjent, kobles du til direkte.
      </p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <input
          className={input}
          placeholder="9 siffer"
          value={org}
          onChange={(e) => setOrg(e.target.value)}
        />
        <button className={btnPrimar} onClick={koble} disabled={!org}>
          Koble systembruker
        </button>
      </div>
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

function Innsending() {
  const [tekst, setTekst] = useState("");
  const [lagret, setLagret] = useState(false);
  const [resultat, setResultat] = useState<Record<string, unknown> | null>(null);
  const [feil, setFeil] = useState<string | null>(null);

  const lagre = async () => {
    setFeil(null);
    try {
      const config = JSON.parse(tekst);
      await api.putData(config);
      setLagret(true);
    } catch (e) {
      setFeil(
        (e as Error).message.startsWith("Unexpected")
          ? "Ugyldig JSON."
          : (e as Error).message,
      );
    }
  };

  const kjor = async (type: string, dryRun: boolean) => {
    setFeil(null);
    setResultat(null);
    try {
      setResultat(await api.innsending(type, dryRun));
    } catch (e) {
      setFeil((e as Error).message);
    }
  };

  const typer: [string, string][] = [
    ["aarsregnskap", "Årsregnskap"],
    ["aksjonaer", "Aksjonærregister"],
    ["skattemelding", "Skattemelding"],
  ];

  return (
    <Kort>
      <p className={monoLabel}>Steg 2 · Tall og innsending</p>
      <h2 className="mt-3 font-display text-2xl font-normal">Årets tall</h2>
      <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
        Lim inn dataene (samme struktur som config.yaml, som JSON). De lagres kun i denne økten
        og slettes når du logger ut.
      </p>
      <textarea
        className={`${input} mt-5 h-44 font-mono text-xs`}
        placeholder='{"selskap": {"org_nummer": "..."}, ...}'
        value={tekst}
        onChange={(e) => setTekst(e.target.value)}
      />
      <button className={`${btnPrimar} mt-4`} onClick={lagre} disabled={!tekst}>
        Lagre data
      </button>

      {lagret && (
        <div className="mt-8 space-y-4 border-t border-border pt-6">
          {typer.map(([t, navn]) => (
            <div key={t} className="flex flex-wrap items-center gap-3">
              <span className="w-40 text-sm">{navn}</span>
              <button className={btnOutline} onClick={() => kjor(t, true)}>
                Dry-run
              </button>
              <button className={btnPrimar} onClick={() => kjor(t, false)}>
                Send inn
              </button>
            </div>
          ))}
        </div>
      )}
      {resultat && (
        <pre className="mt-6 overflow-auto rounded-sm border border-border bg-background p-4 font-mono text-xs">
          {JSON.stringify(resultat, null, 2)}
        </pre>
      )}
      {feil && <p className="mt-4 text-sm text-red-700">{feil}</p>}
    </Kort>
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
      {me.kunde_org ? <Innsending /> : <Onboarding onApproved={onChange} />}
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
