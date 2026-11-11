// Fortsett på en annen enhet: en koblet økt lager en kortvarig overføringslenke (QR + lenke)
// som en ny enhet løser inn for å arve samme binding, uten ny BankID. Løser at sesjonen ellers
// lever per nettleser (signert cookie, ingen DB), så et andre apparat står uten tilkobling.
import { useState } from "react";
import QRCode from "qrcode";
import { btnOutline, feilmelding } from "@wenche/ui";
import { api } from "./api";
import { sporHendelse } from "./sporing";

export function FortsettAnnenEnhet() {
  const [aapen, setAapen] = useState(false);
  const [lenke, setLenke] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [gyldigMin, setGyldigMin] = useState<number | null>(null);
  const [lager, setLager] = useState(false);
  const [kopiert, setKopiert] = useState(false);
  const [feil, setFeil] = useState<string | null>(null);

  const lag = async () => {
    setFeil(null);
    setKopiert(false);
    setLager(true);
    try {
      const r = await api.handoffCreate();
      setLenke(r.lenke);
      setGyldigMin(r.gyldig_sekunder ? Math.round(r.gyldig_sekunder / 60) : null);
      // QR genereres i nettleseren; lenken (med tokenet) forlater aldri enheten her.
      setQr(await QRCode.toDataURL(r.lenke, { margin: 1, width: 320 }));
      setAapen(true);
      sporHendelse("handoff-laget");
    } catch (e) {
      setFeil(feilmelding(e));
    } finally {
      setLager(false);
    }
  };

  const kopier = async () => {
    if (!lenke) return;
    try {
      await navigator.clipboard.writeText(lenke);
      setKopiert(true);
    } catch {
      /* clipboard blokkert (f.eks. ikke-https): lenken vises uansett for manuell kopiering */
    }
  };

  if (!aapen) {
    return (
      <>
        <button className={btnOutline} onClick={lag} disabled={lager}>
          {lager ? "Lager lenke…" : "Fortsett på en annen enhet"}
        </button>
        {feil && (
          <p role="alert" className="mt-3 text-sm text-red-700">
            {feil}
          </p>
        )}
      </>
    );
  }

  return (
    <div className="rounded-sm border border-border bg-background p-4">
      <p className="text-sm leading-relaxed text-muted-foreground">
        Det er to måter å koble den nye enheten på. Lenken gir tilgang uten ny
        BankID-godkjenning, er ferskvare{gyldigMin ? ` (gyldig i ${gyldigMin} minutter)` : ""}, og
        bør bare deles med deg selv.
      </p>

      <div className="mt-5">
        <p className="text-sm font-medium text-foreground">1. Skann QR-koden</p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Bruk kameraet på telefonen eller nettbrettet du vil koble til.
        </p>
        {qr && (
          <img
            src={qr}
            alt="QR-kode for å fortsette på en annen enhet"
            className="mt-3 rounded bg-white p-2"
            width={180}
            height={180}
          />
        )}
      </div>

      <div className="mt-5">
        <p className="text-sm font-medium text-foreground">2. Eller bruk lenken</p>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          Åpne den på den andre enheten, eller send den til deg selv, for eksempel på e-post.
        </p>
        {lenke && (
          <>
            <a
              className="mt-3 block break-all text-sm text-spruce underline-offset-2 hover:underline"
              href={lenke}
            >
              {lenke}
            </a>
            <div className="mt-3 flex items-center gap-3">
              <button className={btnOutline} onClick={kopier}>
                Kopier lenke
              </button>
              {kopiert && <span className="text-xs text-spruce">✓ Kopiert</span>}
            </div>
          </>
        )}
      </div>

      {feil && (
        <p role="alert" className="mt-3 text-sm text-red-700">
          {feil}
        </p>
      )}
    </div>
  );
}
