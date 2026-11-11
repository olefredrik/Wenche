// Skjema-drevet datainntasting. Feltstrukturen er data (felter.ts); én generisk renderer
// (feltrutenett.tsx) bygger config-objektet (samme form som config.yaml) som sendes til
// backenden. Importene (Bodil, SAF-T) og aksjonærlista bor i hver sin fil; her er tilstanden.
import { useEffect, useRef, useState } from "react";
import { AksjonaerListe } from "./aksjonaerer";
import { feilmelding } from "./api";
import { BodilImportModal } from "./bodilimport";
import { EKSEMPEL } from "./eksempel";
import { FJORARET_FELTER, SEKSJONER, UTBYTTE_VEDTAKSDATO_FELT } from "./felter";
import { Feltrutenett } from "./feltrutenett";
import { Panel } from "./komponenter";
import { SaftImportModal, type SaftImporter } from "./saftimport";
import {
  type Aksjonaer,
  flettStyring,
  grunnConfig,
  hent,
  kr,
  medLaastOrg,
  normaliserForLagring,
  sett,
  sumBalanse,
  tomAksjonaer,
} from "./skjemadata";
import { btnOutlineLett as btnOutline, btnPrimar, monoLabel } from "./styles";
import type { Config, SelskapSvar, SkatteberegningSvar } from "./typer";

export { kr, oppsummer, harMinimumsdata, normaliserForLagring } from "./skjemadata";

