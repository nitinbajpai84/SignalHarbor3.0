import { DataTable, Pill } from "../../design";
import type { SourceHealth } from "./api";
import { day } from "./dates";

// Per source, in words: is it late, is the data old, were files turned away, are values still unverified, are breaks open.
const n = (v: number | null) => (v === null ? "Not available yet" : String(v));
const arrival = (s: SourceHealth) => s.never_received ? <Pill tone="draft">Nothing received yet</Pill>
  : s.is_late ? <Pill tone="late">{s.days_late ? `Late by ${s.days_late} day${s.days_late === 1 ? "" : "s"}` : "Late"}</Pill>
    : s.cadence ? <Pill tone="ok">On time</Pill> : <span className="ds-muted">No schedule set</span>;

export default function SourcesTable({ sources }: { sources: SourceHealth[] }) {
  return (
    <DataTable
      columns={[{ key: "source", label: "Source" }, { key: "arrival", label: "Arrival" }, { key: "last", label: "Last received" }, { key: "rejected", label: "Files turned away" },
        { key: "stale", label: "Values older than 90 days" }, { key: "unverified", label: "Values not yet verified" }, { key: "breaks", label: "Open breaks" }]}
      rows={sources.map((s) => ({ source: <><strong>{s.name}</strong><div className="ds-footnote">Owner {s.owner ?? "not named yet"}{s.cadence ? `, arrives ${s.cadence}` : ""}</div></>,
        arrival: arrival(s), last: day(s.last_received), rejected: s.rejected, stale: n(s.stale), unverified: n(s.unverified), breaks: n(s.open_breaks) }))} />
  );
}
