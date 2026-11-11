// Endepunkt-bindinger for self-hosted Wenche oppå den delte fetch-wrapperen og de delte
// endepunktene (lagFellesApi).
import { lagFellesApi, req, type Config, type HelseSvar } from "@wenche/ui";
import type {
  ConfigSvar,
  FristerSvar,
  LagreConfigSvar,
  OppsettStatus,
  SjekkSvar,
  SystembrukerSvar,
  TestTilkoblingSvar,
  UpdateInfo,
} from "./typer";

export const api = {
  ...lagFellesApi(),
  health: () => req<HelseSvar>("/api/health"),
  updateCheck: () => req<UpdateInfo>("/api/update-check"),

  hentConfig: () => req<ConfigSvar>("/api/config"),
  lagreConfig: (config: Config) =>
    req<LagreConfigSvar>("/api/config", { method: "PUT", body: JSON.stringify(config) }),

  oppsettStatus: () => req<OppsettStatus>("/api/oppsett/status"),
  lagreCredentials: (body: { client_id: string; kid: string; orgnr: string }) =>
    req<{ ok: boolean }>("/api/oppsett/credentials", { method: "PUT", body: JSON.stringify(body) }),
  lagreNokkel: (pem: string) =>
    req<{ ok: boolean }>("/api/oppsett/nokkel", { method: "POST", body: JSON.stringify({ pem }) }),
  testTilkobling: () => req<TestTilkoblingSvar>("/api/oppsett/test-tilkobling", { method: "POST" }),
  registrerSystem: () => req<SystembrukerSvar>("/api/oppsett/registrer-system", { method: "POST" }),
  opprettSystembruker: () => req<SystembrukerSvar>("/api/oppsett/systembruker", { method: "POST" }),
  systembrukerStatus: () => req<SystembrukerSvar>("/api/oppsett/systembruker/status", { method: "POST" }),
  oppdaterSystembruker: () =>
    req<SystembrukerSvar>("/api/oppsett/systembruker/oppdater", { method: "POST" }),

  frister: () => req<FristerSvar>("/api/frister"),
  sjekkFrister: () => req<SjekkSvar>("/api/frister/sjekk", { method: "POST" }),
};
