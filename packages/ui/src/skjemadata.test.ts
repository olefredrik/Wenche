import { describe, expect, it } from "vitest";
import { EKSEMPEL } from "./eksempel";
import {
  flettStyring,
  grunnConfig,
  harMinimumsdata,
  hent,
  medLaastOrg,
  normaliserForLagring,
  oppsummer,
  sett,
  sumBalanse,
} from "./skjemadata";

describe("hent og sett", () => {
  it("leser og skriver punkt-stier uten å mutere originalen", () => {
    const c = { selskap: { navn: "A" } };
    expect(hent(c, "selskap.navn")).toBe("A");
    expect(hent(c, "selskap.finnes.ikke")).toBeUndefined();
    expect(hent(null, "selskap.navn")).toBeUndefined();
    const ny = sett(c, "balanse.eiendeler.omloepmidler.bankinnskudd", 10);
    expect(hent(ny, "balanse.eiendeler.omloepmidler.bankinnskudd")).toBe(10);
    expect(c).toEqual({ selskap: { navn: "A" } });
    expect(ny.selskap).toBe(c.selskap); // urørte grener deles, bare stien kopieres
  });
});

describe("normaliserForLagring", () => {
  it("gjør tomme påkrevde tallfelt og aksjonærtall om til 0, og lar valgfrie og tekst stå", () => {
    const n = normaliserForLagring(grunnConfig());
    expect(hent(n, "selskap.aksjekapital")).toBe(0);
    expect(hent(n, "regnskapsaar")).toBe(0);
    expect(hent(n, "balanse.eiendeler.omloepmidler.bankinnskudd")).toBe(0);
    expect(hent(n, "selskap.navn")).toBe("");
    expect(n.aksjonaerer[0].antall_aksjer).toBe(0);
    expect(n.aksjonaerer[0].aksjeklasse).toBe("ordinære");
    expect(hent(n, "skattemelding.eierandel_for_fritaksmetoden")).toBeUndefined();
  });

  it("rører ikke tall som alt er satt, og legger bare til påkrevde felt som mangler", () => {
    const n = normaliserForLagring(EKSEMPEL);
    // Eksempeldataene mangler avsatt_utbytte (nyere felt); det blir 0. Alt annet er uendret.
    expect(hent(n, "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.avsatt_utbytte")).toBe(0);
    expect(n).toEqual(sett(EKSEMPEL, "balanse.egenkapital_og_gjeld.kortsiktig_gjeld.avsatt_utbytte", 0));
  });
});

describe("oppsummer, sumBalanse og harMinimumsdata", () => {
  it("summerer balansen og teller aksjonærer for eksempeldataene", () => {
    const o = oppsummer(EKSEMPEL);
    expect(o.org).toBe("312463938");
    expect(o.aar).toBe(2025);
    expect(o.balansererOk).toBe(true);
    expect(o.antallAksjonaerer).toBe(1);
    expect(sumBalanse(EKSEMPEL)).toEqual({ eiendeler: 130000, ekGjeld: 130000 });
  });

  it("oppdager ubalanse", () => {
    const skeiv = sett(EKSEMPEL, "balanse.eiendeler.omloepmidler.bankinnskudd", 31000);
    expect(oppsummer(skeiv).balansererOk).toBe(false);
    expect(oppsummer(skeiv).balanseDiff).toBe(1000);
  });

  it("krever navn, org.nr. og minst én representant", () => {
    expect(harMinimumsdata(null)).toBe(false);
    expect(harMinimumsdata(grunnConfig())).toBe(false);
    expect(harMinimumsdata({ selskap: { navn: "A", org_nummer: "1", styreleder: "S" } })).toBe(true);
    expect(harMinimumsdata({ selskap: { navn: "A", org_nummer: "1", daglig_leder: " " } })).toBe(false);
  });
});

describe("flettStyring og medLaastOrg", () => {
  it("beholder styringsdata og aksjonærer fra skjemaet når SAF-T mangler dem", () => {
    const saft = { selskap: { navn: "S AS", org_nummer: "1" }, aksjonaerer: [] };
    const eks = {
      selskap: { daglig_leder: "D", styreleder: "", stiftelsesaar: 2018, kontakt_epost: "a@b" },
      aksjonaerer: [{ navn: "X" }],
    };
    const f = flettStyring(saft, eks);
    expect(f.selskap).toEqual({
      navn: "S AS",
      org_nummer: "1",
      daglig_leder: "D",
      styreleder: "",
      stiftelsesaar: 2018,
      kontakt_epost: "a@b",
    });
    expect(f.aksjonaerer).toEqual([{ navn: "X" }]);
  });

  it("låser org.nr. bare når et er oppgitt", () => {
    const c = { selskap: { org_nummer: "1" } };
    expect(medLaastOrg(c, "999").selskap.org_nummer).toBe("999");
    expect(medLaastOrg(c).selskap.org_nummer).toBe("1");
  });
});
