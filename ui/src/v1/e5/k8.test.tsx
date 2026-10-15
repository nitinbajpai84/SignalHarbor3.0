import { statusWord } from "./api";

// Card kinds as sent by E5a (sh_platform/v1/e5_pulse.py).
const c = (kind: string, status_word: string, headline = "x") => ({ kind, status_word, headline, action_type: "" });

test("each card kind reads as one written status word", () => {
  expect(statusWord(c("exception", "Revised · manager final"))).toBe("Revised · manager final");
  expect(statusWord(c("exception", "Break", "Cash differs · Entity B"))).toBe("Break");
  expect(statusWord(c("exception", "Unverified", "Limit breached: private markets share 31%"))).toBe("Limit");
  expect(statusWord(c("statement", "Stale", "Statement missing: Fund A"))).toBe("Late");
  expect(statusWord(c("approval", "Unverified", "Your approval: rule"))).toBe("Waiting for you");
  expect(statusWord(c("build", "Signed", "X is ready for Build"))).toBe("Shared");
  expect(statusWord(c("dashboard", "Official", "Dashboard refreshed"))).toBe("Refreshed");
  expect(statusWord(c("load", "Unverified", "Load failed"))).toBe("Unverified");
});

it("a fund named Limitless is not a limit card", () => {
  expect(statusWord({ kind: "exception", status_word: "Unverified", headline: "Limitless Growth cash differs", action_type: undefined })).toBe("Unverified");
});
