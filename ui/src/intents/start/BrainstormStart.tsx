import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError, apiGet } from "../../api/client";
import AgentChip from "../../components/AgentChip";
import MessageBubble from "../../components/MessageBubble";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { Button, Chip } from "../../design";
import AreaPicker from "../AreaPicker";
import "../session/brainstorm.css";
import type { StartProps } from "../IntentNew";
import { brainstorm, type Answers, type Draft, type Message, type PeopleAnswer, type Related } from "../session/brainstormApi";
import { clock, day, until } from "../session/brainstormCopy";
import { STEPS, bsStart as c } from "./BrainstormStartCopy";

// The Brainstorm's five start questions, "Already being thought about", the people picker, the three-day window and the open (spec 35).
// Answers save to the draft as they are given (POST /session/draft); the open validates the five answers and writes the intent open (POST /session/launch).

type Step = (typeof STEPS)[number]["key"] | "review";
/** 57: answers North filled from an opportunity's hypothesis; each stays guessed while it equals what North wrote. */
type Carried = { from: string; values: Partial<Pick<Answers, "statement" | "context" | "good_outcome" | "areas">> };
const guessed = "Guessed by North";
const carriedLine = (src: string) => `${src}. North filled the answers it could from its hypothesis; each stays Guessed by North until you change it.`;
const LIMITS = { statement: 200, context: 1000, outcome: 300 };

const ymd = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s: string) => { const [y, m, d] = s.split("-").map(Number); return new Date(y!, m! - 1, d!); };
const shift = (d: Date, by: 1 | -1) => { const n = new Date(d); do { n.setDate(n.getDate() + by); } while (n.getDay() === 0 || n.getDay() === 6); return n; };
/** The three working days around a session date: the day before for ideas, the session, the day after. */
export const windowOf = (iso: string) => ({ before: ymd(shift(parse(iso), -1)), session: iso, after: ymd(shift(parse(iso), 1)) });
export const earliest = (today = new Date()) => ymd(shift(today, 1));
export const dateOk = (iso: string | undefined, today = new Date()): boolean => !!iso && /^\d{4}-\d{2}-\d{2}$/.test(iso) && parse(iso).getDay() % 6 !== 0 && iso >= earliest(today);

/** The first missing answer in plain words (the same five checks the open makes), or "" when all are valid. */
export function firstMissing(a: Answers): string {
  if (!a.statement?.trim()) return "Say what the idea or the problem is.";
  if (!a.good_outcome?.trim()) return "Say what a good outcome would look like.";
  const n = a.people?.length ?? 0;
  if (n < 4 || n > 8) return c.picked(n);
  if (!a.areas?.length) return "Pick at least one area.";
  if (!dateOk(a.session_date) || !a.session_time) return c.dateBad;
  if (!a.session_minutes) return "Pick 45 or 60 minutes.";
  return "";
}

