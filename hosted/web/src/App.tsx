import { useEffect, useState } from "react";
import { api } from "./api";

interface Me {
  invited: boolean;
  kunde_org?: string | null;
}

const knapp =
  "rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-40";
const felt = "w-full rounded-md border border-slate-300 px-3 py-2 text-sm";

function Skall({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-3xl px-4 py-3 text-lg font-semibold">👵 Wenche</div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
    </div>
  );
}

function KunInviterte() {
  return (
    <div className="mx-auto max-w-md rounded-lg border bg-white p-6 text-center">
      <h1 className="mb-2 text-xl font-semibold">Wenche er kun for inviterte</h1>
      <p className="text-sm text-slate-500">
        Har du en invite-lenke, åpne den for å komme i gang. Ellers er tjenesten foreløpig
        lukket.
      </p>
    </div>
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
    <div className="space-y-4 rounded-lg border bg-white p-6">
      <h2 className="text-lg font-semibold">Koble til selskapet ditt</h2>
      <p className="text-sm text-slate-500">
        Oppgi organisasjonsnummeret. Første gang må daglig leder/styreleder godkjenne Wenche i
        Altinn (med BankID). Har selskapet allerede godkjent, kobles du til direkte.
      </p>
      <input
        className={felt}
        placeholder="9 siffer"
        value={org}
        onChange={(e) => setOrg(e.target.value)}
      />
      <button className={knapp} onClick={koble} disabled={!org}>
        Koble systembruker
      </button>
      {confirmUrl && (
        <div className="rounded bg-amber-50 p-3 text-sm">
          <p className="mb-1 text-amber-800">Godkjenn i Altinn, så kom tilbake:</p>
          <a className="break-all text-blue-700 underline" href={confirmUrl} target="_blank">
            {confirmUrl}
          </a>
          <div className="mt-2">
            <button className={knapp} onClick={onApproved}>
              Jeg har godkjent — sjekk på nytt
            </button>
          </div>
        </div>
      )}
      {feil && <p className="text-sm text-red-600">{feil}</p>}
    </div>
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

  const typer = ["aarsregnskap", "aksjonaer", "skattemelding"];

  return (
    <div className="space-y-4 rounded-lg border bg-white p-6">
      <h2 className="text-lg font-semibold">Tall og innsending</h2>
      <p className="text-sm text-slate-500">
        Lim inn dataene (samme struktur som config.yaml, som JSON). Dataene lagres kun i denne
        sesjonen og slettes når du logger ut.
      </p>
      <textarea
        className={`${felt} h-48 font-mono text-xs`}
        placeholder='{"selskap": {"org_nummer": "..."}, ...}'
        value={tekst}
        onChange={(e) => setTekst(e.target.value)}
      />
      <button className={knapp} onClick={lagre} disabled={!tekst}>
        Lagre data
      </button>
      {lagret && (
        <div className="space-y-3 border-t pt-4">
          {typer.map((t) => (
            <div key={t} className="flex items-center gap-2">
              <span className="w-36 text-sm capitalize">{t}</span>
              <button className={knapp} onClick={() => kjor(t, true)}>
                Dry-run
              </button>
              <button
                className={`${knapp} bg-red-700 hover:bg-red-600`}
                onClick={() => kjor(t, false)}
              >
                Send inn
              </button>
            </div>
          ))}
        </div>
      )}
      {resultat && (
        <pre className="overflow-auto rounded bg-slate-100 p-3 text-xs">
          {JSON.stringify(resultat, null, 2)}
        </pre>
      )}
      {feil && <p className="text-sm text-red-600">{feil}</p>}
    </div>
  );
}

function Hjem({ me, onChange }: { me: Me; onChange: () => void }) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>Innlogget{me.kunde_org ? ` · org ${me.kunde_org}` : ""}</span>
        <button
          className="text-slate-500 underline"
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
    // Løs inn en evt. invite-lenke (?invite=...) og rydd den ut av URL-en.
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
        <p className="text-slate-500">Laster…</p>
      ) : !me.invited ? (
        <KunInviterte />
      ) : (
        <Hjem me={me} onChange={refresh} />
      )}
    </Skall>
  );
}
