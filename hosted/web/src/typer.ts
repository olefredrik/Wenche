// Typene for den hostede appens egne endepunkter (hosted/api/auth.py, systembruker.py,
// idporten.py). De delte svarene (innsending, dokumenter, SAF-T) kommer fra @wenche/ui.
import type { Fane } from "@wenche/ui";

export interface Me {
  invited: boolean; // gate passert (ID-porten-innlogging eller invite-lenke)
  via_idporten?: boolean; // logget inn via ID-porten (mangler bundet org til velg-org er gjort)
  navn?: string | null; // verifisert navn fra ID-porten
  invite_org?: string | null; // org bundet til økten (invite-token eller velg-org)
  kunde_org?: string | null;
  env?: string;
  demo?: boolean;
  idporten?: boolean; // er ID-porten-innlogging tilgjengelig (prod), styrer gateskjermen
  reportees?: boolean; // har altinn:accessmanagement/authorizedparties-scopet, ellers manuell orgnr
  kontakt?: string | null;
}

export interface InviteSvar {
  invited: boolean;
  invite_org?: string;
  kunde_org?: string;
  feil?: string;
}

export interface VelgOrgSvar {
  ok: boolean;
  invite_org?: string;
  feil?: string;
  kontakt?: string;
}

export interface OrgItem {
  orgnr: string;
  navn: string;
}

export interface OrganisasjonerSvar {
  organisasjoner: OrgItem[];
  feil?: string;
}

export interface SystembrukerSvar {
  status?: string;
  godkjent?: boolean;
  kunde_org?: string | null;
  request_id?: string;
  confirm_url?: string | null;
}

export interface HandoffSvar {
  lenke: string;
  gyldig_sekunder?: number;
}

export type FaneId = "hjem" | "tall" | "dokumenter" | "send";

// Færre steg enn self-hosted: Maskinporten-oppsettet er gjort av operatøren, så brukeren har
// bare Hjem (tilkoblingsstatus) + tre arbeidssteg.
export const FANER: Fane[] = [
  { id: "hjem", navn: "Hjem" },
  { id: "tall", navn: "Tall", steg: 1 },
  { id: "dokumenter", navn: "Dokumenter", steg: 2 },
  { id: "send", navn: "Send", steg: 3 },
];
