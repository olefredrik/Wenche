const steg = [
  {
    ref: "01",
    du: "Logg inn og koble til",
    duDetalj: "Godkjenn kobling i Altinn med BankID. Dette gjøres kun én gang.",
    wenche: "Henter automatisk opplysningene om selskapet ditt fra Enhetsregisteret.",
  },
  {
    ref: "02",
    du: "Fyll inn årets tall",
    duDetalj: "Du legger inn bankinnskudd, aksjeposter og eventuell gjeld.",
    wenche: "Bygger alle nødvendige skjemaer og sjekker at logikken stemmer.",
  },
  {
    ref: "03",
    du: "Send inn til etaten",
    duDetalj: "Se over tallene en siste gang og trykk på knappen.",
    wenche: "Overfører alt direkte til Skatteetaten. Kvittering kommer i Altinn.",
  },
];

const monoLabel = "font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground";

export default function LedgerSection() {
  return (
    <section className="animate-fade-up [animation-delay:100ms]">
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
            Slik fungerer det
          </p>
          <h2 className="mt-2 font-display text-3xl font-normal">Regnskapsboken</h2>
        </div>
        <div className="hidden h-px w-20 bg-foreground/30 sm:block" />
      </div>

      <div className="mt-10 border-t border-foreground/80">
        <div className="hidden grid-cols-[60px_1fr_1fr] border-b border-border py-3 lg:grid">
          <span className={monoLabel}>Ref</span>
          <span className={monoLabel}>Hva du gjør</span>
          <span className={`${monoLabel} pl-6`}>Hva Wenche gjør</span>
        </div>

        {steg.map((s, i) => (
          <div
            key={s.ref}
            className={`grid grid-cols-1 lg:grid-cols-[60px_1fr_1fr] ${
              i === steg.length - 1
                ? "border-b-2 border-foreground"
                : "border-b border-border"
            }`}
          >
            <div className="pt-5 font-mono text-sm text-muted-foreground">{s.ref}</div>
            <div className="py-5 lg:pr-6">
              <h3 className="text-lg font-medium">{s.du}</h3>
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.duDetalj}</p>
            </div>
            <div className="bg-spruce-soft px-6 py-5 lg:border-l lg:border-border lg:bg-paper">
              <p className="text-sm leading-relaxed text-muted-foreground">{s.wenche}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
