// Offentlig API for det delte Wenche-designsystemet.
export * from "./styles";
export * from "./komponenter";
export { req } from "./api";
export type { ApiFeil } from "./api";
export { DataSkjema, kr, oppsummer, harMinimumsdata } from "./skjema";
export {
  SendSeksjon,
  Resultatpanel,
  SeksjonsNav,
} from "./send";
export type { Utfall, Validering, InnsendingFn } from "./send";
export { lastNed } from "./nedlasting";
export type { NedlastFil } from "./nedlasting";
export { Dokumenter } from "./dokumenter";
export type { DokumentFn } from "./dokumenter";
export { NoterSeksjon, tomtLaan, noterFraConfig } from "./noter";
export type { Laan, NoterData } from "./noter";
export { StegNav, GaaVidere } from "./stegnav";
export type { Fane } from "./stegnav";
