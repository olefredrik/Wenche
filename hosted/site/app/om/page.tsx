import Link from "next/link";
import type { Metadata } from "next";
import SiteNav from "@/components/site-nav";
import SiteFooter from "@/components/site-footer";

export const metadata: Metadata = {
  title: "Om prosjektet, Wenche",
  description: "Hva Wenche er, hvem hun er for, og hva hun ikke gjør.",
};

function Bolk({
  label,
  tittel,
  children,
}: {
  label: string;
  tittel: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-12">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </p>
      <h2 className="mt-2 font-display text-2xl font-normal">{tittel}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  );
}

export default function Om() {
  return (
    <>
      <SiteNav />
      <article className="mx-auto max-w-2xl px-6 py-16 lg:py-24">
        <Link
          href="/"
          className="font-mono text-[11px] uppercase tracking-[0.2em] text-spruce"
        >
          ← Tilbake
        </Link>
        <h1 className="mt-6 font-display text-4xl font-normal lg:text-5xl">Om prosjektet</h1>
        <p className="mt-6 text-lg leading-relaxed text-muted-foreground">
          Wenche sender inn årsregnskap, skattemelding og aksjonærregisteroppgave for små,
          passive holdingselskaper, rett til Altinn og Skatteetaten. Du fyller inn tallene; hun
          bygger skjemaene, sjekker dem og sender.
        </p>

        <Bolk label="Hvem hun er for" tittel="Kun passive holdingselskaper">
          <p>
            Wenche er laget for selskaper som i hovedsak eier aksjer og ikke har noen større
            drift. Det er en bevisst avgrensning: ved å gjøre én ting godt kan oppsettet være
            enkelt og innsendingen trygg. Driver du et aktivt selskap med ansatte og mva, er
            Wenche ikke rett verktøy.
          </p>
        </Bolk>

        <Bolk label="Hva hun ikke gjør" tittel="Et verktøy, ikke en regnskapsfører">
          <p>
            Wenche gir ingen råd om hva du bør rapportere, og tar ikke ansvar for at tallene er
            riktige, det er ditt. Hun gjør jobben med å fylle ut skjemaene korrekt og levere dem
            dit de skal. Du har alltid siste ord og godkjenner før noe sendes.
          </p>
        </Bolk>

        <Bolk label="Personvern" tittel="Ingenting lagres">
          <p>
            Tallene du legger inn, inkludert fødselsnummer til aksjonærer, behandles bare mens du
            er innlogget og slettes når du er ferdig. Ingenting lagres i en database, og Wenche
            sender direkte til myndighetene uten noen tredjepart.
          </p>
        </Bolk>

        <Bolk label="Åpen kildekode" tittel="Du kan kjøre henne selv">
          <p>
            Wenche er åpen kildekode. Den hostede tjenesten er en bekvemmelighet for inviterte,
            men du står fritt til å kjøre den samme programvaren på egen maskin, helt gratis.
          </p>
        </Bolk>
      </article>
      <SiteFooter />
    </>
  );
}
