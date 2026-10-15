import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_ZONE, companyZone, day, setCompanyZone, time, when } from "./dates";

describe("date helpers", () => {
  afterEach(() => setCompanyZone(DEFAULT_ZONE));
  it("formats a bare date as written", () => {
    expect(day("2026-10-09")).toBe("9 Oct 2026");
    expect(when("2026-10-09")).toBe("9 Oct 2026");
  });
  it("formats a timestamp in one style", () => {
    expect(when("2026-10-09T09:12:08")).toBe("9 Oct 2026, 09:12");
    expect(time("2026-10-09T09:12:08")).toBe("09:12");
    expect(day("2026-10-09T09:12:08")).toBe("9 Oct 2026");
  });
  it("falls back for empty or bad input", () => {
    expect(day(null)).toBe("");
    expect(day("nope", "Not available yet")).toBe("Not available yet");
  });
  it("shows an instant in the company time zone, Singapore by default, whatever the browser's zone", () => {
    expect(companyZone()).toBe("Asia/Singapore");
    expect(when("2026-10-08T17:30:00+00:00")).toBe("9 Oct 2026, 01:30");
    expect(day("2026-10-08T17:30:00Z")).toBe("9 Oct 2026");
    setCompanyZone("Europe/London");
    expect(when("2026-10-08T17:30:00Z")).toBe("8 Oct 2026, 18:30");
  });
  it("never shifts a date-only value, in any zone", () => {
    for (const tz of ["Pacific/Kiritimati", "Pacific/Pago_Pago", "UTC"]) {
      setCompanyZone(tz);
      expect(day("2026-10-03")).toBe("3 Oct 2026");
      expect(time("2026-10-03")).toBe("");
    }
  });
  it("keeps the zone it had when given an unknown name", () => {
    setCompanyZone("Not/AZone");
    expect(companyZone()).toBe("Asia/Singapore");
    setCompanyZone(null);
    expect(companyZone()).toBe("Asia/Singapore");
  });
});
