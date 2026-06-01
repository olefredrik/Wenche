import Link from "next/link";
import { GITHUB_URL } from "@/lib/config";

export default function SiteFooter() {
  return (
    <footer className="mt-32 border-t border-border">
      <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-4 px-6 py-8 sm:flex-row sm:items-center">
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Laget av
          </span>
          <span className="text-sm font-medium text-foreground">Ole Fredrik Lie</span>
        </div>
        <div className="flex items-center gap-6">
          <Link href="/om" className="text-sm font-medium transition hover:text-spruce">
            Om prosjektet
          </Link>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium transition hover:text-spruce"
          >
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
