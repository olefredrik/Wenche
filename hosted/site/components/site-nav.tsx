import { APP_URL } from "@/lib/config";

export default function SiteNav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <span className="font-display text-2xl font-medium tracking-tight">Wenche</span>
        <div className="flex items-center gap-5">
          <span className="hidden text-xs text-muted-foreground sm:inline">
            Foreløpig kun for spesielt inviterte
          </span>
          <a
            href={APP_URL}
            className="rounded-full bg-spruce px-5 py-2 text-sm font-medium text-background transition hover:brightness-110"
          >
            Logg inn
          </a>
        </div>
      </div>
    </nav>
  );
}
