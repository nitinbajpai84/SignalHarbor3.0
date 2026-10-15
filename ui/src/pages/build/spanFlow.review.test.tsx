// SF18 review of SF16 and SF17: the copy rules on screen words (no ids, no vendor names, no em dashes) and the known jargon gaps.
import { describe, expect, test } from "vitest";
import { flowCopy } from "./flowCopy";
import { plain, sc } from "./spanCopy";

const words = (o: unknown): string[] =>
  typeof o === "string" ? [o] : typeof o === "function" ? [] : o && typeof o === "object" ? Object.values(o).flatMap(words) : [];
const all = [...words(sc), ...words(flowCopy)];

describe("Span and Flow screen words", () => {
  test("no em dash, no vendor or model name, no ids or table names", () => {
    for (const w of all) {
      expect(w).not.toMatch(/\u2014/);
      expect(w).not.toMatch(/claude|anthropic|openai|gpt|gemini/i);
      expect(w).not.toMatch(/\b[A-Z]-\d{4}\b|\bK\d{2}\b|\b(dim|fact|gold|silver|bronze)_/);
    }
  });

  test("plain() removes proposal ids, measure codes and table names", () => {
    const out = plain("P-0004 changes K05 in dim_vehicle and gold.k05.unfunded_commitments");
    expect(out).not.toMatch(/P-0004|K05|dim_vehicle|gold\.k05/);
  });

  test("plain() turns 'Type 1 SCD' into words a family-office reader knows", () => {
    expect(plain("a Type 1 SCD overwrites the old values")).not.toMatch(/SCD|Type 1/);
  });
});
