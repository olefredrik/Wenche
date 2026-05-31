import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Om Wenche",
  description:
    "Hva Wenche er, hva hun gjør, og hva hun ikke gjør. Et innsendingsverktøy for passive holdingselskaper.",
};

function Bolk({ tittel, children }: { tittel: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="mb-3 text-2xl text-blekk">{tittel}</h2>
      <div className="space-y-3 leading-relaxed text-blekk-myk">{children}</div>
    </section>
  );
}

export default function Om() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-2xl px-6 pt-16 pb-24">
        <Link href="/" className="text-sm text-gran underline-offset-2 hover:underline">
          ← Tilbake
        </Link>

        <h1 className="mt-6 mb-8 text-4xl text-blekk sm:text-5xl">Om Wenche</h1>

        <Bolk tittel="Hva Wenche gjør">
          <p>
            Wenche hjelper deg å sende inn de tre tingene et lite holdingselskap må levere hvert
            år: <strong>årsregnskap</strong> til Regnskapsregisteret, <strong>skattemelding</strong>{" "}
            til Skatteetaten, og <strong>aksjonærregisteroppgave</strong>. Du fyller inn tallene,
            Wenche bygger de riktige skjemaene, kontrollerer at de henger sammen, og sender dem
            rett inn via Altinn og Skatteetatens API-er.
          </p>
        </Bolk>

        <Bolk tittel="Hvem hun er for">
          <p>
            Wenche er laget for <strong>passive holdingselskaper</strong>, selskaper som i
            hovedsak eier aksjer og ikke har noen større drift. Det er en bevisst avgrensning:
            ved å gjøre én ting godt, kan oppsettet være enkelt og innsendingen trygg. Driver du
            et aktivt selskap med ansatte, varelager og mva, er Wenche ikke rett verktøy.
          </p>
        </Bolk>

        <Bolk tittel="Hva hun ikke gjør">
          <p>
            Wenche er et <strong>innsendingsverktøy, ikke en regnskapsfører</strong>. Hun gir
            ingen råd om hva du bør rapportere, og hun tar ikke ansvar for at tallene er riktige,
            det er ditt. Hun gjør jobben med å fylle ut skjemaene korrekt og levere dem dit de
            skal. Du har alltid siste ord og godkjenner før noe sendes.
          </p>
        </Bolk>

        <Bolk tittel="Personvern og data">
          <p>
            Tallene du legger inn, inkludert fødselsnummer til aksjonærer, behandles bare mens du
            er innlogget og slettes når du er ferdig. Ingenting lagres i en database. Wenche
            sender direkte til myndighetene; ingen tredjepart er involvert.
          </p>
        </Bolk>

        <Bolk tittel="Åpen kildekode">
          <p>
            Wenche er åpen kildekode. Den hostede tjenesten her er en bekvemmelighet for
            inviterte, men du står fritt til å kjøre den samme programvaren på din egen maskin,
            helt gratis. Koden ligger åpent på{" "}
            <a
              href="https://github.com/olefredrik/wenche"
              target="_blank"
              rel="noopener noreferrer"
              className="text-gran underline-offset-2 hover:underline"
            >
              GitHub
            </a>
            .
          </p>
        </Bolk>

        <Bolk tittel="Hvorfor «Wenche»?">
          <p>
            Fordi noen oppgaver fortjener en rolig, erfaren hånd som har gjort dem mange ganger
            før. Wenche maser ikke, hun bare ordner opp.
          </p>
        </Bolk>
      </div>
    </main>
  );
}
