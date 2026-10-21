import { describe, expect, it } from "vitest";

import { fmtNum } from "./plain";

describe("fmtNum", () => {
  it("groups thousands and drops a decimal's trailing zeros past two places", () => {
    expect(fmtNum("2605031.88000000")).toBe("2,605,031.88");
    expect(fmtNum("880400.00")).toBe("880,400.00");
    expect(fmtNum("1234.123400")).toBe("1,234.1234");
    expect(fmtNum("1250000.000000")).toBe("1,250,000.00");
    expect(fmtNum("Cash 3690000.00 today")).toBe("Cash 3,690,000.00 today");
  });
});
