import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError, apiGet, apiSend, Refused } from "../api/client";
import { Button, EmptyState, PageFrame, Pill, SideCard, type PillTone } from "../design";
import { c } from "./contextCopy";

// The Company context page: upload documents the agents can read as background,
// and accept or reject Lens's suggestions about what to remember. Agents are named with their role.

const AGENTS: { slug: string; label: string; hint: string }[] = [
  { slug: "north", label: "North, the industry expert", hint: "investment policy, capital call schedule, manager list" },
  { slug: "lens", label: "Lens, the business analyst", hint: "glossary, definitions, reported figures, process documents" },
];
const FIRST = "north";
const TONE: Record<string, PillTone> = { ready: "ok" };

interface Doc {
  doc_id: string;
  title: string;
  filename: string;
  status: string;
  visibility: string;
  restricted?: boolean;
  shared_summary: string | null;
  uploaded_at: string;
}

interface DocList {
  documents: Doc[];
  accepted: string[];
  max_mb: number;
  admin?: boolean;
}

interface Pending {
  pending_id: number;
  kind: string;
  subject: string;
  content: string;
}

type StateName = "loading" | "empty" | "error" | "refused" | "populated";

const path = (agent: string) => `/api/agents/${encodeURIComponent(agent)}`;
const when = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
};
const say = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : c.failed);

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",", 2)[1] ?? "");
    r.onerror = () => reject(new Error("unreadable"));
    r.readAsDataURL(file);
  });
}

function Notice({ state, message, onRetry }: { state: StateName; message?: string; onRetry: () => void }) {
  if (state === "populated") return null;
  if (state === "loading") return <p role="status" className="ds-muted">Loading…</p>;
  if (state === "empty") return <EmptyState title={c.listTitle} lines={[message ?? c.empty]} />;
  return (
    <div className="ds-card ds-side">
      <p role="alert" className="ds-warn">{message ?? "That did not work."}</p>
      {state === "error" && <div><Button onClick={onRetry}>Try again</Button></div>}
    </div>
  );
}

