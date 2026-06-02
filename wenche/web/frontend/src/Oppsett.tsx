import { useEffect, useRef, useState } from "react";
import { Kort, Inn, monoLabel, btnPrimar, btnOutlineLett } from "@wenche/ui";
import { api } from "./api";

interface Status {
  env: string;
  credentials: { client_id: string; kid: string; orgnr: string; mangler: string[]; komplett: boolean };
  nokkel: { ok: boolean; sti: string };
  systembruker: { har_forespoersel: boolean; confirm_url: string | null };
}

// Tilstanden til systembruker-koblingen, utledet av status-kallet mot Altinn.
type SysState = "laster" | "godkjent" | "venter" | "avvist" | "ikke_opprettet" | "ukjent";

function Merke({ ok }: { ok: boolean | null }) {
  if (ok === null) return <span className="text-xs text-muted-foreground">sjekker…</span>;
  return ok ? (
    <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-spruce">✓ Klart</span>
  ) : (
    <span className="font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground">
      ○ Gjenstår
    </span>
  );
}

function Steg({
  n,
  tittel,
  ok,
  children,
}: {
  n: number;
  tittel: string;
  ok: boolean | null;
  children: React.ReactNode;
}) {
  return (
    <Kort>
      <div className="flex items-center justify-between">
        <p className={monoLabel}>Steg {n}</p>
        <Merke ok={ok} />
      </div>
      <h3 className="mt-2 font-display text-xl font-normal">{tittel}</h3>
      <div className="mt-4">{children}</div>
    </Kort>
  );
}

