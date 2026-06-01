import { APP_URL } from "@/lib/config";

export default function Sidebar() {
  return (
    <aside className="mt-16 animate-fade-up [animation-delay:300ms] lg:mt-0">
      <div className="space-y-8 lg:sticky lg:top-24">
        {/* Kort 1, Hvem er Wenche? */}
        <div className="relative overflow-hidden rounded-sm border border-border bg-spruce-soft p-8">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-spruce">
            Hvem er Wenche?
          </p>
          <h2 className="mt-3 font-display text-2xl font-normal">
            En rolig stund ved kjøkkenbordet
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Jeg har sett min andel av kompliserte skjemaer og frustrerende feilmeldinger i
            Altinn. Min oppgave er å gjøre årsoppgjøret til noe du faktisk kan ta i ditt eget
            tempo, snarere enn en kilde til stress.
          </p>
          <p className="mt-6 -rotate-2 font-signature text-3xl leading-none text-spruce">
            Hilsen Wenche
          </p>
          <svg
            className="pointer-events-none absolute -bottom-2 -right-3 h-28 w-28 rotate-12 text-spruce opacity-[0.06]"
            viewBox="0 0 100 100"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path d="M8 82 L68 22" strokeLinecap="round" />
            <path d="M68 22 L77 13 L86 22 L77 31 Z" />
            <path d="M12 78 L20 86" strokeLinecap="round" />
          </svg>
        </div>

        {/* Kort 2, Status */}
        <div className="border-l-2 border-spruce py-1 pl-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Status
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Invite-only. For spesielt inviterte testere i denne omgang.
          </p>
        </div>

        {/* Logg inn */}
        <a
          href={APP_URL}
          className="block w-full rounded-full border border-foreground py-4 text-center font-medium transition hover:bg-foreground hover:text-background"
        >
          Logg inn
        </a>
      </div>
    </aside>
  );
}