function SummaryCell({ doc, agent, onDone }: { doc: Doc; agent: string; onDone: (msg: string) => void }) {
  const [text, setText] = useState(doc.shared_summary ?? "");
  const [busy, setBusy] = useState(false);
  const publish = async () => {
    setBusy(true);
    try {
      await apiSend("POST", `${path(agent)}/docs/${doc.doc_id}/publish-summary`, { summary: text });
      onDone(c.published);
    } catch (e) {
      onDone(say(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
      <input className="ds-input" style={{ flex: 1, fontSize: 12 }} type="text" aria-label={c.summaryLabel(doc.title)} placeholder={c.summaryHint} value={text} onChange={(e) => setText(e.target.value)} />
      <Button disabled={busy} onClick={publish}>{c.publish}</Button>
    </div>
  );
}

function PendingList({ agent, onDone }: { agent: string; onDone: (msg: string) => void }) {
  const [rows, setRows] = useState<Pending[] | null>(null);
  const load = useCallback(() => {
    apiGet<{ pending: Pending[] }>(`${path(agent)}/pending-memories`)
      .then((r) => setRows(r.pending))
      .catch(() => setRows([]));
  }, [agent]);
  useEffect(load, [load]);

  const decide = async (p: Pending, decision: "accept" | "reject") => {
    try {
      await apiSend("POST", `${path(agent)}/pending-memories/${p.pending_id}/decide`, { decision });
      load();
      onDone(decision === "accept" ? "Saved." : "Declined.");
    } catch (e) {
      onDone(say(e));
    }
  };

  if (rows === null) return <p className="ds-muted">Loading…</p>;
  if (rows.length === 0) return <p className="ds-muted">{c.pendingEmpty}</p>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {rows.map((p) => (
        <div key={p.pending_id} className="ds-card">
          <div style={{ marginBottom: 8 }}>
            <strong>{p.subject}</strong>
            <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
              <Pill tone="draft">{c.suggestion}</Pill>
              <Pill tone="draft">{p.kind}</Pill>
            </div>
          </div>
          <p className="ds-muted" style={{ marginBottom: 8 }}>{p.content}</p>
          <div style={{ display: "flex", gap: 8 }}>
            <Button variant="primary" onClick={() => decide(p, "accept")}>{c.accept}</Button>
            <Button onClick={() => decide(p, "reject")}>{c.reject}</Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function UploadForm({ agent, data, onDone }: { agent: string; data: DocList | undefined; onDone: (msg: string) => void }) {
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [vis, setVis] = useState("private");
  const [restricted, setRestricted] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return onDone(c.chooseFile);
    if (data && file.size > data.max_mb * 1024 * 1024) return onDone(c.tooBig(data.max_mb));
    setBusy(true);
    try {
      const content = await readBase64(file);
      await apiSend("POST", `${path(agent)}/docs`, { filename: file.name, title, description: desc, visibility: vis, restricted, data: content });
      setTitle("");
      setDesc("");
      if (fileRef.current) fileRef.current.value = "";
      onDone(c.uploaded(file.name));
    } catch (e) {
      onDone(e instanceof Error && e.message === "unreadable" ? c.unreadable : say(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ds-card">
      <strong style={{ display: "block", marginBottom: 16 }}>{c.uploadTitle}</strong>
      <form style={{ display: "flex", flexDirection: "column", gap: 12 }} onSubmit={submit}>
        <label>
          <span className="ds-muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{c.agent}</span>
          <select className="ds-input" value={agent} onChange={(e) => { /* controlled by parent */ }}>
            {AGENTS.map((a) => (
              <option key={a.slug} value={a.slug}>{a.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="ds-muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{c.docTitle}</span>
          <input className="ds-input" type="text" placeholder={c.docTitleHint} value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          <span className="ds-muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{c.description}</span>
          <input className="ds-input" type="text" placeholder={c.descriptionHint} value={desc} onChange={(e) => setDesc(e.target.value)} />
        </label>
        <label>
          <span className="ds-muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{c.visibility}</span>
          <select className="ds-input" value={vis} onChange={(e) => setVis(e.target.value)}>
            <option value="private">{c.private}</option>
            <option value="shared">{c.shared}</option>
            <option value="shared_full">{c.sharedFull}</option>
          </select>
        </label>
        {vis !== "shared_full" && <p className="ds-muted" style={{ fontSize: 12, margin: "0 0 8px" }}>{c.visibilityHint(agent)}</p>}
        <label style={{ display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
          <input type="checkbox" checked={restricted} onChange={(e) => setRestricted(e.target.checked)} />
          <span className="ds-muted" style={{ fontSize: 12 }}>{c.restricted}</span>
        </label>
        <label>
          <span className="ds-muted" style={{ fontSize: 12, display: "block", marginBottom: 4 }}>{c.file}</span>
          <input className="ds-input" type="file" ref={fileRef} />
        </label>
        <p className="ds-muted" style={{ fontSize: 12, margin: 0 }}>{c.uploadHint(AGENTS.find((a) => a.slug === agent)?.hint ?? "")}</p>
        {data ? <p className="ds-muted" style={{ fontSize: 12, margin: 0 }}>{c.accepted(data.accepted, data.max_mb)}</p> : null}
        <div>
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? c.uploading : c.upload}
          </Button>
        </div>
      </form>
    </div>
  );
}

export default function ContextPage() {
  const [agent, setAgent] = useState(FIRST);
  const [state, setState] = useState<StateName>("loading");
  const [data, setData] = useState<Record<string, DocList> | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [note, setNote] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    let live = true;
    setState("loading");
    Promise.all(AGENTS.map((a) => apiGet<DocList>(`${path(a.slug)}/docs`)))
      .then((all) => {
        if (!live) return;
        setData(Object.fromEntries(AGENTS.map((a, i) => [a.slug, all[i]])) as Record<string, DocList>);
        setState(all.every((d) => d.documents.length === 0) ? "empty" : "populated");
        setIsAdmin(all[0]?.admin ?? false);
      })
      .catch((e: unknown) => live && setState(e instanceof Refused ? "refused" : "error"));
    return () => {
      live = false;
    };
  }, [attempt]);

  const reload = useCallback(() => {
    setAttempt((a) => a + 1);
    setNote("");
  }, []);

  const done = (msg: string) => {
    setNote(msg);
    setTimeout(() => reload(), 500);
  };

  return (
    <div className="ds-screen">
      <PageFrame title={c.title} subline={c.sub}>
        <Notice state={state} message={state === "refused" ? c.noAccess : state === "empty" ? c.empty : undefined} onRetry={reload} />

        {isAdmin && state !== "empty" && state !== "error" && state !== "refused" && (
          <UploadForm agent={agent} data={data?.[agent]} onDone={done} />
        )}

        {note ? <p role="status" className="ds-muted">{note}</p> : null}

        {state === "populated" || state === "empty" ? (
          <>
            {!isAdmin && <p className="ds-muted">{c.adminOnly}</p>}
            {AGENTS.map((ag) => (
              <div key={ag.slug}>
                <h2 style={{ marginTop: 32, marginBottom: 16, fontSize: 18 }}>{ag.label}</h2>
                {(data?.[ag.slug]?.documents ?? []).length === 0 ? (
                  <p className="ds-muted">{c.emptyAgent}</p>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    {(data?.[ag.slug]?.documents ?? []).map((d) => (
                      <div key={d.doc_id} className="ds-card">
                        <div style={{ marginBottom: 8 }}>
                          <strong>{d.title}</strong>
                          <div style={{ display: "flex", gap: 6, marginTop: 4, alignItems: "center" }}>
                            <Pill tone={TONE[d.status] ?? "draft"}>{d.status === "ready" ? c.ready : d.status}</Pill>
                            <span className="ds-muted" style={{ fontSize: 12 }}>
                              {c.visibilityName[d.visibility] ?? d.visibility}
                              {d.restricted ? `, ${c.restrictedName}` : ""}
                            </span>
                          </div>
                        </div>
                        <p className="ds-muted" style={{ fontSize: 12, margin: "8px 0" }}>{d.filename}</p>
                        <p className="ds-muted" style={{ fontSize: 11, margin: "4px 0" }}>Uploaded {when(d.uploaded_at)}</p>

                        {isAdmin && (
                          <div style={{ marginTop: 12 }}>
                            {d.shared_summary === null && (
                              <>
                                <p className="ds-muted" style={{ fontSize: 12, marginBottom: 8 }}>{c.summaryLabel(d.title)}</p>
                                <SummaryCell doc={d} agent={ag.slug} onDone={done} />
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </>
        ) : null}

        {isAdmin && (state === "populated" || state === "empty") && (
          <div style={{ marginTop: 40 }}>
            <h2 style={{ marginBottom: 16, fontSize: 18 }}>{c.pendingTitle}</h2>
            <div className="ds-card">
              <strong style={{ display: "block", marginBottom: 12, fontSize: 14 }}>{c.pendingEyebrow}</strong>
              <PendingList agent={agent} onDone={done} />
            </div>
          </div>
        )}
      </PageFrame>
    </div>
  );
}
