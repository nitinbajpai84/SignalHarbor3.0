import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill, day, time, type PillTone } from "../../design";
import type { LayoutItem, Size } from "../cxui/api";
import { useProjectTitle } from "../s1/useProjectTitle";
import * as api from "./api";
import Canvas, { type Slot } from "./Canvas";
import RefreshLine from "./RefreshLine";
import StarterBanner from "./StarterBanner";
import { Composer } from "../voice";
import { ChatHead, ChatLog, PictureBox, readBase64, useRemembered, type Turn } from "../cxui/LumenChat";
import TileCard from "../cxui/TileCard";
import ChecksPanel from "./ChecksPanel";
import HistoryDrawer from "./HistoryDrawer";
import Inspector from "./Inspector";
import OptionsPanel from "./OptionsPanel";
import SketchPanel from "./SketchPanel";
import * as tk from "./talkApi";
import { STATUS_WORDS, type Status, type Studio, type StudioRow } from "./api";

// DS1: /centre/build/p/:projectId/studio?d=<dashboard>. Makers arrange widgets and send the dashboard for approval; the head of data or the sponsor
// approves it here, and only then does Consume show it. Nothing on this page is visible to readers until it is published.
// OP1: Lumen here is the Consume conversation, moved: a thread kept per dashboard, proposals as tile previews with Accept and Not this, follow-ups that edit the last tile.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const KIND_WORDS: Record<string, string> = { figure: "Figure", line: "Line chart", bar: "Bar chart", area: "Area chart", table: "Table", status: "Status list", note: "Text note",
  bullet: "Against a target", waterfall: "What moved it (bridge)", small_multiples: "One small chart each", calendar: "Calendar", treemap: "Share map", kpi_strip: "Headline strip" };
const TONE: Record<Status, PillTone> = { draft: "draft", submitted: "open", published: "signed" };

