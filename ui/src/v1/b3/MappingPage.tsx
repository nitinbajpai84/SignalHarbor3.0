import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Chip, DataTable, EmptyState, PageFrame, Pill } from "../../design";
import { useSession } from "../../useSession";
import { downloadSheet, draftMapping, editRow, getMapping, type Layer, type MappingRow, type MappingView, type RowEdit, type RowStatus } from "./api";

const LAYERS: Layer[] = ["landing", "silver", "gold"];
const ARCHITECT = ["analyst", "company_admin"];
const EDITED = ["source_field", "transformation", "rule", "test"] as const;
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** /centre/build/:iid/mapping: Span's ETL mapping sheet; the architect corrects lines, anyone with access downloads it. */
export default function MappingPage() {
  const iid = useParams().iid ?? "";
  const roles = useSession().user?.roles ?? [];
  const canEdit = roles.some((r) => ARCHITECT.includes(r));
  const [view, setView] = useState<MappingView | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [layer, setLayer] = useState<Layer | "all">("all");
  const [status, setStatus] = useState<RowStatus | "all">("all");
  const [editing, setEditing] = useState<MappingRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "That did not work. Please try again.");
    }
    setBusy(false);
  }

  useEffect(() => {
    getMapping(iid)
      .then(setView, (err: unknown) => {
        if (!(err instanceof ApiError && err.status === 404)) setError(err instanceof ApiError ? err.message : "The sheet could not be read.");
      })
      .finally(() => setLoaded(true));
  }, [iid]);

  const sheet = view?.sheet ?? null;
  const rows = (sheet?.rows ?? []).filter((r) => (layer === "all" || r.layer === layer) && (status === "all" || r.status === status));
  const unclear = sheet?.rows.filter((r) => r.status === "unclear").length ?? 0;

  async function save(row: MappingRow) {
    const edit: RowEdit = { source_field: row.source_field, transformation: row.transformation, rule: row.rule, test: row.test, status: row.status };
    await act(async () => {
      const { row: saved } = await editRow(iid, row.n, edit);
      setView((v) => v && { ...v, sheet: { ...v.sheet, rows: v.sheet.rows.map((r) => (r.n === saved.n ? saved : r)) } });
      setEditing(null);
    });
  }

  return (
    <PageFrame title="Mapping sheet" subline="Span's ETL mapping from the signed intent of work, the scan and the pipeline contracts."
      actions={<>
        {canEdit && <Button onClick={() => act(async () => setView(await draftMapping(iid)))} disabled={busy}>{sheet ? "Ask Span to draft again" : "Ask Span to draft"}</Button>}
        {sheet && <Button variant="primary" disabled={busy} onClick={() => act(() => downloadSheet(iid, sheet.version))}>Download .xlsx</Button>}
      </>}>
      {error ? <p role="alert">{error}</p> : null}
      {!loaded ? <p className="ds-muted">Loading…</p> : !sheet ? (
        <EmptyState title="No mapping sheet yet" lines={["Span drafts one row per target field once the intent of work is signed."]} />
      ) : (
        <>
          <p className="ds-muted">
            Drafted by Span, the build agent{view?.drafted_at ? ` on ${view.drafted_at.slice(0, 16).replace("T", " ")}` : ""}. Version {sheet.version}:{" "}
            {sheet.rows.length} rows, {unclear} unclear.
          </p>
          {view?.fallback && view.message ? <p>{view.message}</p> : null}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "12px 0" }} aria-label="Filters">
            {(["all", ...LAYERS] as const).map((l) => (
              <Chip key={l} tone={layer === l ? "active" : "default"} onClick={() => setLayer(l)}>{l === "all" ? "All layers" : cap(l)}</Chip>
            ))}
            {(["all", "mapped", "unclear"] as const).map((s) => (
              <Chip key={s} tone={status === s ? "active" : "default"} onClick={() => setStatus(s)}>{s === "all" ? "Any status" : cap(s)}</Chip>
            ))}
          </div>
          {editing && (
            <form className="ds-card" style={{ display: "grid", gap: 8, padding: 16, marginBottom: 16 }}
              onSubmit={(e) => { e.preventDefault(); void save(editing); }}>
              <strong>Row {editing.n}: {editing.target_table}.{editing.target_field}</strong>
              {EDITED.map((k) => (
                <label key={k} style={{ display: "flex", flexDirection: "column", gap: 4 }}>{cap(k.replace("_", " "))}
                  <input value={editing[k]} maxLength={500} onChange={(e) => setEditing({ ...editing, [k]: e.target.value })} />
                </label>
              ))}
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Status
                <select value={editing.status} onChange={(e) => setEditing({ ...editing, status: e.target.value as RowStatus })}>
                  <option value="mapped">Mapped</option>
                  <option value="unclear">Unclear</option>
                </select>
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <Button type="submit" variant="primary" disabled={busy}>Save row</Button>
                <Button onClick={() => setEditing(null)}>Cancel</Button>
              </div>
            </form>
          )}
          {rows.length === 0 ? <p>No rows match these filters.</p> : (
            <DataTable
              columns={[{ key: "n", label: "No." }, { key: "layer", label: "Layer" }, { key: "target", label: "Target" }, { key: "source", label: "Source" },
                { key: "transformation", label: "Transformation" }, { key: "rule", label: "Rule" }, { key: "test", label: "Test" },
                { key: "status", label: "Status" }, ...(canEdit ? [{ key: "edit", label: "" }] : [])]}
              rows={rows.map((r) => ({
                n: r.n, layer: cap(r.layer), target: `${r.target_table}.${r.target_field}`,
                source: r.source_field ? `${r.source_table || r.source_id} · ${r.source_field}` : <span className="ds-muted">Not available yet</span>,
                transformation: r.transformation, rule: r.rule || "None", test: r.test,
                status: <Pill tone={r.status === "mapped" ? "ok" : "late"}>{cap(r.status)}</Pill>,
                edit: <Button onClick={() => setEditing(r)} disabled={busy} aria-label={`Edit row ${r.n}`}>Edit</Button>,
              }))}
            />
          )}
        </>
      )}
    </PageFrame>
  );
}
