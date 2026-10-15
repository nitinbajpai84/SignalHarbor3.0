import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import MessageBubble from "../../components/MessageBubble";
import { Button, Chip, EmptyState, PageFrame } from "../../design";
import { Composer, SpeakButton, useReadAloud } from "../voice";
import Workbench, { type Doc } from "../workbench/Workbench";
import ProjectTag from "../p1/ProjectTag";
import ModeLine from "../router/ModeLine";
import { useProposals } from "../workbench/proposals";
import { getBrief, readBase64, sendChat, type Brief, type LumenChat } from "./api";

// C3: /centre/consume/design and /centre/consume/design/:iid. L1: the conversation with Lumen is docked on the right of the workbench; on
// the left a strip of three documents: Consumption brief, Views preview, and Levers and outside data.

const CSS = `
.c3-view{border:1px solid currentColor;border-radius:8px;padding:10px;margin-bottom:12px}
.c3-boxes{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px;margin:8px 0}
.c3-box{border:1px dashed currentColor;border-radius:6px;padding:10px 8px;min-height:48px;font-size:13px}
`;
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const when = (at: string) => {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
};

function names(chat: LumenChat) {
  const k = new Map(chat.kpis.map((x) => [x.code, x.name]));
  const f = new Map(chat.feeds.map((x) => [x.id, x.kind]));
  return { kpi: (c: string) => k.get(c) ?? "A figure no longer signed", feed: (id: string) => f.get(id) ?? id.replace(/_/g, " ") };
}

function BriefDoc({ chat }: { chat: LumenChat }) {
  const b: Brief = chat.brief;
  const n = names(chat);
  const empty = !b.views.length && !b.existing_dashboards.length && !b.end_user_inputs.length && !b.notes.length;
  if (empty) return <p className="ds-muted">Lumen fills the brief as you talk.</p>;
  return (
    <>
      {b.views.map((v) => (
        <section key={v.name} style={{ marginBottom: 12 }}>
          <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>{v.name}</h3>
          <p style={{ margin: 0 }}><span className="ds-muted">Who reads it: </span>{v.audience || "Not stated"}</p>
          <p style={{ margin: 0 }}><span className="ds-muted">Figures, in order: </span>{v.kpis.map(n.kpi).join(", ") || "Not stated"}</p>
          <p style={{ margin: 0 }}><span className="ds-muted">Compared with: </span>{v.comparisons.join(", ") || "Not stated"}</p>
          {v.filters.length ? <p style={{ margin: 0 }}><span className="ds-muted">Filters: </span>{v.filters.join(", ")}</p> : null}
          <p style={{ margin: 0 }}><span className="ds-muted">Refresh: </span>{v.refresh || "Not stated"}</p>
        </section>
      ))}
      {b.existing_dashboards.length ? <p><span className="ds-muted">Brought in: </span>{b.existing_dashboards.map((d) => d.name).join(", ")}</p> : null}
      {b.notes.length ? <ul style={{ paddingLeft: 18 }}>{b.notes.map((x) => <li key={x}>{x}</li>)}</ul> : null}
      {b.end_user_inputs.length ? (
        <section>
          <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>What readers said</h3>
          {b.end_user_inputs.map((x, i) => <p key={i} style={{ margin: "0 0 4px" }}><strong>{x.by}</strong>: {x.answer}</p>)}
        </section>
      ) : null}
    </>
  );
}

function LeversDoc({ chat, ask }: { chat: LumenChat; ask: string }) {
  const b = chat.brief;
  const n = names(chat);
  return (
    <>
      {b.feeds_wanted.length ? <p style={{ marginTop: 0 }}><span className="ds-muted">Outside feeds wanted: </span>{b.feeds_wanted.map(n.feed).join(", ")}</p> : null}
      {b.levers.length ? (
        <section style={{ marginBottom: 12 }}>
          <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>What-if levers</h3>
          {b.levers.map((l) => <p key={l.name} style={{ margin: 0 }}>{l.name}{l.affects.length ? `, moves ${l.affects.map(n.kpi).join(", ")}` : ""}{l.range ? ` (${l.range})` : ""}</p>)}
        </section>
      ) : null}
      {!b.feeds_wanted.length && !b.levers.length ? <p className="ds-muted">Lumen lists the what-if levers and the outside data here as you talk.</p> : null}
      <h3 style={{ margin: "12px 0 4px", fontSize: 15 }}>What Lumen has read</h3>
      <p style={{ margin: 0 }}>{chat.kpis.length} signed {chat.kpis.length === 1 ? "figure" : "figures"}{chat.kpis.length ? `: ${chat.kpis.map((k) => k.name).join(", ")}` : ""}</p>
      <p style={{ margin: "4px 0 0" }}>{b.existing_dashboards.length} brought in, {b.end_user_inputs.length} answers from readers</p>
      <p className="ds-muted" style={{ margin: "4px 0 0" }}>Skill: {chat.skill}</p>
      <p style={{ margin: "8px 0 0" }}>Readers can give their view in three short questions: <Link className="ds-link" to={ask}>open the short questions</Link> and share this page&apos;s address.</p>
    </>
  );
}

