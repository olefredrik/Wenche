import { useEffect, useState, type FormEvent } from "react";
import QRCode from "qrcode";
import { api } from "./api";
import { sporSidevisning, sporHendelse } from "./sporing";
import {
  DataSkjema,
  SendSeksjon,
  Dokumenter,
  NoterSeksjon,
  noterFraConfig,
  StegNav,
  GaaVidere,
  Kort,
  Panel,
  oppsummer,
  harMinimumsdata,
  btnPrimar,
  btnOutline,
  monoLabel,
  type Fane,
  type InnsendingFn,
  type NoterData,
} from "@wenche/ui";

interface Me {
  invited: boolean;
  invite_org?: string | null;
  kunde_org?: string | null;
  env?: string;
  demo?: boolean;
  selvbetjening?: boolean;
  kontakt?: string | null;
}

function DemoBanner() {
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-6 py-2 text-center text-sm text-amber-900">
      Demo mot Altinns testmiljø (tt02). Ingenting sendes til ekte myndigheter, fyll gjerne
      inn eksempeldata.
    </div>
  );
}

type FaneId = "hjem" | "tall" | "dokumenter" | "send";

// Færre steg enn self-hosted: Maskinporten-oppsettet er gjort av operatøren, så brukeren har
// bare Hjem (tilkoblingsstatus) + tre arbeidssteg.
const FANER: Fane[] = [
  { id: "hjem", navn: "Hjem" },
  { id: "tall", navn: "Tall", steg: 1 },
  { id: "dokumenter", navn: "Dokumenter", steg: 2 },
  { id: "send", navn: "Send", steg: 3 },
];

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

