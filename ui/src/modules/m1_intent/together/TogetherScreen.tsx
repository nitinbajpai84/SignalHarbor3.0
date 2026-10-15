import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import AgentChip from "../../../components/AgentChip";
import MessageBubble from "../../../components/MessageBubble";
import PageHead from "../../../components/PageHead";
import ScreenState from "../../../components/ScreenState";
import StatusPill from "../../../components/StatusPill";
import { holdRoom, getTogether, makeCharterDraft, resumeRoom, sayDone, type TogetherView } from "../api";
import { problemText, usePolled } from "../board/usePolled";
import * as L from "../board/layout";
import { m1Companion, m1Together as t } from "../copy";
import { m1Define } from "../define/copy";
import NiraDock from "../NiraDock"; // M1-UI2
import StageTimer from "../timer/StageTimer";
import ClusterCard from "./ClusterCard";

/**
 * Stage 7, back in the room (deck slide 10): every group with its note count, a vote bar per option with a live tally,
 * agree marks and a short thread; the organiser ticks groups into the charter, and can hold the room when Nira asks.
 */
export default function TogetherScreen({ sessionId: given }: { sessionId?: string } = {}) {
  const params = useParams();
  const sessionId = given ?? params.sessionId ?? "";
  const room = usePolled(() => getTogether(sessionId), `together:${sessionId}`);
  const notYet = room.failure instanceof ApiError && room.failure.status === 409;
  const v = room.data;
  return (
    <>
      <PageHead
        title={t.title}
        eyebrow={t.eyebrow}
        sub={v ? t.summary(v.clusters.length, v.ticked_count) : undefined}
        actions={v ? <StatusPill tone={v.held ? "warning" : "info"}>{v.held ? t.heldStage : t.stage}</StatusPill> : undefined}
      />
      {notYet ? (
        <p role="status" className="state n-muted">
          {t.notYet}
        </p>
      ) : (
        <ScreenState state={room.state} onRetry={room.reload} message={room.state === "error" ? problemText(room.failure) : undefined}>
          {v ? <Room sessionId={sessionId} view={v} put={room.put} reload={room.reload} /> : null}
        </ScreenState>
      )}
      <NiraDock
        sessionId={sessionId}
        stage="together"
        actions={[{ label: m1Companion.actions.toCharter, to: `/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/charter` }]}
      />
    </>
  );
}

function Room({ sessionId, view, put, reload }: { sessionId: string; view: TogetherView; put: (v: TogetherView) => void; reload: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const navigate = useNavigate();
  const open = view.can_vote && !view.held;
  async function hold(on: boolean) {
    setBusy(true);
    setError(null);
    try {
      await (on ? holdRoom(sessionId) : resumeRoom(sessionId));
      reload();
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : t.holdFailed);
    } finally {
      setBusy(false);
    }
  }
  // Ending early is the charter draft: the same call that moves the room from together to signing, never a second path.
  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await makeCharterDraft(sessionId, true); // the screen has asked about open groups already
      navigate(`/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/charter`);
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : t.finishFailed);
      setAsking(false);
    } finally {
      setBusy(false);
    }
  }
  async function done(on: boolean) {
    setBusy(true);
    setError(null);
    try {
      put(await sayDone(sessionId, on));
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : t.doneFailed);
    } finally {
      setBusy(false);
    }
  }
  const decided = view.clusters.length > 0 && view.open_count === 0;
  const canFinish = view.organiser && !view.held;
  const nira = view.held
    ? view.organiser ? t.niraHeld : t.niraGuestHeld
    : view.organiser ? (decided ? t.niraDecided(view.ticked_count) : t.niraAsk(view.ticked_count, view.open_count)) : t.niraGuest(view.ticked_count, view.open_count);
  const finishClick = () => (view.open_count > 0 ? setAsking(true) : void finish());
  return (
    <>
      <StageTimer sessionId={sessionId} />
      <p><Link className="n-btn" to={`/modules/m1_intent/define/${encodeURIComponent(sessionId)}`}>{m1Define.openShelves}</Link></p>
      <div style={{ ...L.column(10), ...L.gap }}>
        <AgentChip name="Nira" status={view.held ? "waiting" : "idle"} />
        <MessageBubble from="agent" who={t.niraName} text={nira}>
          {view.organiser ? (
            <div className="m1-actions">
              {decided && canFinish ? (
                <button type="button" className="n-btn primary" disabled={busy} onClick={finishClick}>
                  {t.finishNow}
                </button>
              ) : null}
              <button type="button" className={decided && canFinish ? "n-btn" : "n-btn primary"} disabled={busy} onClick={() => void hold(!view.held)}>
                {view.held ? t.resume : t.hold}
              </button>
            </div>
          ) : null}
        </MessageBubble>
        {canFinish && !decided ? (
          asking ? (
            <div role="alertdialog" aria-label={t.finishSure(view.open_count)} className="m1-actions">
              <span>{t.finishSure(view.open_count)}</span>
              <button type="button" className="n-btn primary" disabled={busy} onClick={() => void finish()}>
                {t.finishYes}
              </button>
              <button type="button" className="n-btn" onClick={() => setAsking(false)}>
                {t.finishNo}
              </button>
            </div>
          ) : (
            <div className="m1-actions">
              <button type="button" className="n-btn" disabled={busy} onClick={finishClick}>
                {t.finishButton}
              </button>
            </div>
          )
        ) : null}
        {view.organiser && view.people_count > 0 ? <p role="status" className="n-muted">{t.doneCount(view.done_count, view.people_count)}</p> : null}
        {!view.organiser && open ? (
          <div className="m1-actions">
            <button type="button" className="n-btn" aria-pressed={view.i_done} disabled={busy} onClick={() => void done(!view.i_done)}>
              {view.i_done ? t.notDone : t.imDone}
            </button>
          </div>
        ) : null}
        {error ? (
          <p role="alert" className="state state-error">
            {error}
          </p>
        ) : null}
        {view.held ? <p role="status" className="n-muted">{t.heldCannot}</p> : null}
      </div>
      {view.clusters.length === 0 ? (
        <div className="n-empty">
          <p className="ebody">{t.empty}</p>
        </div>
      ) : (
        <div style={L.column(14)}>
          {view.clusters.map((c) => (
            <ClusterCard key={c.id} sessionId={sessionId} cluster={c} options={view.options} open={open} organiser={view.organiser} names={view.names} onView={put} />
          ))}
        </div>
      )}
      {view.on_its_own_count > 0 ? <p className="n-muted">{t.alone(view.on_its_own_count)}</p> : null}
    </>
  );
}