export default function Oppsett({ env }: { env: string }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [cred, setCred] = useState({ client_id: "", kid: "", orgnr: "" });
  const [sysState, setSysState] = useState<SysState>("laster");
  const [confirmUrl, setConfirmUrl] = useState<string | null>(null);
  const [melding, setMelding] = useState<{ tone: "ok" | "feil"; tekst: string } | null>(null);
  const [lagrer, setLagrer] = useState(false);
  const [tester, setTester] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [testResultat, setTestResultat] = useState<any | null>(null);
  const [jobber, setJobber] = useState<string | null>(null);
  const [visAvansert, setVisAvansert] = useState(false);
  const filRef = useRef<HTMLInputElement>(null);

  const last = async () => {
    const s: Status = await api.oppsettStatus();
    setStatus(s);
    setCred({ client_id: s.credentials.client_id, kid: s.credentials.kid, orgnr: s.credentials.orgnr });
    setConfirmUrl(s.systembruker.confirm_url);
    // Hent ekte systembruker-status fra Altinn når det finnes en forespørsel og creds er på plass.
    if (s.systembruker.har_forespoersel && s.credentials.komplett && s.nokkel.ok) {
      try {
        const r = await api.systembrukerStatus();
        setSysState((r.status as SysState) ?? "ukjent");
      } catch {
        setSysState("ukjent");
      }
    } else {
      setSysState("ikke_opprettet");
    }
  };

  useEffect(() => {
    last().catch((e) => setMelding({ tone: "feil", tekst: (e as Error).message }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const miljoNavn = env === "test" ? "testmiljø (tt02)" : "produksjon";
  const credsOk = !!status?.credentials.komplett;
  const nokkelOk = !!status?.nokkel.ok;
  const sysOk = sysState === "godkjent";
  const altKlart = credsOk && nokkelOk && sysOk;

  const nesteSteg = !credsOk
    ? "Fyll inn Maskinporten-feltene i Steg 1."
    : !nokkelOk
      ? "Last opp den private nøkkelen i Steg 2."
      : !sysOk
        ? "Koble Wenche til Altinn i Steg 3."
        : null;

  const lagreCred = async () => {
    setLagrer(true);
    setMelding(null);
    try {
      await api.lagreCredentials(cred);
      await last();
      setMelding({ tone: "ok", tekst: "Konfigurasjon lagret." });
    } catch (e) {
      setMelding({ tone: "feil", tekst: (e as Error).message });
    } finally {
      setLagrer(false);
    }
  };

  const lastOppNokkel = async (file: File) => {
    setMelding(null);
    try {
      await api.lagreNokkel(await file.text());
      await last();
      setMelding({ tone: "ok", tekst: "Privat nøkkel lagret." });
    } catch (e) {
      setMelding({ tone: "feil", tekst: (e as Error).message });
    }
  };

  const test = async () => {
    setTester(true);
    setTestResultat(null);
    try {
      const r = await api.testTilkobling();
      setTestResultat(r);
      if (r.systembruker?.status) setSysState(r.systembruker.status as SysState);
    } catch (e) {
      setTestResultat({ auth_ok: false, melding: (e as Error).message });
    } finally {
      setTester(false);
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const kjorSys = async (navn: string, fn: () => Promise<any>) => {
    setJobber(navn);
    setMelding(null);
    try {
      const r = await fn();
      if (r.confirm_url) setConfirmUrl(r.confirm_url);
      if (navn === "opprett") setSysState("venter");
      if (navn === "status" && r.status) setSysState(r.status as SysState);
      if (navn === "registrer") setMelding({ tone: "ok", tekst: r.oppdatert ? "System oppdatert." : "System registrert." });
      await api.oppsettStatus().then((s: Status) => setStatus(s));
    } catch (e) {
      setMelding({ tone: "feil", tekst: (e as Error).message });
    } finally {
      setJobber(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Oppsett</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Koble Wenche til Altinn for {miljoNavn} i tre steg. Verdiene lagres lokalt i{" "}
          <code className="font-mono">~/.wenche/.env</code> og sendes aldri til noen server.
        </p>
      </div>

      {/* Statusbanner: hvor er jeg, og hva er neste steg? */}
      <div
        className={`rounded-sm border p-5 ${altKlart ? "border-spruce/30 bg-spruce-soft" : "border-border bg-paper"}`}
      >
        {altKlart ? (
          <p className="font-display text-lg text-spruce">✓ Wenche er klar til innsending</p>
        ) : (
          <>
            <p className="font-display text-lg">Slik kommer du i gang</p>
            <p className="mt-1 text-sm text-muted-foreground">Neste steg: {nesteSteg}</p>
          </>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
          <button
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-spruce underline-offset-2 hover:underline disabled:opacity-40"
            onClick={test}
            disabled={tester}
          >
            {tester ? "Tester…" : "Test tilkobling"}
          </button>
          {testResultat && (
            <span className={testResultat.auth_ok ? "text-spruce" : "text-red-700"}>
              {testResultat.auth_ok ? "✓ " : "✗ "}
              {testResultat.melding}
              {testResultat.systembruker ? ` · ${testResultat.systembruker.melding}` : ""}
            </span>
          )}
        </div>
      </div>

      {melding && (
        <p className={`text-sm ${melding.tone === "ok" ? "text-spruce" : "text-red-700"}`}>
          {melding.tone === "ok" ? "✓ " : ""}
          {melding.tekst}
        </p>
      )}

      {/* Steg 1 — Maskinporten */}
      <Steg n={1} tittel="Maskinporten-klient og organisasjon" ok={credsOk}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Inn label="Maskinporten klient-ID" value={cred.client_id} onChange={(v) => setCred({ ...cred, client_id: v })} />
          <Inn label="Nøkkel-ID (kid)" value={cred.kid} onChange={(v) => setCred({ ...cred, kid: v })} />
          <Inn
            label={env === "test" ? "Test-orgnr (Tenor)" : "Organisasjonsnummer"}
            value={cred.orgnr}
            onChange={(v) => setCred({ ...cred, orgnr: v })}
          />
        </div>
        <button className={`${btnPrimar} mt-4`} onClick={lagreCred} disabled={lagrer}>
          {lagrer ? "Lagrer…" : "Lagre konfigurasjon"}
        </button>
      </Steg>

      {/* Steg 2 — Privat nøkkel */}
      <Steg n={2} tittel="Privat RSA-nøkkel" ok={nokkelOk}>
        {nokkelOk ? (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="text-spruce">✓ Nøkkel på plass</span>
            <span className="font-mono text-xs text-muted-foreground">{status?.nokkel.sti}</span>
            <button
              className="text-xs text-muted-foreground underline-offset-2 hover:text-spruce hover:underline"
              onClick={() => filRef.current?.click()}
            >
              Bytt nøkkel
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <p className="w-full text-sm text-muted-foreground">
              Last opp den private RSA-nøkkelen (.pem) Wenche bruker mot Maskinporten. Den lagres
              lokalt og sendes aldri videre.
            </p>
            <button className={btnOutlineLett} onClick={() => filRef.current?.click()}>
              Last opp nøkkelfil (.pem)
            </button>
          </div>
        )}
        <input
          ref={filRef}
          type="file"
          accept=".pem,.key"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) lastOppNokkel(f);
          }}
        />
      </Steg>

      {/* Steg 3 — Systembruker */}
      <Steg n={3} tittel="Koble Wenche til Altinn" ok={sysOk ? true : sysState === "laster" ? null : false}>
        <Systembruker
          sysState={sysState}
          confirmUrl={confirmUrl}
          jobber={jobber}
          klar={credsOk && nokkelOk}
          visAvansert={visAvansert}
          setVisAvansert={setVisAvansert}
          kjorSys={kjorSys}
        />
      </Steg>
    </div>
  );
}

function Systembruker({
  sysState,
  confirmUrl,
  jobber,
  klar,
  visAvansert,
  setVisAvansert,
  kjorSys,
}: {
  sysState: SysState;
  confirmUrl: string | null;
  jobber: string | null;
  klar: boolean;
  visAvansert: boolean;
  setVisAvansert: (v: boolean) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  kjorSys: (navn: string, fn: () => Promise<any>) => Promise<void>;
}) {
  const opprett = (
    <button className={btnPrimar} onClick={() => kjorSys("opprett", api.opprettSystembruker)} disabled={!!jobber || !klar}>
      {jobber === "opprett" ? "Oppretter…" : "Opprett systembruker"}
    </button>
  );
  const sjekk = (
    <button className={btnOutlineLett} onClick={() => kjorSys("status", api.systembrukerStatus)} disabled={!!jobber}>
      {jobber === "status" ? "Sjekker…" : "Sjekk status"}
    </button>
  );

  return (
    <div className="space-y-4">
      {sysState === "godkjent" ? (
        <p className="text-sm text-spruce">
          ✓ Wenche er koblet til Altinn og kan sende inn på vegne av selskapet.
        </p>
      ) : sysState === "venter" ? (
        <>
          <p className="text-sm text-muted-foreground">
            Forespørselen venter på godkjenning i Altinn. Daglig leder eller styreleder må
            godkjenne med BankID. Trykk «Sjekk status» når det er gjort.
          </p>
          {confirmUrl && (
            <div className="rounded-sm border border-border bg-background p-4 text-sm">
              <p className="text-muted-foreground">Åpne lenken, godkjenn med BankID:</p>
              <a
                href={confirmUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 block break-all text-spruce underline-offset-2 hover:underline"
              >
                {confirmUrl}
              </a>
            </div>
          )}
          {sjekk}
        </>
      ) : sysState === "avvist" ? (
        <>
          <p className="text-sm text-red-700">Forespørselen ble avvist. Opprett en ny.</p>
          {opprett}
        </>
      ) : sysState === "laster" ? (
        <p className="text-sm text-muted-foreground">Henter status…</p>
      ) : (
        <>
          <p className="text-sm text-muted-foreground">
            Opprett en systembruker-forespørsel og godkjenn den i Altinn med BankID (daglig leder
            eller styreleder). Da kan Wenche sende inn på vegne av selskapet.
            {!klar && " Fullfør Steg 1 og 2 først."}
          </p>
          {opprett}
        </>
      )}

      {/* Sjelden brukte handlinger, skjult bak Avansert (jf. NiceGUI-en). */}
      <details open={visAvansert} onToggle={(e) => setVisAvansert((e.target as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer font-mono text-[11px] uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground">
          Avansert
        </summary>
        <p className="mt-2 text-xs text-muted-foreground">
          Trengs sjelden — bruk disse hvis du må re-registrere systemet, sjekke status manuelt
          eller legge til nye rettigheter på en allerede godkjent systembruker.
        </p>
        <div className="mt-3 flex flex-wrap gap-3">
          <button className={btnOutlineLett} onClick={() => kjorSys("registrer", api.registrerSystem)} disabled={!!jobber}>
            {jobber === "registrer" ? "Registrerer…" : "Registrer system på nytt"}
          </button>
          <button className={btnOutlineLett} onClick={() => kjorSys("status", api.systembrukerStatus)} disabled={!!jobber}>
            {jobber === "status" ? "Sjekker…" : "Sjekk status"}
          </button>
          <button className={btnOutlineLett} onClick={() => kjorSys("oppdater", api.oppdaterSystembruker)} disabled={!!jobber}>
            {jobber === "oppdater" ? "Sender…" : "Oppdater rettigheter"}
          </button>
        </div>
      </details>
    </div>
  );
}
