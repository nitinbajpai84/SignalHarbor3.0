import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import { Button, PageFrame, Pill } from "../../design";
import { useSession } from "../../useSession";
import {
  approveProposal, getCatalogue, getProposal, listVersions, proposeColumn, proposeScript, proposeTable, rejectProposal,
  type Catalogue, type Version,
} from "./api";

// E0a: /centre/admin/model, the Admin "Data model" page: the approved model, tables by group, and changes waiting for the head of data.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const when = (at?: string | null) => (at ? at.slice(0, 16).replace("T", " ") : "");
const STATE: Record<Version["state"], string> = { proposed: "Waiting for a decision", approved: "In use", rejected: "Not accepted", superseded: "Replaced" };
const TONE = { proposed: "open", approved: "ok", rejected: "failed", superseded: "draft" } as const;

export default function AdminModel() {
  const [params, setParams] = useSearchParams();
  const roles = useSession().user?.roles ?? [];
  const canAct = roles.includes("analyst") || roles.includes("company_admin");
  const canDecide = roles.includes("head_of_data") || roles.includes("company_admin"); // ROLE1: the head of data decides; the data engineer reads and proposes
  const [cat, setCat] = useState<Catalogue | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [note, setNote] = useState("");
  const load = useCallback(() => Promise.all([getCatalogue(), listVersions()]).then(([c, v]) => { setCat(c); setVersions(v); }).catch((e) => setNote(plain(e))), []);
  useEffect(() => { void load(); }, [load]);
  const open = Number(params.get("proposal") || 0);
  const crumbs = <Link to="/centre/admin/agents">Agents and templates</Link>;
  const changes = versions.filter((v) => v.version > 1);

  return (
    <PageFrame title="Data model" crumbs={crumbs}
      subline="The tables and columns your company's data is stored in. Only an approved version is used by the agents and the data intake.">
      {note ? <p role="alert">{note}</p> : null}
      {open ? <ProposalPage n={open} canAct={canDecide} back={() => { setParams({}); void load(); }} /> : (
        <>
          <Panel title="The model in use" actions={cat ? <a href="/api/v1/model/script" target="_blank" rel="noreferrer">Open the script</a> : null}>
            {cat ? <p>Version {cat.version}. {cat.state === "approved" ? "Approved" : cat.state}{cat.approved_by ? ` by ${cat.approved_by}` : ""}{cat.approved_at ? ` on ${when(cat.approved_at)}` : ""}.</p> : <p>Loading the model.</p>}
          </Panel>
          {canAct ? <Propose onDone={(v) => { setParams({ proposal: String(v.version) }); void load(); }} tables={cat?.groups.flatMap((g) => g.tables.map((t) => t.name)) ?? []} /> : null}
          <Panel title="Changes">
            {changes.length === 0 ? <p>No changes have been proposed yet.</p> : (
              <ul>
                {changes.map((v) => (
                  <li key={v.version}>
                    <Pill tone={TONE[v.state]}>{STATE[v.state]}</Pill>{" "}
                    <Link to={`?proposal=${v.version}`}>{v.summary || `Change ${v.version}`}</Link> <small>proposed by {v.proposed_by}, {when(v.proposed_at)}</small>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          {cat?.layers ? (
            <Panel title="Three layers" eyebrow="Raw, trusted, and ready to use">
              <p><strong>Bronze</strong>: files as they arrived, one table for each kind of file.</p>
              {cat.layers.bronze.length === 0 ? <p>No files have been loaded yet.</p> : (
                <ul>{cat.layers.bronze.map((t) => <li key={t.name}>{t.name} <small>from {t.source}</small></li>)}</ul>
              )}
              <p><strong>Silver</strong>: the trusted data model below, {cat.layers.silver.tables} tables.</p>
              <p><strong>Gold</strong>: tables built for one project after its build plan is approved.</p>
              {cat.layers.gold.length === 0 ? <p>None yet.</p> : (
                <ul>{cat.layers.gold.map((t) => <li key={t.name}>{t.name} <small>for project {t.project_ids.join(", ")}</small></li>)}</ul>
              )}
            </Panel>
          ) : null}
          {cat?.groups.map((g) => (
            <Panel key={g.name} title={g.name.replace(/_/g, " ")}>
              {g.tables.map((t) => (
                <details key={t.name}>
                  <summary>{t.name.replace(/_/g, " ")} {t.layer === "company" ? <Pill tone="signed">Your company</Pill> : <Pill tone="draft">Core</Pill>}</summary>
                  {t.note ? <p>{t.note}</p> : null}
                  <table>
                    <thead><tr><th>Column</th><th>Holds</th><th>Required</th><th>Notes</th></tr></thead>
                    <tbody>
                      {t.columns.map((c) => (
                        <tr key={c.name}>
                          <td>{c.name}{c.layer === "company" && t.layer === "core" ? <> <Pill tone="signed">Added</Pill></> : null}</td>
                          <td>{c.type}</td><td>{c.null ? "No" : "Yes"}</td><td>{c.note}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              ))}
            </Panel>
          ))}
        </>
      )}
    </PageFrame>
  );
}

function Propose({ onDone, tables }: { onDone: (v: Version) => void; tables: string[] }) {
  const [msg, setMsg] = useState("");
  const [kind, setKind] = useState<"table" | "column">("table");
  const [table, setTable] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("text");
  const [optional, setOptional] = useState(true);
  const [about, setAbout] = useState("");
  const go = async (fn: () => Promise<Version>) => {
    setMsg("");
    try { onDone(await fn()); } catch (e) { setMsg(plain(e)); }
  };
  const upload = async (file: File | undefined) => { if (file) await go(async () => proposeScript(await file.text(), "")); };
  return (
    <Panel title="Propose a change" eyebrow="Your company's own tables">
      <p>You can add tables, or add columns to a table. Core tables and columns cannot be changed or removed. The head of data decides.</p>
      <p><label>Upload a script file <input type="file" accept=".dbml,.txt" onChange={(e) => void upload(e.target.files?.[0])} /></label></p>
      <p>Or describe one change:</p>
      <div role="group" aria-label="Kind of change">
        <label><input type="radio" checked={kind === "table"} onChange={() => setKind("table")} /> A new table</label>{" "}
        <label><input type="radio" checked={kind === "column"} onChange={() => setKind("column")} /> A new column on a table</label>
      </div>
      {kind === "column" ? (
        <p><label>Table <select value={table} onChange={(e) => setTable(e.target.value)}><option value="">Choose a table</option>{tables.map((t) => <option key={t}>{t}</option>)}</select></label></p>
      ) : null}
      <p><label>{kind === "table" ? "Table name (lowercase, with underscores)" : "Column name"} <input value={name} onChange={(e) => setName(e.target.value)} /></label></p>
      <p><label>{kind === "table" ? "What it holds" : "Note"} <input value={about} onChange={(e) => setAbout(e.target.value)} /></label></p>
      <p>
        <label>{kind === "table" ? "Type of its first column, label" : "Holds"} <select value={type} onChange={(e) => setType(e.target.value)}>
          {["text", "varchar(100)", "int", "numeric(18,4)", "date", "timestamptz", "boolean", "uuid"].map((t) => <option key={t}>{t}</option>)}
        </select></label>{" "}
        <label><input type="checkbox" checked={optional} onChange={(e) => setOptional(e.target.checked)} /> May be left empty</label>
      </p>
      <Button variant="primary" disabled={!name || (kind === "column" && !table)} onClick={() => void go(() => kind === "table"
        ? proposeTable(name, about, [{ name: "id", type: "uuid", null: false }, { name: "organization_id", type: "uuid", null: false }, { name: "label", type, null: optional }])
        : proposeColumn(table, { name, type, null: optional, note: about }))}>Send for approval</Button>
      {msg ? <p role="alert">{msg}</p> : null}
    </Panel>
  );
}

function ProposalPage({ n, canAct, back }: { n: number; canAct: boolean; back: () => void }) {
  const [v, setV] = useState<Version | null>(null);
  const [why, setWhy] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { getProposal(n).then(setV).catch((e) => setMsg(plain(e))); }, [n]);
  const act = async (fn: () => Promise<Version>) => { setMsg(""); try { setV(await fn()); } catch (e) { setMsg(plain(e)); } };
  if (!v) return <><p>{msg || "Loading the change."}</p><Button onClick={back}>Back to the data model</Button></>;
  return (
    <>
      <Panel title="What would change" actions={<Pill tone={TONE[v.state]}>{STATE[v.state]}</Pill>}>
        <p>Proposed by {v.proposed_by}, {when(v.proposed_at)}.</p>
        <ul>{(v.diff?.words ?? []).map((w) => <li key={w}>{w}</li>)}</ul>
        {v.breaking?.length ? <div role="alert"><strong>This would break existing sheet mappings:</strong><ul>{v.breaking.map((b) => <li key={b}>{b}</li>)}</ul></div> : null}
        <p><a href={`/api/v1/model/script?version=${v.version}`} target="_blank" rel="noreferrer">Open the script</a></p>
      </Panel>
      <Panel title="Trial on a copy of the warehouse">
        <p>{v.sandbox ? <><Pill tone={v.sandbox.ok ? "ok" : "failed"}>{v.sandbox.ok ? "Works" : "Fails"}</Pill> {v.sandbox.message}</> : "Not tried yet."}</p>
      </Panel>
      {v.state === "rejected" ? <p>Not accepted by {v.rejected_by}: {v.reason}</p> : null}
      {v.state === "approved" ? <p>Approved by {v.approved_by}, {when(v.approved_at)}.</p> : null}
      {v.state === "proposed" && canAct ? (
        <Panel title="Your decision">
          <p>Only the head of data can decide, and not on a change they proposed themselves.</p>
          <Button variant="primary" onClick={() => void act(() => approveProposal(n))}>Approve</Button>{" "}
          <label>Reason if not this <input value={why} onChange={(e) => setWhy(e.target.value)} /></label>{" "}
          <Button disabled={!why.trim()} onClick={() => void act(() => rejectProposal(n, why))}>Not this</Button>
        </Panel>
      ) : null}
      {v.state === "proposed" && !canAct ? <p className="ds-muted">The head of data decides on this change.</p> : null}
      {msg ? <p role="alert">{msg}</p> : null}
      <Button onClick={back}>Back to the data model</Button>
    </>
  );
}