export function BrainstormStart({ draftId }: StartProps) {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const [a, setA] = useState<Answers | null>(null);
  const [failed, setFailed] = useState(false);
  const [error, setError] = useState("");
  const [related, setRelated] = useState<Related[] | "off" | null>(null);
  const [checked, setChecked] = useState("");
  const [people, setPeople] = useState<PeopleAnswer | null>(null);
  const [more, setMore] = useState(false);
  const [peopleFailed, setPeopleFailed] = useState(false);
  const [q, setQ] = useState("");
  const [confirmedOutcome, setConfirmedOutcome] = useState(false);
  const [okMessage, setOkMessage] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ id: string; message: Message; before: string; session: string; time: string } | null>(null);
  const [note, setNote] = useState("");
  const [areaNames, setAreaNames] = useState<Record<string, string>>({});
  const dirty = useRef<Partial<Answers>>({});
  const msgEdited = useRef(false);
  const step = (params.get("step") as Step | null) ?? "q1";
  const narrow = typeof window !== "undefined" && window.innerWidth < 700;

  useEffect(() => {
    let live = true;
    apiGet<Draft>(`/api/intents/${draftId}`).then((d) => {
      if (!live) return;
      const s = d.start_answers ?? {};
      msgEdited.current = !!s.message;
      const hint = d.north_proposal?.title || d.north_proposal?.text || "";
      if (!s.session_time) dirty.current = { ...dirty.current, session_time: "10:00" };  // the start time is a suggestion until the organiser changes it
      setA({ session_time: "10:00", ...s, ...(s.statement || !hint ? {} : { statement: hint.slice(0, LIMITS.statement) }), ...(s.title || !d.title ? {} : { title: d.title }) });
    }, () => live && setFailed(true));
    return () => { live = false; };
  }, [draftId]);

  useEffect(() => {
    apiGet<{ areas: { id: string; name: string }[] }>("/api/intents/areas").then((r) => setAreaNames(Object.fromEntries((r.areas ?? []).map((x) => [x.id, x.name]))), () => undefined);
  }, []);

  const set = useCallback((patch: Partial<Answers>) => { dirty.current = { ...dirty.current, ...patch }; setA((x) => ({ ...(x ?? {}), ...patch })); }, []);
  const save = useCallback(async (extra: Partial<Answers> = {}): Promise<boolean> => {
    const body = { ...dirty.current, ...extra };
    dirty.current = {};
    if (Object.keys(body).length === 0) return true;
    setError("");
    try {
      const r = await brainstorm.act<{ message_draft: Message | null }>(draftId, "draft", { answers: body, origin: window.location.origin });
      // North redrafts the message as answers change, until the organiser edits it (then her words stand)
      if (r.message_draft && !msgEdited.current) setA((x) => ({ ...(x ?? {}), message: r.message_draft! }));
      return true;
    } catch { setError(c.saveFailed); return false; }
  }, [draftId]);
  const go = (to: Step) => setParams((p) => { const n = new URLSearchParams(p); n.set("step", to); return n; });

  const checkRelated = useCallback(async (statement: string) => {
    if (statement.trim().length < 5 || statement === checked) return;
    setChecked(statement); setRelated(null);
    try {
      const r = await brainstorm.act<{ related: Related[] }>(draftId, "related", { statement });
      setRelated(r.related);
    } catch { setRelated("off"); }
  }, [draftId, checked]);

  const loadPeople = useCallback(async (picked: string[], extra = false) => {
    if (!a) return;
    setMore(extra); setPeopleFailed(false);
    try { setPeople(await brainstorm.act<PeopleAnswer>(draftId, "suggest-people", { statement: `${a.statement ?? ""} ${a.context ?? ""}`, areas: a.areas ?? [], picked })); } catch { setPeople(null); setPeopleFailed(true); }
    setMore(false);
  }, [draftId, a]);
  useEffect(() => { if (step === "q3" && a && !people && !peopleFailed) void loadPeople(a.people ?? []); }, [step, a, people, peopleFailed, loadPeople]);
  useEffect(() => { if (step === "q1" && a?.statement && related === null && !checked) void checkRelated(a.statement); }, [step, a?.statement, related, checked, checkRelated]);

  const nameOf = useMemo(() => Object.fromEntries((people?.people ?? []).map((p) => [p.id, p])), [people]);

  if (failed) return <ScreenState state="error" message={c.loadFailed} onRetry={() => window.location.reload()} />;
  if (!a) return <ScreenState state="loading" />;

  const picked = a.people ?? [];
  const missing = firstMissing(a);
  const idx = STEPS.findIndex((s) => s.key === step);
  const w = a.session_date && dateOk(a.session_date) ? windowOf(a.session_date) : null;
  const sessionText = w ? `${day(w.session)}, ${a.session_minutes ? until(`${w.session}T${a.session_time ?? "10:00"}`, a.session_minutes) : a.session_time}` : "";
  const answered: Record<string, boolean> = { q1: !!a.statement?.trim(), q2: !!a.good_outcome?.trim(), q3: picked.length >= 4 && picked.length <= 8, q4: !!a.areas?.length, q5: !!w && !!a.session_minutes };
  const here = answered.q1 ? (answered.q2 ? (answered.q3 ? (answered.q4 ? (answered.q5 ? "review" : "q5") : "q4") : "q3") : "q2") : "q1";
  const reach = (to: Step) => to === "review" ? !missing : STEPS.findIndex((s) => s.key === to) <= STEPS.findIndex((s) => s.key === here) || answered[to];
  const next = async () => { if (!(await save())) return; const k = STEPS[idx + 1]?.key; go(k ?? "review"); };
  const leave = async () => { if (await save()) nav("/centre/intent", { state: { toast: c.toast } }); };

  const open = async () => {
    setBusy(true); setError("");
    try {
      const r = await brainstorm.act<{ id: string; message: Message; window: { before: string; session: string }; session_at: string }>(draftId, "launch", {
        answers: { title: a.title, purpose: a.purpose, message: a.message }, origin: window.location.origin });
      setDone({ id: r.id, message: r.message, before: day(r.window.before), session: day(r.session_at), time: clock(r.session_at) });
    } catch (e) { setError(e instanceof ApiError && e.status < 500 && e.message ? e.message : c.openFailed); }
    setBusy(false);
  };
  const copy = (text: string) => { navigator.clipboard?.writeText(text).then(() => setNote(c.copied), () => setNote(c.copyFailed)) ?? setNote(c.copyFailed); };

  if (done) {
    return (
      <div className="bs-invite">
        <h2>{c.opened}</h2>
        <p>{c.openedLines(done.before, done.session, done.time)}</p>
        <p className="n-muted">{c.copyLead}</p>
        <label htmlFor="bs-sent"><strong>{c.invitation}</strong></label>
        <textarea id="bs-sent" readOnly rows={8} value={`${done.message.subject}\n\n${done.message.body}`} />
        <div className="bs-row">
          <Button onClick={() => copy(`${done.message.subject}\n\n${done.message.body}`)}>{c.copyMessage}</Button>
          <Button onClick={() => copy(done.message.subject)}>{c.copySubject}</Button>
          {note ? <span role="status" className="n-muted">{note}</span> : null}
        </div>
        <Button variant="primary" onClick={() => nav(`/centre/intent/${done.id}`)}>{c.goTo}</Button>
      </div>
    );
  }

  const stepper = (
    <ol aria-label="Steps" className="bs-steps">
      {STEPS.map((s, i) => (
        <li key={s.key}>
          <button type="button" className={`ds-chip${step === s.key ? " ds-chip--active" : ""}`} aria-current={step === s.key ? "step" : undefined}
            disabled={!reach(s.key)} onClick={() => go(s.key)}>{i + 1} {s.label}{answered[s.key] ? " ✓" : ""}</button>
        </li>
      ))}
      <li><button type="button" className={`ds-chip${step === "review" ? " ds-chip--active" : ""}`} disabled={!!missing} onClick={() => go("review")}>6 {c.review}</button></li>
    </ol>
  );
  const carried = (a as Answers & { carried?: Carried }).carried;
  const isGuess = (k: keyof Carried["values"]) => !!carried && carried.values[k] !== undefined && JSON.stringify(carried.values[k]) === JSON.stringify(a[k]);
  const row = (label: string, text: string, to: Step, k?: keyof Carried["values"]) => text ? (
    <li key={to}><strong>{label}</strong>: {text} {k && isGuess(k) ? <Chip>{guessed}</Chip> : null} <button type="button" className="bs-link" onClick={() => go(to)}>{c.change}</button></li>
  ) : null;
  const soFar = (
    <ul className="bs-sofar">
      {row(c.rows.statement, a.statement ?? "", "q1", "statement")}
      {row(c.rows.outcome, a.good_outcome ?? "", "q2", "good_outcome")}
      {row(c.rows.people, picked.length ? `${picked.length}: ${picked.map((id) => nameOf[id]?.name ?? "").filter(Boolean).join(", ") || ""}` : "", "q3")}
      {row(c.rows.areas, (a.areas ?? []).map((x) => areaNames[x] ?? x).join(", "), "q4", "areas")}
      {row(c.rows.session, sessionText && w ? `${sessionText} (${day(w.before)} to ${day(w.after)})` : "", "q5")}
      {!answered.q1 ? <li className="n-muted">{c.nothingYet}</li> : null}
    </ul>
  );

  const q1 = (
    <>
      <label htmlFor="bs-statement">{c.statement}{isGuess("statement") ? <span className="n-muted"> ({guessed})</span> : null}</label>
      <input id="bs-statement" value={a.statement ?? ""} maxLength={LIMITS.statement} placeholder={c.statementPlaceholder}
        onChange={(e) => set({ statement: e.target.value })} onBlur={() => { void save(); void checkRelated(a.statement ?? ""); }} />
      {(a.statement?.length ?? 0) > 160 ? <p className="n-muted">{a.statement!.length} / {LIMITS.statement}</p> : null}
      <label htmlFor="bs-context">{c.context}{isGuess("context") ? <span className="n-muted"> ({guessed})</span> : null}</label>
      <textarea id="bs-context" rows={3} value={a.context ?? ""} maxLength={LIMITS.context} placeholder={c.contextPlaceholder} onChange={(e) => set({ context: e.target.value })} onBlur={() => void save()} />
      {!a.related_checked?.dismissed && a.statement ? (
        <Panel title={c.relatedTitle} eyebrow={c.suggestion}>
          {related === null ? <p className="n-muted">{c.relatedChecking}</p>
            : related === "off" ? <p>{c.relatedOff} <Link to="/centre/intent/backlog">{c.backlog}</Link></p>
            : related.length === 0 ? <p>{c.relatedEmpty}</p>
            : <ul className="bs-replies">{related.map((r) => {
              const used = (a.related ?? []).some((x) => x.ref === r.ref && x.used_as_context);
              return (
                <li key={r.ref}><span><Chip>{c.typeName[r.type] ?? r.type}</Chip> <strong>{r.title}</strong> <span className="n-muted">{r.state === "closed" || r.state === "cancelled" ? r.state : r.ends ? c.openEnds(day(r.ends)) : r.state}</span><br /><span className="n-muted">{r.why}</span></span>
                  <span className="bs-row"><Link className="ds-btn" to={`/centre/intent/${r.ref}`} target="_blank">{c.open}</Link>
                    <Button onClick={() => { set({ related: used ? (a.related ?? []).filter((x) => x.ref !== r.ref) : [...(a.related ?? []), { ...r, used_as_context: true }] }); void save(); }}>{used ? c.usedContext : c.useContext}</Button></span></li>
              );
            })}</ul>}
          <Button onClick={() => { set({ related_checked: { at: new Date().toISOString(), shown: Array.isArray(related) ? related.length : 0, dismissed: true } }); void save(); }}>{c.different}</Button>
        </Panel>
      ) : null}
    </>
  );
  const q2 = (
    <>
      <label htmlFor="bs-outcome">{c.outcomeField}{isGuess("good_outcome") ? <span className="n-muted"> ({guessed})</span> : null}</label>
      <textarea id="bs-outcome" rows={3} value={a.good_outcome ?? ""} maxLength={LIMITS.outcome} placeholder={c.outcomePlaceholder}
        onChange={(e) => { set({ good_outcome: e.target.value }); setConfirmedOutcome(false); }} onBlur={() => void save()} />
      {a.good_outcome?.trim() ? (
        <MessageBubble from="agent" who="North" text={c.readBack(a.good_outcome.trim())}>
          {confirmedOutcome ? null : <div className="bs-row"><Button variant="primary" onClick={() => setConfirmedOutcome(true)}>{c.right}</Button>
            <Button onClick={() => document.getElementById("bs-outcome")?.focus()}>{c.correct}</Button></div>}
        </MessageBubble>
      ) : null}
    </>
  );
  const shown = (people?.people ?? []).filter((p) => !q || `${p.name} ${p.role} ${p.team}`.toLowerCase().includes(q.toLowerCase()));
  const toggle = (id: string, why: boolean) => {
    const on = picked.includes(id);
    const people_ = on ? picked.filter((x) => x !== id) : [...picked, id];
    const sug = new Set(a.suggested ?? []);
    if (!on && why) sug.add(id);
    if (on) sug.delete(id);
    set({ people: people_, suggested: [...sug] });
  };
  const person = (p: PeopleAnswer["people"][number]) => (
    <li key={p.id}>
      <button type="button" className={`bs-person${picked.includes(p.id) ? " bs-person--on" : ""}`} aria-pressed={picked.includes(p.id)} title={p.reason ?? undefined} onClick={() => toggle(p.id, p.suggested)}>
        <strong>{p.name}</strong> <span className="n-muted">{[p.role, p.team].filter(Boolean).join(", ")}</span>
        {p.suggested ? <> <Chip>{c.suggestedChip}</Chip> <span className="n-muted">{p.reason}</span></> : null}
      </button>
    </li>
  );
  const q3 = (
    <>
      <div className="bs-row">{picked.map((id) => <Chip key={id} onClick={() => toggle(id, false)}>{nameOf[id]?.name ?? id} ×</Chip>)}</div>
      <p role="status" style={{ color: picked.length >= 4 && picked.length <= 8 ? "var(--ds-teal-bright)" : "var(--ds-amber)" }}>{c.picked(picked.length)}</p>
      {picked.length >= 3 ? <p className="n-muted">{c.seatNote}</p> : null}
      <label htmlFor="bs-search">{c.search}</label>
      <input id="bs-search" value={q} onChange={(e) => setQ(e.target.value)} />
      {peopleFailed ? <ScreenState state="error" message={c.peopleFailed} onRetry={() => void loadPeople(picked)} /> : people === null ? <ScreenState state="loading" /> : people.people.length === 0 ? <p>{c.noPeople} <Link to="/centre/profile">{c.profileLink}</Link></p> : (
        <>
          {shown.some((p) => p.suggested) ? <><h3 className="bs-h">{c.suggested}</h3><ul className="bs-people">{shown.filter((p) => p.suggested).map(person)}</ul></> : null}
          <h3 className="bs-h">{c.everyone}</h3>
          <ul className="bs-people">{shown.filter((p) => !p.suggested).map(person)}</ul>
          <Button disabled={more} onClick={() => void loadPeople(picked, true)}>{more ? c.suggestingMore : c.suggestMore}</Button>
        </>
      )}
    </>
  );
  const sugNames = picked.map((id) => nameOf[id]?.name).filter((x): x is string => !!x);
  const q4 = (
    <>
      <AreaPicker value={a.areas ?? []} onChange={(ids) => { set({ areas: ids }); void save({ areas: ids }); }} affectedMayRead={!!a.affected_may_read}
        suggestion={sugNames.length && people?.suggested_areas.length ? { names: sugNames, areaIds: people.suggested_areas } : undefined} />
      <p className="n-muted">{c.areasHelp}</p>
      <label className="ds-north__choice"><input type="checkbox" checked={!!a.affected_may_read} onChange={(e) => { set({ affected_may_read: e.target.checked }); void save({ affected_may_read: e.target.checked }); }} /> {c.mayRead}</label>
      {a.affected_may_read ? <p className="n-muted">{c.mayReadOn}</p> : null}
      <label className="ds-north__choice"><input type="checkbox" checked={!!a.anonymous_ideas} onChange={(e) => { set({ anonymous_ideas: e.target.checked }); void save({ anonymous_ideas: e.target.checked }); }} /> {c.anonymous}</label>
      {a.anonymous_ideas ? <p className="n-muted">{c.anonymousNote}</p> : null}
    </>
  );
  const q5 = (
    <>
      <div className="bs-row">
        <div><label htmlFor="bs-date">{c.date}</label><input id="bs-date" type="date" min={earliest()} value={a.session_date ?? ""} onChange={(e) => set({ session_date: e.target.value })} onBlur={() => void save()} /></div>
        <div><label htmlFor="bs-time">{c.time}</label><input id="bs-time" type="time" value={a.session_time ?? ""} onChange={(e) => set({ session_time: e.target.value })} onBlur={() => void save()} /></div>
      </div>
      {a.session_date && !dateOk(a.session_date) ? <p role="alert" className="ds-north__error">{c.dateBad}</p> : null}
      <fieldset className="bs-row" style={{ border: 0, padding: 0 }}>
        <legend>{c.length}</legend>
        {[45, 60].map((m) => (
          <label key={m} className="ds-north__choice"><input type="radio" name="bs-length" checked={a.session_minutes === m} onChange={() => { set({ session_minutes: m }); void save({ session_minutes: m }); }} /> {c.minutes(m)}</label>
        ))}
      </fieldset>
      {w ? (
        <Panel title={c.windowHead}>
          <ul className="bs-sofar"><li>{c.before(day(w.before))}</li><li>{c.session(day(w.session), a.session_minutes ? until(`${w.session}T${a.session_time ?? "10:00"}`, a.session_minutes) : a.session_time ?? "")}</li><li>{c.after(day(w.after))}</li></ul>
          <p><strong>{c.ends(day(w.after))}</strong></p>
        </Panel>
      ) : null}
    </>
  );
  const body: Record<string, ReactNode> = { q1, q2, q3, q4, q5 };

  const review = (
    <>
      <p>{c.reviewLead}</p>
      <Panel title={c.soFar}>{soFar}</Panel>
      <Panel title={c.northDraft} eyebrow={c.suggestion}>
        <label htmlFor="bs-title">{c.title}</label>
        <input id="bs-title" value={a.title ?? a.statement ?? ""} maxLength={200} onChange={(e) => { set({ title: e.target.value }); setOkMessage(false); }} onBlur={() => void save()} />
        <label htmlFor="bs-purpose">{c.purpose}</label>
        <input id="bs-purpose" value={a.purpose ?? (a.good_outcome ? `To find: ${a.good_outcome}` : "")} maxLength={500} onChange={(e) => { set({ purpose: e.target.value }); setOkMessage(false); }} onBlur={() => void save()} />
        <label htmlFor="bs-subject">{c.subject}</label>
        <input id="bs-subject" value={a.message?.subject ?? ""} onChange={(e) => { msgEdited.current = true; set({ message: { subject: e.target.value, body: a.message?.body ?? "" } }); setOkMessage(false); }} onBlur={() => void save()} />
        <label htmlFor="bs-body">{c.body}</label>
        <textarea id="bs-body" rows={9} value={a.message?.body ?? ""} onChange={(e) => { msgEdited.current = true; set({ message: { subject: a.message?.subject ?? "", body: e.target.value } }); setOkMessage(false); }} onBlur={() => void save()} />
        <Button variant={okMessage ? "secondary" : "primary"} onClick={() => { setOkMessage(true); void save({ title: a.title ?? a.statement, purpose: a.purpose ?? `To find: ${a.good_outcome}` }); }}>{okMessage ? c.confirmed : c.looksRight}</Button>
      </Panel>
      {!okMessage ? <p className="n-muted">{c.needConfirm}</p> : null}
      <div className="bs-row">
        <Button variant="primary" disabled={!okMessage || busy || !!missing} onClick={() => void open()}>{busy ? c.opening : c.openNow}</Button>
        <Button onClick={() => void leave()}>{c.saveLeave}</Button>
      </div>
      {missing ? <p className="n-muted">{missing}</p> : null}
    </>
  );

  const lead = step === "review" ? null : (c as unknown as Record<string, { lead: string; why: string }>)[step]!;
  const hasNext = step !== "review" && answered[step] === true && (step !== "q2" || confirmedOutcome || !!a.good_outcome?.trim());
  return (
    <div className="bs-start">
      <div className="bs-row"><Chip>{c.type}</Chip> <Link className="ds-link" to="/centre/intent/new">{c.changeType}</Link></div>
      {carried ? <p className="n-muted">{carriedLine(carried.from)}</p> : null}
      {stepper}
      <div className="bs-cols">
        <div className="bs-colmain">
          {narrow ? <details className="ds-card bs-box"><summary>{c.questionOf(Math.max(1, idx + 1))}</summary>{soFar}</details> : null}
          <AgentChip name="North" status="waiting" />
          {lead ? <MessageBubble from="agent" who="North" text={lead.lead}><p className="n-muted">{c.whyAsk} {lead.why}</p></MessageBubble> : null}
          <div className="bs-fields">{step === "review" ? review : body[step]}</div>
          {error ? <p role="alert" className="ds-north__error">{error} {error === c.openFailed ? <button type="button" className="bs-link" onClick={() => void open()}>{c.retry}</button> : null}</p> : null}
          {step !== "review" ? (
            <div className="bs-foot">
              <Button disabled={idx <= 0} onClick={() => go(STEPS[idx - 1]!.key)}>{c.back}</Button>
              <Button variant="primary" disabled={!hasNext} onClick={() => void next()}>{c.next}</Button>
              <Button onClick={() => void leave()}>{c.saveLeave}</Button>
            </div>
          ) : <div className="bs-foot"><Button onClick={() => go("q5")}>{c.back}</Button></div>}
        </div>
        {!narrow ? <aside className="ds-card bs-box bs-colside"><h3 className="bs-h">{c.soFar}</h3>{soFar}</aside> : null}
      </div>
    </div>
  );
}

export default BrainstormStart;
