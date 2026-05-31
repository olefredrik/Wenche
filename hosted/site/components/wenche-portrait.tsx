// Plassholder-portrett av Wenche. Klar for å byttes med en egen illustrasjon
// (gjerne med naturtro blunking à la Arvid) når den foreligger, da bytter vi
// emoji-en med to <Image>-lag som veksles.
export default function WenchePortrait() {
  return (
    <div className="mx-auto mb-7 flex h-32 w-32 items-center justify-center rounded-full bg-gran/10 ring-4 ring-gran/15 sm:h-40 sm:w-40">
      <span
        className="text-6xl sm:text-7xl"
        role="img"
        aria-label="Wenche"
      >
        👵
      </span>
    </div>
  );
}
