// Etter ID-porten-innlogging: velg selskap. Når altinn:accessmanagement/authorizedparties-
// scopet er tildelt (me.reportees), hentes listen over orger brukeren kan representere fra
// Altinn automatisk. Ellers (eller ved feil) faller steget tilbake til manuell orgnr-inntasting
// med brreg-navnematch.
import { useEffect, useState, type FormEvent } from "react";
import { Kort, btnOutline, btnPrimar, feilmelding, monoLabel } from "@wenche/ui";
import { api } from "./api";
import { sporHendelse } from "./sporing";
import type { Me, OrgItem } from "./typer";

const tilgangInput =
  "w-full rounded-md border border-border bg-background px-4 py-2.5 text-sm outline-none focus:border-spruce";

export function VelgOrg({ me, onValgt }: { me: Me; onValgt: () => void }) {
  // Uten reportees-scopet finnes ingen Altinn-liste å hente: start rett i manuell modus.
  const [orger, setOrger] = useState<OrgItem[] | null>(me.reportees ? null : []);
  const [listeFeil, setListeFeil] = useState<string | null>(null);
  const [visManuel, setVisManuel] = useState(false);
  const [manueltOrgnr, setManueltOrgnr] = useState("");
  const [sender, setSender] = useState(false);
  const [handlingsFeil, setHandlingsFeil] = useState<string | null>(null);

  useEffect(() => {
    if (!me.reportees) return; // ingen Altinn-liste uten scopet; manuell inntasting vises
    api
      .hentOrganisasjoner()
      .then((r) => {
        setOrger(r.organisasjoner ?? []);
        if (r.feil) setListeFeil(r.feil);
      })
      .catch(() => {
        setOrger([]);
        setListeFeil("Kunne ikke hente selskapslisten. Skriv inn organisasjonsnummeret manuelt.");
      });
  }, [me.reportees]);

  const velgFraListe = async (orgnr: string) => {
    setHandlingsFeil(null);
    setSender(true);
    try {
      const r = await api.velgOrgAltinn(orgnr);
      if (r.ok) {
        sporHendelse("velg-org-altinn-ok");
        onValgt();
      } else {
        setHandlingsFeil(r.feil ?? "Kunne ikke gi tilgang.");
      }
    } catch (err) {
      setHandlingsFeil(feilmelding(err));
    } finally {
      setSender(false);
    }
  };

  const velgManuelt = async (e: FormEvent) => {
    e.preventDefault();
    setHandlingsFeil(null);
    setSender(true);
    try {
      const r = await api.velgOrg(manueltOrgnr);
      if (r.ok) {
        sporHendelse("velg-org-manuell-ok");
        onValgt();
      } else {
        sporHendelse("velg-org-avvist");
        setHandlingsFeil(r.feil ?? "Kunne ikke gi tilgang.");
      }
    } catch (err) {
      setHandlingsFeil(feilmelding(err));
    } finally {
      setSender(false);
    }
  };

  const laster = orger === null;
  const visListe = !laster && (orger?.length ?? 0) > 0 && !visManuel;

  return (
    <Kort>
      <p className={monoLabel}>Velg selskap</p>
      <h2 className="mt-3 font-display text-3xl font-normal">
        Hei{me.navn ? `, ${me.navn}` : ""}
      </h2>

      {laster ? (
        <p className="mt-4 text-sm text-muted-foreground">Henter selskapslisten...</p>
      ) : visListe ? (
        <>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Velg selskapet du vil sende inn for.
          </p>
          <div className="mt-6 space-y-3">
            {orger!.map((org) => (
              <button
                key={org.orgnr}
                className={`${btnOutline} w-full text-left`}
                disabled={sender}
                onClick={() => velgFraListe(org.orgnr)}
              >
                <span className="block font-medium">{org.navn}</span>
                <span className="block text-xs text-muted-foreground">{org.orgnr}</span>
              </button>
            ))}
          </div>
          <button
            className="mt-4 text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => setVisManuel(true)}
          >
            Ikke i listen?
          </button>
        </>
      ) : (
        <>
          {!laster && (
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
              {listeFeil ??
                "Wenche må vite hvilket organisasjonsnummer hun skal ordne papirene for. Husk " +
                  "at du må være daglig leder eller styreleder for å kunne gi henne fullmakt til " +
                  "å sende inn på dine vegne."}
            </p>
          )}
          <form className="mt-6 space-y-4" onSubmit={velgManuelt}>
            <label className="block">
              <span className="mb-1 block text-xs text-muted-foreground">Organisasjonsnummer</span>
              <input
                className={tilgangInput}
                inputMode="numeric"
                autoComplete="off"
                value={manueltOrgnr}
                onChange={(e) => setManueltOrgnr(e.target.value)}
                aria-invalid={!!handlingsFeil}
                required
              />
            </label>
            <button className={`${btnPrimar} w-full sm:w-auto`} type="submit" disabled={sender}>
              {sender ? "Sjekker…" : "Fortsett"}
            </button>
          </form>
          {visManuel && (
            <button
              className="mt-4 text-xs text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setVisManuel(false)}
            >
              Tilbake til listen
            </button>
          )}
        </>
      )}

      {handlingsFeil && (
        <p role="alert" className="mt-4 text-sm leading-relaxed text-red-700">
          {handlingsFeil}
        </p>
      )}
    </Kort>
  );
}
