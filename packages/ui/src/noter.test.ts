import { describe, expect, it } from "vitest";
import { noterFraConfig, tomtLaan } from "./noter";

describe("noterFraConfig", () => {
  it("tåler manglende og delvise noter", () => {
    expect(noterFraConfig(null)).toEqual({ antall_ansatte: 0, laan_til_naerstaaende: [] });
    expect(noterFraConfig({ noter: { antall_ansatte: 2 } })).toEqual({ antall_ansatte: 2, laan_til_naerstaaende: [] });
    const n = noterFraConfig({ noter: { laan_til_naerstaaende: [{ motpart: "Eier", saldo: 5000 }] } });
    expect(n.laan_til_naerstaaende).toEqual([{ ...tomtLaan(), motpart: "Eier", saldo: 5000 }]);
  });
});
