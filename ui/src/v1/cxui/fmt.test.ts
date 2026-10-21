import { describe, expect, it } from "vitest";

import { fmt1, fmtValue, pct1 } from "./fmt";

describe("dashboard number format", () => {
  it("reads a long string and shows one decimal with separators", () => {
    expect(fmtValue("2605031.88000")).toBe("2,605,031.9");
    expect(fmtValue("3690000.0000")).toBe("3,690,000.0");
    expect(fmtValue("641686.56000000")).toBe("641,686.6");
    expect(fmtValue("0.0000")).toBe("0.0");
  });
  it("shows integers with a .0", () => {
    expect(fmtValue(1234)).toBe("1,234.0");
    expect(fmtValue(0)).toBe("0.0");
    expect(fmtValue("42", true)).toBe("42.0");
  });
  it("leaves digit-only strings and other text alone unless strict", () => {
    expect(fmtValue("2024")).toBe("2024");
    expect(fmtValue("2024-01-31")).toBe("2024-01-31");
    expect(fmtValue("Acme Ltd")).toBe("Acme Ltd");
  });
  it("handles negatives and does not show -0.0", () => {
    expect(fmtValue(-1234567.891)).toBe("-1,234,567.9");
    expect(fmtValue("-0.04")).toBe("0.0");
    expect(fmt1(-0.01)).toBe("0.0");
  });
  it("keeps the % and uses one decimal", () => {
    expect(fmtValue("12.3456%")).toBe("12.3%");
    expect(fmtValue("-5%")).toBe("-5.0%");
    expect(pct1(4.167)).toBe("4.2%");
  });
});
