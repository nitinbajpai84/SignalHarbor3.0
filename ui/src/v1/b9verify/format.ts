// V6 (WALK 10): figures and dates the way people read them. Decimal strings are grouped as text, never turned into floats first.
export const pct = (v: string | null, places = 2) => (v == null ? "Not available yet" : `${Number(v).toFixed(places)}%`);
export const pts = (v: string | null) => (v == null ? "Not available yet" : `${Number(v) > 0 ? "+" : ""}${Number(v).toFixed(2)} pts`);
export const ask = (e: unknown) => (e instanceof Error ? e.message : "That did not work. Please try again.");

/** 10500000 -> "10,500,000"; 4.1700 -> "4.17"; text that is not a number comes back as it is. */
export function num(v: string | null | undefined, places?: number): string {
  if (v == null || v === "") return "Not available yet";
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(String(v).trim());
  if (!m) return String(v);
  const [, sign = "", whole = "", frac = ""] = m;
  const f = places == null ? frac.replace(/0+$/, "") : Number(`0.${frac || "0"}`).toFixed(places).slice(2);
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}${grouped}${f ? `.${f}` : ""}`;
}

/** Signed difference: +180,000 or -2. */
export const signed = (v: string, places?: number) => `${Number(v) > 0 ? "+" : ""}${num(v, places)}`;
