/** The one number format for dashboards: thousands separators and exactly one decimal place. */
const one = { minimumFractionDigits: 1, maximumFractionDigits: 1 } as const;
export const fmt1 = (n: number): string => (Object.is(Math.round(n * 10) / 10, -0) ? 0 : n).toLocaleString("en-GB", one);
export const pct1 = (n: number): string => `${fmt1(n)}%`;

const NUMERIC = /^[-+]?\d+(\.\d+)?$/, PERCENT = /^[-+]?\d+(\.\d+)?%$/;
/**
 * A dashboard value as text. Numbers, and strings that are only a number (a Decimal read from the database arrives as "2605031.88000"), get the one-decimal format;
 * "12.345%" keeps its % at one decimal. Other text is left alone. `strict` also converts digit-only strings ("2024" in a table could be a year, a headline figure never is).
 */
export function fmtValue(v: unknown, strict = false): string {
  if (typeof v === "number") return Number.isFinite(v) ? fmt1(v) : String(v);
  if (typeof v !== "string") return String(v ?? "");
  const s = v.trim();
  if (PERCENT.test(s)) return pct1(Number(s.slice(0, -1)));
  if (NUMERIC.test(s) && (strict || s.includes("."))) return fmt1(Number(s));
  return v;
}
