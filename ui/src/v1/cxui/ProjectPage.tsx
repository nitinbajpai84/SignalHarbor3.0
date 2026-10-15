import { useProjectTitle } from "../s1/useProjectTitle";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame } from "../../design";
import { apiSend } from "../../api/client";
import { Composer } from "../voice";
import Workbench, { type Doc } from "../workbench/Workbench";
import Canvas from "../b7/Canvas";
import { ChatHead, ChatLog, useRemembered, type Turn } from "./LumenChat";
import TileCard from "./TileCard";
import {
  ask, askProject, getDashboard, getPeople, getTables, listDashboards, share, why,
  type Dashboard, type GoldTable, type Person, type Why,
} from "./api";

// C2, OP1: /centre/consume/p/:projectId. The published dashboards of the project to read, with Lumen on the left answering questions about what is shown
// (figures, why one moved, where it is from). Nothing here builds or changes a dashboard: that is the Build studio (b7), where Lumen's conversation lives.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const REFRESH: Record<string, string> = { same: "with each pipeline run", daily: "daily", weekly: "weekly" };  // UC10-06: the dashboard header says when that run is
// NU-22: the dashboard comes with the person's own talk with Lumen, so a reload shows the conversation
type WithTalk = Dashboard & { talk?: Turn[] };

function TablesDrawer({ tables }: { tables: GoldTable[] }) {
  if (!tables.length) return <p className="ds-muted">This project has no figures yet. Build produces them once the plan is approved.</p>;
  return (
    <ul>{tables.map((t) => (
      <li key={t.name}><strong>{t.name}</strong> <span className="ds-muted">{t.rows} rows</span>
        <div className="ds-muted">{t.columns.map((c) => c.name).join(", ")}</div></li>
    ))}</ul>
  );
}

const evidenceLine = (e: Why["evidence"][number]) => ("period" in e ? `${e.period}: ${e.value}` : `${e.split}: ${e.change}`);

function ShareForm({ board, people, onShare }: { board: Dashboard; people: Person[]; onShare: (audience: string[], refresh: string) => void }) {
  const [picked, setPicked] = useState<string[]>(board.audience);
  const [refresh, setRefresh] = useState<string>(board.refresh);
  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  return (
    <form onSubmit={(e) => { e.preventDefault(); onShare(picked, refresh); }} aria-label="Share this dashboard">
      <fieldset>
        <legend>Who can open this dashboard</legend>
        {people.length ? people.map((m) => (
          <label key={m.id} style={{ display: "block" }}><input type="checkbox" checked={picked.includes(m.id)} onChange={() => toggle(m.id)} /> {m.name}{m.role ? <span className="ds-muted"> · {m.role}</span> : null}</label>
        )) : <p className="ds-muted">No one else in the company has access to this data yet.</p>}
      </fieldset>
      <label>Refresh <select value={refresh} onChange={(e) => setRefresh(e.target.value)}>
        <option value="same">With each pipeline run</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select></label>{" "}
      <Button type="submit">Share with these people</Button>
    </form>
  );
}

