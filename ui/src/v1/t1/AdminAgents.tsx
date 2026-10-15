import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import { Button, Chip, PageFrame, Pill } from "../../design";
import { useSession } from "../../useSession";
import {
  adoptTemplate, answerRequest, createTemplate, getGovernance, getLog, getTemplate, KIND_NAMES, listRequests, listSkills, listTemplates,
  resetSkill, retireTemplate, saveGovernance, saveSkill, saveTemplate,
  type AgentSkill, type Field, type Governance, type LogRow, type Req, type Template, type TemplateSummary,
} from "./api";

// T1: /centre/admin/agents, the company admin's console: Templates, Agent skills, Governance rules, Requests, and the change log.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const TYPES: Field["type"][] = ["text", "long_text", "list", "table", "number", "date", "person", "choice"];
const TABS = ["Templates", "Agent skills", "Governance rules", "Requests", "Change log"] as const;
type Tab = (typeof TABS)[number];
const when = (at: string | null) => (at ? at.slice(0, 16).replace("T", " ") : "");
type Act = (fn: () => Promise<unknown>, done: string, keep?: string) => Promise<void>;

export default function AdminAgents() {
  const roles = useSession().user?.roles ?? [];
  const [tab, setTab] = useState<Tab>("Templates");
  if (!roles.includes("company_admin")) {
    return <PageFrame title="Agents and templates"><p role="alert">Only your company admin can open this page.</p></PageFrame>;
  }
  return (
    <PageFrame title="Agents and templates" actions={<Link to="/centre/admin/model">Data model</Link>} subline="Choose the templates your company works to, tune what each agent knows about you, and set the rules every design follows.">
      <div role="tablist" aria-label="Sections" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        {TABS.map((t) => <Chip key={t} tone={t === tab ? "active" : "default"} onClick={() => setTab(t)}>{t}</Chip>)}
      </div>
      {tab === "Templates" ? <Templates /> : tab === "Agent skills" ? <Skills /> : tab === "Governance rules" ? <Rules />
        : tab === "Requests" ? <Requests /> : <ChangeLog />}
    </PageFrame>
  );
}

// ---- templates ----------------------------------------------------------------------------------------------------------------

