import { useState } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import { agreeWith, commentOn, tickCluster, voteOn, type NamesRule, type TogetherCluster, type TogetherView, type VoteChoice, type VoteOption } from "../api";
import * as L from "../board/layout";
import { NoteList } from "../board/ClusterPanel";
import { m1Lean, m1Notes, m1Together as t } from "../copy";

interface Props {
  sessionId: string;
  cluster: TogetherCluster;
  options: VoteChoice[];
  /** Voting, agreeing and commenting are open (the room is together and not held). */
  open: boolean;
  organiser: boolean;
  names?: NamesRule;
  onView: (v: TogetherView) => void;
}

/** One group in the room (deck slide 10): its counts, a bar per option with a live tally, agree, a short thread, and the organiser's tick. */
export default function ClusterCard({ sessionId, cluster, options, open, organiser, names = "choice", onView }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [anonymous, setAnonymous] = useState(false);
  const label = (id: VoteOption | null) => options.find((o) => o.id === id)?.label ?? "";

  async function act(work: () => Promise<TogetherView>, fail: string, done?: () => void) {
    setBusy(true);
    setError(null);
    try {
      onView(await work());
      done?.();
    } catch (e) {
      setError(e instanceof ApiError && e.message ? e.message : fail);
    } finally {
      setBusy(false);
    }
  }

  const tick = organiser ? (
    <label style={{ ...L.wrap(6), marginBottom: 0 }}>
      <input
        type="checkbox"
        aria-label={t.tickLabel(cluster.name)}
        checked={cluster.ticked}
        disabled={busy || !open}
        onChange={(e) => void act(() => tickCluster(sessionId, cluster.id, e.target.checked), t.tickFailed)}
      />
      <span>{t.inCharter}</span>
      {cluster.auto_ticked ? <span className="m1-help">{m1Lean.together.byVote}</span> : null}
      {cluster.tie && !cluster.ticked ? <span className="m1-help">{m1Lean.together.tie}</span> : null}
    </label>
  ) : (
    <StatusPill tone={cluster.ticked ? "success" : "muted"}>{cluster.ticked ? t.inCharter : t.carried}</StatusPill>
  );

  return (
    <Panel title={cluster.name} eyebrow={t.counts(cluster.note_count, cluster.agree_count, cluster.comment_count)} actions={tick}>
      <h3>{t.voteTitle}</h3>
      <div role="group" aria-label={`${t.voteTitle}: ${cluster.name}`}>
        {options.map((o) => {
          const n = cluster.votes[o.id];
          const mine = cluster.my_vote === o.id;
          return (
            <div key={o.id} style={L.voteRow}>
              <strong style={L.voteName}>{o.label}</strong>
              <div className="n-room-progress-bar" style={L.voteBar} aria-hidden="true">
                <div className="fill" style={{ width: `${cluster.vote_total > 0 ? Math.round((n / cluster.vote_total) * 100) : 0}%` }} />
              </div>
              <span style={L.voteCount}>{t.votes(n)}</span>
              <button
                type="button"
                className={`n-btn${mine ? " primary" : ""}`}
                aria-pressed={mine}
                aria-label={t.voteOn(o.label, cluster.name)}
                disabled={busy || !open}
                onClick={() => void act(() => voteOn(sessionId, cluster.id, mine ? null : o.id), t.voteFailed)}
              >
                {o.label}
              </button>
            </div>
          );
        })}
      </div>
      <p className="n-muted">{cluster.priority ? t.priority(label(cluster.priority)) : cluster.vote_total > 0 ? t.noPriority : t.voteNone}</p>
      <div className="m1-actions">
        <button
          type="button"
          className={`n-btn${cluster.my_agree ? " primary" : ""}`}
          aria-pressed={cluster.my_agree}
          aria-label={t.agreeLabel(cluster.name)}
          disabled={busy || !open}
          onClick={() => void act(() => agreeWith(sessionId, cluster.id, !cluster.my_agree), t.voteFailed)}
        >
          {t.agree} · {cluster.agree_count}
        </button>
      </div>
      <details>
        <summary>{t.notes}</summary>
        <NoteList notes={cluster.notes} />
      </details>
      <h3>{t.comments}</h3>
      {cluster.comments.length === 0 ? (
        <p className="n-muted">{t.noComments}</p>
      ) : (
        <ul style={L.thread}>
          {cluster.comments.map((c, i) => (
            <li key={i}>
              <strong>{c.anonymous ? t.anonymous : (c.author_name ?? "")}</strong> {c.text}
            </li>
          ))}
        </ul>
      )}
      <form
        style={{ ...L.wrap(10), alignItems: "flex-end" }}
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim() !== "") void act(() => commentOn(sessionId, cluster.id, text, names === "choice" ? anonymous : names === "anonymous"), t.commentFailed, () => setText(""));
        }}
      >
        <label style={L.commentField}>
          {t.commentField}
          <input type="text" value={text} maxLength={300} disabled={!open} onChange={(e) => setText(e.target.value)} />
        </label>
        {names === "choice" ? (
          <label style={{ ...L.wrap(6), marginBottom: 0 }}>
            <input type="checkbox" checked={anonymous} disabled={!open} onChange={(e) => setAnonymous(e.target.checked)} />
            <span>{t.commentAnon}</span>
          </label>
        ) : (
          <span className="m1-help">{names === "named" ? m1Notes.namesNamed : m1Notes.namesAnonymous}</span>
        )}
        <button type="submit" className="n-btn" disabled={busy || !open || text.trim() === ""}>
          {t.commentSend}
        </button>
      </form>
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
    </Panel>
  );
}
