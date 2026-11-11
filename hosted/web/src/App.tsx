import { useEffect, useState } from "react";
import {
  AppHeader,
  Banner,
  Dokumenter,
  GaaVidere,
  StegNav,
  harMinimumsdata,
  useUlagretVakt,
  type Config,
} from "@wenche/ui";
import { api } from "./api";
import { IDP_FEIL, KontaktLenke } from "./felles";
import { Gate } from "./Gate";
import { HjemFane } from "./HjemFane";
import { SendFane } from "./SendFane";
import { sporHendelse, sporSidevisning } from "./sporing";
import { TallFane } from "./TallFane";
import { FANER, type FaneId, type Me } from "./typer";
import { VelgOrg } from "./VelgOrg";

// Manuell Umami-pageview (auto-track er av i index.html). Kalles FØRST etter at invite-tokenet
// er fjernet fra URL-en, så tokenet aldri sendes til analytics.
function sporVisning() {
  const w = window as Window & { umami?: { track?: () => void } };
  const kjor = () => w.umami?.track?.();
  if (w.umami) kjor();
  else window.addEventListener("load", kjor, { once: true });
}

const TJENESTE_NEDE = "Fikk ikke kontakt med Wenche. Last siden på nytt om litt.";

export default function App() {
  const [me, setMe] = useState<Me | null>(null);
  const [fane, setFane] = useState<FaneId>("hjem");
  const [config, setConfig] = useState<Config | null>(null);
  const [ulagret, setUlagret] = useState(false);
  // Feil ved innløsning av en invite-/handoff-lenke, utlogging eller kontakt med tjenesten.
  // Vises som banner så en avvist lenke ikke svelges stille (se useEffect under).
  // Startverdi fra URL-en: ID-porten-callbacken redirecter hit med ?idp_feil=<kode> ved avbrutt
  // eller mislykket innlogging. Lest ved mount (ikke i en effekt), ryddet ut av URL-en under.
  const [lenkeFeil, setLenkeFeil] = useState<string | null>(() => {
    const kode = new URLSearchParams(window.location.search).get("idp_feil");
    return kode ? (IDP_FEIL[kode] ?? IDP_FEIL.mislyktes) : null;
  });

  // Feiler /me (tjenesten nede, proxy-feil), vis det i stedet for å late som om brukeren ikke er
  // invitert.
  const refresh = () =>
    api
      .me()
      .then(setMe)
      .catch(() => {
        setMe({ invited: false });
        setLenkeFeil(TJENESTE_NEDE);
      });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    // Tokenet ligger i URL-fragmentet (#invite=..., #handoff=...): fragmentet sendes aldri til
    // serveren, så det havner ikke i noen access-logg. Eldre lenker med ?invite= godtas fortsatt.
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const invite = fragment.get("invite") ?? params.get("invite");
    const handoff = fragment.get("handoff") ?? params.get("handoff");
    // Feilkoden fra ID-porten-callbacken er alt vist (startverdien til lenkeFeil); her ryddes
    // den bare ut av URL-en, som med invite/handoff.
    const idpFeil = params.get("idp_feil");
    // En invite-lenke åpner porten; en handoff-lenke (fra en alt koblet enhet) arver bindingen
    // direkte. Begge løses inn FØR URL-en ryddes og analytics kjører, så tokenet aldri lekker.
    const losInn = invite
      ? api.invite(invite)
      : handoff
        ? api.handoffUse(handoff)
        : null;
    if (losInn) {
      losInn
        .then((r) => {
          // En avvist eller utløpt lenke svarer 200 med {invited:false, feil}. Uten dette ville
          // brukeren havnet stille på gateskjermen (eller en gammel økt fra et tidligere forsøk,
          // som viser samme tilkoblingsskjerm) uten å skjønne at lenken var ugyldig. Vis feilen.
          if (r && !r.invited) setLenkeFeil(r.feil ?? "Ugyldig invitasjonslenke.");
        })
        .catch(() => setLenkeFeil("Kunne ikke lese invitasjonslenken. Prøv igjen, eller be om en ny."))
        .finally(() => {
          window.history.replaceState({}, "", window.location.pathname);
          refresh();
          sporVisning();
        });
    } else {
      if (idpFeil) {
        window.history.replaceState({}, "", window.location.pathname);
      }
      refresh();
      sporVisning();
    }
     
  }, []);

  const naviger = (id: string) => {
    setFane(id as FaneId);
    window.scrollTo({ top: 0 });
    sporSidevisning(`/${id}`); // virtuell pageview (URL-en endres ikke i SPA-en)
  };
  // Fanebytte avmonterer skjemaet, så ulagrede endringer må bekreftes først.
  const { forsoekNaviger, dialog: ulagretDialog } = useUlagretVakt(ulagret, naviger);

  const loggUt = () => {
    api
      .logout()
      .then(refresh)
      .catch(() => setLenkeFeil("Kunne ikke logge ut. Prøv igjen."));
  };

  const invited = !!me?.invited;

  return (
    <div className="min-h-screen">
      {me?.demo && (
        <Banner>
          Demo mot Altinns testmiljø (tt02). Ingenting sendes til ekte myndigheter, fyll gjerne
          inn eksempeldata.
        </Banner>
      )}
      <AppHeader
        env={me?.env}
        bredde="max-w-2xl"
        hoyre={
          <div className="flex items-center gap-4 text-xs">
            {invited && (
              <button className="text-muted-foreground transition hover:text-spruce" onClick={loggUt}>
                Logg ut
              </button>
            )}
            <a href="https://www.wenche.cloud" className="text-muted-foreground transition hover:text-spruce">
              ← wenche.cloud
            </a>
          </div>
        }
        // Steg-navet vises først når selskapet er koblet. Før det er appen kun en
        // tilkoblingsskjerm, så man ikke kan ta i bruk løsningen uten systembruker.
        nav={invited && me?.kunde_org ? <StegNav faner={FANER} aktiv={fane} onNaviger={forsoekNaviger} /> : undefined}
      />

      <main className="mx-auto max-w-2xl px-6 py-12">
        {lenkeFeil && (
          <div
            role="alert"
            className="mb-8 flex items-start justify-between gap-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm leading-relaxed text-red-700"
          >
            <span>
              {lenkeFeil}
              {me?.kontakt && lenkeFeil !== TJENESTE_NEDE && (
                <>
                  {" "}
                  Be om en ny lenke: <KontaktLenke kontakt={me.kontakt} />.
                </>
              )}
            </span>
            <button
              className="shrink-0 text-red-700/70 transition hover:text-red-700"
              onClick={() => setLenkeFeil(null)}
              aria-label="Lukk"
            >
              ✕
            </button>
          </div>
        )}
        {!me ? (
          <p className="text-sm text-muted-foreground">Laster…</p>
        ) : !me.invited ? (
          <Gate me={me} />
        ) : me.via_idporten && !me.invite_org ? (
          // Logget inn med ID-porten, men ingen org bundet ennå: velg selskap.
          <VelgOrg me={me} onValgt={refresh} />
        ) : !me.kunde_org ? (
          // Port: før selskapet er koblet er dette den eneste skjermen (ingen steg).
          <HjemFane me={me} onChange={refresh} />
        ) : (
          <>
            {fane === "hjem" && <HjemFane me={me} onChange={refresh} />}
            {fane === "tall" && (
              <TallFane
                config={config}
                env={me.env}
                org={me.kunde_org}
                onLagret={setConfig}
                onUlagret={setUlagret}
              />
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
              onNaviger={forsoekNaviger}
              disabled={fane === "tall" && !harMinimumsdata(config)}
              disabledHint="Trykk «Lagre data» for å gå videre. (Krever selskapsnavn og minst daglig leder eller styreleder.)"
            />
          </>
        )}
      </main>
      {ulagretDialog}
    </div>
  );
}
