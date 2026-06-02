import { useEffect, useState } from "react";
import { api } from "./api";
import {
  DataSkjema,
  SendSeksjon,
  SeksjonsNav,
  Kort,
  oppsummer,
  btnPrimar,
  btnOutline,
  monoLabel,
  type InnsendingFn,
} from "@wenche/ui";

interface Me {
  invited: boolean;
  invite_org?: string | null;
  kunde_org?: string | null;
  env?: string;
}

// Lenke til vilkårene (publisert på markedssiden wenche-web).
const VILKAAR_URL = "https://www.wenche.cloud/vilkaar";

// Hostet samtykke: vilkår + OFL-ansvarsfraskrivelse (operatøren er databehandler).
const HOSTET_SAMTYKKE = (
  <span>
    Jeg har lest og godtar{" "}
    <a
      href={VILKAAR_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="text-spruce underline-offset-2 hover:underline"
    >
      vilkårene
    </a>
    , sender på eget ansvar, og bekrefter at jeg har fullmakt til å sende på vegne av
    selskapet og at tallene er korrekte. OFL Holding AS kan ikke holdes ansvarlig for feil
    eller tap ved bruk av tjenesten.
  </span>
);

function Skall({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-6 py-4">
          <span className="font-display text-2xl font-medium tracking-tight">Wenche</span>
          <a
            href="https://www.wenche.cloud"
            className="text-xs text-muted-foreground transition hover:text-spruce"
          >
            ← wenche.cloud
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-6 py-12">{children}</main>
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
  const [venter, setVenter] = useState(false); // venter på godkjenning i Altinn

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
        setVenter(true);
      }
    } catch (e) {
      setFeil((e as Error).message);
    } finally {
      setKobler(false);
    }
  };

  const sjekkNaa = async () => {
    setFeil(null);
    try {
      const r = await api.systembrukerStatus();
      if (r.godkjent) onApproved();
      else setFeil("Ikke godkjent ennå. Fullfør i Altinn og prøv igjen om litt.");
    } catch (e) {
      setFeil((e as Error).message);
    }
  };

  // Mens vi venter på godkjenning i Altinn: poll status, så UI-et går videre av seg selv
  // når daglig leder/styreleder har godkjent (uten at brukeren må trykke noe).
  useEffect(() => {
    if (!venter) return;
    const id = setInterval(async () => {
      try {
        const r = await api.systembrukerStatus();
        if (r.godkjent) {
          clearInterval(id);
          onApproved();
        }
      } catch {
        /* nettverksglipp e.l.: prøver igjen ved neste intervall */
      }
    }, 4000);
    return () => clearInterval(id);
    // onApproved utelatt med vilje: den er funksjonelt stabil (frisker opp me).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [venter]);

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
          <p className="text-muted-foreground">
            Daglig leder eller styreleder må godkjenne Wenche i Altinn med BankID. Åpne lenken,
            godkjenn, så kommer du videre automatisk her:
          </p>
          <a
            className="mt-2 block break-all text-spruce underline-offset-2 hover:underline"
            href={confirmUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            {confirmUrl}
          </a>
          <div className="mt-4 flex items-center gap-3">
            <button className={btnOutline} onClick={sjekkNaa}>
              Jeg har godkjent, sjekk nå
            </button>
            {venter && (
              <span className="text-xs text-muted-foreground">Venter på godkjenning…</span>
            )}
          </div>
        </div>
      )}
      {feil && <p className="mt-4 text-sm text-red-700">{feil}</p>}
    </Kort>
  );
}

function Innsending({ env }: { env?: string }) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [config, setConfig] = useState<any | null>(null);

  // Klienten er fasit: vi holder config lokalt og sender den med innsendings-requesten.
  // Ingenting lagres server-side mellom kall (bedre personvern + tåler at serveren sover).
  const lagre = async (c: unknown) => {
    setConfig(c);
  };

  // Innsending med selvhelende systembruker-binding: en 409 betyr at bindingen gikk tapt
  // (serveren sov/restartet). Den reises FØR noen innsending skjer, så det er trygt å
  // rebinde (AlreadyApproved, ingen BankID) og prøve én gang til — ingen dobbeltinnsending.
  const innsending: InnsendingFn = async (type, dryRun, cfg) => {
    try {
      return await api.innsending(type, dryRun, cfg);
    } catch (e) {
      if (!dryRun && (e as { status?: number }).status === 409) {
        await api.systembrukerRequest();
        return await api.innsending(type, dryRun, cfg);
      }
      throw e;
    }
  };

  const o = config ? oppsummer(config) : null;

  return (
    <div className="space-y-6">
      <SeksjonsNav
        lenker={[
          ["#selskap", "Selskap"],
          ["#resultatregnskap", "Regnskap"],
          ["#skattemelding", "Skattemelding"],
          ["#aksjonaerer", "Aksjonærer"],
          ...(o ? ([["#send", "Send"]] as [string, string][]) : []),
        ]}
      />
      <Kort>
        <DataSkjema onLagre={lagre} visEksempel={env === "test"} />
      </Kort>
      {o && (
        <SendSeksjon
          config={config}
          innsending={innsending}
          env={env}
          org={o.org}
          samtykke={HOSTET_SAMTYKKE}
        />
      )}
    </div>
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

// Manuell Umami-pageview (auto-track er av i index.html). Kalles FØRST etter at
// invite-tokenet er fjernet fra URL-en, så tokenet aldri sendes til analytics.
function sporVisning() {
  const w = window as Window & { umami?: { track?: () => void } };
  const kjor = () => w.umami?.track?.();
  if (w.umami) kjor();
  else window.addEventListener("load", kjor, { once: true });
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
          sporVisning();
        });
    } else {
      refresh();
      sporVisning();
    }
  }, []);

  // Keep-alive-heartbeat: holder Fly-maskinen våken mens appen er i AKTIV bruk, så scale-to-zero
  // ikke sovner midt i en økt. Pinger KUN når fanen er synlig OG brukeren har vært aktiv siste
  // 10 min, så en glemt åpen fane lar maskinen sove (ingen løpsk kostnad). Trygt å la den sove
  // takket være at klienten er fasit + selvhelende binding.
  useEffect(() => {
    let sisteAktivitet = Date.now();
    const merkAktiv = () => {
      sisteAktivitet = Date.now();
    };
    const hendelser = ["mousemove", "keydown", "click", "touchstart", "scroll"];
    hendelser.forEach((e) => window.addEventListener(e, merkAktiv, { passive: true }));
    const id = setInterval(() => {
      const aktiv =
        document.visibilityState === "visible" && Date.now() - sisteAktivitet < 10 * 60 * 1000;
      if (aktiv) fetch("/api/health").catch(() => {});
    }, 45000);
    return () => {
      clearInterval(id);
      hendelser.forEach((e) => window.removeEventListener(e, merkAktiv));
    };
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
