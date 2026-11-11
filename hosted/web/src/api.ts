// Hostet-spesifikke endepunkt-bindinger oppå den delte fetch-wrapperen og de delte
// endepunktene (lagFellesApi). Same-origin i dev via Vite-proxy, så cookies (sesjon) følger
// med uten CORS-styr.
import { lagFellesApi, req, type SelskapSvar } from "@wenche/ui";
import type {
  HandoffSvar,
  InviteSvar,
  Me,
  OrganisasjonerSvar,
  SystembrukerSvar,
  VelgOrgSvar,
} from "./typer";

export const api = {
  ...lagFellesApi(),
  me: () => req<Me>("/api/auth/me"),
  invite: (token: string) =>
    req<InviteSvar>("/api/auth/invite", { method: "POST", body: JSON.stringify({ token }) }),
  // ID-porten + Altinn: hent liste over orger brukeren kan handle for (bruker access_token
  // fra sesjonen til å veksle mot Altinn og hente autoriserte parter). Returnerer alltid
  // {organisasjoner, feil?}, tom liste ved feil, så SPA-en kan falle tilbake til manuell input.
  hentOrganisasjoner: () => req<OrganisasjonerSvar>("/api/auth/idporten/organisasjoner"),
  // Bind sesjonen til org valgt fra Altinn-listen (re-verifiserer mot Altinn, ingen brreg-sjekk).
  velgOrgAltinn: (org: string) =>
    req<VelgOrgSvar>("/api/auth/idporten/velg-org", { method: "POST", body: JSON.stringify({ org }) }),
  // ID-porten-rollesjekk (manuell fallback): etter BankID-innlogging bekreftes det verifiserte
  // navnet (fra sesjonen) mot orgnr i Enhetsregisteret. Navnet sendes ikke fra klienten, bare orgnr.
  velgOrg: (org: string) =>
    req<VelgOrgSvar>("/api/auth/velg-org", { method: "POST", body: JSON.stringify({ org }) }),
  // Fortsett på en annen enhet: en koblet økt lager en kortvarig overføringslenke (QR),
  // den nye enheten løser den inn og arver bindingen.
  handoffCreate: () => req<HandoffSvar>("/api/auth/handoff/create", { method: "POST" }),
  handoffUse: (token: string) =>
    req<InviteSvar>("/api/auth/handoff/use", { method: "POST", body: JSON.stringify({ token }) }),
  logout: () => req<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  systembrukerRequest: () => req<SystembrukerSvar>("/api/systembruker/request", { method: "POST" }),
  systembrukerStatus: () => req<SystembrukerSvar>("/api/systembruker/status", { method: "POST" }),
  // Forhåndsfyll: daglig leder, styreleder og stiftelsesår fra Enhetsregisteret for den koblede
  // orgen (offentlige data, lagres ikke). SAF-T bærer ikke disse feltene, så uten dette må de
  // skrives manuelt etter import.
  selskap: () => req<SelskapSvar>("/api/selskap"),
};
