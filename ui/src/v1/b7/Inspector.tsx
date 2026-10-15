import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import type { LayoutItem } from "../cxui/api";
import { getStudio, type LibraryTable } from "./api";
import { duplicateWidget, patchTile, removeWidget, type TilePatch } from "./panelsApi";

// STUDIO2 F2 (design board 1, "This chart"): change how the selected widget is shown. Each choice is saved at once and recorded as a step.
export const SHOWN_AS: Record<string, string> = {
  figure: "Figure", line: "Lines", bar: "Bars", area: "Area", table: "Table", status: "Status list", bullet: "Bullet (against a target)", waterfall: "Waterfall (what moved it)",
  small_multiples: "Small charts, one per group", calendar: "Calendar heat map", treemap: "Treemap (shares)", kpi_strip: "Strip of key figures",
};
const SELECT = { background: "transparent", color: "inherit", border: "1px solid currentColor", borderRadius: 9, padding: 9, width: "100%" } as const;
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const blank = (item: LayoutItem) => ({ kind: item.kind, measure: "", when: "", split: "", column: "", values: "", title: item.title });

export default function Inspector({ pid, did, item, onChanged }: { pid: string; did: string; item: LayoutItem; onChanged: () => void }) {
  const [tables, setTables] = useState<LibraryTable[]>([]);
  const [kinds, setKinds] = useState<string[]>(Object.keys(SHOWN_AS));
  const [vals, setVals] = useState(blank(item));
  const [error, setError] = useState("");
  useEffect(() => { setVals(blank(item)); setError(""); }, [item.id]);  // eslint-disable-line react-hooks/exhaustive-deps -- reset only for a different widget
  useEffect(() => { // the column choices come from the tables this dashboard reads
    let live = true;
    getStudio(pid, did).then((s) => { if (live) { setTables(s.library.tables); setKinds([...new Set([...s.library.kinds.filter((k) => k !== "note"), ...Object.keys(SHOWN_AS)])]); } }).catch(() => undefined);
    return () => { live = false; };
  }, [pid, did]);

  const tid = item.tile;
  if (!tid) return <aside aria-label="Selected chart"><p className="ds-muted">A note has nothing to set here. Change its words on the grid.</p></aside>;
  const mine = tables.filter((t) => (item.reads ?? []).includes(t.label));
  const cols = (mine.length ? mine : tables).flatMap((t) => t.columns);
  const act = async (fn: () => Promise<unknown>) => { setError(""); try { await fn(); onChanged(); } catch (e) { setError(plain(e)); } };
  const save = (p: TilePatch) => act(() => patchTile(pid, did, tid, p));
  const pick = (key: "measure" | "when" | "split", label: string, hint: string) => (
    <label style={{ display: "block", fontSize: 12 }}>{label}
      <select aria-label={label} style={SELECT} value={vals[key]} onChange={(e) => { setVals({ ...vals, [key]: e.target.value }); if (e.target.value) void save({ [key]: e.target.value }); }}>
        <option value="">{hint}</option>{cols.map((c) => <option key={c.name} value={c.name}>{c.name.replace(/_/g, " ")}</option>)}</select></label>);
  return (
    <aside aria-label="Selected chart" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="ds-eyebrow">THIS CHART</div>
      <label style={{ display: "block", fontSize: 12 }}>Shown as
        <select aria-label="Shown as" style={SELECT} value={vals.kind} onChange={(e) => { setVals({ ...vals, kind: e.target.value }); void save({ kind: e.target.value }); }}>
          {kinds.map((k) => <option key={k} value={k}>{SHOWN_AS[k] ?? k}</option>)}</select></label>
      {pick("measure", "Down the side", "Keep as it is")}
      {pick("when", "Across", "Keep as it is")}
      {pick("split", "Split by", "No split")}
      <div style={{ fontSize: 12 }}>
        <label style={{ display: "block" }}>Only, column
          <select aria-label="Only, column" style={SELECT} value={vals.column} onChange={(e) => setVals({ ...vals, column: e.target.value })}>
            <option value="">Everything</option>{cols.map((c) => <option key={c.name} value={c.name}>{c.name.replace(/_/g, " ")}</option>)}</select></label>
        {vals.column ? <label style={{ display: "block", marginTop: 6 }}>Only these values, separated by commas
          <input aria-label="Only these values" style={SELECT} value={vals.values} onChange={(e) => setVals({ ...vals, values: e.target.value })}
            onBlur={() => { const v = vals.values.split(",").map((x) => x.trim()).filter(Boolean); if (v.length) void save({ only: { column: vals.column, values: v } }); }} /></label> : null}
      </div>
      <label style={{ display: "block", fontSize: 12 }}>Title
        <input aria-label="Title" style={SELECT} value={vals.title} onChange={(e) => setVals({ ...vals, title: e.target.value })}
          onBlur={() => { if (vals.title.trim() && vals.title !== item.title) void save({ title: vals.title.trim() }); }} /></label>
      <p className="ds-muted" style={{ fontSize: 12, margin: 0 }}>{item.reads?.length ? `Reads ${item.reads.join(", ")}. ` : ""}Every figure comes from the table, never typed.</p>
      {error ? <p role="alert">{error}</p> : null}
      <div style={{ display: "flex", gap: 8 }}>
        <Button onClick={() => void act(() => duplicateWidget(pid, did, item.id))}>Duplicate</Button>
        <Button onClick={() => void act(() => removeWidget(pid, did, item.id))}>Remove</Button>
      </div>
    </aside>
  );
}
