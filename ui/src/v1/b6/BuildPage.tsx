import { useProjectTitle } from "../s1/useProjectTitle";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import { Button, PageFrame, Pill } from "../../design";
import { useSession } from "../../useSession";
import { Composer } from "../voice";
import Workbench, { type Doc } from "../workbench/Workbench";
import * as api from "./api";
import ModeLine from "../router/ModeLine";
import UsedLine from "../teach/UsedLine";
import type { Used } from "../teach/api";
import { ProjectRooms } from "../b8/RoomSwitcher";
import { readBase64 } from "../i6/api";
import { Approval, Rooms, Diagram, ModelChanges, Pipeline, Sources, Tables } from "./Steps";

// B1: /centre/build/p/:projectId. Span on the left (the workbench), six documents on the right, each with its state in words.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const when = (at: string) => { const d = new Date(at); return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }); };

export default function BuildPage() {
  const { projectId = "" } = useParams();
  const projectTitle = useProjectTitle(projectId);
  const roles = useSession().user?.roles ?? [];
  const subline = roles.some((r) => r === "analyst" || r === "admin") ? "Check Span's plan, then approve it." : "The data team is building this. You will be told when it is live.";
  const [plan, setPlan] = useState<api.Plan | api.NoPlan | null>(null);
  const [pending, setPending] = useState<api.Pending[]>([]);
  const [runs, setRuns] = useState<api.Run[]>([]);
  const [chat, setChat] = useState<api.Turn[]>([]);
  const [used, setUsed] = useState<Used[]>([]);
  const [failed, setFailed] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const end = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      setPlan(await api.getPlan(projectId)); setFailed("");
      api.getRuns(projectId).then((r) => setRuns(r.runs)).catch(() => undefined);
      api.getChat(projectId).then((c) => { setChat(c.turns); setPending(c.pending ?? []); }).catch(() => undefined);
    } catch (e) { setFailed(plain(e)); }
  }, [projectId]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [chat, busy]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await fn(); await load(); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  };
  const talk = (said: string, up: File[]) => { // files are stored first (kept for this project, as North's), then named in the turn
    if (!said && !up.length) return;
    void act(async () => {
      for (const f of up) await api.sendChatFile(projectId, f.name, await readBase64(f));
      const c = await api.sendChat(projectId, said, up.map((f) => f.name));
      setChat(c.turns); setUsed(c.used ?? []); setPending(c.pending ?? []); setText(""); setFiles([]);
    });
  };

  if (failed) return <PageFrame title="Build Centre"><p role="alert">{failed} <Button onClick={() => void load()}>Try again</Button></p></PageFrame>;
  const studio = <> · <Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(projectId)}/studio`}>Dashboard studio</Link></>;
  if (!plan) return <PageFrame title="Build Centre"><p className="ds-muted" role="status">Opening the project.</p></PageFrame>;

  const pendingList = pending.filter((c) => c.status === "pending");
  const changes = pendingList.length ? (
    <div role="group" aria-label="Changes Span proposes" style={{ margin: "8px 0" }}>
      {pendingList.map((c) => (
        <p key={c.id}>{c.summary}.{" "}
          <Button variant="primary" disabled={busy} onClick={() => void act(() => api.acceptChange(projectId, c.id))}>Accept</Button>{" "}
          <Button disabled={busy} onClick={() => void act(() => api.rejectChange(projectId, c.id))}>Not this</Button></p>))}
    </div>) : null;
  const chatLog = (
    <>
      {chat.length === 0 ? <MessageBubble from="agent" who="Span" text="Hello, I am Span. I have read the intent of work. Tell me what to change in the build, or ask me why a table is there." /> : null}
      {chat.map((t, i) => <MessageBubble key={t.id} from={t.by === "span" ? "agent" : "human"} who={t.name} when={when(t.at)} text={t.text}>{i === chat.length - 1 ? <UsedLine used={used} /> : null}</MessageBubble>)}
      {changes}
      {busy ? <p className="ds-muted" role="status">Span is working…</p> : null}
      <div ref={end} />
    </>
  );
  const composer = <Composer agent="Span" text={text} setText={setText} files={files} setFiles={setFiles} onSend={talk} busy={busy} error={error} />;
  if (!("tables" in plan)) {
    return (
      <PageFrame title={projectTitle} subline={subline} crumbs={<><Link className="ds-link" to="/centre/build">All projects</Link> · <Link className="ds-link" to={`/centre/project/${encodeURIComponent(projectId)}`}>Project page: documents, run book, deviations</Link></>}>
        <ProjectRooms pid={projectId} />
        <p><Rooms iid={plan.intent_id} />{studio}</p>
        <p>Span has not proposed a plan yet.</p>
        {!plan.intent_signed ? <p className="ds-muted">The intent of work is not signed yet, so Span has nothing to plan from.</p> : null}
        <Button variant="primary" disabled={busy || !plan.can?.propose} onClick={() => void act(() => api.propose(projectId))}>Ask Span to propose a plan</Button>
        {!plan.can?.propose ? <p className="ds-muted">Only the data team can ask for a plan.</p> : null}
        {error ? <p role="alert">{error}</p> : null}
        {chatLog}
        {composer}
      </PageFrame>
    );
  }

  const doc = (id: string, n: number, title: string, state: string, render: () => ReactNode): Doc =>
    ({ id, title: `${n} ${title}`, render: () => <><p style={{ marginTop: 0 }}><Pill tone="draft">{state}</Pill></p>{render()}</> });
  const landed = plan.sources.filter((s) => s.files.length).length;
  const runState = runs[0] ? `Last run ${runs[0].status}` : "No runs yet";
  const docs: Doc[] = [
    doc("sources", 1, "Sources", `${landed} of ${plan.sources.length} with files`, () => <Sources plan={plan} pid={projectId} />),
    doc("model", 2, "Model changes", plan.model_changes ? api.MODEL_STATES[plan.model_diff?.state ?? ""] ?? "Proposed" : "No change", () => <ModelChanges plan={plan} />),
    doc("tables", 3, "Tables", `${plan.tables.length} tables`, () => <Tables plan={plan} />),
    doc("diagram", 4, "Diagram", api.STATE_NAMES[plan.state], () => <Diagram pid={projectId} />),
    doc("approval", 5, "Approval", api.STATE_NAMES[plan.state], () => (
      <Approval plan={plan} busy={busy} onPropose={() => void act(() => api.propose(projectId))} onApprove={(note) => void act(() => api.approve(projectId, note))}
        onSendBack={(r) => void act(() => api.reject(projectId, r))} />)),
    doc("pipeline", 6, "Pipeline", runState, () => (
      <Pipeline plan={plan} runs={runs} busy={busy} pid={projectId} onRun={(m) => void act(() => api.startRun(projectId, m))} onSchedule={(s) => void act(() => api.setSchedule(projectId, s))} />)),
  ];

  return (
    <PageFrame title={projectTitle} subline={subline} crumbs={<><Link className="ds-link" to="/centre/build">All projects</Link> · <Link className="ds-link" to={`/centre/project/${encodeURIComponent(projectId)}`}>Project page: documents, run book, deviations</Link></>}>
      <ProjectRooms pid={projectId} />
        <p><Rooms iid={plan.intent_id} />{studio}</p>
      <Workbench layoutKey="span" documents={docs} agent="Span" iid="" canAdd={false}
        chatHead={<><strong>Span, the build agent</strong><ModeLine /></>}
chatLog={chatLog}
        composer={composer} />
    </PageFrame>
  );
}
