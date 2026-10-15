import { Component, Suspense, lazy, useMemo, useState, type ComponentType, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import ScreenState from "../../components/ScreenState";
import { Button, Chip } from "../../design";
import { EventsLink } from "./EventsView";
import { ClosedLine, isClosed } from "../PeoplePanel";
import { problemText, usePolled } from "../../modules/m1_intent/board/usePolled";
import "../../modules/m1_intent/wall/wall.css";
import { wallCopy } from "../../modules/m1_intent/wall/copy";
import { brainstorm, type Sess } from "../session/brainstormApi";
import { bsCopy as t, clock, day, until, weekday } from "../session/brainstormCopy";
import { GroupPanel, IdeaBox, IdeaCard, IdeaPanel, PhaseClock, PhaseStrip, SessionBar } from "../session/SessionParts";
import "../session/brainstorm.css";

// The Brainstorm session (spec 36) and its stage view: the invitation, "add your ideas" before the session (spec 35), then one lane of ideas that
// North groups, the group phase, and the hand-over to converge (another card). The wall's own styles and "Are you sure?" pattern are reused.

const CONVERGE = import.meta.glob("../session/Converge.tsx") as Record<string, () => Promise<{ default: ComponentType<{ intentId: string }> }>>;
class Guard extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}
function Converge({ id }: { id: string }) {
  const load = CONVERGE["../session/Converge.tsx"];
  const C = useMemo(() => (load ? lazy(load) : null), [load]);
  const wait = <p className="bs-note">{t.chooseLater}</p>;
  if (!C) return wait;
  return <Guard fallback={wait}><Suspense fallback={<ScreenState state="loading" />}><C intentId={id} /></Suspense></Guard>;
}

function copyText(text: string, say: (s: string) => void) {
  navigator.clipboard?.writeText(text).then(() => say(t.copied), () => say(t.copyFailed)) ?? say(t.copyFailed);
}

function Invitations({ s }: { s: Sess }) {
  const [note, setNote] = useState("");
  const c = s.counts;
  return (
    <section aria-label={t.invitations} className="ds-card bs-side">
      <h3>{t.invitations}</h3>
      {c ? <p>{t.invitedLine(c.total, c.accepted, c.declined)}</p> : null}
      <ul className="bs-replies">{(s.invited ?? []).map((p) => <li key={p.name}><span>{p.name}</span><small>{t.statusWord[p.status] ?? p.status}{p.reason ? `: ${p.reason}` : ""}</small></li>)}</ul>
      {s.message ? (
        <>
          <label htmlFor="bs-msg"><strong>{t.message}</strong></label>
          <textarea id="bs-msg" readOnly rows={6} value={`${s.message.subject}\n\n${s.message.body}`} />
          <div className="bs-row">
            <Button onClick={() => copyText(`${s.message!.subject}\n\n${s.message!.body}`, setNote)}>{t.copyMessage}</Button>
            <Button onClick={() => copyText(s.message!.subject, setNote)}>{t.copySubject}</Button>
            {note ? <span role="status" className="bs-note">{note}</span> : null}
          </div>
        </>
      ) : null}
    </section>
  );
}

/** The invited person's card: the statement, the good outcome, the session and the window, and the answer. */
// On the stage view the invitation card of spec 06 (above this view) holds the statement and the answer; this adds the brainstorm's rows only.
function Invitation({ s, id, onDone, answer }: { s: Sess; id: string; onDone: () => void; answer: boolean }) {
  const [no, setNo] = useState(false);
  const [why, setWhy] = useState("");
  const [msg, setMsg] = useState("");
  const send = async (a: "accept" | "decline") => {
    setMsg("");
    try { await brainstorm.act(id, "answer", { answer: a, reason: why }); onDone(); } catch (e) { setMsg(problemText(e)); }
  };
  return (
    <section aria-label="Invitation" className="bs-invite">
      {answer ? <><p className="bs-note">{s.organiser ? t.invitedHead(s.organiser) : t.invitedHeadNoName}</p>
        <h1 className="ds-wall__title">{s.statement}</h1></> : null}
      {s.context ? <p>{s.context}</p> : null}
      <p>{t.goodOutcome(s.good_outcome ?? "")}</p>
      {s.window ? <p>{t.sessionLine(day(s.session_at), until(s.session_at, s.session_minutes), day(s.window.before), day(s.window.after))}</p> : null}
      {answer ? <div className="bs-row">
        <Button variant="primary" onClick={() => void send("accept")}>{t.accept}</Button>
        <Button onClick={() => setNo(true)}>{t.decline}</Button>
      </div> : null}
      {no ? (
        <form className="bs-box" onSubmit={(e) => { e.preventDefault(); if (why.trim()) void send("decline"); }}>
          <label htmlFor="bs-why-no">{t.declineWhy}</label>
          <input id="bs-why-no" value={why} maxLength={200} onChange={(e) => setWhy(e.target.value)} />
          <Button type="submit" disabled={!why.trim()}>{t.declineSend}</Button>
        </form>
      ) : null}
      {msg ? <p role="alert" className="ds-north__error">{msg}</p> : null}
    </section>
  );
}

