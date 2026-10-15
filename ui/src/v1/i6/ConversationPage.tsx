import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import AgentChip from "../../components/AgentChip";
import MessageBubble from "../../components/MessageBubble";
import ModeLine from "../router/ModeLine";
import { Button, Chip, PageFrame, Pill } from "../../design";
import type { LineEdit } from "../i4/api";
import {
  downloadHref, editLine, getChat, getOpen, kindOf, readBase64, sendChat, sendToBuild, startChat,
  type Chat, type Sow, type UpFile,
} from "./api";
import SourceChips, { type Source } from "./SourceChips";
import Swimlane from "./Swimlane";
import SopPanel from "./SopPanel";
import Line from "./Line";
import UsedLine from "../teach/UsedLine";
import DocumentLayout from "../t1/DocumentLayout";
import { switchTemplate, type LayoutDoc } from "../t1/api";
import { Composer, SpeakButton, useReadAloud } from "../voice";
import Workbench, { type Doc } from "../workbench/Workbench";
import { useProposals, type Proposed } from "../workbench/proposals";
import ProjectTag, { useProjectId } from "../p1/ProjectTag";
import { useProjectTitle } from "../s1/useProjectTitle";
import { projectOf } from "../p1/api";
import LockedProject from "../g1/LockedProject";
import { isLock, type Lock } from "../g1/api";
import { useSessionIfAny } from "../../useSession";

// I6b: /centre/intent and /centre/intent/:iid. L1: the conversation with North is docked on the right of the workbench; on the left a strip
// of three documents: Intent of work, Process map and Definitions. Thread bubbles and the composer come from I3's ThreadPage, the line
// edit from I4's SowPage (saved through I4's PUT).

const when = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
/** a9.3: a project past signing has left the Intent Centre; its stage is said once, and "Send to Build" is not offered again. */
const CONTEXT_ROLES = new Set(["company_admin", "sponsor", "analyst"]);
const PAST_SIGNING: Record<string, string> = { designed: "In Build", built: "Built", live: "Live" };
const toUp = async (files: File[]): Promise<UpFile[]> =>
  Promise.all(files.map(async (f) => ({ name: f.name, data: await readBase64(f), kind: kindOf(f.name) })));

function Block({ title, empty, children }: { title: string; empty: boolean; children: ReactNode }) {
  return (
    <section style={{ marginBottom: 12 }}>
      <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>{title}</h3>
      {empty ? <p className="ds-muted" style={{ margin: 0 }}>North fills this as you talk.</p> : children}
    </section>
  );
}

