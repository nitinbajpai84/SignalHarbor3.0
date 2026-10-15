import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button, PageFrame, Pill } from "../../design";
import { acceptMapping, approveFund, editMapping, getFile, loadAllSheets, loadFile, profileFile, rejectMapping, STATE_NAMES, STATE_TONES, type FileDetail, type MappingEdit } from "./api";
import { plain, when } from "./IntakePage";

// E0c3: one file. Profile summary, mapping column by column (Accept / Not this for permitted people), control totals, load result.
export default function FilePage() {
  const { fileId = "" } = useParams();
  const [d, setD] = useState<FileDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [asking, setAsking] = useState(false);
  const [why, setWhy] = useState("");
  const [draft, setDraft] = useState<Record<string, MappingEdit>>({});
  const mapping = d?.mapping;
  useEffect(() => {  // the editable copy of the proposed lines
    setDraft(Object.fromEntries((mapping?.columns ?? []).map((c) => [c.source_column, {
      source: c.source_column, target: !c.target_table || c.target_table === "ignore" ? "ignore" : `${c.target_table}.${c.target_field}`,
      date_format: c.date_format ?? "", multiply: c.multiply ? String(c.multiply) : "", decimal: c.decimal ?? "" }])));
  }, [mapping]);
  const setLine = (src: string, patch: Partial<MappingEdit>) => setDraft((x) => ({ ...x, [src]: { ...x[src]!, ...patch } }));
  const refresh = useCallback(() => { getFile(fileId).then((x) => { setD(x); setError(""); }).catch((e) => setError(plain(e))); }, [fileId]);
  useEffect(() => { refresh(); }, [refresh]);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); refresh(); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  };

  if (!d) return <PageFrame title="Data intake">{error ? <p role="alert">{error}</p> : <p className="ds-muted" role="status">Loading the file.</p>}</PageFrame>;
  const m = d.mapping;
  const proposed = m?.state === "proposed";
  const editing = proposed && !!m?.can_edit;
  const need = d.needs_approval;
  const choose = need?.choose_portfolio ?? [];
  const save = () => editMapping(m!.id, Object.values(draft));
  return (
    <PageFrame title={d.name} subline={`${d.source_label || d.source_code} · received ${when(d.received_at)} · owner ${d.owner ?? "none yet"}`}
      actions={<Pill tone={STATE_TONES[d.state]}>{STATE_NAMES[d.state]}</Pill>}>
      <p><Link className="ds-link" to="/centre/data/intake">Back to all files</Link></p>
      {error ? <p role="alert">{error}</p> : null}

      <h2>What we read</h2>
      {d.profile ? (
        <dl>
          <dt>Sheet</dt><dd>{d.profile.sheet}</dd>
          <dt>Header row</dt><dd>{d.profile.header_row}</dd>
          <dt>Columns</dt><dd>{d.profile.columns.map((c) => c.name).join(", ")}</dd>
          <dt>Units</dt><dd>{d.profile.units ?? "Not stated"}</dd>
          <dt>Dates</dt><dd>{d.profile.date_format ?? "Not clear"}</dd>
        </dl>
      ) : <p className="ds-muted">Not read yet. {d.can_act ? <Button disabled={busy} onClick={() => void run(() => profileFile(d.id))}>Read this file</Button> : null}</p>}

      <h2>Mapping</h2>
      {m ? (
        <>
          <p>Version {m.version} · <Pill tone={m.state === "approved" ? "signed" : m.state === "proposed" ? "draft" : "restricted"}>{m.state === "approved" ? "Approved" : m.state === "proposed" ? "Proposed" : "Retired"}</Pill></p>
          <table className="ds-table" style={{ width: "100%" }}>
            <thead><tr><th>Source column</th><th>Goes to</th>{editing ? <><th>Date format</th><th>Multiply by</th><th>Decimal mark</th></> : <th>Transform</th>}</tr></thead>
            <tbody>{m.columns.map((c) => {
              const l = draft[c.source_column];
              return editing && l ? (
                <tr key={c.source_column}>
                  <td>{c.source_column}</td>
                  <td><input list="targets" aria-label={`Goes to for ${c.source_column}`} value={l.target} onChange={(e) => setLine(c.source_column, { target: e.target.value })} /></td>
                  <td><input aria-label={`Date format for ${c.source_column}`} placeholder="%Y-%m-%d" size={10} value={l.date_format ?? ""} onChange={(e) => setLine(c.source_column, { date_format: e.target.value })} /></td>
                  <td><input aria-label={`Multiply by for ${c.source_column}`} size={6} value={l.multiply ?? ""} onChange={(e) => setLine(c.source_column, { multiply: e.target.value })} /></td>
                  <td><select aria-label={`Decimal mark for ${c.source_column}`} value={l.decimal ?? ""} onChange={(e) => setLine(c.source_column, { decimal: e.target.value })}>
                    <option value="">Point (1,234.50)</option><option value=",">Comma (1.234,50)</option></select></td>
                </tr>
              ) : <tr key={c.source_column}><td>{c.source_column}</td><td>{c.target_table === "ignore" || !c.target_table ? "Ignored" : `${c.target_table}.${c.target_field}`}</td><td>{c.transform ?? "None"}</td></tr>;
            })}</tbody>
          </table>
          {editing ? <datalist id="targets">{(d.target_options ?? ["ignore"]).map((o) => <option key={o} value={o} />)}</datalist> : null}
          {editing ? <p className="ds-muted">Change a line if the proposal is wrong, then Accept. The corrected mapping is kept for the next file from this source.</p> : null}
          {editing && !m.can_decide ? <Button disabled={busy} onClick={() => void run(save)}>Save changes</Button> : null}
          {proposed && m.can_decide ? (
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
              {editing ? <Button disabled={busy} onClick={() => void run(save)}>Save changes</Button> : null}
              <Button variant="primary" disabled={busy} onClick={() => void run(async () => { if (editing) await save(); await acceptMapping(m.id); })}>Accept</Button>
              <Button disabled={busy} onClick={() => setAsking(!asking)}>Not this</Button>
              {asking ? (
                <>
                  <label>Why not? (optional) <input type="text" value={why} maxLength={300} onChange={(e) => setWhy(e.target.value)} /></label>
                  <Button disabled={busy} onClick={() => void run(async () => { await rejectMapping(m.id, why); setAsking(false); })}>Turn it down</Button>
                </>
              ) : null}
            </div>
          ) : proposed ? <p className="ds-muted">Waiting for the sheet owner or a data engineer to decide.</p> : null}
        </>
      ) : <p className="ds-muted">No mapping yet. The data agent proposes one once the file is read.</p>}

      {choose.length && m?.can_fix ? (
        <>
          <h2>Which portfolio?</h2>
          {choose.map((c) => (
            <p key={c.entity}>{c.entity} has more than one portfolio and the file does not say which. Use{" "}
              <select aria-label={`Portfolio for ${c.entity}`} defaultValue="" onChange={(e) => e.target.value && void run(() => editMapping(m.id, [], { "portfolios.portfolio_code": e.target.value }))}>
                <option value="">Choose one</option>{c.options.map((o) => <option key={o} value={o}>{o}</option>)}</select> for the whole file, then load it again.</p>))}
        </>
      ) : null}
      {m?.fixed && Object.keys(m.fixed).length ? <p className="ds-muted">Fixed for the whole file: {Object.entries(m.fixed).map(([k, v]) => `${k} = ${v}`).join(", ")}</p> : null}
      {need && (need.funds.length || need.portfolios.length) ? (
        <>
          <h2>Waiting for approval</h2>
          <p>These names were not approved yet, so their rows are held back. Approve them, then load the file again.</p>
          <ul>
            {need.funds.map((f) => (
              <li key={f.name}>Fund {f.name}{f.candidates.length ? ` (looks like ${f.candidates.join(", ")})` : ""}{" "}
                {f.identifier_id && need.can_approve ? <Button disabled={busy} onClick={() => void run(() => approveFund(f.identifier_id!))}>Approve {f.name}</Button>
                  : <span className="ds-muted">{f.identifier_id ? "Waiting for Operations or the data engineer." : "No matching fund in the data model; it needs adding to the master data."}</span>}</li>))}
            {need.portfolios.map((p) => <li key={p}>Portfolio {p}: not in the company's master data. Ask the head of data to add it.</li>)}
          </ul>
        </>
      ) : null}

      <h2>Control totals</h2>
      {d.control_totals.length ? (
        <table className="ds-table" style={{ width: "100%" }}>
          <thead><tr><th>Measure</th><th>In the file</th><th>Loaded</th><th>Passed</th></tr></thead>
          <tbody>{d.control_totals.map((t) => (
            <tr key={t.measure}><td>{t.measure}</td><td>{t.in_file}</td><td>{t.loaded}</td><td>{t.passed ? "Yes" : "No"}</td></tr>))}</tbody>
        </table>
      ) : <p className="ds-muted">Nothing to check until the file is loaded.</p>}

      <h2>Load</h2>
      {d.load_result ? (
        <>
          <p role="status">{d.load_result.message}</p>
          {d.load_result.held_back?.length ? <p>Held back until a person matches them: {d.load_result.held_back.join(", ")}.</p> : null}
        </>
      ) : <p className="ds-muted">Not loaded yet.</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {d.can_act && d.state !== "loaded" && (!m || m.state === "approved") ? <Button variant="primary" disabled={busy} onClick={() => void run(() => loadFile(d.id))}>{m ? "Load this file" : "Propose a mapping"}</Button> : null}
        {d.can_act && /\.(xlsx|xlsm)$/i.test(d.name) ? <Button disabled={busy} onClick={() => void run(() => loadAllSheets(d.id))}>Load every sheet</Button> : null}
      </div>
    </PageFrame>
  );
}