/** Before the session: "Add your ideas" (spec 35 Screen D). Others' ideas are never here; the organiser sees counts. */
function Before({ s, id, reload, run }: { s: Sess; id: string; reload: () => void; run: (a: string, b?: Record<string, unknown>) => void }) {
  const [edit, setEdit] = useState<{ id: string; text: string } | null>(null);
  const [msg, setMsg] = useState("");
  const mine = s.ideas;
  const closed = s.state !== "open";
  const save = async (act: string, body: Record<string, unknown>, after?: () => void) => {
    setMsg("");
    try { await brainstorm.act(id, act, body); after?.(); reload(); } catch (e) { setMsg(problemText(e)); }
  };
  return (
    <div className="ds-wall__body">
      <div className="ds-wall__main">
        <h1 className="ds-wall__title">{t.thinkBefore(weekday(s.session_at), s.statement ?? s.title)}</h1>
        {s.context ? <p className="ds-wall__sentence">{s.context}</p> : null}
        <p>{t.goodOutcome(s.good_outcome ?? "")}</p>
        {s.window ? <p className="ds-wall__sentence">{t.sessionLine(day(s.session_at), until(s.session_at, s.session_minutes), day(s.window.before), day(s.window.after))}</p> : null}
        {s.role === "observer" ? <p className="bs-note">{t.accessNote}</p> : (
          <>
            <p className="bs-note">{closed ? t.windowShut : s.ideas_open ? t.windowOpen : t.windowNotYet(day(s.starts))}</p>
            {s.ideas_open && !closed ? <IdeaBox id={id} sess={s} onDone={reload} before /> : null}
            <h2>{t.yours}</h2>
            {mine.length === 0 ? <p className="bs-note">{t.noneYet}</p> : (
              <ul className="ds-wall-lane__cards">
                {mine.map((i) => (
                  <li key={i.id} className="ds-wall-card"><div className="ds-wall-card__body">
                    {edit?.id === i.id ? (
                      <>
                        <textarea aria-label={t.edit} rows={2} maxLength={600} value={edit.text} onChange={(e) => setEdit({ id: i.id, text: e.target.value })} />
                        <div className="bs-row"><Button variant="primary" disabled={!edit.text.trim()} onClick={() => void save("idea-edit", { id: i.id, text: edit.text }, () => setEdit(null))}>{t.save}</Button>
                          <Button onClick={() => setEdit(null)}>{t.cancel}</Button></div>
                      </>
                    ) : (
                      <>
                        <p className="ds-wall-card__text">{i.text}</p>
                        <small className="ds-wall-card__foot"><span>{i.anonymous ? t.anonymous : t.you}</span>
                          <span className="bs-row"><button type="button" className="bs-link" onClick={() => setEdit({ id: i.id, text: i.text })}>{t.edit}</button>
                            <button type="button" className="bs-link" onClick={() => void save("idea-withdraw", { id: i.id })}>{t.takeBack}</button></span></small>
                      </>
                    )}
                  </div></li>
                ))}
              </ul>
            )}
            <p className="bs-note">{t.othersPrivate}</p>
          </>
        )}
        {msg ? <p role="alert" className="ds-north__error">{msg}</p> : null}
      </div>
      {s.role === "organiser" ? (
        <aside className="ds-wall__north bs-aside bs-aside--open">
          <p>{s.prethink && s.prethink.ideas > 0 ? t.prethink(s.prethink.authors, s.prethink.invited, s.prethink.ideas) : t.prethinkNone}</p>
          <SessionBar id={id} sess={s} run={run} />
          <Invitations s={s} />
        </aside>
      ) : null}
    </div>
  );
}

/** The phase timer; in Converge there is none, the count stays open to the end of the time box. */
function Clock({ s }: { s: Sess }) {
  if (s.phase !== "converge") return <PhaseClock seconds={s.remaining_seconds} paused={!!s.paused} />;
  return <span className="bs-clock" data-testid="count-until">{s.ends ? `The count stays open until ${day(s.ends)}, ${clock(s.ends)}.` : t.clockNone}</span>;
}

/** "Decided in <title>": the Decisions made from this brainstorm that the viewer may open. */
function DecidedIn({ s }: { s: Sess }) {
  if (!s.decided_in?.length) return null;
  return <p className="bs-note">{t.decidedIn} {s.decided_in.map((d, i) => <span key={d.id}>{i ? ", " : ""}<Link to={`/centre/intent/${d.id}`}>{d.title}</Link></span>)}</p>;
}