// Vis en kontaktvei (mailto: eller https) som en klikkbar lenke, med lesbar tekst.
function KontaktLenke({ kontakt }: { kontakt?: string | null }) {
  if (!kontakt) return null;
  const tekst = kontakt.startsWith("mailto:") ? kontakt.slice("mailto:".length) : kontakt.replace(/^https?:\/\//, "");
  return (
    <a
      href={kontakt}
      target={kontakt.startsWith("mailto:") ? undefined : "_blank"}
      rel="noopener noreferrer"
      className="text-spruce underline-offset-2 hover:underline"
    >
      {tekst}
    </a>
  );
}

const tilgangInput =
  "w-full rounded-md border border-border bg-background px-4 py-2.5 text-sm outline-none focus:border-spruce";

function KunInviterte({ me, onApproved }: { me: Me; onApproved: () => void }) {
  const [navn, setNavn] = useState("");
  const [org, setOrg] = useState("");
  const [sender, setSender] = useState(false);
  const [feil, setFeil] = useState<string | null>(null);

  const send = async (e: FormEvent) => {
    e.preventDefault();
    setFeil(null);
    setSender(true);
    try {
      const r = await api.beOmTilgang(navn, org);
      if (r.invited) {
        sporHendelse("tilgang-innvilget");
        onApproved();
      } else {
        sporHendelse("tilgang-avvist");
        setFeil(r.feil ?? "Kunne ikke gi tilgang.");
      }
    } catch (err) {
      setFeil((err as Error).message);
    } finally {
      setSender(false);
    }
  };

  return (
    <Kort>
      <p className={monoLabel}>Tilgang</p>
      <h1 className="mt-3 font-display text-3xl font-normal">Wenche er i en tidlig testfase</h1>
      <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
        Jeg holder fortsatt på å teste tjenesten og gjøre den stabil.
      </p>

      {me.selvbetjening ? (
        <>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Vil du prøve den for ditt eget selskap? Skriv inn navnet ditt og organisasjonsnummeret
            til selskapet du vil bruke Wenche for. Står du som daglig leder eller styremedlem i
            Enhetsregisteret, slipper du inn med en gang og kobler selskapet med BankID i neste
            steg. Navnet brukes bare til oppslaget og lagres ikke.
          </p>
          <form className="mt-6 space-y-4" onSubmit={send}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-xs text-muted-foreground">Fullt navn</span>
                <input
                  className={tilgangInput}
                  autoComplete="name"
                  value={navn}
                  onChange={(e) => setNavn(e.target.value)}
                  aria-invalid={!!feil}
                  required
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs text-muted-foreground">Organisasjonsnummer</span>
                <input
                  className={tilgangInput}
                  inputMode="numeric"
                  autoComplete="off"
                  value={org}
                  onChange={(e) => setOrg(e.target.value)}
                  aria-invalid={!!feil}
                  required
                />
              </label>
            </div>
            <button className={`${btnPrimar} w-full sm:w-auto`} type="submit" disabled={sender}>
              {sender ? "Sjekker…" : "Be om tilgang"}
            </button>
          </form>
          {feil && (
            <p role="alert" className="mt-4 text-sm leading-relaxed text-red-700">
              {feil} Stemmer ikke dette, eller har du skjermet adresse, ta kontakt:{" "}
              <KontaktLenke kontakt={me.kontakt} />.
            </p>
          )}
        </>
      ) : (
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          Vil du prøve den? Ta kontakt: <KontaktLenke kontakt={me.kontakt} />.
        </p>
      )}
    </Kort>
  );
}

// Koble systembruker (BankID i Altinn). Vises på Hjem når selskapet ikke er koblet ennå.
function Onboarding({ org, onApproved }: { org?: string | null; onApproved: () => void }) {
  const [confirmUrl, setConfirmUrl] = useState<string | null>(null);
  const [feil, setFeil] = useState<string | null>(null);
  const [kobler, setKobler] = useState(false);
  const [venter, setVenter] = useState(false);

  const koble = async () => {
    setFeil(null);
    setConfirmUrl(null);
    setKobler(true);
    try {
      const r = await api.systembrukerRequest();
      if (r.godkjent || r.status === "AlreadyApproved") onApproved();
      else {
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

  // Poll status mens vi venter, så UI-et går videre av seg selv når daglig leder/styreleder
  // har godkjent i Altinn.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [venter]);

  return (
    <Kort>
      <p className={monoLabel}>Tilkobling</p>
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
            {venter && <span className="text-xs text-muted-foreground">Venter på godkjenning…</span>}
          </div>
        </div>
      )}
      {feil && <p className="mt-4 text-sm text-red-700">{feil}</p>}
    </Kort>
  );
}

// Fortsett på en annen enhet: en koblet økt lager en kortvarig overføringslenke (QR + lenke)
// som en ny enhet løser inn for å arve samme binding, uten ny BankID. Løser at sesjonen ellers
// lever per nettleser (signert cookie, ingen DB), så et andre apparat står uten tilkobling.
function FortsettAnnenEnhet() {
  const [aapen, setAapen] = useState(false);
  const [lenke, setLenke] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [gyldigMin, setGyldigMin] = useState<number | null>(null);
  const [lager, setLager] = useState(false);
  const [kopiert, setKopiert] = useState(false);
  const [feil, setFeil] = useState<string | null>(null);

  const lag = async () => {
    setFeil(null);
    setKopiert(false);
    setLager(true);
    try {
      const r = await api.handoffCreate();
      setLenke(r.lenke);
      setGyldigMin(r.gyldig_sekunder ? Math.round(r.gyldig_sekunder / 60) : null);
      // QR genereres i nettleseren; lenken (med tokenet) forlater aldri enheten her.
      setQr(await QRCode.toDataURL(r.lenke, { margin: 1, width: 320 }));
      setAapen(true);
      sporHendelse("handoff-laget");
    } catch (e) {
      setFeil((e as Error).message);
    } finally {
      setLager(false);
    }
  };

  const kopier = async () => {
    if (!lenke) return;
    try {
      await navigator.clipboard.writeText(lenke);
      setKopiert(true);
    } catch {
      /* clipboard blokkert (f.eks. ikke-https): lenken vises uansett for manuell kopiering */
    }
  };

  if (!aapen) {
    return (
      <button className={btnOutline} onClick={lag} disabled={lager}>
        {lager ? "Lager lenke…" : "Fortsett på en annen enhet"}
      </button>
    );
  }

  return (
    <div className="rounded-sm border border-border bg-background p-4">
      <p className="text-sm leading-relaxed text-muted-foreground">
        Det er to måter å koble den nye enheten på. Lenken gir tilgang uten ny
        BankID-godkjenning, er ferskvare{gyldigMin ? ` (gyldig i ${gyldigMin} minutter)` : ""}, og
        bør bare deles med deg selv.
      </p>

      <div className="mt-5">
        <p className="text-sm font-medium text-foreground">1. Skann QR-koden</p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Bruk kameraet på telefonen eller nettbrettet du vil koble til.
        </p>
        {qr && (
          <img
            src={qr}
            alt="QR-kode for å fortsette på en annen enhet"
            className="mt-3 rounded bg-white p-2"
            width={180}
            height={180}
          />
        )}
      </div>

      <div className="mt-5">
        <p className="text-sm font-medium text-foreground">2. Eller bruk lenken</p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Åpne den på den andre enheten, eller send den til deg selv, for eksempel på e-post.
        </p>
        {lenke && (
          <>
            <a
              className="mt-3 block break-all text-sm text-spruce underline-offset-2 hover:underline"
              href={lenke}
            >
              {lenke}
            </a>
            <div className="mt-3 flex items-center gap-3">
              <button className={btnOutline} onClick={kopier}>
                Kopier lenke
              </button>
              {kopiert && <span className="text-xs text-spruce">✓ Kopiert</span>}
            </div>
          </>
        )}
      </div>

      {feil && <p className="mt-3 text-sm text-red-700">{feil}</p>}
    </div>
  );
}

// Hjem: tilkoblingsstatus. Koblet → bekreftelse + «sjekk tilkobling». Ikke koblet → onboarding.
function HjemFane({ me, onChange }: { me: Me; onChange: () => void }) {
  const [sjekker, setSjekker] = useState(false);
  const [melding, setMelding] = useState<string | null>(null);

  // Bekreft at en godkjent systembruker fortsatt finnes for selskapet. Bruker `request`
  // (ikke `status`): en allerede godkjent kunde har ingen ventende forespørsel, så `status`
  // ville svart «ingen aktiv forespørsel» selv om tilkoblingen er aktiv. `request` sjekker
  // eksisterende systembrukere og returnerer «AlreadyApproved» uten å lage en ny forespørsel.
  const sjekk = async () => {
    setSjekker(true);
    setMelding(null);
    try {
      const r = await api.systembrukerRequest();
      if (r.godkjent || r.status === "AlreadyApproved") {
        setMelding("✓ Tilkoblingen er aktiv.");
      } else {
        setMelding("Tilkoblingen er ikke lenger aktiv. Last siden på nytt for å koble på nytt.");
      }
    } catch (e) {
      setMelding((e as Error).message);
    } finally {
      setSjekker(false);
    }
  };

  if (!me.kunde_org) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="font-display text-2xl font-normal">Velkommen</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Koble selskapet ditt til Altinn for å komme i gang. Maskinporten-oppsettet er
            allerede gjort for deg.
          </p>
        </div>
        <Onboarding org={me.invite_org} onApproved={onChange} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Hjem</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Fyll inn tallene under «Tall», se over dokumentene, og send inn under «Send».
        </p>
      </div>
      <Kort accent>
        <p className={monoLabel}>Tilkobling</p>
        <p className="mt-2 font-display text-lg text-spruce">
          ✓ Selskapet ditt (org {me.kunde_org}) er koblet til Altinn
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Wenche kan sende inn på vegne av selskapet. Du kan når som helst kontrollere at
          tilkoblingen fortsatt er aktiv.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-4">
          <button
            className="font-mono text-[11px] uppercase tracking-[0.15em] text-spruce underline-offset-2 hover:underline disabled:opacity-40"
            onClick={sjekk}
            disabled={sjekker}
          >
            {sjekker ? "Sjekker…" : "Sjekk tilkobling"}
          </button>
          {melding && <span className="text-sm text-muted-foreground">{melding}</span>}
        </div>
      </Kort>
      <Kort>
        <p className={monoLabel}>Flere enheter</p>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Tilkoblingen gjelder denne nettleseren.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Vil du bruke Wenche på telefonen eller en annen maskin, lag en lenke her og åpne den
          der, så kobles den enheten til i tillegg, uten ny godkjenning. Begge forblir koblet.
        </p>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          En enhet du ikke vil bruke lenger, logger du ut med «Logg ut».
        </p>
        <div className="mt-4">
          <FortsettAnnenEnhet />
        </div>
      </Kort>
    </div>
  );
}

// Tall: skjema + noter. Klienten er fasit (ingen disk); lagring setter App-config-en.
function TallFane({
  config,
  env,
  org,
  onLagret,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  config: any;
  env?: string;
  org?: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onLagret: (c: any) => void;
}) {
  const [noter, setNoter] = useState<NoterData>(() => noterFraConfig(config));
  const [lagret, setLagret] = useState(false);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const lagre = async (formConfig: any) => {
    onLagret({ ...formConfig, noter });
    setLagret(true);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Tall</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Fyll inn selskapsopplysninger, regnskap, balanse, skattemelding og aksjonærer. Trykk
          «Lagre data», så kan du se over dokumentene og sende inn.
        </p>
      </div>
      <Kort>
        <DataSkjema
          onLagre={lagre}
          visEksempel={env === "test"}
          initial={config ?? undefined}
          laastOrg={org ?? undefined}
          importerSaft={api.importerSaft}
          prefillSelskap={api.selskap}
          saftMerknad="SAF-T-filen behandles i minnet i EØS og lagres ikke."
          ekstraSeksjon={<NoterSeksjon noter={noter} setNoter={setNoter} />}
        />
      </Kort>
      {lagret && <p className="text-sm text-spruce">✓ Lagret. Gå videre til «Dokumenter» eller «Send».</p>}
    </div>
  );
}

// Send: dry-run + bekreft + ekte innsending, med selvhelende 409-rebind.
function SendFane({ config, me }: { config: any; me: Me }) {
  if (!me.kunde_org) {
    return (
      <Panel tone="advarsel" tittel="Ikke koblet ennå">
        Koble selskapet ditt til Altinn på «Hjem» før du sender inn.
      </Panel>
    );
  }
  if (!config) {
    return (
      <Panel tone="advarsel" tittel="Ingen data ennå">
        Fyll inn og lagre tallene under «Tall» før du sender inn.
      </Panel>
    );
  }

  // Selvhelende systembruker-binding: en 409 betyr at bindingen gikk tapt (serveren sov/
  // restartet). Den reises FØR innsending, så det er trygt å rebinde og prøve én gang til.
  const innsending: InnsendingFn = async (type, dryRun, cfg) => {
    if (dryRun) sporHendelse("send-start", { type });
    try {
      const data = await api.innsending(type, dryRun, cfg);
      if (!dryRun) sporHendelse("send-ok", { type });
      return data;
    } catch (e) {
      if (!dryRun && (e as { status?: number }).status === 409) {
        await api.systembrukerRequest();
        const data = await api.innsending(type, dryRun, cfg);
        sporHendelse("send-ok", { type });
        return data;
      }
      throw e;
    }
  };

  const o = oppsummer(config);
  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-normal">Send inn</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Wenche kontrollerer tallene og viser en oppsummering før noe sendes til myndighetene.
        </p>
      </div>
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

// Manuell Umami-pageview (auto-track er av i index.html). Kalles FØRST etter at invite-tokenet
// er fjernet fra URL-en, så tokenet aldri sendes til analytics.
function sporVisning() {
  const w = window as Window & { umami?: { track?: () => void } };
  const kjor = () => w.umami?.track?.();
  if (w.umami) kjor();
  else window.addEventListener("load", kjor, { once: true });
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [fane, setFane] = useState<FaneId>("hjem");
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [config, setConfig] = useState<any | null>(null);

  const refresh = () => api.me().then(setMe).catch(() => setMe({ invited: false }));

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const invite = params.get("invite");
    const handoff = params.get("handoff");
    // En invite-lenke åpner porten; en handoff-lenke (fra en alt koblet enhet) arver bindingen
    // direkte. Begge løses inn FØR URL-en ryddes og analytics kjører, så tokenet aldri lekker.
    const losInn = invite
      ? api.invite(invite)
      : handoff
        ? api.handoffUse(handoff)
        : null;
    if (losInn) {
      losInn
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
  // ikke sovner midt i en økt. Pinger kun når fanen er synlig og brukeren har vært aktiv siste
  // 10 min, så en glemt åpen fane lar maskinen sove.
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

  const naviger = (id: string) => {
    setFane(id as FaneId);
    window.scrollTo({ top: 0 });
    sporSidevisning(`/${id}`); // virtuell pageview (URL-en endres ikke i SPA-en)
  };

  const invited = !!me?.invited;

  return (
    <div className="min-h-screen">
      {me?.demo && <DemoBanner />}
      <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="mx-auto max-w-2xl px-6">
          <div className="flex items-center justify-between py-4">
            <div className="flex items-baseline gap-2">
              <span className="font-display text-2xl font-medium tracking-tight">Wenche</span>
              {me?.env === "test" && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-amber-800">
                  Test
                </span>
              )}
            </div>
            <div className="flex items-center gap-4 text-xs">
              {invited && (
                <button
                  className="text-muted-foreground transition hover:text-spruce"
                  onClick={() => api.logout().then(refresh)}
                >
                  Logg ut
                </button>
              )}
              <a
                href="https://www.wenche.cloud"
                className="text-muted-foreground transition hover:text-spruce"
              >
                ← wenche.cloud
              </a>
            </div>
          </div>
          {/* Steg-navet vises først når selskapet er koblet — før det er appen kun en
              tilkoblingsskjerm, så man ikke kan ta i bruk løsningen uten systembruker. */}
          {invited && me?.kunde_org && (
            <nav className="pb-1">
              <StegNav faner={FANER} aktiv={fane} onNaviger={naviger} />
            </nav>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-6 py-12">
        {!me ? (
          <p className="text-sm text-muted-foreground">Laster…</p>
        ) : !me.invited ? (
          <KunInviterte me={me} onApproved={refresh} />
        ) : !me.kunde_org ? (
          // Port: før selskapet er koblet er dette den eneste skjermen (ingen steg).
          <HjemFane me={me} onChange={refresh} />
        ) : (
          <>
            {fane === "hjem" && <HjemFane me={me} onChange={refresh} />}
            {fane === "tall" && (
              <TallFane config={config} env={me.env} org={me.kunde_org} onLagret={setConfig} />
            )}
            {fane === "dokumenter" && (
              <Dokumenter
                config={config}
                dokument={(type, cfg) =>
                  api.dokument(type, cfg).then((r) => {
                    sporHendelse("dokument-last-ned", { type });
                    return r;
                  })
                }
              />
            )}
            {fane === "send" && <SendFane config={config} me={me} />}
            <GaaVidere
              faner={FANER}
              aktiv={fane}
              onNaviger={naviger}
              disabled={fane === "tall" && !harMinimumsdata(config)}
              disabledHint="Trykk «Lagre data» for å gå videre. (Krever selskapsnavn og minst daglig leder eller styreleder.)"
            />
          </>
        )}
      </main>
    </div>
  );
}
