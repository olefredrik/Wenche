// Umami-sporing — KUN for den hostede tjenesten (demo + prod). Bevisst utenfor packages/ui og
// wenche/web, så den open-source/self-hostede koden forblir analytics-fri. No-op hvis Umami
// ikke er lastet. Vi sporer kun fane-/hendelsesnavn, aldri skjemadata (fnr o.l.).

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function track(...args: any[]): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (window as any).umami?.track?.(...args);
}

// Virtuell sidevisning for SPA-navigasjon (URL-en endres ikke). Gir en funnel i Umami.
export function sporSidevisning(sti: string): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  track((props: any) => ({ ...props, url: sti }));
}

// Egendefinert hendelse, f.eks. «send-ok» med { type }.
export function sporHendelse(navn: string, data?: Record<string, unknown>): void {
  if (data) track(navn, data);
  else track(navn);
}
