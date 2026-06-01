export default function Hero() {
  return (
    <section className="animate-fade-up">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
        Årsoppgjøret, rolig sortert
      </p>
      <h1 className="mt-6 font-display text-5xl font-normal leading-[1.05] lg:text-7xl">
        Fristen nærmer seg.
        <br />
        <span className="text-spruce">Ta det med ro.</span>
      </h1>
      <p className="mt-8 max-w-xl text-xl leading-relaxed text-muted-foreground">
        Jeg sender inn årsregnskap, skattemelding og aksjonærregisteroppgave for ditt passive
        holdingselskap direkte til Altinn. Du fyller inn tallene, jeg ordner resten.
      </p>
    </section>
  );
}