function ViewsDoc({ chat }: { chat: LumenChat }) {
  const b = chat.brief;
  const n = names(chat);
  if (!b.views.length) return <p className="ds-muted">A sketch of the page appears once Lumen knows which figures come first.</p>;
  return (
    <div aria-label="Sketch of the Consume page">
      {b.views.map((v) => (
        <div key={v.name} className="c3-view">
          <strong>{v.name}</strong>
          <span className="ds-muted">{v.audience ? ` · ${v.audience}` : ""}{v.refresh ? ` · ${v.refresh}` : ""}</span>
          {v.filters.length ? <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>{v.filters.map((f) => <Chip key={f}>{f}</Chip>)}</div> : null}
          <div className="c3-boxes">
            {v.kpis.map((c) => <div key={c} className="c3-box">{n.kpi(c)}{v.comparisons.length ? <div className="ds-muted">vs {v.comparisons[0]}</div> : null}</div>)}
          </div>
        </div>
      ))}
      {b.levers.length ? (
        <div className="c3-view"><strong>What if</strong>
          {b.levers.map((l) => <div key={l.name} className="c3-box" style={{ marginTop: 6 }}>{l.name} ◀───●───▶{l.range ? ` ${l.range}` : ""}</div>)}
        </div>
      ) : null}
      {b.feeds_wanted.length ? <p className="ds-muted">Outside feeds: {b.feeds_wanted.map(n.feed).join(", ")}</p> : null}
    </div>
  );
}

/** The Consume centre's design conversation: Lumen drafts the consumption brief with the analyst or screen designer. */
export default function DesignPage() {
  const { iid = "" } = useParams();
  const [chat, setChat] = useState<LumenChat | null>(null);
  const [failed, setFailed] = useState("");
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try { setChat(await getBrief(iid || undefined)); setFailed(""); } catch (err) { setFailed(plain(err)); }
  }, [iid]);
  useEffect(() => { void load(); }, [load]);
  const pr = useProposals(iid || chat?.intent_id || "", chat?.proposals, load);

  const lastLumen = chat?.turns.filter((t) => t.by === "lumen").at(-1);
  useReadAloud(lastLumen ? { id: lastLumen.id, text: lastLumen.text } : null);

  async function send(said: string, pending: File[]) {
    if (!chat?.intent_id || (!said && !pending.length)) return;
    setBusy(true);
    setError("");
    try {
      const up = await Promise.all(pending.map(async (f) => ({ name: f.name, data: await readBase64(f) })));
      setChat(await sendChat(chat.intent_id, said, up));
      setText(""); setFiles([]);
    } catch (err) {
      setError(plain(err));
    } finally {
      setBusy(false);
    }
  }

  if (failed) return <PageFrame title="Shape what you see"><p role="alert">{failed} <Button onClick={() => void load()}>Try again</Button></p></PageFrame>;
  if (!chat) return <PageFrame title="Shape what you see"><p className="ds-muted" role="status">Opening the conversation…</p></PageFrame>;
  if (!chat.intent_id) return <PageFrame title="Shape what you see"><EmptyState title="Nothing to shape yet" lines={[chat.line ?? ""]} /></PageFrame>;

  const ask = `/centre/consume/design/${encodeURIComponent(chat.intent_id)}/ask`;
  const docs: Doc[] = [
    { id: "brief", title: "Consumption brief", proposes: ["brief"], render: () => <BriefDoc chat={chat} /> },
    { id: "views", title: "Views preview", render: () => <ViewsDoc chat={chat} /> },
    { id: "levers", title: "Levers and outside data", render: () => <LeversDoc chat={chat} ask={ask} /> },
  ];
  return (
    <PageFrame title="Shape what you see" subline={chat.title ? `For ${chat.title}. Say what people should see; Lumen drafts the brief.` : undefined}>
      <style>{CSS}</style>
      <ProjectTag iid={chat.intent_id} />
      <p><Link className="ds-link" to="/centre/consume">Back to the Consume page</Link></p>
      <Workbench layoutKey="lumen" documents={docs} agent="Lumen" iid={chat.intent_id} proposals={pr.proposals} onAccept={pr.onAccept} onReject={pr.onReject} changeError={pr.error} changeBusy={pr.busy}
        chatHead={<><strong>Lumen, the consume agent</strong><ModeLine /></>}
        chatLog={<>
          {!chat.turns.length ? <MessageBubble from="agent" who="Lumen" text={chat.greeting} /> : chat.turns.map((t) => (
            <MessageBubble key={t.id} from={t.by === "lumen" ? "agent" : "human"} who={t.name} when={when(t.at)} text={t.text}
              tags={(t.files ?? []).map((f) => f.name)}>
              {t.by === "lumen" ? <SpeakButton text={t.text} /> : null}
            </MessageBubble>
          ))}
          {busy ? <p className="ds-muted" role="status">Lumen is thinking…</p> : null}
        </>}
        composer={<Composer agent="Lumen" text={text} setText={setText} files={files} setFiles={setFiles} onSend={(said, up) => void send(said, up)}
          busy={busy} error={error} />} />
    </PageFrame>
  );
}