function Templates() {
  const [rows, setRows] = useState<TemplateSummary[]>([]);
  const [open, setOpen] = useState<Template | null>(null);
  const [note, setNote] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("intent_of_work");

  const load = useCallback(() => listTemplates("", true).then(setRows).catch((e) => setNote(plain(e))), []);
  useEffect(() => { void load(); }, [load]);
  const act: Act = async (fn, done, keep) => {
    setNote("");
    try { await fn(); setNote(done); await load(); if (keep) setOpen(await getTemplate(keep)); } catch (e) { setNote(plain(e)); }
  };
  const made = async (body: Parameters<typeof createTemplate>[0]) => { const m = await createTemplate(body); setOpen(await getTemplate(m.id)); };

  return (
    <>
      <Panel title="Templates">
        {note ? <p role="status">{note}</p> : null}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
          <input className="ds-input" aria-label="Name for a new template" placeholder="Name for a new template or copy" value={name} onChange={(e) => setName(e.target.value)} />
          <select className="ds-input" aria-label="Document" value={kind} onChange={(e) => setKind(e.target.value)}>
            {Object.entries(KIND_NAMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <Button disabled={!name.trim()} onClick={() => act(() => made({ kind, name }), "Draft created.")}>New template</Button>
        </div>
        {Object.entries(KIND_NAMES).map(([k, label]) => (
          <div key={k} style={{ margin: "8px 0" }}>
            <strong>{label}</strong>
            {rows.filter((r) => r.kind === k).map((r) => (
              <div key={r.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: "4px 0" }}>
                <Button onClick={() => getTemplate(r.id).then(setOpen).catch((e) => setNote(plain(e)))}>{r.name}</Button>
                <Pill tone={r.state === "adopted" ? "signed" : r.state === "retired" ? "late" : "draft"}>{r.state}</Pill>
                <span className="ds-muted">version {r.version}{r.standard ? ", the company's standard" : ""}{r.unadopted_changes ? ", changes not adopted yet" : ""}</span>
                <Button disabled={!name.trim()} onClick={() => act(() => made({ from_id: r.id, name }), "Draft created.")}>Create from this</Button>
              </div>
            ))}
          </div>
        ))}
      </Panel>
      {open ? <Editor key={`${open.id}-${open.version}-${open.unadopted_changes}`} t={open} act={act} /> : null}
    </>
  );
}

function Editor({ t, act }: { t: Template; act: Act }) {
  const [title, setTitle] = useState(t.name);
  const [desc, setDesc] = useState(t.description);
  const [fields, setFields] = useState<Field[]>(t.fields);
  const [preview, setPreview] = useState(false);
  const set = (i: number, patch: Partial<Field>) => setFields((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  const add = () => setFields((fs) => [...fs, { key: `field_${fs.length + 1}`, label: "New field", help: "", required: false, type: "text" }]);
  const save = () => act(() => saveTemplate(t.id, { name: title, description: desc, fields }), "Saved. Adopt it to make it the version people see.", t.id);
  return (
    <Panel title={`Edit: ${t.name}`} actions={<span className="ds-muted">{KIND_NAMES[t.kind]}, version {t.version}</span>}>
      <label>Name <input className="ds-input" value={title} onChange={(e) => setTitle(e.target.value)} /></label>{" "}
      <label>Description <input className="ds-input" value={desc} onChange={(e) => setDesc(e.target.value)} style={{ minWidth: 280 }} /></label>
      {fields.map((f, i) => (
        <div key={i} style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", margin: "6px 0" }}>
          <input className="ds-input" aria-label={`Label of field ${i + 1}`} value={f.label} onChange={(e) => set(i, { label: e.target.value })} />
          <input className="ds-input" aria-label={`Key of field ${i + 1}`} value={f.key} onChange={(e) => set(i, { key: e.target.value })} style={{ width: 110 }} />
          <select className="ds-input" aria-label={`Type of field ${i + 1}`} value={f.type} onChange={(e) => set(i, { type: e.target.value as Field["type"] })}>
            {TYPES.map((x) => <option key={x}>{x}</option>)}
          </select>
          <label><input type="checkbox" checked={f.required} onChange={(e) => set(i, { required: e.target.checked })} /> Must fill</label>
          <input className="ds-input" aria-label={`Help for field ${i + 1}`} placeholder="Help text" value={f.help} onChange={(e) => set(i, { help: e.target.value })} style={{ flex: "1 1 200px" }} />
          <Button onClick={() => setFields((fs) => fs.filter((_, j) => j !== i))}>Remove</Button>
        </div>
      ))}
      <p className="ds-muted">Every template ends with “{t.free_text.label}”.</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button onClick={add}>Add a field</Button>
        <Button variant="primary" onClick={save}>Save</Button>
        <Button onClick={() => setPreview(!preview)}>{preview ? "Hide preview" : "Preview as a person sees it"}</Button>
        <Button onClick={() => act(() => adoptTemplate(t.id), "Adopted: a new version.", t.id)} disabled={t.state === "retired"}>Adopt</Button>
        <Button onClick={() => act(() => adoptTemplate(t.id, true), "Adopted as the company's standard.", t.id)} disabled={t.state === "retired"}>Adopt as standard</Button>
        <Button onClick={() => act(() => retireTemplate(t.id), "Retired. Documents already started keep their version.", t.id)} disabled={t.state === "retired"}>Retire</Button>
      </div>
      {preview ? (
        <div aria-label="Preview">
          <h3>What North will ask you</h3>
          <ol>{fields.filter((f) => f.required).map((f) => <li key={f.key}>{f.label}{f.help ? <span className="ds-muted"> ({f.help})</span> : null}</li>)}</ol>
          <p className="ds-muted">If there is time:</p>
          <ul>{fields.filter((f) => !f.required).map((f) => <li key={f.key}>{f.label}</li>)}<li>{t.free_text.label}</li></ul>
        </div>
      ) : null}
    </Panel>
  );
}

// ---- agent skills -------------------------------------------------------------------------------------------------------------

function Skills() {
  const [all, setAll] = useState<AgentSkill[]>([]);
  const [agent, setAgent] = useState("");
  const [file, setFile] = useState("");
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const load = useCallback(() => listSkills().then((a) => { setAll(a); return a; }).catch((e) => { setNote(plain(e)); return [] as AgentSkill[]; }), []);
  useEffect(() => { void load(); }, [load]);
  const f = all.find((a) => a.agent === agent)?.files.find((x) => x.name === file);
  const pick = (a: string, name: string, body: string) => { setAgent(a); setFile(name); setText(body); setNote(""); };
  const after = async (done: string) => {
    const fresh = await load();
    const nf = fresh.find((x) => x.agent === agent)?.files.find((x) => x.name === file);
    if (nf) setText(nf.text);
    setNote(done);
  };
  return (
    <Panel title="Agent skills">
      <p className="ds-muted">A file you change here is your company's copy and is used instead of the standard one; “Back to the standard” removes it.</p>
      {all.map((a) => (
        <div key={a.agent} style={{ margin: "6px 0", display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <strong>{a.label}</strong>
          {a.files.map((x) => (
            <Chip key={x.name} tone={a.agent === agent && x.name === file ? "active" : "default"} onClick={() => pick(a.agent, x.name, x.text)}>
              {x.name}{x.source === "company" ? " (your copy)" : ""}
            </Chip>
          ))}
        </div>
      ))}
      {f ? (
        <>
          <textarea className="ds-input" aria-label={`${agent} ${file}`} rows={14} value={text} onChange={(e) => setText(e.target.value)} style={{ width: "100%" }} />
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="primary" onClick={() => saveSkill(agent, file, text).then(() => after("Saved as your company's copy.")).catch((e) => setNote(plain(e)))}>Save</Button>
            <Button disabled={f.source !== "company"} onClick={() => resetSkill(agent, file).then(() => after("Back to the standard.")).catch((e) => setNote(plain(e)))}>Back to the standard</Button>
          </div>
        </>
      ) : null}
      {note ? <p role="status">{note}</p> : null}
    </Panel>
  );
}

// ---- governance rules ---------------------------------------------------------------------------------------------------------

function Rules() {
  const [g, setG] = useState<Governance | null>(null);
  const [rules, setRules] = useState<Governance["rules"]>([]);
  const [note, setNote] = useState("");
  useEffect(() => { getGovernance().then((x) => { setG(x); setRules(x.rules); }).catch((e) => setNote(plain(e))); }, []);
  const set = (i: number, patch: Partial<Governance["rules"][number]>) => setRules((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <Panel title="Governance rules" actions={g ? <span className="ds-muted">version {g.version}{g.by ? `, by ${g.by}` : ""}</span> : null}>
      <p className="ds-muted">Plain sentences, each with an owner. The architect builds every design to follow them.</p>
      {rules.map((r, i) => (
        <div key={i} style={{ display: "flex", gap: 6, margin: "6px 0", flexWrap: "wrap" }}>
          <input className="ds-input" aria-label={`Rule ${i + 1}`} value={r.rule} onChange={(e) => set(i, { rule: e.target.value })} style={{ flex: "1 1 360px" }} />
          <input className="ds-input" aria-label={`Owner of rule ${i + 1}`} placeholder="Owner" value={r.owner} onChange={(e) => set(i, { owner: e.target.value })} />
          <Button onClick={() => setRules((rs) => rs.filter((_, j) => j !== i))}>Remove</Button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8 }}>
        <Button onClick={() => setRules((rs) => [...rs, { rule: "", owner: "" }])}>Add a rule</Button>
        <Button variant="primary" onClick={() => saveGovernance(rules).then((x) => { setG(x); setRules(x.rules); setNote("Saved as a new version."); }).catch((e) => setNote(plain(e)))}>Save</Button>
      </div>
      {note ? <p role="status">{note}</p> : null}
    </Panel>
  );
}

// ---- requests and the change log ----------------------------------------------------------------------------------------------

function Requests() {
  const [rows, setRows] = useState<Req[]>([]);
  const [note, setNote] = useState("");
  const load = useCallback(() => listRequests().then(setRows).catch((e) => setNote(plain(e))), []);
  useEffect(() => { void load(); }, [load]);
  const answer = (id: string, state: Req["state"]) => answerRequest(id, state).then(load).catch((e) => setNote(plain(e)));
  return (
    <Panel title="Requests">
      {note ? <p role="alert">{note}</p> : null}
      {rows.length ? rows.map((r) => (
        <div key={r.id} style={{ margin: "8px 0" }}>
          <strong>{r.id}</strong> <Pill tone={r.state === "open" ? "open" : r.state === "done" ? "signed" : "late"}>{r.state}</Pill>{" "}
          <span className="ds-muted">{r.by}, {when(r.at)}{r.about ? `, about ${r.about}` : ""}</span>
          <div>{r.text}</div>
          {r.state === "open" ? (
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              <Button onClick={() => answer(r.id, "done")}>Mark done</Button><Button onClick={() => answer(r.id, "declined")}>Decline</Button>
            </div>
          ) : null}
        </div>
      )) : <p className="ds-muted">No requests. People ask from the Intent Centre welcome page.</p>}
    </Panel>
  );
}

function ChangeLog() {
  const [rows, setRows] = useState<LogRow[]>([]);
  useEffect(() => { getLog().then(setRows).catch(() => undefined); }, []);
  return (
    <Panel title="Change log">
      {rows.length ? <ul>{rows.map((r, i) => <li key={i}>{when(r.at)}: {r.by} {r.what}{r.ref ? ` (${r.ref})` : ""}{r.note ? `, ${r.note}` : ""}</li>)}</ul>
        : <p className="ds-muted">Nothing has been changed yet.</p>}
    </Panel>
  );
}