/** I1: what North learned about each source: structured or not, who owns it, how often it arrives, the sample files attached. */
type SourceRow = Sow["sources"][number] & { structure?: string; arrives?: string; samples?: string[] };
function SourcesBlock({ sow }: { sow: Sow }) {
  const rows = sow.sources as SourceRow[];
  return (
    <section aria-label="Sources" style={{ marginBottom: 12 }}>
      <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>Sources: systems and files</h3>
      {!rows.length ? <p className="ds-muted" style={{ margin: 0 }}>North asks which systems or files hold the data, who owns them and how often they arrive.</p> : (
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {rows.map((s, i) => {
            const structure = s.structure || (s.kind === "document" ? "unstructured" : "structured");
            const samples = [...(s.samples ?? []), ...(s.sample_path ? [s.sample_path.split("/").pop() ?? ""] : [])].filter(Boolean);
            return (
              <li key={s.id || i}>
                <strong>{s.name}</strong> <Pill tone="draft">{structure === "unstructured" ? "Unstructured" : "Structured"}</Pill>
                <span className="ds-muted"> {s.owner || s.arrives || samples.length
                  ? [s.owner && `Owner: ${s.owner}.`, s.arrives && `Arrives ${s.arrives}.`, samples.length && `Sample: ${samples.join(", ")}.`].filter(Boolean).join(" ")
                  : "North will ask who owns this and how often it arrives."}</span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function IntentDoc({ sow, save }: { sow: Sow | null; save: (e: LineEdit) => Promise<void> }) {
  if (!sow) return <p className="ds-muted">The intent of work starts with your first message.</p>;
  const can = sow.state === "draft";
  const g = sow.goal;
  return (
    <>
      <p style={{ marginTop: 0 }}><Pill tone={can ? "draft" : "signed"}>{can ? "Draft" : "Signed"}</Pill> Version {sow.version}</p>
      <Block title="Goal" empty={!g?.line}>
        {g ? <>
          <Line label="Goal" value={g.line} edit={{ section: "goal", field: "line" }} can={can} save={save} />
          <Line label="Why" value={g.why} edit={{ section: "goal", field: "why" }} can={can} save={save} />
          <Line label="Needed by" value={g.needed_by} edit={{ section: "goal", field: "needed_by" }} can={can} save={save} />
        </> : null}
      </Block>
      <SourcesBlock sow={sow} />
      {sow.sources.map((s, i) => (
        <Line key={s.id || i} label={`What ${s.name} holds`} value={s.holds}
          edit={{ section: "sources", index: i, field: "holds" }} can={can} save={save} />
      ))}
      {sow.catalogue.length ? <p className="ds-muted" style={{ margin: "0 0 12px" }}>{sow.catalogue.length} catalogue {sow.catalogue.length === 1 ? "table" : "tables"} drafted.</p> : null}
      <Block title="Rules" empty={!sow.governance.length}>
        {sow.governance.map((r, i) => (
          <Line key={i} label={r.kind === "access" ? "Access" : r.kind === "retention" ? "Retention" : "Approval"} value={r.rule}
            edit={{ section: "governance", index: i, field: "rule" }} can={can} save={save} />
        ))}
      </Block>
      <Block title="Unclear" empty={!sow.unclear.length}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {sow.unclear.map((u) => <span key={u.id} title={u.who_can_settle ? `Who can settle it: ${u.who_can_settle}` : undefined}>
            <Chip tone={u.settled ? "active" : "default"}>{u.question}</Chip></span>)}
        </div>
      </Block>
    </>
  );
}

function DefinitionsDoc({ sow, save, iid }: { sow: Sow | null; save: (e: LineEdit) => Promise<void>; iid: string }) {
  const pid = useProjectId(iid);
  if (!sow) return <p className="ds-muted">The definitions start with your first message.</p>;
  const can = sow.state === "draft";
  return (
    <>
      <Block title="KPIs" empty={!sow.kpis.length}>
        {sow.kpis.map((k, i) => (
          <div key={k.code || i}>
            <strong>{k.name}</strong>{" "}
            {k.pack_suggested ? <Pill tone="draft">Suggestion</Pill> : null}{k.status === "unclear" ? <Pill tone="late">Unclear</Pill> : null}
            <Line label="Definition" value={k.definition} edit={{ section: "kpis", index: i, field: "definition" }} can={can} save={save} />
          </div>
        ))}
      </Block>
      {pid ? <p style={{ margin: 0 }}><Link className="ds-link" to={`/centre/project/${encodeURIComponent(pid)}?artefact=benchmarks`}>Open the benchmark sheet</Link></p> : null}
    </>
  );
}

function DefinitionsLayout({ doc, iid, ...rest }: { doc: LayoutDoc; iid: string; can: boolean; save: (e: LineEdit) => Promise<void>; onSwitch?: (kind: string, id: string) => void }) {
  const pid = useProjectId(iid);
  return <DocumentLayout doc={doc} {...rest} after={pid ? <p style={{ margin: 0 }}><Link className="ds-link" to={`/centre/project/${encodeURIComponent(pid)}?artefact=benchmarks`}>Open the benchmark sheet</Link></p> : undefined} />;
}

function ProcessDoc({ map, ok, correct, busy }: { map: Chat["process_map"] | null; ok: () => void; correct: (n: number) => void; busy: boolean }) {
  const [pick, setPick] = useState<number | null>(null);
  if (!map?.steps.length) return <p className="ds-muted">North draws the process here once you describe how the work is done today.</p>;
  return (
    <>
      <Swimlane map={map} selected={pick} onSelect={setPick} />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
        <Button variant="primary" disabled={busy} onClick={ok}>{"That's right"}</Button>
        <Button disabled={busy} onClick={() => correct(pick ?? map.steps[0]?.n ?? 1)}>Correct a step</Button>
      </div>
    </>
  );
}

/** T1b: the process map laid out from its template; the swimlane (or the numbered list) with the person's confirm and correct buttons. */
function ProcessLayout({ doc, map, ok, correct, busy, ...rest }: { doc: LayoutDoc; map: Chat["process_map"] | null; ok: () => void; correct: (n: number) => void; busy: boolean;
  can: boolean; save: (e: LineEdit) => Promise<void>; onSwitch?: (kind: string, id: string) => void }) {
  const [pick, setPick] = useState<number | null>(null);
  const has = !!map?.steps.length;
  return (
    <DocumentLayout doc={doc} {...rest} swim={has && map ? <Swimlane map={map} selected={pick} onSelect={setPick} /> : undefined}
      after={has && map ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <Button variant="primary" disabled={busy} onClick={ok}>{"That's right"}</Button>
          <Button disabled={busy} onClick={() => correct(pick ?? map.steps[0]?.n ?? 1)}>Correct a step</Button>
        </div>) : undefined} />
  );
}

/** The Intent Centre: one conversation with North, the intent of work drafted live beside it. */
export default function ConversationPage() {
  const { iid = "" } = useParams();
  const nav = useNavigate();
  const roles = useSessionIfAny()?.user?.roles;
  const [chat, setChat] = useState<Chat | null>(null);
  const [greeting, setGreeting] = useState("");
  const [looking, setLooking] = useState(true);
  const [failed, setFailed] = useState("");
  const [lock, setLock] = useState<Lock | null>(null);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const box = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const projectTitle = useProjectTitle(chat?.project_id || undefined);  // NI1: the header names the project, never its id

  const load = useCallback(async () => {
    try { setChat(await getChat(iid)); setFailed(""); setLock(null); } catch (err) {
      setFailed(plain(err));
      // a9.1: a project the person may not read shows its lock card with "Request access", never a "Try again" that cannot succeed
      if (err instanceof ApiError && err.status === 403) await projectOf(iid).then((p) => { if (isLock(p)) setLock(p); }).catch(() => undefined);
    }
  }, [iid]);
  const pr = useProposals(chat?.id || iid, chat?.proposals, load);

  useEffect(() => {
    if (iid) { setLooking(false); void load(); return; }
    setChat(null);
    let live = true;
    getOpen()
      .then((o) => {
        if (!live) return;
        if (o.id) nav(`/centre/intent/${encodeURIComponent(o.id)}`, { replace: true });
        else { setGreeting(o.greeting); setLooking(false); }
      })
      .catch(() => { if (live) setLooking(false); });
    return () => { live = false; };
  }, [iid, load, nav]);

  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [chat, busy]);
  const lastNorth = chat?.turns.filter((t) => t.by === "north").at(-1);
  useReadAloud(lastNorth ? { id: lastNorth.id, text: lastNorth.text } : null);

  async function talk(said: string, pending: File[]) {
    if (!said && pending.length === 0) return;
    setBusy(true);
    setError("");
    try {
      const up = await toUp(pending);
      if (!iid) {
        if (!said) throw new ApiError("Say in a line what you would like to build first.", 400);
        const made = await startChat(said, up);
        setText(""); setFiles([]);
        setChat(made);
        nav(`/centre/intent/${encodeURIComponent(made.id || made.intent_id)}`);
        return;
      }
      setChat(await sendChat(iid, said, up));
      setText(""); setFiles([]);
    } catch (err) {
      setError(plain(err));
    } finally {
      setBusy(false);
    }
  }

  function correct(n: number) {
    setText(`Step ${n}: `);
    box.current?.focus();
  }

  const save = async (edit: LineEdit) => {
    if (!chat) return;
    try {
      const sow = await editLine(iid, chat.sow.version, edit);
      setChat({ ...chat, sow });
      setError("");
    } catch (err) {
      setError(plain(err));
      throw err;
    }
  };

  if (failed && lock) return <LockedProject lock={lock} onChange={() => void load()} />;
  if (failed) return <PageFrame title="Intent Centre"><p role="alert">{failed} <Button onClick={() => void load()}>Try again</Button></p></PageFrame>;
  if (looking || (iid && !chat)) return <PageFrame title="Intent Centre"><p className="ds-muted">Opening the conversation…</p></PageFrame>;

  const sow = chat?.sow ?? null;
  const laid = (kind: string) => chat?.layout?.documents.find((d) => d.kind === kind);  // T1b: the template's layout, when the server sent one
  const canEdit = sow?.state === "draft";
  const switchTo = async (kind: string, id: string) => {
    try { await switchTemplate(iid, kind, id); await load(); setError(""); } catch (err) { setError(plain(err)); }
  };
  const ready = chat?.state === "sow_ready";
  const signed = sow?.state === "signed";
  // UC9-09: the context library is for the roles c4.permissions.yaml names; anyone else (an approver, a participant) never asks for it
  const canAdd = !roles || roles.some((r) => CONTEXT_ROLES.has(r));
  const hello = greeting || "Hello, I am North. Add context below if you have files I should read. What would you like to build?";
  const sent = chat?.build;
  const past = PAST_SIGNING[(chat as (Chat & { stage?: string | null }) | null)?.stage ?? ""];
  const toBuild = async () => {
    setBusy(true);
    try { const b = await sendToBuild(iid); setChat(chat ? { ...chat, build: b } : chat); setError(""); } catch (err) { setError(plain(err)); } finally { setBusy(false); }
  };
  const buildStep = signed ? (past
    ? <p role="status"><Pill tone="signed">{past}</Pill> This work has left the Intent Centre; the project page follows it from here.</p>
    : sent
    ? <p role="status"><Pill tone="signed">Sent to Build</Pill> The head of data has a card in Action for this project.</p>
    : <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <Button variant="primary" disabled={busy} onClick={() => void toBuild()}>Send to Build</Button>
        <span className="ds-muted">The head of data will plan the build.</span>
      </div>) : null;
  const handOver = ready && !signed ? (
    <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
      <Link to={`/centre/intent/${encodeURIComponent(chat?.id || iid)}/sow`} className="ds-btn ds-btn--primary">Sign the intent of work</Link>
      <a className="ds-link" href={downloadHref(chat?.id || iid)} download>Download a copy</a>
    </div>
  ) : null;

  const docs: Doc[] = [
    { id: "sow", title: "Intent of work", proposes: ["sow"], render: () => laid("intent_of_work")
      ? <><DocumentLayout doc={laid("intent_of_work") as LayoutDoc} can={!!canEdit} save={save} iid={iid} />{sow ? <SourcesBlock sow={sow} /> : null}</>
      : <IntentDoc sow={sow} save={save} /> },
    { id: "process", title: "Process map", proposes: ["process_map"], render: () => {
      const d = laid("process_map");
      const map = chat?.process_map ?? sow?.process ?? null;
      const ok = () => void talk("The process map is right", []);
      return d ? <ProcessLayout doc={d} map={map} busy={busy || signed || !iid} ok={ok} correct={correct} can={!!canEdit} save={save} onSwitch={signed ? undefined : (k, id) => void switchTo(k, id)} />
        : <ProcessDoc map={map} busy={busy || signed || !iid} ok={ok} correct={correct} />; } },
    { id: "definitions", title: "Definitions", render: () => laid("definitions")
      ? <DefinitionsLayout doc={laid("definitions") as LayoutDoc} iid={chat?.id || iid} can={!!canEdit} save={save} onSwitch={signed ? undefined : (k, id) => void switchTo(k, id)} />
      : <DefinitionsDoc sow={sow} save={save} iid={chat?.id || iid} /> },
  ];

  return (
    <PageFrame title={chat?.landing ? "What do you need?" : sow?.title || "What do you need?"}
      subline={<>{chat?.project_id && projectTitle && projectTitle !== chat.project_id ? <>Project: <strong>{projectTitle}</strong>. </> : null}
        {chat?.landing ? "That was a question, so nothing is drafted yet. When you say what you need, North starts the draft." : "Describe the report, check or process you want in your own words. North, the industry expert, drafts it beside you."}</>}
      actions={iid ? <Link className="ds-btn" to="/centre/intent?new=1">Start a new intent</Link> : undefined}>
      <ProjectTag iid={iid} />
      <Workbench layoutKey="north" documents={docs} agent="North" iid={canAdd ? iid : ""} canAdd={canAdd} proposals={pr.proposals} onAccept={pr.onAccept} onReject={pr.onReject} changeError={pr.error} changeBusy={pr.busy}
        chatHead={<><AgentChip name="North" status={busy ? "thinking" : ready || signed ? "idle" : "waiting"} /><ModeLine /></>}
        chatLog={<>
          {!chat ? <MessageBubble from="agent" who="North" text={hello} /> : chat.turns.map((t) => (
            <MessageBubble key={t.id} from={t.by === "north" ? "agent" : "human"} who={t.by === "north" ? t.name || "North" : t.name}
              when={when(t.at)} text={t.text} tags={(t.files ?? []).map((f) => `${f.name} (${f.kind})`)}>
              {t.by === "north" ? <SpeakButton text={t.text} /> : null}
              {t.id === lastNorth?.id ? <UsedLine used={chat?.used} /> : null}
              {t.by === "north" ? <SourceChips iid={chat?.id || iid} sources={(t as { sources?: Source[] }).sources} /> : null}
            </MessageBubble>
          ))}
          {busy ? <p className="ds-muted" role="status">North is thinking…</p> : null}
          {handOver}
          {buildStep}
          {signed && iid ? <SopPanel iid={chat?.id || iid} /> : null}
          <div ref={end} />
        </>}
        composer={<Composer agent="North" text={text} setText={setText} files={files} setFiles={setFiles} onSend={(said, up) => void talk(said, up)}
          busy={busy} disabled={signed} error={error} boxRef={box} placeholder={signed ? "The intent of work is signed." : !iid ? "Describe what you need in your own words, for example: a monthly performance report by entity, net of fees" : undefined} />} />
    </PageFrame>
  );
}
