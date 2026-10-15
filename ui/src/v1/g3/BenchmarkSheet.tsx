import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Pill } from "../../design";
import { readBase64, uploadItem } from "../c4/api";
import { exportSheet, getChecks, getSheet, readReport, setFigure, signSheet, type Check, type SheetRow, type SheetView } from "./api";

// G3: the benchmark sheet inside the project's artefact view: one column per dimension, then reported, expected, tolerance, source, stated by.
const said = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not work. Please try again.");
const num = (n: number | null | undefined) => (n === null || n === undefined ? "" : String(n));

function result(r: SheetRow, checks: Check[]) {
  const c = checks.find((x) => x.row_id === r.id) ?? checks.find((x) => !x.row_id && x.code === r.code && x.period === r.dims?.period);
  if (!c) return <span className="ds-muted">Not loaded yet</span>;
  if (c.met === null) return <Pill tone="draft">Not compared</Pill>;
  const got = c.got === null ? `no figure in the loaded data${c.why ? ` (${c.why})` : ""}` : String(c.got);
  return <><Pill tone={c.met ? "ok" : "failed"}>{c.met ? "Met" : "Missed"}</Pill> <span className="ds-muted">expected {num(c.expected)}, got {got}</span></>;
}

function Figure({ iid, r, done }: { iid: string; r: SheetRow; done: () => void }) {
  const [v, setV] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <form style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }} onSubmit={(e) => {
      e.preventDefault();
      if (v.trim()) setFigure(iid, r.id, v.trim()).then(done).catch((x: unknown) => setProblem(said(x)));
    }}>
      <input className="ds-input" aria-label={`Reported figure for ${r.kpi ?? r.code}`} value={v} onChange={(e) => setV(e.target.value)} style={{ width: "9em" }} />
      <Button type="submit" disabled={!v.trim()}>Save figure</Button>
      {problem ? <span role="alert" className="ds-muted">{problem}</span> : null}
    </form>
  );
}

// "Drop last month's report": the file goes into the library first (K1 decides who may read it), then the sheet reads it.
function DropReport({ iid, done }: { iid: string; done: () => void }) {
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pick = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setProblem(null);
    try {
      const data = await readBase64(file);
      let got = await uploadItem({ name: file.name, data, iid });
      if ("similar" in got) got = await uploadItem({ name: file.name, data, iid, force: true });
      const id = "item" in got ? got.item.id : "duplicate" in got ? got.duplicate.id : "";
      if (!id) throw new Error("upload");
      const r = await readReport(iid, { item_id: id });
      setProblem(r.read ? null : "No figures were found in that file.");
      done();
    } catch (e) { setProblem(said(e)); } finally { setBusy(false); }
  };
  return (
    <label style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
      <span>Drop last month&apos;s report</span>
      <input type="file" aria-label="Drop last month's report" disabled={busy} onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ""; }} />
      {problem ? <span role="alert" className="ds-warn">{problem}</span> : null}
    </label>
  );
}

export default function BenchmarkSheet({ iid, pid }: { iid: string; pid: string }) {
  const [view, setView] = useState<SheetView | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [refusal, setRefusal] = useState<string | null>(null);
  const [gone, setGone] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((a) => a + 1), []);

  useEffect(() => {
    let live = true;
    getSheet(iid).then((v) => { if (live) { setView(v); setGone(false); } }).catch(() => { if (live) setGone(true); });
    getChecks(iid).then((c) => { if (live) setChecks(c); }).catch(() => undefined);  // no check yet is not an error
    return () => { live = false; };
  }, [iid, attempt]);

  if (gone) return <p className="ds-muted">The benchmark sheet could not be opened. Please try again.</p>;
  if (!view) return <p className="ds-muted">Opening the benchmark sheet…</p>;
  const rows = view.sheet.rows.filter((r) => !r.dropped);
  const dims = view.columns;
  const signed = view.sheet.state === "signed";
  return (
    <section className="ds-card" style={{ padding: 16, marginBottom: 12 }} aria-label="Benchmark figures">
      <p style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: "0 0 8px" }}>
        <strong>Benchmark sheet</strong> <Pill tone={signed ? "signed" : "draft"}>{signed ? "Signed" : "Draft"}</Pill>
        <span className="ds-muted">Version {view.sheet.version}</span>
        <Button onClick={() => void exportSheet(pid)}>Download .xlsx</Button>
        {!signed ? <DropReport iid={iid} done={reload} /> : null}
        {!signed ? <Button variant="primary" onClick={() => signSheet(iid).then(() => { setRefusal(null); reload(); }).catch((e: unknown) => setRefusal(said(e)))}>Sign the sheet</Button> : null}
      </p>
      {refusal ? <p role="alert" className="ds-warn">{refusal}</p> : null}
      {view.required.length ? <p className="ds-muted" style={{ margin: "0 0 8px" }}>Signed by {view.required.join(" and ")}.</p> : null}
      {rows.length === 0 ? <p className="ds-muted">No rows yet. Tell North which figures you report today and by what.</p> : (
        <div style={{ overflowX: "auto" }}>
          <table className="ds-table" style={{ width: "100%" }}>
            <thead><tr>
              <th scope="col">KPI</th>{dims.map((d) => <th key={d} scope="col">{d}</th>)}
              <th scope="col">Reported</th><th scope="col">Expected</th><th scope="col">Tolerance</th><th scope="col">Source</th><th scope="col">Stated by</th><th scope="col">After the load</th>
            </tr></thead>
            <tbody>{rows.map((r) => {
              const need = r.reported === null || r.status === "needs figure";
              return (
                <tr key={r.id} aria-label={`${r.kpi ?? r.code} row`} style={need ? { background: "var(--ds-highlight, rgba(255, 196, 0, 0.15))" } : undefined}>
                  <td>{r.kpi ?? r.code}{r.proposed ? <> <Pill tone="draft">Proposed</Pill></> : null}</td>
                  {dims.map((d) => <td key={d}>{r.dims?.[d] ?? ""}</td>)}
                  <td>{need ? <><Pill tone="late">needs figure</Pill><p style={{ margin: "4px 0" }}>No figure yet for {[r.kpi ?? r.code, ...Object.values(r.dims ?? {})].join(", ")}. Type it here or drop last month&apos;s report in.</p>
                    {signed ? null : <Figure iid={iid} r={r} done={reload} />}</> : num(r.reported)}</td>
                  <td>{num(r.expected)}</td><td>{num(r.tolerance)}</td>
                  <td>{r.source_doc ? <Link className="ds-link" to={`/centre/build/${encodeURIComponent(iid)}/source?file=${encodeURIComponent(r.source_doc)}&line=${r.line ?? ""}`}>{r.source_doc.split("/").pop()}, line {r.line}</Link> : r.source ?? ""}</td>
                  <td>{r.stated_by ?? ""}</td>
                  <td>{result(r, checks)}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}
