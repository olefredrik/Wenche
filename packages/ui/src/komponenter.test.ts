import { describe, expect, it } from "vitest";
import { formaterVerdi, grupperTusen, tolkTall } from "./komponenter";

describe("tallformatering i skjemaet", () => {
  it("grupperer tusener med hardt mellomrom og bevarer fortegn og desimaler", () => {
    expect(grupperTusen(1000)).toBe("1 000");
    expect(grupperTusen(1000000)).toBe("1 000 000");
    expect(grupperTusen(-2500.5)).toBe("-2 500,5");
    expect(grupperTusen(12)).toBe("12");
    expect(grupperTusen(Number.NaN)).toBe("");
  });

  it("tolker det brukeren skriver til et rent tall, eller tomt under redigering", () => {
    expect(tolkTall("1 000,5")).toBe(1000.5);
    expect(tolkTall("1 000")).toBe(1000);
    expect(tolkTall("-")).toBe("");
    expect(tolkTall("")).toBe("");
    expect(tolkTall("abc")).toBe("");
    expect(tolkTall("-12.5")).toBe(-12.5);
  });

  it("formaterer verdier fra config til visning", () => {
    expect(formaterVerdi("")).toBe("");
    expect(formaterVerdi(null)).toBe("");
    expect(formaterVerdi(1000)).toBe("1 000");
    expect(formaterVerdi("1000")).toBe("1 000");
    expect(formaterVerdi("tekst")).toBe("");
  });
});
