// Delte typer for API-svarene begge appene mottar. Speiler pydantic-modellene i
// wenche/web/felles/svar.py; endres de der, endres de her (leveranse 8 genererer dem).

// Config-objektet slik skjemaet bygger det og backenden leser det (samme form som
// config.yaml). Strukturen er data (felter.ts), så typen er løs fram til JSON Schema-typene
// kommer. Én navngitt type i stedet for `any` overalt, så bruken er lett å finne igjen.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Config = Record<string, any>;

// Dry-run: lokal validering uten nettverk.
export interface ValideringSvar {
  dry_run: boolean;
  ok: boolean;
  feil: string[];
  advarsler: string[];
  antall_aksjonaerer?: number;
  regnskapsaar?: number;
}

// Ekte innsending. `resultat` er signeringslenken (årsregnskap, skattemelding) eller
// kvitteringen fra Skatteetaten (aksjonærregister). `krever_bekreftelse` betyr at ingenting
// ble sendt fordi brukeren må bekrefte først (klage på skjønnsfastsetting).
export interface InnsendingSvar {
  sendt: boolean;
  resultat?: string | Record<string, unknown>;
  klage?: boolean;
  krever_bekreftelse?: string;
  melding?: string;
}

export type InnsendingResultat = ValideringSvar | InnsendingSvar;

export function erValidering(svar: InnsendingResultat): svar is ValideringSvar {
  return "ok" in svar && !("sendt" in svar);
}

export interface NedlastFil {
  filnavn: string;
  mime: string;
  base64: string;
}

export interface FilerSvar {
  filer: NedlastFil[];
}

export interface SkatteberegningSvar {
  beregnet_skatt: number;
  skattepliktig_inntekt: number;
  foert_skattekostnad: number;
}

// SAF-T-importen gir en config, pluss advarsler som ikke er et config-felt.
export type SaftImportSvar = Config & { _advarsler?: string[] };

// Forhåndsfyll fra Enhetsregisteret (hostet).
export interface SelskapSvar {
  org_nummer: string;
  navn: string;
  forretningsadresse: string;
  daglig_leder: string;
  styreleder: string;
  stiftelsesaar: number;
  stiftelsesdato: string;
}

export interface HelseSvar {
  status: string;
  env: string;
  wenche: string;
  vendor_konfigurert?: boolean;
}
