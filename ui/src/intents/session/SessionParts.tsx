import { useEffect, useRef, useState, type ReactNode } from "react";

import { Button, Chip } from "../../design";
import { problemText } from "../../modules/m1_intent/board/usePolled";
import { brainstorm, type Group, type Idea, type Sess } from "./brainstormApi";
import { bsCopy as t, mmss } from "./brainstormCopy";

// The parts of the Brainstorm screens (spec 36). They reuse the wall's card styles (wall.css) and its "Are you sure?" pattern.

export function Ask({ label, question = t.sure, onYes, variant = "secondary" }: { label: string; question?: string; onYes: () => void; variant?: "primary" | "secondary" }) {
  const [sure, setSure] = useState(false);
  if (!sure) return <Button variant={variant} onClick={() => setSure(true)}>{label}</Button>;
  return (
    <div role="alertdialog" aria-label={question} className="ds-stagebar__sure">
      <span>{question}</span>
      <Button variant="primary" onClick={() => { setSure(false); onYes(); }}>{t.yes}</Button>
      <Button onClick={() => setSure(false)}>{t.no}</Button>
    </div>
  );
}

/** The phase clock: the server decides the time, this counts down between polls. */
export function PhaseClock({ seconds, paused }: { seconds: number | null | undefined; paused: boolean }) {
  const at = useRef(Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => { at.current = Date.now(); setNow(Date.now()); }, [seconds]);
  useEffect(() => { const i = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(i); }, []);
  if (seconds === null || seconds === undefined) return <span className="bs-clock bs-clock--none">{t.clockNone}</span>;
  const left = paused ? seconds : seconds - Math.floor((now - at.current) / 1000);
  return <span role="timer" aria-label="Time left in this phase" className={`bs-clock${left <= 0 ? " bs-clock--over" : ""}`}>{mmss(left)}</span>;
}

export function PhaseStrip({ phase }: { phase: string }) {
  const order = ["diverge", "group", "converge"];
  const at = order.indexOf(phase);
  return (
    <div>
      <ol aria-label="Phases" className="ds-stagebar__stages">
        {order.map((p, i) => (
          <li key={p} aria-current={i === at ? "step" : undefined}
            className={`ds-stagebar__stage${i === at ? " ds-stagebar__stage--now" : at > i || phase === "closed" ? " ds-stagebar__stage--done" : ""}`}>
            {at > i || phase === "closed" ? "✓ " : ""}{t.phases[p]}
          </li>
        ))}
      </ol>
      <p className="bs-rule">{at < 0 ? t.notOpened : t.rules[phase]}</p>
    </div>
  );
}

/** One field and one button: the idea box before and during the session. Hide my name only where the organiser allowed it. */
export function IdeaBox({ id, sess, onDone, before = false }: { id: string; sess: Sess; onDone: () => void; before?: boolean }) {
  const [text, setText] = useState("");
  const [why, setWhy] = useState("");
  const [showWhy, setShowWhy] = useState(false);
  const [hide, setHide] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const phase = sess.phase;
  if (!before && phase === "converge") return <p className="bs-note" id="idea-box">{t.converging}</p>;
  if (!before && phase === "closed") return <p className="bs-note" id="idea-box">{t.closedBox}</p>;
  if (sess.paused) return <p className="bs-note" id="idea-box">{t.pausedBox}</p>;
  if (sess.role === "observer") return null;
  const send = async () => {
    setBusy(true); setMsg("");
    try {
      await brainstorm.act(id, "idea", { text, why, anonymous: hide });
      setText(""); setWhy(""); setMsg(before ? t.kept : ""); onDone();
    } catch (e) { setMsg(problemText(e)); }
    setBusy(false);
  };
  return (
    <form id="idea-box" className="ds-card bs-box" onSubmit={(e) => { e.preventDefault(); if (text.trim() && !busy) void send(); }}>
      <label htmlFor="bs-idea" className="ds-wall-sr">{t.ideaBox}</label>
      <textarea id="bs-idea" rows={2} maxLength={600} value={text} placeholder={before ? t.ideaFieldPlaceholder : t.ideaPlaceholder} onChange={(e) => setText(e.target.value)} />
      {!before && (showWhy
        ? <><label htmlFor="bs-why">{t.whyField}</label><textarea id="bs-why" rows={2} maxLength={600} value={why} onChange={(e) => setWhy(e.target.value)} /></>
        : <button type="button" className="bs-link" onClick={() => setShowWhy(true)}>{t.say}</button>)}
      {sess.anonymous_allowed && (
        <label className="ds-north__choice"><input type="checkbox" checked={hide} onChange={(e) => setHide(e.target.checked)} /> {t.hideName}. {t.hideNameNote}</label>
      )}
      <div className="bs-row">
        <Button variant="primary" type="submit" disabled={!text.trim() || busy}>{busy ? t.adding : before ? t.addYours : t.add}</Button>
        {msg ? <span role="status" className="bs-note">{msg}</span> : null}
      </div>
    </form>
  );
}

