// Småting flere av de hostede skjermene deler: vilkår, samtykketekst, feilkoder fra ID-porten
// og kontaktlenken.

// Lenke til vilkårene (publisert på markedssiden wenche-web).
export const VILKAAR_URL = "https://www.wenche.cloud/vilkaar";

// Feilkoder fra ID-porten-callbacken (hosted/api/idporten.py), oversatt her. Backend sender en
// kode, ikke tekst, så ingen kan lage en lenke som viser en vilkårlig melding i banneret.
export const IDP_FEIL: Record<string, string> = {
  avbrutt: "Innloggingen ble avbrutt. Prøv igjen.",
  mislyktes: "Innloggingen kunne ikke fullføres. Prøv igjen.",
  navn_mangler: "Fikk ikke navnet ditt fra ID-porten. Ta kontakt for manuell tilgang.",
};

// Hostet samtykke: vilkår + OFL-ansvarsfraskrivelse (operatøren er databehandler).
export const HOSTET_SAMTYKKE = (
  <span>
    Jeg har lest og godtar{" "}
    <a
      href={VILKAAR_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="text-spruce underline-offset-2 hover:underline"
    >
      vilkårene
    </a>
    , sender på eget ansvar, og bekrefter at jeg har fullmakt til å sende på vegne av
    selskapet og at tallene er korrekte. OFL Holding AS kan ikke holdes ansvarlig for feil
    eller tap ved bruk av tjenesten.
  </span>
);

// Vis en kontaktvei (mailto: eller https) som en klikkbar lenke, med lesbar tekst.
export function KontaktLenke({ kontakt }: { kontakt?: string | null }) {
  if (!kontakt) return null;
  const tekst = kontakt.startsWith("mailto:")
    ? kontakt.slice("mailto:".length)
    : kontakt.replace(/^https?:\/\//, "");
  return (
    <a
      href={kontakt}
      target={kontakt.startsWith("mailto:") ? undefined : "_blank"}
      rel="noopener noreferrer"
      className="text-spruce underline-offset-2 hover:underline"
    >
      {tekst}
    </a>
  );
}
