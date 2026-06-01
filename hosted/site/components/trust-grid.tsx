const items = [
  {
    label: "Avgrensning",
    tittel: "Begrenset og bevisst",
    tekst:
      "Wenche er spesialisert. Hun fungerer kun for passive holdingselskaper (uten ansatte eller drift). Hun er et innsendingsverktøy, ikke en regnskapsfører. Du eier tallene og har kontrollen.",
  },
  {
    label: "Trygghet",
    tittel: "Full tillit",
    tekst:
      "Ingenting lagres utenfor din egen økt. Når du lukker vinduet, er dataene borte. Prosjektet er åpen kildekode og kan kjøres selv om du foretrekker det.",
  },
];

export default function TrustGrid() {
  return (
    <section className="grid animate-fade-up grid-cols-1 gap-12 [animation-delay:200ms] sm:grid-cols-2">
      {items.map((it) => (
        <div key={it.label}>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            {it.label}
          </p>
          <h3 className="mt-2 font-display text-2xl font-normal">{it.tittel}</h3>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{it.tekst}</p>
        </div>
      ))}
    </section>
  );
}