function Projector({ s }: { s: Sess }) {
  const g = s.phase === "group" || s.phase === "converge";
  return (
    <div className="bs-proj">
      <div className="bs-proj__top"><h1>{s.statement ?? s.title}</h1><Clock s={s} /></div>
      <p className="bs-proj__phase"><strong>{t.phases[s.phase ?? ""] ?? ""}</strong> {s.prompts?.[s.phase as "diverge" | "group"]?.text ?? ""}</p>
      <p className="bs-proj__count" data-testid="idea-count">{s.ideas_count ?? 0}</p>
      <p className="bs-note">{t.ideas(s.ideas_count ?? 0)}</p>
      {g ? (s.groups.length === 0 ? <p className="bs-note">{t.notGrouped}</p> : <ul className="bs-proj__groups">{s.groups.map((x) => <li key={x.id}><span>{x.name}</span><span>{x.count}</span></li>)}</ul>) : null}
      <p className="bs-proj__join" data-testid="join-box">{t.joinAt} <strong>{window.location.host}/centre/intent/{s.id}/session</strong></p>
      <p className="bs-proj__foot">{s.paused ? t.paused : t.live}{s.here ? ` · ${t.people(s.here.n, s.here.total)}` : ""}</p>
    </div>
  );
}

export default function SessionView() {
  const { intentId = "", view } = useParams<{ intentId: string; view?: string }>();
  const [params, setParams] = useSearchParams();
  const [projector, setProjector] = useState(params.get("display") === "projector");
  const [mine, setMine] = useState(false);
  const [group, setGroup] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [sheet, setSheet] = useState<"north" | "more" | null>(null);
  const [err, setErr] = useState("");
  const { state, data: s, failure, reload } = usePolled(() => brainstorm.session(intentId, projector ? "projector" : undefined), `bs:${intentId}:${projector}`);

  const run = async (act: string, body: Record<string, unknown> = {}) => {
    setErr("");
    try { await brainstorm.act(intentId, act, body); reload(); } catch (e) { setErr(problemText(e)); }
  };

  if (state === "loading" || (state === "error" && !s)) {
    const notYet = (failure as { status?: number } | null)?.status === 409;
    return <ScreenState state={state === "loading" ? "loading" : notYet ? "empty" : "error"} message={state === "error" ? problemText(failure) : undefined} onRetry={reload} />;
  }
  if (state === "refused") return <ScreenState state="refused" />;
  if (!s) return <ScreenState state="loading" />;

  const card = params.get("card");
  const open = s.ideas.find((i) => i.id === card);
  const org = s.role === "organiser";
  const lane = s.ideas.filter((i) => (!mine || i.mine) && (!group || i.group_id === group));
  const ph = s.phase ?? "not_opened";
  const prompt = ph === "diverge" || ph === "group" ? s.prompts?.[ph] : undefined;

  // W2F2: a closed brainstorm that never ran a session (or that this person never joined) reads as closed: one line, no invitation, no
  // "Open the session". On the stage view the line sits above (StagePanels); the /session route has no panels, so it carries its own.
  if (isClosed(s.state) && s.mode !== "live" && s.mode !== "closed") return view === "session" ? <div className="ds-screen ds-wall"><ClosedLine intentId={intentId} state={s.state} /></div> : null;
  // a participant with no recorded answer is still invited: only a recorded "Declined" reads as declined
  if (s.mode === "invitation" || (s.mode === "declined" && s.my_status !== "Declined")) return <div className="ds-screen ds-wall"><Invitation s={s} id={intentId} onDone={reload} answer={view === "session"} /></div>;
  if (s.mode === "declined") return <div className="ds-screen ds-wall"><p>{t.declined}</p></div>;
  if (projector) return <div className="ds-screen ds-wall ds-wall--projector bs-projector"><Chip tone="active" onClick={() => setProjector(false)}>{t.exitProjector}</Chip><Projector s={s} /></div>;

  const head = (
    <header className="ds-wall__head">
      <p className="ds-wall__crumb">{t.crumbLead}<strong>{s.title}</strong></p>
      <div className="ds-wall__stats">
        {s.mode === "live" || s.mode === "closed" ? <span>{t.ideas(s.ideas_count ?? 0)}</span> : null}
        {s.here ? <span data-testid="participants">{t.people(s.here.n, s.here.total)}</span> : null}
        {s.mode === "live" ? (s.paused ? <span className="ds-wall__when">{t.paused}</span> : <span className="ds-wall__live">{t.live}</span>) : null}
      </div>
    </header>
  );
  if (s.mode === "before") return <div className="ds-screen ds-wall">{head}<DecidedIn s={s} /><Before s={s} id={intentId} reload={reload} run={(a, b) => void run(a, b)} />{err ? <p role="alert" className="ds-north__error">{err}</p> : null}</div>;

  const edited = prompt?.edited_by ? t.editedBy(prompt.edited_by) : t.northSuggests;
  return (
    <div className="ds-screen ds-wall bs-live">
      {head}<EventsLink intentId={intentId} /><DecidedIn s={s} />
      <div className="ds-wall__body">
        <div className="ds-wall__main">
          <div className="bs-statement">
            <p className="ds-wall__sentence">{t.lead}</p>
            <h1 className="ds-wall__title">{s.statement ?? s.title}</h1>
            {s.good_outcome ? <p className="bs-note">{t.goodOutcome(s.good_outcome)}</p> : null}
          </div>
          <div className="bs-strip"><PhaseStrip phase={ph} />{s.mode === "live" ? <Clock s={s} /> : null}</div>
          {prompt ? (
            <div className="ds-card bs-prompt">
              <small className="ds-wall-card__from">{edited}</small>
              {editing === null ? <p>{prompt.text}</p> : (
                <>
                  <textarea aria-label={t.editPrompt} rows={3} maxLength={600} value={editing} onChange={(e) => setEditing(e.target.value)} />
                  <div className="bs-row">
                    <Button variant="primary" disabled={!editing.trim()} onClick={() => { void run("prompt", { phase: ph, text: editing }); setEditing(null); }}>{t.usePrompt}</Button>
                    <Button onClick={() => { void run("prompt", { phase: ph, reset: true }); setEditing(null); }}>{t.resetPrompt}</Button>
                  </div>
                </>
              )}
              {org && editing === null && !s.paused ? <button type="button" className="bs-link" onClick={() => setEditing(prompt.text)}>{t.editPrompt}</button> : null}
            </div>
          ) : null}
          {s.mode === "closed" || ph === "converge" ? <Converge id={intentId} /> : null}
          <div className="ds-wall__tools">
            <Chip tone={mine ? "active" : "default"} onClick={() => setMine(!mine)}>{wallCopy.onlyMine}</Chip>
            {org ? <Chip onClick={() => setProjector(true)}>{wallCopy.projector}</Chip> : null}
            {group ? <Chip tone="active" onClick={() => setGroup(null)}>{s.groups.find((g) => g.id === group)?.name ?? ""} ×</Chip> : null}
          </div>
          <section aria-label="Ideas" className="ds-card ds-wall-lane" data-testid="lane">
            {open ? <IdeaPanel key={open.id} id={intentId} idea={open} sess={s} groups={s.groups} onClose={() => setParams({})} onChange={reload} /> : null}
            <ul className="ds-wall-lane__cards">
              {lane.length === 0 ? <li className="ds-wall-lane__empty">{s.ideas.length === 0 ? t.emptyLane : wallCopy.emptyLane}</li> : null}
              {lane.map((i) => <IdeaCard key={i.id} idea={i} groupName={ph === "group" || ph === "converge" || ph === "closed" ? i.group_name ?? t.notGrouped : null} onOpen={() => setParams({ card: i.id })} />)}
            </ul>
          </section>
          <IdeaBox id={intentId} sess={s} onDone={reload} />
          {err ? <p role="alert" className="ds-north__error">{err} <button type="button" className="bs-link" onClick={() => setErr("")}>{wallCopy.retry}</button></p> : null}
        </div>
        <aside aria-label={t.northHead} className={`ds-wall__north bs-aside${sheet ? " bs-aside--open" : ""}`}>
          {org ? <SessionBar id={intentId} sess={s} run={(a, b) => void run(a, b)} /> : null}
          <div className="ds-north__who"><span className="ds-north__mark" aria-hidden="true">N</span><strong>{t.northHead}<span>{t.northRole}</span></strong></div>
          {(s.north_lines ?? []).map((l) => <p key={l} className="ds-north__turn">{l}</p>)}
          <GroupPanel id={intentId} sess={s} active={group} onPick={setGroup} onChange={reload} />
        </aside>
      </div>
      <div className="bs-bottom">
        {s.can_add ? <Button variant="primary" onClick={() => document.getElementById("idea-box")?.scrollIntoView({ behavior: "smooth" })}>{t.ideaBox}</Button> : null}
        {/* one North: the button opens the intent's North sheet (NorthPanel); the groups stay behind "More" */}
        <Button onClick={() => { setSheet(null); window.dispatchEvent(new Event("north:open")); }}>{t.talk}</Button>
        <Button onClick={() => setSheet(sheet === "more" ? null : "more")}>{sheet === "more" ? t.close : org ? t.more : "Groups"}</Button>
      </div>
    </div>
  );
}
