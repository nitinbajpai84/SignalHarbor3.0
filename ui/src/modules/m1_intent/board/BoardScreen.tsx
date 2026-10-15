import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import AgentChip from "../../../components/AgentChip";
import MessageBubble from "../../../components/MessageBubble";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { shellCopy } from "../../../components/shellCopy";
import { copy } from "../../../copy";
import {
  addCluster, closeRooms, getBoard, getBoardCounts, groupNotes, moveNote, renameCluster, restoreGrouping, splitCluster, startTogether,
  type BoardNote, type BoardView,
} from "../api";
import { m1Board as t } from "../copy";
import NiraDock from "../NiraDock"; // M1-UI2
import StageTimer from "../timer/StageTimer";
import ClusterPanel, { NoteList } from "./ClusterPanel";
import * as L from "./layout";
import { problemText, usePolled } from "./usePolled";

interface Props {
  sessionId?: string;
  /** Called when the room has come back together (a guest's page moves on by itself; a route page just reloads). */
  onTogether?: () => void;
}

/**
 * Stage 6, the brainstorm board (deck slide 9). While the rooms are open the organiser sees counts only; when they
 * close, everyone sees the notes, grouped by North, with the organiser able to move a note, rename a group or split one.
 */
export default function BoardScreen({ sessionId: given, onTogether }: Props = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? "";
  const board = usePolled(() => getBoard(sessionId), `board:${sessionId}`);
  const notYet = board.failure instanceof ApiError && board.failure.status === 409;
  return (
    <>
      <PageHead title={t.title} eyebrow={t.eyebrow} sub={board.data ? t.summary(board.data.counts.notes, board.data.counts.clusters, board.data.counts.on_its_own) : undefined}
        actions={<StatusPill tone="info">{t.stageLabel}</StatusPill>} />
      {notYet ? (
        <WaitingRooms sessionId={sessionId} onClosed={board.reload} />
      ) : (
        <ScreenState state={board.state} onRetry={board.reload} message={board.state === "error" ? problemText(board.failure) : undefined}>
          {board.data ? <Board sessionId={sessionId} view={board.data} put={board.put} onTogether={onTogether} /> : null}
        </ScreenState>
      )}
      <NiraDock sessionId={sessionId} stage="board" />
    </>
  );
}

/** The rooms are open: the organiser's live counts and the way to close them; everyone else is told when the board comes. */
function WaitingRooms({ sessionId, onClosed }: { sessionId: string; onClosed: () => void }) {
  const counts = usePolled(() => getBoardCounts(sessionId), `counts:${sessionId}`);
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function close() {
    setBusy(true);
    setError(null);
    try {
      await closeRooms(sessionId);
      onClosed();
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : t.closeFailed);
    } finally {
      setBusy(false);
      setAsking(false);
    }
  }
  const c = counts.data;
  return (
    <>
      <StageTimer sessionId={sessionId} />
      <Panel title={t.waitingTitle} eyebrow={t.eyebrow}>
        {c ? (
          <>
            <p role="status" style={L.bigCount}>
              {t.counts(c.submitted, c.drafts, c.people_with_drafts)}
            </p>
            <p className="n-muted">{t.waitingHelp}</p>
            {asking ? (
              <div role="alertdialog" aria-label={t.closeSure} className="m1-actions">
                <span>{t.closeSure}</span>
                <button type="button" className="n-btn primary" disabled={busy} onClick={() => void close()}>
                  {t.closeYes}
                </button>
                <button type="button" className="n-btn" onClick={() => setAsking(false)}>
                  {t.closeNo}
                </button>
              </div>
            ) : (
              <button type="button" className="n-btn primary" onClick={() => setAsking(true)}>
                {t.close}
              </button>
            )}
          </>
        ) : (
          <p className="state n-muted">{t.notYet}</p>
        )}
        {error ? (
          <p role="alert" className="state state-error">
            {error}
          </p>
        ) : null}
      </Panel>
    </>
  );
}