export default function ProjectPage() {
  const { projectId = "" } = useParams();
  const projectTitle = useProjectTitle(projectId);
  const [qs] = useSearchParams();
  const [board, setBoard] = useState<Dashboard | null>(null);
  const [tables, setTables] = useState<GoldTable[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [failed, setFailed] = useState("");
  const [ready, setReady] = useState(false);  // UC10B-004: until the first answer, say it is opening, never "no figures"
  const box = useRef<HTMLTextAreaElement>(null);
  const known = useRemembered(turns.length);  // what Lumen remembers about this person, shown in the chat head

  const want = qs.get("d");
  const load = useCallback(async () => {
    try {
      const [t, all] = await Promise.all([getTables(projectId), listDashboards(projectId)]);  // the server lists published dashboards only
      setTables(t);
      const id = want ?? all[0]?.id;
      const b: WithTalk | null = id ? await getDashboard(projectId, id) : null;
      setBoard(b);
      setTurns(b?.talk ?? []);
      setFailed("");
      setReady(true);
    } catch (e) { setFailed(plain(e)); }
    getPeople(projectId).then(setPeople, () => setPeople([]));  // only the maker may share; others see an empty picker
  }, [projectId, want]);
  useEffect(() => { void load(); }, [load]);

  async function run(fn: () => Promise<void>) {
    setBusy(true); setError("");
    try { await fn(); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  }
  const refetch = async (id: string) => setBoard(await getDashboard(projectId, id));
  const talk = (said: string) => run(async () => {
    setTurns((t) => [...t, { by: "person", text: said }]);
    const r = board ? await ask(projectId, board.id, said) : await askProject(projectId, said);  // no published dashboard: the project-level talk
    setTurns((t) => [...t, { by: "lumen", text: r.reply, link: r.link, used: r.used }]);
    setText("");
  });
  // H1-07: a fresh talk empties the thread Lumen reads
  const freshTalk = (b: Dashboard) => run(async () => {
    await apiSend("POST", `/api/v1/consume/p/${encodeURIComponent(projectId)}/dashboards/${encodeURIComponent(b.id)}/ask`, { new_talk: true });
    setTurns([]);
  });
  const whyMoved = (b: Dashboard, tid: string, title: string) => run(async () => {
    setTurns((t) => [...t, { by: "person", text: `Why did "${title}" move?` }]);
    const w = await why(projectId, b.id, tid);
    setTurns((t) => [...t, { by: "lumen", text: [w.answer, ...w.evidence.map(evidenceLine), ...w.caveats].join("\n") }]);
  });

  if (failed) return <PageFrame title="Consume"><p role="alert">{failed} <Button onClick={() => void load()}>Try again</Button></p></PageFrame>;
  const accepted = board?.tiles.filter((t) => t.state === "accepted") ?? [];
  const opening = <p className="ds-muted" role="status">Opening the figures.</p>;
  const docs: Doc[] = [
    { id: "dash", title: board?.title ?? "Dashboard", render: () => !ready ? opening : !board || !accepted.length
        ? <p className="ds-muted">No dashboard has been published for this project yet. Dashboards are built in Build › Dashboard studio, and appear here once they are approved.</p>
        : board.layout?.items.length
          ? <>
              <Canvas pid={projectId} did={board.id} layout={board.layout} />
              <p className="ds-muted" style={{ marginBottom: 4 }}>Ask Lumen why a figure moved:</p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                {accepted.map((t) => <Button key={t.id} onClick={() => void whyMoved(board, t.id, t.title)}>Why did {t.title} move</Button>)}
              </div>
            </>
          : <>{accepted.map((t) => <TileCard key={t.id} pid={projectId} did={board.id} tile={t} onWhy={() => void whyMoved(board, t.id, t.title)} />)}</> },
    { id: "tables", title: "Figures available", render: () => ready ? <TablesDrawer tables={tables} /> : opening },
    { id: "share", title: "Share", render: () => board
        ? <><p>Shared with: {board.audience_people?.length ? board.audience_people.map((m) => m.name).join(", ") : "nobody yet"}. Refresh: {REFRESH[board.refresh] ?? board.refresh}.</p>
            <ShareForm key={board.id + board.audience.join()} board={board} people={people}
              onShare={(a, r) => void run(async () => { await share(projectId, board.id, a, r); await refetch(board.id); })} /></>
        : <p className="ds-muted">Nothing has been published for this project yet.</p> },
  ];
  return (
    <PageFrame title={projectTitle} subline="The published dashboards of this project. Ask Lumen about the figures you see; dashboards are built in Build › Dashboard studio.">
      <Workbench layoutKey="lumen" documents={docs} agent="Lumen" iid="" canAdd={false}
        chatHead={<ChatHead busy={busy} known={known} onFresh={board && turns.length ? () => void freshTalk(board) : undefined} />}
        chatLog={<ChatLog busy={busy} turns={turns} intro="Ask me about the figures on this dashboard: what a number is, why it moved, where it comes from. To build or change a dashboard, use Build › Dashboard studio." />}
        composer={<Composer agent="Lumen" text={text} setText={setText} files={files} setFiles={setFiles} busy={busy} error={error} boxRef={box}
          onSend={(said) => void talk(said)} placeholder="For example: why did net worth move in September?" />} />
    </PageFrame>
  );
}
