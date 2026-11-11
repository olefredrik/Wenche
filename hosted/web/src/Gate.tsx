// Gateskjerm. I prod (ID-porten konfigurert): logg inn med BankID. På demo (ID-porten av):
// invite-lenke (løses inn via URL-fragmentet) er porten, ellers en kontaktvei. Den frie
// navnematchen er fjernet; med ID-porten er navnet verifisert, ikke innskrevet.
import { Kort, btnPrimar, monoLabel } from "@wenche/ui";
import { KontaktLenke } from "./felles";
import { sporHendelse } from "./sporing";
import type { Me } from "./typer";

export function Gate({ me }: { me: Me }) {
  return (
    <Kort>
      <p className={monoLabel}>Tilgang</p>
      <h2 className="mt-3 font-display text-3xl font-normal">Logg inn</h2>
      {me.idporten ? (
        <>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            Wenche er ikke kravstor. Men hun må vite hvem hun jobber for. Logg inn med ID-porten,
            velg BankID og gå videre. Ditt fødselsnummer benyttes kun for autentisering og lagres
            ikke.
          </p>
          {/* Full-page navigasjon: backenden redirecter videre til ID-porten. */}
          <a
            className={`${btnPrimar} mt-6 inline-block`}
            href="/api/auth/idporten/login"
            onClick={() => sporHendelse("idporten-start")}
          >
            Logg inn med BankID
          </a>
        </>
      ) : (
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          Wenche er i en tidlig testfase. Vil du prøve den? Ta kontakt:{" "}
          <KontaktLenke kontakt={me.kontakt} />.
        </p>
      )}
    </Kort>
  );
}
