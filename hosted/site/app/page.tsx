import Link from "next/link";
import WenchePortrait from "@/components/wenche-portrait";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:5173";

function Merke({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-blekk-myk">
      <span className="text-gran">✓</span>
      {children}
    </span>
  );
}

function Steg({
  nr,
  tittel,
  tekst,
}: {
  nr: number;
  tittel: string;
  tekst: string;
}) {
  return (
    <div className="rounded-2xl border border-krem-myk bg-white p-6 shadow-sm">
      <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-gran/10 font-semibold text-gran">
        {nr}
      </div>
      <h3 className="mb-1.5 text-lg text-blekk">{tittel}</h3>
      <p className="text-sm leading-relaxed text-blekk-myk">{tekst}</p>
    </div>
  );
}

function Soyle({ tittel, tekst }: { tittel: string; tekst: string }) {
  return (
    <div>
      <h3 className="mb-2 text-lg text-blekk">{tittel}</h3>
      <p className="text-sm leading-relaxed text-blekk-myk">{tekst}</p>
    </div>
  );
}

export default function Home() {
  return (
    <main className="min-h-screen">
      {/* Hero */}
      <section className="mx-auto max-w-3xl px-6 pt-16 pb-20 text-center sm:pt-24">
        <WenchePortrait />
        <h1 className="mb-3 text-5xl font-normal tracking-tight text-blekk sm:text-6xl">
          Wenche
        </h1>
        <p className="mb-5 text-xl text-blekk sm:text-2xl">
          Hun tar årsoppgjøret for holdingselskapet ditt.
        </p>
        <p className="mx-auto mb-9 max-w-xl text-base leading-relaxed text-blekk-myk">
          Årsregnskap, skattemelding og aksjonærregisteroppgave, sendt rett til Altinn og
          Skatteetaten. Du fyller inn tallene; Wenche ordner skjemaene, sjekker dem, og sender
          dem inn. Ferdig før kaffen er kald.
        </p>
        <a
          href={APP_URL}
          className="inline-flex items-center gap-2 rounded-lg bg-gran px-8 py-3.5 text-base font-medium text-krem transition-colors hover:bg-gran-myk"
        >
          Logg inn
        </a>
        <p className="mt-4 text-sm text-blekk-myk">
          Wenche er foreløpig kun for spesielt inviterte.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-x-6 gap-y-2">
          <Merke>Ingenting lagres</Merke>
          <Merke>Du eier tallene</Merke>
          <Merke>Åpen kildekode</Merke>
        </div>
      </section>

      {/* Slik fungerer det */}
      <section className="mx-auto max-w-3xl px-6 pb-20">
        <h2 className="mb-10 text-center text-sm font-semibold uppercase tracking-wider text-blekk-myk">
          Slik fungerer det
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Steg
            nr={1}
            tittel="Logg inn"
            tekst="Du får en innloggingslenke på e-post. Ingen passord å huske."
          />
          <Steg
            nr={2}
            tittel="Koble selskapet"
            tekst="Godkjenn Wenche i Altinn én gang, med BankID. Da kan hun sende inn på vegne av selskapet ditt."
          />
          <Steg
            nr={3}
            tittel="Fyll inn tallene"
            tekst="Legg inn regnskapstall, aksjonærer og det skattemeldingen trenger. Wenche regner ut og sjekker underveis."
          />
          <Steg
            nr={4}
            tittel="Send inn"
            tekst="Se gjennom, og send. Wenche leverer til Altinn og Skatteetaten og gir deg kvitteringen."
          />
        </div>
      </section>

      {/* Hvem er Wenche */}
      <section className="mx-auto max-w-2xl px-6 pb-20">
        <div className="rounded-2xl bg-krem-myk p-8 sm:p-10">
          <h2 className="mb-4 text-2xl text-blekk">Hvem er Wenche?</h2>
          <p className="mb-4 leading-relaxed text-blekk-myk">
            Wenche er for deg som eier et lite, rolig holdingselskap, som ikke driver med noe
            særlig annet enn å eie. Likevel skal det hvert år leveres årsregnskap, skattemelding
            og aksjonærregisteroppgave. Det er ikke vanskelig, men det er fiklete, og fristene
            kommer alltid på et ugunstig tidspunkt.
          </p>
          <p className="leading-relaxed text-blekk-myk">
            Wenche kan dette utenat. Du gir henne tallene; hun fyller ut de riktige skjemaene,
            passer på at de henger sammen, og sender dem dit de skal. Du beholder kontrollen og
            ansvaret for tallene, Wenche tar det kjedelige.
          </p>
        </div>
      </section>

      {/* Trygt og ryddig */}
      <section className="mx-auto max-w-3xl px-6 pb-28">
        <h2 className="mb-10 text-center text-sm font-semibold uppercase tracking-wider text-blekk-myk">
          Trygt og ryddig
        </h2>
        <div className="grid grid-cols-1 gap-8 text-center sm:grid-cols-3">
          <Soyle
            tittel="Ingenting lagres"
            tekst="Tallene dine lever bare i økten og slettes når du er ferdig. Ingen database, ingenting liggende igjen."
          />
          <Soyle
            tittel="Du eier tallene"
            tekst="Wenche er et innsendingsverktøy, ikke en regnskapsfører. Du fyller inn og godkjenner; hun formidler."
          />
          <Soyle
            tittel="Åpen kildekode"
            tekst="Wenche er åpen kildekode. Vil du heller kjøre henne på egen maskin, er det helt gratis."
          />
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-krem-myk bg-krem-myk/40">
        <div className="mx-auto flex max-w-3xl flex-col items-center justify-between gap-3 px-6 py-6 text-xs text-blekk-myk sm:flex-row">
          <span>
            Laget av{" "}
            <a
              href="https://olefredrik.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline-offset-2 hover:underline"
            >
              Ole Fredrik Lie
            </a>
          </span>
          <div className="flex items-center gap-4">
            <Link href="/om" className="underline-offset-2 hover:underline">
              Om Wenche
            </Link>
            <a
              href="https://github.com/olefredrik/wenche"
              target="_blank"
              rel="noopener noreferrer"
              className="underline-offset-2 hover:underline"
            >
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