function Board({ sessionId, view, put, onTogether }: { sessionId: string; view: BoardView; put: (v: BoardView) => void; onTogether?: () => void }) {
  const [mode, setMode] = useState<"grouped" | "raw">("grouped");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [newName, setNewName] = useState("");
  // the four kinds of note are kept apart: one tab for each, and "all" shows every kind
  const [kind, setKind] = useState<string>("all");
  const kinds = view.kinds ?? [];
  const inKind = (n: BoardNote) => kind === "all" || (n.kind ?? "intent") === kind;
  const clusters = view.clusters
    .map((c) => ({ ...c, notes: c.notes.filter(inKind) }))
    .filter((c) => kind === "all" || c.notes.length > 0 || c.note_ids.length === 0);
  const alone = view.on_its_own.filter(inKind);
  const kindName = (k: string | null | undefined) => (k === "mixed" ? t.kindMixed : kinds.find((x) => x.id === k)?.heading);
  const asked = useRef(false);
  const editable = view.can_edit;

  async function run(work: () => Promise<BoardView | { state: string }>, fail: string) {
    setBusy(true);
    setError(null);
    try {
      const r = await work();
      if ("clusters" in r) put(r);
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : fail);
    } finally {
      setBusy(false);
    }
  }
  const group = () => run(() => groupNotes(sessionId), copy.states.error);

  // the organiser's screen asks North to group, once, the first time the board is open
  useEffect(() => {
    if (view.organiser && view.stage === "board" && view.status === "none" && !asked.current) {
      asked.current = true;
      void group();
    }
  }, [view.organiser, view.stage, view.status]);

  const together = () =>
    run(async () => {
      await startTogether(sessionId);
      onTogether?.();
      return { state: "together" };
    }, t.togetherFailed);

  const grouping = view.status === "none" && view.organiser && busy;
  const aloneCount = view.counts.on_its_own;
  const grouped = view.counts.notes - aloneCount;
  return (
    <>
      <div style={{ ...L.column(10), ...L.gap }}>
        <AgentChip name="North" status={grouping ? "thinking" : view.status === "failed" ? "blocked" : "idle"} />
        {view.counts.notes === 0 ? (
          <p className="n-muted">{t.empty}</p>
        ) : view.status === "none" ? (
          <p role="status" className="n-muted">
            {t.grouping}
          </p>
        ) : view.status === "failed" ? (
          <MessageBubble from="agent" who={t.north} text={t.failed}>
            {view.organiser ? (
              <button type="button" className="n-btn" disabled={busy} onClick={() => void group()}>
                {t.retry}
              </button>
            ) : null}
          </MessageBubble>
        ) : (
          <MessageBubble from="agent" who={t.north} tags={[shellCopy.suggestion]} text={(view.edited ? t.editedLine(view.counts.clusters, aloneCount) : t.groupedLine(grouped, view.counts.clusters, aloneCount)) + (editable ? ` ${t.dragHelp}` : "")} />
        )}
      </div>
      {view.grouped_without_north ? (
        <div className="m1-actions" role="status">
          <span>{t.withoutNorth}</span>
          {view.organiser ? (
            <button type="button" className="n-btn" disabled={busy} onClick={() => void group()}>
              {t.regroup}
            </button>
          ) : null}
        </div>
      ) : null}
      {view.paused_from ? <p role="status" className="state n-muted">{t.held}</p> : null}
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      {view.counts.notes > 0 ? (
        <div className="m1-actions" style={L.gap} role="group" aria-label={t.viewSwitch}>
          <button type="button" className={`n-btn${mode === "grouped" ? " primary" : ""}`} aria-pressed={mode === "grouped"} onClick={() => setMode("grouped")}>
            {t.viewGrouped}
          </button>
          <button type="button" className={`n-btn${mode === "raw" ? " primary" : ""}`} aria-pressed={mode === "raw"} onClick={() => setMode("raw")}>
            {t.viewRaw}
          </button>
        </div>
      ) : null}
      {kinds.length > 0 && view.counts.notes > 0 ? (
        <div className="m1-actions" style={L.gap} role="group" aria-label={t.kindFilter}>
          <button type="button" className={`n-btn${kind === "all" ? " primary" : ""}`} aria-pressed={kind === "all"} onClick={() => setKind("all")}>
            {t.kindCount(t.kindAll, view.counts.notes)}
          </button>
          {kinds.map((k) => (
            <button key={k.id} type="button" className={`n-btn${kind === k.id ? " primary" : ""}`} aria-pressed={kind === k.id} onClick={() => setKind(k.id)}>
              {t.kindCount(k.heading, view.by_kind?.[k.id] ?? 0)}
            </button>
          ))}
        </div>
      ) : null}
      {kind !== "all" && clusters.length === 0 && alone.length === 0 && view.counts.notes > 0 ? <p className="n-muted">{t.kindNone}</p> : null}
      {mode === "raw" ? (
        <Panel title={t.viewRaw} eyebrow={t.noteCount(view.counts.notes)}>
          <NoteList notes={[...clusters.flatMap((c) => c.notes), ...alone]} />
        </Panel>
      ) : (
        <div className="m1-cluster-grid" style={L.clusterGrid}>
          {clusters.map((c) => (
            <ClusterPanel
              key={c.id}
              cluster={c}
              kindName={kind === "all" ? kindName(c.kind) : undefined}
              clusters={view.clusters}
              editable={editable}
              busy={busy}
              onMove={(noteId, to) => void run(() => moveNote(sessionId, noteId, to), copy.states.error)}
              onRename={(name) => run(() => renameCluster(sessionId, c.id, name), copy.states.error)}
              onSplit={(ids) => run(() => splitCluster(sessionId, c.id, ids), copy.states.error)}
            />
          ))}
          {view.counts.notes > 0 ? (
            <ClusterPanel
              own
              cluster={{ id: "own", name: t.onItsOwn, source: "north", reasoning: "", note_ids: alone.map((n) => n.id), notes: alone }}
              clusters={view.clusters}
              editable={editable}
              busy={busy}
              onMove={(noteId, to) => void run(() => moveNote(sessionId, noteId, to), copy.states.error)}
            />
          ) : null}
        </div>
      )}
      {view.organiser && editable ? (
        <form
          className="m1-actions"
          style={{ marginTop: 18 }}
          onSubmit={(e) => {
            e.preventDefault();
            const name = newName.trim();
            if (name) void run(() => addCluster(sessionId, name), copy.states.error).then(() => setNewName(""));
          }}
        >
          <input type="text" maxLength={80} aria-label={t.clusterName} placeholder={t.clusterName} value={newName} onChange={(e) => setNewName(e.target.value)} />
          <button type="submit" className="n-btn" disabled={busy || !newName.trim()}>
            {t.makeCluster}
          </button>
          <span className="n-muted">{t.makeClusterHelp}</span>
        </form>
      ) : null}
      {view.organiser ? (
        <div className="m1-actions" style={{ marginTop: 18 }}>
          {view.can_restore ? (
            restoring ? (
              <div role="alertdialog" aria-label={t.restoreSure} className="m1-actions">
                <span>{t.restoreSure}</span>
                <button
                  type="button"
                  className="n-btn primary"
                  disabled={busy}
                  onClick={() => void run(() => restoreGrouping(sessionId), copy.states.error).then(() => setRestoring(false))}
                >
                  {t.restoreYes}
                </button>
                <button type="button" className="n-btn" onClick={() => setRestoring(false)}>
                  {t.closeNo}
                </button>
              </div>
            ) : (
              <button type="button" className="n-btn" disabled={busy || !editable} onClick={() => setRestoring(true)}>
                {t.restore}
              </button>
            )
          ) : null}
          {view.stage === "board" && view.status !== "none" ? (
            <>
              <button type="button" className="n-btn primary" disabled={busy} onClick={() => void together()}>
                {t.toTogether}
              </button>
              <span className="n-muted">{t.toTogetherHelp}</span>
            </>
          ) : null}
        </div>
      ) : (
        <p className="n-muted">{t.readOnly}</p>
      )}
    </>
  );
}