export default function StudioPage() {
  const { projectId = "" } = useParams();
  const title = useProjectTitle(projectId);
  const [qs, setQs] = useSearchParams();
  const want = qs.get("d");
  const [list, setList] = useState<StudioRow[] | null>(null);
  const [canMake, setCanMake] = useState(false);
  const [board, setBoard] = useState<Studio | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [kind, setKind] = useState("line");
  const [table, setTable] = useState("");
  const [note, setNote] = useState("");
  const [ask, setAsk] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [askNote, setAskNote] = useState("");
  const [askFiles, setAskFiles] = useState<File[]>([]);
  const [pic, setPic] = useState<File | null>(null);
  const [noFigures, setNoFigures] = useState(false);
  const known = useRemembered(turns.length);
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);
  const [drawer, setDrawer] = useState(false);
  const [panel, setPanel] = useState<"options" | "checks" | "sketch" | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.listStudio(projectId);
      setList(r.dashboards); setCanMake(r.can_make);
      const id = want ?? (r.dashboards.find((x) => !x.archived) ?? r.dashboards[0])?.id;
      // a sponsor may not open a draft (after sending one back it is one): the list stays, the canvas is empty
      setBoard(id ? await api.getStudio(projectId, id).catch((e: unknown) => { if (e instanceof ApiError && e.status === 403) return null; throw e; }) : null);
      setError("");
    } catch (e) { setError(plain(e)); setList((l) => l ?? []); }
  }, [projectId, want]);
  useEffect(() => { void load(); }, [load]);
  const boardId = board?.id;
  const refreshStep = useCallback(() => { if (boardId) tk.getHistory(projectId, boardId).then((h) => setStep(h.now), () => undefined); }, [projectId, boardId]);
  useEffect(refreshStep, [refreshStep, board?.rev]);
  // every change made by a panel, the history or an undo: read the dashboard again at once
  const reload = useCallback(async () => { if (boardId) try { setBoard(await api.getStudio(projectId, boardId)); } catch (e) { setError(plain(e)); } refreshStep(); }, [projectId, boardId, refreshStep]);
  useEffect(() => { if (board && !table) setTable(board.library.tables[0]?.name ?? ""); }, [board, table]);
  useEffect(() => { setTurns(board?.talk ?? []); setAskNote(""); }, [board?.id]);  // eslint-disable-line react-hooks/exhaustive-deps -- the thread is read when a dashboard is opened

  async function run(fn: () => Promise<Studio | null | void>) {
    setBusy(true); setError("");
    try { const b = await fn(); if (b) setBoard(b); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  }
  const items = board?.layout.items ?? [];
  const rows = board?.layout.rows ?? 2;
  const send = (its: LayoutItem[], extra: { title?: string; company_wide?: boolean } = {}, r = rows) =>
    run(() => api.saveLayout(projectId, board!.id, its.map((i) => ({ id: i.id, row: i.row, col: i.col, size: i.size as Size, ...(i.h && i.h > 1 ? { h: i.h } : {}), ...(i.kind === "note" ? { text: i.text } : {}) })), r, { ...extra, rev: board!.rev }));
  const selectedItem = items.find((i) => i.id === selected) ?? null;

  const create = (t: string) => run(async () => {
    const b = await api.createStudio(projectId, t.trim() || "New dashboard");
    setQs({ d: b.id }); setName("");
    return b;
  });
  const add = () => run(async () => {
    if (!slot) throw new ApiError("Choose an empty slot on the grid first.", 400);
    const r = await api.addWidget(projectId, board!.id, kind === "note" ? { kind, text: note, ...slot } : { kind, table, ...slot });
    setSlot(null); setNote("");
    return r.dashboard;
  });
  const place = (t: { dashboard_id: string; tile_id: string }) => run(async () => {
    if (!slot) throw new ApiError("Choose an empty slot on the grid first.", 400);
    const r = await api.addWidget(projectId, board!.id, { kind: "lumen", dashboard_id: t.dashboard_id, tile_id: t.tile_id, ...slot });
    setSlot(null);
    return r.dashboard;
  });
  // STUDIO2: a talk is applied at once (no Accept step); Lumen's reply shows and the canvas reloads. Send is never greyed out; an empty send says what to do.
  const askLumen = async (text: string) => {
    setBusy(true); setAskNote("");
    setTurns((t) => [...t, { by: "person", text }]);
    try {
      const reading = pic ? { name: pic.name, data: await readBase64(pic), no_client_figures: noFigures } : undefined;
      const r = await tk.talk(projectId, board!.id, { text, ...(selectedItem ? { widget: selectedItem.id } : {}), ...(reading ? { reading } : {}) });
      setTurns((t) => [...t, { by: "lumen", text: r.reply }]); setAsk(""); setPic(null); setNoFigures(false); setStep(r.step);
      setBoard(await api.getStudio(projectId, board!.id));
    } catch (e) { setAskNote(plain(e)); } finally { setBusy(false); }
  };
  const freshTalk = () => run(async () => { await api.askSlot(projectId, board!.id, { new_talk: true }); setTurns([]); });
  const accept = (tid: string) => run(async () => {
    const r = await api.acceptTile(projectId, board!.id, tid, slot ?? {});
    setSlot(null);
    return r.dashboard;
  });
  const acceptStarter = () => run(() => api.acceptStarter(projectId, board!.id));
  const undo = () => run(async () => { await tk.undo(projectId, board!.id); refreshStep(); return api.getStudio(projectId, board!.id); });
  const sendStarter = () => run(async () => { if (board!.starter?.status === "proposed") await api.acceptStarter(projectId, board!.id); return api.submitStudio(projectId, board!.id); });
  const askStarter = () => document.getElementById("b7-talk")?.scrollIntoView?.({ block: "center" });
  const startOne = () => run(async () => { const b = await api.startStarter(projectId); setQs({ d: b.id }); return b; });
  const remove = () => {
    if (!window.confirm(`Delete the draft "${board!.title}"? This cannot be undone.`)) return;
    void run(async () => { await api.deleteStudio(projectId, board!.id); setBoard(null); if (want) setQs({}); else await load(); });
  };
  const reject = (tid: string) => run(() => api.rejectTile(projectId, board!.id, tid));

  if (list === null) return <PageFrame title="Dashboard studio"><p className="ds-muted" role="status">Opening the studio.</p></PageFrame>;
  const crumbs = <><Link className="ds-link" to={`/centre/build/p/${encodeURIComponent(projectId)}`}>Back to the build</Link> · <Link className="ds-link" to="/centre/build">All projects</Link></>;
  const archived = list.filter((d) => d.archived && d.id !== board?.id).length;
  const picker = list.length ? (
    <nav aria-label="Dashboards in this project" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
      {list.filter((d) => showArchived || !d.archived || d.id === board?.id).map((d) => <Button key={d.id} aria-pressed={board?.id === d.id} onClick={() => { setQs({ d: d.id }); setSlot(null); setSelected(null); }}>
        {board?.id === d.id ? board.title : d.title} <span className="ds-muted" style={{ marginLeft: 6 }}>{STATUS_WORDS[board?.id === d.id ? board.status : d.status]}{(board?.id === d.id ? board.can.approve : d.waiting_for_you) ? ", needs you" : ""}</span></Button>)}
      {archived ? <Button variant="secondary" onClick={() => setShowArchived((s) => !s)}>{showArchived ? "Hide archived drafts" : `Show archived drafts (${archived})`}</Button> : null}
    </nav>) : null;
  const maker = (
    <form onSubmit={(e) => { e.preventDefault(); void create(name); }} aria-label="Start a dashboard" style={{ margin: "8px 0" }}>
      <label>Name of the new dashboard <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Monthly board pack" /></label>{" "}
      <Button type="submit" variant="primary" disabled={busy}>Start a dashboard</Button>
    </form>);

  if (!board) {
    return (
      <PageFrame title="Dashboard studio" subline={`${title}: arrange widgets, send them for approval, and the approved dashboard appears in Consume.`} crumbs={crumbs}>
        {picker}
        {error ? <p role="alert">{error}</p> : null}
        {canMake ? <>{!list.length ? <p>There is no dashboard for this project yet. <Button disabled={busy} onClick={() => void startOne()}>Ask Lumen for a starter dashboard</Button></p> : null}{maker}</> : <p className="ds-muted">Only the data team can start a dashboard. Nothing is waiting for you here.</p>}
      </PageFrame>
    );
  }
  const edit = board.can.edit;
  const rv = board.review ?? null;
  const builder = rv?.built_by ?? null;
  const lastEmpty = rows > 1 && !items.some((i) => i.row === rows - 1);
  return (
    <PageFrame title={<>Dashboard studio <Pill tone={TONE[board.status]}>{STATUS_WORDS[board.status]}</Pill></>}
      subline={`${title}: arrange widgets, send them for approval, and the approved dashboard appears in Consume.`} crumbs={crumbs}>
      <div className={board.starter ? "ds-dark" : undefined}>{/* V6B: Lumen's starter is drawn dark, as in design H10 */}
      {picker}
      {canMake ? maker : null}
      <h2 style={{ marginBottom: 0 }}>{board.title}</h2>
      <p className="ds-muted" style={{ margin: "2px 0" }}>
        Version {board.version}{board.published_version && board.status !== "published" ? `. Version ${board.published_version} stays in Consume until this one is approved` : ""}.
        {board.submitted_by && board.status === "submitted" ? ` Sent for approval by ${board.submitted_by}${board.submitted_at ? ` on ${day(board.submitted_at)}` : ""}.` : ""}
        {board.approved_by && board.status === "published" ? ` Approved by ${board.approved_by}${board.approved_at ? ` on ${day(board.approved_at)}` : ""}.` : ""}
      </p>
      <RefreshLine refresh={board.refresh} />
      {board.sent_back ? <p role="status"><strong>Sent back by {board.sent_back.by}:</strong> {board.sent_back.reason}</p> : null}
      {error ? <p role="alert">{error}</p> : null}

      <StarterBanner board={board} busy={busy} onAccept={() => void acceptStarter()} onAsk={askStarter} onSend={() => void sendStarter()} />

      {board.can.approve ? (
        <section aria-label="Waiting for your approval" className="ds-card b7-panel b8-tools b7-approve" style={{ padding: 16, margin: "8px 0" }}>
          <span className="ds-eyebrow" data-tone="amber">WAITING FOR YOUR APPROVAL</span>
          <h3 className="ds-serif" style={{ margin: "4px 0 6px", fontSize: 24 }}>Approve the dashboard before it goes to the council</h3>
          {builder ? <p style={{ margin: "0 0 6px" }}>{builder} built it, so someone else signs it off. It came to you because you can approve it.</p> : null}
          {rv?.submitted_by ? <p className="ds-muted" style={{ margin: "0 0 10px" }}>Before this: {builder ? `${builder} built the dashboard with Lumen. ` : ""}{rv.submitted_by} sent it for approval{rv.submitted_at ? ` on ${day(rv.submitted_at)}${time(rv.submitted_at) ? ` at ${time(rv.submitted_at)}` : ""}` : ""}.</p> : null}
          <p>Check the preview below, which uses the live figures, and the sources of each widget.</p>
          <ul aria-label="Widgets and where they read">
            {items.map((i) => <li key={i.id}>{i.title}: {i.kind === "note" ? "a text note" : `reads ${(i.reads ?? []).join(", ") || "Not available yet"}`}</li>)}
          </ul>
          {rv ? (
            <div aria-label="What Lumen checked" role="group" className="b7-checks">
              <h4 style={{ margin: "12px 0 6px" }}>What Lumen checked</h4>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
                {rv.checks.map((c) => (
                  <li key={c.title} data-ok={c.ok === null ? "unknown" : String(c.ok)} style={{ display: "grid", gridTemplateColumns: "22px 1fr", gap: 8 }}>
                    <span aria-hidden="true">{c.ok === true ? "✓" : c.ok === false ? "!" : "–"}</span>
                    <span><strong>{c.title}</strong>{c.ok === null ? <span className="ds-muted"> · not checked</span> : null}<br /><span className="ds-muted">{c.detail}</span></span>
                  </li>))}
              </ul>
            </div>) : null}
          <label style={{ display: "block", marginTop: 12 }}>Note to {builder?.split(" ")[0] || "the maker"} (needed only if you send it back)
            <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={2} style={{ display: "block", width: "100%" }} /></label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "8px 0" }}>
            <Button variant="primary" disabled={busy} onClick={() => void run(() => api.approveStudio(projectId, board.id))}>Approve</Button>
            <Button disabled={busy || !reason.trim()} onClick={() => void run(async () => { await api.sendBack(projectId, board.id, reason); setReason(""); await load(); return null; })}>Send back</Button>
          </div>
          <p className="ds-muted" style={{ margin: 0 }}>Approving lets {builder?.split(" ")[0] || "the maker"} choose where it is delivered. It does not send anything yet.</p>
        </section>) : null}
      {board.status === "submitted" && !board.can.approve ? <p className="ds-muted" role="status">This dashboard is waiting for the head of data or the sponsor. It cannot be changed until they approve it or send it back.</p> : null}

      {(edit || (board.status === "submitted" && !board.can.approve)) ? (
        <div role="toolbar" aria-label="Draft actions" className="b7-topbar">
          <Pill tone={TONE[board.status]}>{STATUS_WORDS[board.status]} · step {step}</Pill>
          <Button disabled={busy || !edit} onClick={() => void undo()}>Undo</Button>
          <Button aria-pressed={drawer} onClick={() => setDrawer((o) => !o)}>History</Button>
          {board.status === "draft" && !board.published_version && edit ? <Button disabled={busy} onClick={remove}>Discard draft</Button> : null}
          <Button variant="primary" disabled={busy || !board.can.submit} onClick={() => void run(() => api.submitStudio(projectId, board.id))}>Send for approval</Button>
        </div>) : null}
      {drawer ? <HistoryDrawer pid={projectId} did={board.id} canWithdraw={board.status === "submitted" && !board.can.approve} canDiscard={board.status === "draft" && !board.published_version && edit}
        onChanged={() => void reload()} onDiscard={remove} onClose={() => setDrawer(false)} /> : null}

      {panel === "sketch" ? <section aria-label="Build from a sketch" className="b7-panel" style={{ margin: "12px 0" }}>
        <SketchPanel pid={projectId} did={board.id} onChanged={() => void reload()} /></section> : null}
      <div className="b7-three" data-edit={edit}>
        {edit ? <section id="b7-talk" aria-label="Talk to Lumen" className="b7-panel b8-tools b7-chat">
            <h3 style={{ marginTop: 0 }}>Talk to Lumen</h3>
            <ChatHead busy={busy} known={known} onFresh={turns.length ? () => void freshTalk() : undefined} />
            <p className="ds-muted" role="status" style={{ margin: "4px 0" }}>{selectedItem ? `About this chart: ${selectedItem.title}. Your next message changes it.` : "Ask for a figure, or change the last one (\"make it dots\", \"in SGD\"). Lumen puts it on the canvas at once; Undo takes it back."}</p>
            <ChatLog busy={busy} turns={turns} intro="Tell me the figures you want and how they should look, in words or with a picture. I put them on the canvas at once, from the figures this project has; say what to change, or Undo.">
              {board.tiles.filter((t) => t.state === "proposed" && !t.starter).map((t) => (
                <TileCard key={t.id} pid={projectId} did={board.id} tile={{ id: t.id, title: t.title, kpi: t.kpi ?? "", sql: "", spec: t.spec, note: t.note ?? "", state: "proposed" }}
                  load={() => api.studioTileData(projectId, board.id, t.id)} onDecide={(how) => void (how === "accept" ? accept(t.id) : reject(t.id))} />))}
            </ChatLog>
            <PictureBox pic={pic} setPic={setPic} noFigures={noFigures} setNoFigures={setNoFigures} />
            <Composer agent="Lumen" text={ask} setText={setAsk} files={askFiles} setFiles={setAskFiles} busy={busy} placeholder="Add cash by entity as bars"
              onSend={(t) => void askLumen(t)} onEmpty={() => setAskNote("Type what you want, for example: cash by entity as bars")} />
            {askNote ? <p role="status" className="ds-muted">{askNote}</p> : null}
          </section> : null}

        <div className="b7-canvas">
          <Canvas pid={projectId} did={board.id} layout={board.layout} editable={edit} load={(tid) => api.studioTileData(projectId, board.id, tid)}
            slot={slot} onSlot={(s) => { setSlot(s); setSelected(null); }} selected={selected} onSelect={setSelected}
            onChange={(its) => void send(its)} onRemove={(id) => void send(items.filter((i) => i.id !== id))} onProblem={setError} />
          {!items.length ? <p className="ds-muted">The grid is empty. Click &quot;Add a widget here&quot;, then choose what goes in it.</p> : null}
          {edit ? <p className="b7-rows">
            <Button disabled={busy || rows >= 40} onClick={() => void send(items, {}, rows + 1)}>Add a row</Button>{" "}
            <Button disabled={busy || !lastEmpty} onClick={() => void send(items, {}, rows - 1)}>Remove the last row</Button></p> : null}
        </div>
        {edit ? (
          <div className="b7-right">
          <section aria-label="Inspector" className="b7-panel b8-tools">
            <h3 style={{ marginTop: 0 }}>This chart</h3>
            {selectedItem ? <>
              <Inspector pid={projectId} did={board.id} item={selectedItem} onChanged={() => void reload()} />
              {selectedItem.tile ? <Button aria-pressed={panel === "options"} onClick={() => setPanel(panel === "options" ? null : "options")}>Show me 3 options</Button> : null}{" "}
            </> : <p className="ds-muted">Click a chart on the canvas to change it here.</p>}
            <Button aria-pressed={panel === "checks"} onClick={() => setPanel(panel === "checks" ? null : "checks")}>Checks</Button>{" "}
            <Button aria-pressed={panel === "sketch"} onClick={() => setPanel(panel === "sketch" ? null : "sketch")}>Build from a sketch</Button>
            {panel === "options" && selectedItem?.tile ? <OptionsPanel pid={projectId} did={board.id} tid={selectedItem.tile} onChanged={() => void reload()} /> : null}
            {panel === "checks" ? <ChecksPanel pid={projectId} did={board.id} onChanged={() => void reload()} /> : null}
          </section>
          <aside aria-label="Widget library" className="b7-panel b8-tools">
            <h3 style={{ marginTop: 0 }}>Widget library</h3>
            <p className="ds-muted" role="status">{selectedItem ? `Selected: ${selectedItem.title}.` : slot ? `Slot chosen: row ${slot.row + 1}, column ${slot.col + 1}.` : "Choose an empty slot on the grid."}</p>
            <div role="group" aria-label="Widget types" style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {board.library.kinds.map((k) => <Button key={k} aria-pressed={kind === k} onClick={() => setKind(k)}>{KIND_WORDS[k] ?? k}</Button>)}
            </div>
            {kind === "note"
              ? <label style={{ display: "block", marginTop: 8 }}>Note <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} style={{ display: "block", width: "100%" }} /></label>
              : <label style={{ display: "block", marginTop: 8 }}>Reads this table
                  <select value={table} onChange={(e) => setTable(e.target.value)} style={{ display: "block", width: "100%" }}>
                    {board.library.tables.map((t) => <option key={t.name} value={t.name}>{t.label}</option>)}</select></label>}
            {kind !== "note" && !board.library.tables.length ? <p className="ds-muted">This project has no figures yet. Build produces them once the plan is approved and has run.</p> : null}
            <p><Button variant="primary" disabled={busy || !slot} onClick={() => void add()}>Add widget to the slot</Button></p>

            <h4>Lumen&apos;s tiles for this project</h4>
            {board.library.lumen.length ? <ul style={{ paddingLeft: 16 }}>{board.library.lumen.map((t) => (
              <li key={t.dashboard_id + t.tile_id}>{t.title} <span className="ds-muted">suggested{t.reads.length ? `, reads ${t.reads.join(", ")}` : ""}</span>{" "}
                <Button disabled={busy || !slot} onClick={() => void place(t)}>Place in the slot</Button></li>))}</ul>
              : board.tiles.some((t) => t.starter)
                ? <p className="ds-muted">Lumen&apos;s starter tiles are on the grid: {board.tiles.filter((t) => t.starter).map((t) => t.title).join("; ")}. Take one off the grid and it comes back here.</p>
                : <p className="ds-muted">Lumen has not suggested any tiles for this project yet. Ask below.</p>}

            <h4>This dashboard</h4>
            <label style={{ display: "block" }}>Title <input defaultValue={board.title} key={board.title} onBlur={(e) => { if (e.target.value.trim() && e.target.value !== board.title) void send(items, { title: e.target.value }); }} /></label>
            <label style={{ display: "block" }}><input type="checkbox" checked={board.company_wide} onChange={(e) => void send(items, { company_wide: e.target.checked })} /> Show under Company reports once published</label>
            {!board.can.submit && board.status === "published" ? <p className="ds-muted">Published. Change anything and a new draft version starts; Consume keeps showing this one until the new one is approved.</p> : null}
          </aside></div>) : null}
      </div>
      </div>
    </PageFrame>
  );
}
