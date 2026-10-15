import type { CSSProperties } from "react";

// M1-P07 layout only (no colour): stickies, panels, pills and bars come from the legacy styles already imported.
// Inline because the look test allows one stylesheet outside styles/legacy and that one is not this package's.
export const column = (gap: number): CSSProperties => ({ display: "flex", flexDirection: "column", gap });
export const wrap = (gap: number): CSSProperties => ({ display: "flex", flexWrap: "wrap", alignItems: "center", gap });
export const clusterGrid: CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))", gap: 14, alignItems: "start",
};
export const noteList: CSSProperties = { listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 10 };
export const moveField: CSSProperties = { display: "flex", flexDirection: "column", gap: 2, marginTop: 8, fontSize: 12 };
export const smallLine: CSSProperties = { fontSize: 12, marginTop: 6 };
export const voteRow: CSSProperties = { display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, margin: "6px 0" };
export const voteName: CSSProperties = { flex: "0 0 7.5em" };
export const voteBar: CSSProperties = { flex: "1 1 120px" };
export const voteCount: CSSProperties = { fontVariantNumeric: "tabular-nums", minWidth: "5.5em", textAlign: "right" };
export const thread: CSSProperties = { listStyle: "none", margin: "8px 0", padding: 0, display: "flex", flexDirection: "column", gap: 6 };
export const commentField: CSSProperties = { flex: "1 1 220px", marginBottom: 0 };
export const bigCount: CSSProperties = { fontSize: 18, fontVariantNumeric: "tabular-nums" };
export const gap: CSSProperties = { marginTop: 14, marginBottom: 14 };