export function IdeaCard({ idea, onOpen, groupName }: { idea: Idea; onOpen: () => void; groupName?: string | null }) {
  return (
    <li className="ds-wall-card bs-idea" data-kind="card">
      <div className="ds-wall-card__body">
        <button type="button" className="bs-idea__text" onClick={onOpen} aria-label={`Open the idea: ${idea.text}`}>{idea.text}</button>
        <small className="ds-wall-card__foot">
          <span>{idea.anonymous ? t.anonymous : idea.mine ? t.you : idea.author ?? t.anonymous}</span>
          <span className="bs-idea__meta">
            {idea.replies.length ? <span>{t.replies(idea.replies.length)}</span> : null}
            {groupName ? <Chip>{groupName}</Chip> : null}
          </span>
        </small>
      </div>
    </li>
  );
}

/** The idea opened over the lane: full words, author, group, the replies and "Build on this". */
export function IdeaPanel({ id, idea, sess, groups, onClose, onChange }: { id: string; idea: Idea; sess: Sess; groups: Group[]; onClose: () => void; onChange: () => void }) {
  const [reply, setReply] = useState("");
  const [hide, setHide] = useState(false);
  const [edit, setEdit] = useState<string | null>(null);
  const [msg, setMsg] = useState("");
  const live = sess.phase === "diverge" || sess.phase === "group";
  const writable = live && !sess.paused && sess.role !== "observer";
  const run = async (fn: () => Promise<unknown>, after?: () => void) => {
    setMsg("");
    try { await fn(); after?.(); onChange(); } catch (e) { setMsg(problemText(e)); }
  };
  return (
    <aside aria-label="Idea" className="ds-card bs-panel">
      <div className="bs-row"><strong>{idea.anonymous ? t.anonymous : idea.author ?? t.anonymous}</strong><Button onClick={onClose}>{t.close}</Button></div>
      {edit === null ? <p className="ds-wall-card__text">{idea.text}</p>
        : <><textarea aria-label={t.edit} rows={3} maxLength={600} value={edit} onChange={(e) => setEdit(e.target.value)} />
          <Button variant="primary" disabled={!edit.trim()} onClick={() => void run(() => brainstorm.act(id, "idea-edit", { id: idea.id, text: edit, why: idea.why }), () => setEdit(null))}>{t.save}</Button></>}
      {idea.why ? <p className="bs-note"><strong>{t.whyField}:</strong> {idea.why}</p> : null}
      <p className="bs-note">{idea.group_name ? <Chip>{idea.group_name}</Chip> : t.notGrouped}</p>
      {sess.phase === "group" && !sess.paused && sess.role !== "observer" ? (
        <label className="bs-note">{t.moveTo}{" "}
          <select aria-label={t.moveTo} value="" onChange={(e) => { if (e.target.value) void run(() => brainstorm.act(id, "move", { id: idea.id, to: e.target.value, name: "A new group" })); }}>
            <option value="">{idea.group_name ?? t.notGrouped}</option>
            {groups.filter((g) => g.id !== idea.group_id).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            <option value="new">{t.newGroup}</option>
          </select>
        </label>
      ) : null}
      <h3>{t.buildOn}</h3>
      {idea.replies.length === 0 ? <p className="bs-note">{t.noReplies}</p> : (
        <ul className="bs-replies">{idea.replies.map((r) => <li key={r.id}><span>{r.text}</span><small>{r.anonymous ? t.anonymous : r.mine ? t.you : r.author}</small></li>)}</ul>
      )}
      {writable ? (
        <form className="bs-box" onSubmit={(e) => { e.preventDefault(); if (reply.trim()) void run(() => brainstorm.reply(id, idea.id, { text: reply, anonymous: hide }), () => setReply("")); }}>
          <textarea aria-label={t.buildOn} rows={2} maxLength={400} value={reply} placeholder={t.buildOnPlaceholder} onChange={(e) => setReply(e.target.value)} />
          {sess.anonymous_allowed ? <label className="ds-north__choice"><input type="checkbox" checked={hide} onChange={(e) => setHide(e.target.checked)} /> {t.hideName}</label> : null}
          <Button variant="primary" type="submit" disabled={!reply.trim()}>{t.buildOnButton}</Button>
        </form>
      ) : null}
      {idea.mine && sess.phase !== "closed" && sess.role !== "observer" && edit === null ? (
        <div className="bs-row"><Button onClick={() => setEdit(idea.text)}>{t.edit}</Button>
          <Ask label={t.withdraw} onYes={() => void run(() => brainstorm.act(id, "idea-withdraw", { id: idea.id }), onClose)} /></div>
      ) : null}
      {msg ? <p role="alert" className="ds-north__error">{msg} <button type="button" className="bs-link" onClick={() => setMsg("")}>{t.retry}</button></p> : null}
    </aside>
  );
}

/** North's groups: name and count, a tap filters or scrolls, rename in the group phase. Cards North has not placed are listed as such. */
export function GroupPanel({ id, sess, active, onPick, onChange }: { id: string; sess: Sess; active: string | null; onPick: (g: string | null) => void; onChange: () => void }) {
  const [renaming, setRenaming] = useState<string | null>(null);
  const [name, setName] = useState("");
  const loose = sess.ideas.filter((i) => !i.group_id).length;
  const rename = async (gid: string) => {
    try { await brainstorm.act(id, "rename", { group_id: gid, name }); setRenaming(null); onChange(); } catch { /* the next poll shows the old name */ }
  };
  return (
    <section aria-label={t.groupsHead} className="bs-groups">
      <h3>{t.groupsHead}</h3>
      {sess.groups.length === 0 ? <p className="bs-note">{t.groupsEmpty}</p> : (
        <ul>
          {sess.groups.map((g) => (
            <li key={g.id}>
              {renaming === g.id ? (
                <form className="bs-row" onSubmit={(e) => { e.preventDefault(); void rename(g.id); }}>
                  <input aria-label={t.rename} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
                  <Button variant="primary" type="submit" disabled={!name.trim()}>{t.save}</Button>
                  <Button onClick={() => setRenaming(null)}>{t.cancel}</Button>
                </form>
              ) : (
                <>
                  <button type="button" className={`bs-group${active === g.id ? " bs-group--on" : ""}`} aria-pressed={active === g.id} onClick={() => onPick(active === g.id ? null : g.id)}>
                    <span>{g.name}</span><span>{g.count}</span>
                  </button>
                  {sess.phase === "group" && !sess.paused && sess.role !== "observer" ? <button type="button" className="bs-link" onClick={() => { setRenaming(g.id); setName(g.name); }}>{t.rename}</button> : null}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
      {loose > 0 && sess.groups.length > 0 ? <p className="bs-note">{loose} {t.notGrouped.toLowerCase()}</p> : null}
      {sess.grouped_by_words ? <p className="bs-note">{t.groupedByWords}</p> : null}
    </section>
  );
}

/** The organiser's controls: one primary button per state, each behind "Are you sure?". */
export function SessionBar({ id, sess, run, children }: { id: string; sess: Sess; run: (act: string, body?: Record<string, unknown>) => void; children?: ReactNode }) {
  const [minutes, setMinutes] = useState(5);
  const ph = sess.phase ?? "not_opened";
  const live = ph === "diverge" || ph === "group";
  const open = ph === "diverge" || ph === "group" || ph === "converge";
  return (
    <nav aria-label={t.barLabel} className="ds-card ds-stagebar bs-bar" data-session={id}>
      {ph === "not_opened" ? <Ask variant="primary" label={t.bar.open} onYes={() => run("open")} /> : null}
      {live && sess.paused ? <Ask variant="primary" label={t.bar.resume} onYes={() => run("resume")} /> : null}
      {live && !sess.paused ? <Ask variant="primary" label={ph === "diverge" ? t.bar.group : t.bar.converge} onYes={() => run("phase", { to: ph === "diverge" ? "group" : "converge" })} /> : null}
      {live && !sess.paused ? <Ask label={t.bar.pause} onYes={() => run("pause")} /> : null}
      {ph === "group" && !sess.paused ? ((sess.ideas_count ?? 0) < 2 ? <Button disabled title={t.addIdeasFirst}>{t.addIdeasFirst}</Button> : <Ask label={t.groupAgain} question={t.groupAgainSure} onYes={() => run("group")} />) : null}
      {open ? (
        <span className="bs-row">
          <label className="ds-wall-sr" htmlFor="bs-min">{t.addTimeLead}</label>
          <select id="bs-min" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>{[5, 10, 15].map((m) => <option key={m} value={m}>{m} min</option>)}</select>
          <Button onClick={() => run("add-time", { minutes })}>{t.bar.time}</Button>
        </span>
      ) : null}
      {open ? <Ask label={t.bar.close} question={t.closeSure} onYes={() => run("close")} /> : null}
      {children}
    </nav>
  );
}