export function DataSkjema({
  onLagre,
  visEksempel = false,
  initial,
  lagreEtikett = "Lagre data",
  stegEtikett = "Årets tall",
  ekstraSeksjon,
  laastOrg,
  importerSaft,
  saftMerknad,
  prefillSelskap,
  beregnSkatt,
  onUlagret,
}: {
  onLagre: (config: Config) => Promise<void>;
  visEksempel?: boolean;
  // Startverdi (self-hosted laster eksisterende config.yaml fra disk; hostet starter tomt).
  initial?: Config;
  lagreEtikett?: string;
  // Etiketten øverst («Steg 2 · Årets tall»); hver app nummererer stegene sine.
  stegEtikett?: string;
  // Valgfri tilleggsseksjon (f.eks. noter) som vises sist, rett før «Lagre data», slik at
  // den lagres sammen med resten av skjemaet i ett trykk.
  ekstraSeksjon?: React.ReactNode;
  // Hostet kjenner selskapet fra invitasjonen: org.nr forhåndsutfylles, låses i feltet, og
  // tvinges tilbake ved import/eksempeldata (innsending krever at config-org == kunde-org).
  laastOrg?: string;
  // Valgfri SAF-T-import: parser en opplastet SAF-T Financial-fil til config-form. Hver app
  // injiserer sin binding. Uten denne vises ikke SAF-T-knappen.
  importerSaft?: SaftImporter;
  // Valgfri merknad i SAF-T-modalen (hostet bruker den til personvern-info om EØS/ingen lagring).
  saftMerknad?: React.ReactNode;
  // Valgfri forhåndsfylling av styringsdata SAF-T ikke bærer (daglig leder, styreleder,
  // stiftelsesår) fra Enhetsregisteret. Hostet injiserer henteren; self-hosted lar den være.
  prefillSelskap?: () => Promise<SelskapSvar>;
  // Valgfritt forslag til skattekostnad: kjernen beregner 22 % av skattepliktig inntekt fra
  // tallene i skjemaet. Forslag, aldri auto-utfylling: brukeren fører selv tallet han signerer
  // på. Uten denne vises ikke forslags-knappen.
  beregnSkatt?: (config: Config) => Promise<SkatteberegningSvar>;
  // Kalles når skjemaet får eller mister ulagrede endringer, så appen kan vakte fanebytte.
  onUlagret?: (ulagret: boolean) => void;
}) {
  const laasteFelter = laastOrg ? ["selskap.org_nummer"] : [];
  const [config, setConfig] = useState<Config>(() => medLaastOrg(initial ?? grunnConfig(), laastOrg));
  const [lagrer, setLagrer] = useState(false);
  const [lagreFeil, setLagreFeil] = useState<string | null>(null);
  const [visBodil, setVisBodil] = useState(false);
  const [visSaft, setVisSaft] = useState(false);

  // Stabile radnøkler for aksjonærene (ikke indeks), så React ikke blander tallfeltenes
  // interne tilstand når en rad midt i lista fjernes. Nye nøkler når hele lista byttes ut.
  const antallStart = (config.aksjonaerer ?? []).length;
  const nokkelTeller = useRef(antallStart);
  const [nokler, setNokler] = useState<number[]>(() => Array.from({ length: antallStart }, (_, i) => i));
  const nyeNokler = (n: number) => {
    const fra = nokkelTeller.current;
    nokkelTeller.current += n;
    return Array.from({ length: n }, (_, i) => fra + i);
  };
  const erstattConfig = (c: Config) => {
    setConfig(c);
    setNokler(nyeNokler((c.aksjonaerer ?? []).length));
  };

  // Ulagret = skjemaet avviker fra baselinen (startverdien eller siste lagring). Lastet config
  // regnes ikke som «ulagret». Vakter både sidelukking (beforeunload) og, via onUlagret,
  // fanebytte i appen.
  const [pristine, setPristine] = useState(() => JSON.stringify(config));
  const ulagret = JSON.stringify(config) !== pristine;
  const ulagretRef = useRef(ulagret);
  useEffect(() => {
    ulagretRef.current = ulagret;
    onUlagret?.(ulagret);
  }, [ulagret, onUlagret]);
  useEffect(() => () => onUlagret?.(false), [onUlagret]);
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (ulagretRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  // Forhåndsfyll styringsdata SAF-T ikke bærer (daglig leder, styreleder, stiftelsesår) fra
  // Enhetsregisteret ved kobling, kun der feltet står tomt, så det ikke overskriver noe brukeren
  // (eller en importert config) alt har fylt. Fail-soft: feiler oppslaget, forblir skjemaet tomt.
  // Forhåndsfyll teller ikke som ulagret endring (baselinen flettes likt), men må fortsatt lagres.
  useEffect(() => {
    if (!prefillSelskap) return;
    let avbrutt = false;
    const flett = (c: Config, d: SelskapSvar): Config => {
      const s = c.selskap ?? {};
      return {
        ...c,
        selskap: {
          ...s,
          navn: String(s.navn ?? "").trim() || d.navn || "",
          forretningsadresse: String(s.forretningsadresse ?? "").trim() || d.forretningsadresse || "",
          daglig_leder: String(s.daglig_leder ?? "").trim() || d.daglig_leder || "",
          styreleder: String(s.styreleder ?? "").trim() || d.styreleder || "",
          stiftelsesaar: Number(s.stiftelsesaar) || d.stiftelsesaar || 0,
          stiftelsesdato: String(s.stiftelsesdato ?? "").trim() || d.stiftelsesdato || "",
        },
      };
    };
    prefillSelskap()
      .then((d) => {
        if (avbrutt || !d) return;
        setConfig((c) => flett(c, d));
        setPristine((p) => JSON.stringify(flett(JSON.parse(p), d)));
      })
      .catch(() => {});
    return () => {
      avbrutt = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Postlisten er en integrasjonsflate uten egne skjemafelt. Uten denne tellingen er den
  // usynlig for den som har arvet en config fra regnskapssystemet sitt, og en kode som
  // Skatteetaten avviser blir umulig å spore herfra.
  const antallEgneKoder: number = Array.isArray(config?.naeringsspesifikasjon?.poster)
    ? config.naeringsspesifikasjon.poster.length
    : 0;

  const oppdater = (key: string, val: unknown) => setConfig((c) => sett(c, key, val));

  // Forslag til skattekostnad. Hentes kun når brukeren ber om det, og settes kun inn ved et
  // eksplisitt trykk: Wenche fastsetter ikke tallet, den regner det ut som hjelp.
  const [skattForslag, setSkattForslag] = useState<number | null>(null);
  const [skattLaster, setSkattLaster] = useState(false);
  const [skattFeil, setSkattFeil] = useState<string | null>(null);
  const hentSkattForslag = async () => {
    if (!beregnSkatt) return;
    setSkattLaster(true);
    setSkattFeil(null);
    try {
      const d = await beregnSkatt(normaliserForLagring(config));
      setSkattForslag(Number(d?.beregnet_skatt) || 0);
    } catch (e) {
      // Fjern et eldre forslag, ellers står «Sett inn» igjen ved siden av feilen.
      setSkattForslag(null);
      setSkattFeil(feilmelding(e, "Klarte ikke å beregne skatten"));
    } finally {
      setSkattLaster(false);
    }
  };

  const { eiendeler: sumEiendeler, ekGjeld: sumEkGjeld } = sumBalanse(config);
  const diff = sumEiendeler - sumEkGjeld;
  const balansererOk = Math.abs(diff) < 0.01;

  const aksjonaerer: Aksjonaer[] = config.aksjonaerer ?? [];
  const settAksj = (i: number, felt: keyof Aksjonaer, val: string | number) =>
    setConfig((c) => ({
      ...c,
      aksjonaerer: (c.aksjonaerer as Aksjonaer[]).map((a, j) => (j === i ? { ...a, [felt]: val } : a)),
    }));
  const fjernAksj = (i: number) => {
    setNokler((n) => n.filter((_, j) => j !== i));
    setConfig((c) => ({ ...c, aksjonaerer: (c.aksjonaerer as Aksjonaer[]).filter((_, j) => j !== i) }));
  };
  const leggTilAksj = () => {
    setNokler((n) => [...n, nokkelTeller.current++]);
    setConfig((c) => ({ ...c, aksjonaerer: [...(c.aksjonaerer ?? []), tomAksjonaer()] }));
  };

  const lagre = async () => {
    setLagrer(true);
    setLagreFeil(null);
    try {
      await onLagre(normaliserForLagring(config));
      // Etter vellykket lagring er gjeldende innhold den nye baselinen.
      setPristine(JSON.stringify(config));
    } catch (e) {
      setLagreFeil(feilmelding(e, "Kunne ikke lagre."));
    } finally {
      setLagrer(false);
    }
  };

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className={monoLabel}>{stegEtikett}</p>
        <div className="flex items-center gap-4">
          <button
            className="text-xs font-medium text-spruce underline-offset-2 hover:underline"
            onClick={() => setVisBodil(true)}
          >
            Hent tall fra Bodil
          </button>
          {importerSaft && (
            <button
              className="text-xs font-medium text-spruce underline-offset-2 hover:underline"
              onClick={() => setVisSaft(true)}
            >
              Importer fra SAF-T
            </button>
          )}
          {visEksempel && (
            <button
              className="text-xs text-muted-foreground underline-offset-2 hover:text-spruce hover:underline"
              onClick={() => erstattConfig(medLaastOrg(structuredClone(EKSEMPEL), laastOrg))}
            >
              Fyll inn eksempeldata (test)
            </button>
          )}
        </div>
      </div>

      {visBodil && (
        <BodilImportModal
          onImportert={(c) => erstattConfig(medLaastOrg(c, laastOrg))}
          onLukk={() => setVisBodil(false)}
        />
      )}

      {visSaft && importerSaft && (
        <SaftImportModal
          importerSaft={importerSaft}
          merknad={saftMerknad}
          onLukk={() => setVisSaft(false)}
          onImportert={(data, foregaaende) => {
            if (foregaaende) {
              // Kun fjorårets sammenligningstall: merge inn i gjeldende config, rør ikke resten.
              setConfig((c) => ({ ...c, foregaaende_aar: data.foregaaende_aar }));
            } else {
              erstattConfig(medLaastOrg(flettStyring(data, config), laastOrg));
            }
          }}
        />
      )}

      {SEKSJONER.map((s) => (
        <section key={s.tittel} id={s.id} className="scroll-mt-32">
          <h3 className="mb-4 font-display text-xl font-normal">{s.tittel}</h3>
          <Feltrutenett felter={s.felter} config={config} oppdater={oppdater} laasteFelter={laasteFelter} />
          {s.id === "skattemelding" && antallEgneKoder > 0 && (
            <div className="mt-4 rounded-sm border border-border bg-background p-4 text-sm">
              <p className={monoLabel}>Eksakte grupperingskoder</p>
              <p className="mt-2 leading-relaxed text-muted-foreground">
                Denne konfigurasjonen har en egen kodefordeling for næringsspesifikasjonen
                ({antallEgneKoder} {antallEgneKoder === 1 ? "post" : "poster"} under{" "}
                <code className="font-mono">naeringsspesifikasjon.poster</code>), som regel lagt
                inn av et regnskapssystem. Kodene brukes i stedet for Wenches standardfordeling,
                og de kan ikke redigeres her. Summene må stemme med tallene over, så endrer du et
                beløp må listen oppdateres av systemet som lagde den.
              </p>
              <button
                className="mt-3 text-spruce underline underline-offset-2"
                // Fjerningen lagres først ved «Lagre data», og vakten mot ulagrede endringer
                // fanger et uhell. Derfor ingen bekreftelsesdialog, i tråd med resten av skjemaet.
                onClick={() => setConfig(({ naeringsspesifikasjon: _fjernet, ...resten }) => resten)}
              >
                Bruk standardkoder i stedet
              </button>
            </div>
          )}
          {s.id === "resultatregnskap" && beregnSkatt && (
            <div className="mt-4 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <button className={btnOutline} onClick={hentSkattForslag} disabled={skattLaster}>
                  {skattLaster ? "Beregner…" : "Foreslå skattekostnad"}
                </button>
                {skattForslag !== null && (
                  <>
                    <span className="text-muted-foreground">
                      Beregnet skatt (22 %): {kr(skattForslag)}
                    </span>
                    <button
                      className="text-spruce underline underline-offset-2"
                      onClick={() => oppdater("resultatregnskap.skattekostnad", skattForslag)}
                    >
                      Sett inn
                    </button>
                  </>
                )}
              </div>
              {skattFeil && (
                <p role="alert" className="mt-2 text-red-700">
                  {skattFeil}
                </p>
              )}
              {skattForslag !== null && (
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                  Forslaget er 22 % av skattepliktig inntekt slik Wenche beregner den, etter
                  fritaksmetoden og fremført underskudd. Det dekker ikke utsatt skatt eller andre
                  permanente forskjeller, så kontroller tallet før du fører det. Husk «Betalbar
                  skatt» under kortsiktig gjeld hvis skatten ikke er betalt ved årsslutt.
                </p>
              )}
            </div>
          )}
          {s.id === "balanse" && (
            <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
              <span className="text-muted-foreground">Sum eiendeler: {kr(sumEiendeler)}</span>
              <span className="text-muted-foreground">Sum EK + gjeld: {kr(sumEkGjeld)}</span>
              <span className={balansererOk ? "text-spruce" : "text-red-700"}>
                {balansererOk ? "Balansen går opp" : `Differanse: ${kr(diff)}`}
              </span>
            </div>
          )}
        </section>
      ))}

      <details id="fjoraaret" className="scroll-mt-32 border-t border-border pt-6">
        <summary className="cursor-pointer font-display text-xl font-normal">
          Fjorårets tall
        </summary>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Sammenligningstall for fjoråret, påkrevd etter regnskapsloven. Kan stå tomt kun
          hvis selskapet ble stiftet i dette regnskapsåret og ikke har et fjorår å
          sammenligne med. Importerer du fra Bodil, er disse allerede fylt inn.
        </p>
        <div className="mt-4">
          <Feltrutenett felter={FJORARET_FELTER} config={config} oppdater={oppdater} />
        </div>
      </details>

      <section id="aksjonaerer" className="scroll-mt-32">
        <h3 className="mb-4 font-display text-xl font-normal">Aksjonærer</h3>
        <AksjonaerListe
          aksjonaerer={aksjonaerer}
          nokler={nokler}
          onEndre={settAksj}
          onFjern={fjernAksj}
          onLeggTil={leggTilAksj}
        />
        {(aksjonaerer.some((a) => Number(a.utbytte_utbetalt) > 0) || !!hent(config, UTBYTTE_VEDTAKSDATO_FELT.key)) && (
          <div className="mt-6">
            <Feltrutenett felter={[UTBYTTE_VEDTAKSDATO_FELT]} config={config} oppdater={oppdater} />
          </div>
        )}
      </section>

      {ekstraSeksjon}

      {lagreFeil && (
        <Panel tone="feil" tittel="Kunne ikke lagre">
          {lagreFeil}
        </Panel>
      )}
      <button className={btnPrimar} onClick={lagre} disabled={lagrer}>
        {lagrer ? "Lagrer…" : lagreEtikett}
      </button>
    </div>
  );
}
