import type { CSSProperties } from "react";

/** Layout for the work list. Inline, with the earlier stylesheet's tokens only: a new CSS file would break the look test
 * that allows exactly one stylesheet outside styles/legacy. Grids wrap by themselves, so nothing needs a media query. */
export const S: Record<string, CSSProperties> = {
  prov: { display: "grid", gap: 4, minWidth: 120 },
  by: { fontSize: 11.5 },
  h3: { fontFamily: "var(--font-heading)", fontSize: 15, margin: "16px 0 8px" },
  detail: { display: "grid", gap: 8 },
  field: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8, alignItems: "end", marginBottom: 8 },
  label: { display: "grid", gap: 4, fontSize: 12, color: "var(--text-muted)" },
  fieldset: { border: 0, padding: 0, margin: "0 0 8px" },
  list: { listStyle: "none", margin: "0 0 8px", padding: 0, display: "grid", gap: 10 },
  owner: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12, alignItems: "start", borderBottom: "1px solid var(--border-hairline)", paddingBottom: 10 },
  problem: { marginTop: 14 },
};
