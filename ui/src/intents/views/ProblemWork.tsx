import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import Panel from "../../components/Panel";
import { Button, Chip, SideCard } from "../../design";
import { problemViewCopy as t } from "../problemCopy";
import { LinkButton, act, day } from "./ProblemTriage";
import type { Person, ProblemRecord } from "./problemTypes";

// Screen A (spec 42): what we know, the thread, the cause, the fix, the confirm taps, and the doors to a bigger answer.
type Props = { v: ProblemRecord; reload: (v?: ProblemRecord) => void; setError: (m: string) => void };
const box: React.CSSProperties = { display: "block", width: "100%", boxSizing: "border-box" };

export function WhatWeKnow({ v }: { v: ProblemRecord }) {
  const k = v.what_we_know;
  return (
    <Panel title={t.known} actions={<Chip>{t.suggestedBy}</Chip>}>
      {!k || k.sentences.length === 0 ? <p className="n-muted">{t.knownEmpty}</p> : (
        <p>{k.sentences.map((s) => <span key={s.source_ref.id}>{s.text} <Chip>{s.source_ref.label}</Chip> </span>)}</p>)}
    </Panel>
  );
}

export function Thread({ v, reload, setError }: Props) {
  const [text, setText] = useState("");
  const [anon, setAnon] = useState(false);
  const [all, setAll] = useState(false);
  const notes = v.notes ?? [];
  const shown = all ? notes : notes.slice(-3);
  return (
    <Panel title={t.thread}>
      {notes.length === 0 ? <p className="n-muted">{t.threadEmpty}</p> : (
        <>
          {!all && notes.length > 3 && <p><Button onClick={() => setAll(true)}>{t.showAll}</Button></p>}
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {shown.map((n) => <li key={n.id} style={{ marginBottom: 10 }}><strong>{n.anonymous ? t.anonymous : n.by ?? "North"}</strong> <Chip>{n.role}</Chip> <span className="n-muted">{day(n.at, v.tz)}</span><div>{n.text}</div></li>)}
          </ul>
        </>)}
      {v.can_resolve?.note && (
        <div>
          <label>{t.noteLabel}<textarea aria-label={t.noteLabel} rows={3} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} style={box} /></label>
          <label style={{ display: "block", minHeight: 44 }}><input type="checkbox" checked={anon} onChange={(e) => setAnon(e.target.checked)} /> {t.anon}</label>
          <Button variant="primary" disabled={!text.trim()} onClick={() => void act(`/api/intents/${v.id}/problem/note`, { text, anonymous: anon }, setError, (r) => { setText(""); setAnon(false); reload(r); })}>{t.addNote}</Button>
        </div>)}
    </Panel>
  );
}

export function CauseBlock({ v, reload, setError }: Props) {
  const rc = v.root_cause;
  const can = v.can_resolve;
  const [text, setText] = useState("");
  const [unknown, setUnknown] = useState(false);
  const [reason, setReason] = useState("");
  useEffect(() => { setText(rc?.text && !rc.unknown ? rc.text : ""); }, [rc?.text, rc?.unknown]);
  const url = `/api/intents/${v.id}/problem/cause`;
  const confirmed = !!rc?.confirmed_at;
  return (
    <Panel title={t.causeTitle} actions={rc ? <Chip>{confirmed ? t.confirmedBy(rc.confirmed_by ?? "") : t.draftBy}</Chip> : undefined}>
      {!rc ? <p className="n-muted">{t.causeEmpty}</p> : rc.unknown ? <p>{t.unknownLine(rc.reason ?? "")}</p> : <p>{rc.text}</p>}
      {rc?.fallback && !confirmed && <p className="n-muted">{t.causePlain}</p>}
      {rc && rc.based_on.length > 0 && <p className="n-muted">{t.basedOn}: {rc.based_on.length}</p>}
      {rc?.questions && !confirmed && <><p className="n-muted">{t.questions}</p><ul>{rc.questions.map((q) => <li key={q}>{q}</li>)}</ul></>}
      {v.me.owner && v.stage_key === "find_cause" && v.state === "open" && (
        <div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <Button disabled={!can?.draft_cause} onClick={() => void act(url, { action: "draft" }, setError, reload)}>{t.draftCause}</Button>
            {!can?.draft_cause && <span className="n-muted">{t.draftFirst}</span>}
          </div>
          <label style={{ display: "block", marginTop: 8 }}>{t.causeText}<textarea aria-label={t.causeText} rows={3} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} style={box} /></label>
          <p><Button variant="primary" disabled={!text.trim()} onClick={() => void act(url, { action: "confirm", text }, setError, reload)}>{t.confirmCause}</Button>{" "}
            <LinkButton onClick={() => setUnknown(!unknown)}>{t.unknown}</LinkButton></p>
          {unknown && <div><input type="text" aria-label={t.unknownReason} placeholder={t.unknownReason} value={reason} onChange={(e) => setReason(e.target.value)} style={{ ...box, minHeight: 44 }} />
            <Button disabled={reason.trim().length < 10} onClick={() => void act(url, { action: "unknown", reason }, setError, reload)}>{t.unknownSave}</Button></div>}
        </div>)}
    </Panel>
  );
}

export function FixBlock({ v, reload, setError }: Props) {
  const fx = v.fix;
  const [people, setPeople] = useState<Person[]>([]);
  const [kind, setKind] = useState("fixed");
  const [f, setF] = useState({ what: "", by: "", done_at: "", real_fix_by: "", reason: "", accepted_by: "" });
  const [none, setNone] = useState(false);
  const owner = v.me.owner && v.state === "open" && !!v.root_cause?.confirmed_at && (v.stage_key === "fix" || v.stage_key === "confirm");
  useEffect(() => { if (owner && people.length === 0) apiGet<{ people: Person[] }>("/api/intents/problem/start").then((r) => setPeople(r.people), () => undefined); }, [owner, people.length]);
  const set = (p: Partial<typeof f>) => setF((x) => ({ ...x, ...p }));
  const url = `/api/intents/${v.id}/problem/fix`;
  const who = (name: string, onChange: (x: string) => void, label: string) => (
    <label style={{ display: "block", marginTop: 8 }}>{label}<select aria-label={label} value={name} onChange={(e) => onChange(e.target.value)} style={{ ...box, minHeight: 44 }}>
      <option value="">Pick a person</option>{people.map((p) => <option key={p.id} value={p.name}>{p.name}</option>)}</select></label>);
  return (
    <Panel title={t.fixTitle}>
      {fx ? <p>{fx.kind === "accepted_no_fix" ? t.acceptedShown(fx.accepted_by ?? "", fx.reason ?? "") : fx.kind === "workaround" ? t.workaroundShown(fx.what ?? "", fx.by ?? "", day(fx.real_fix_by, v.tz))
        : t.fixShown(fx.what ?? "", fx.by ?? "", day(fx.done_at, v.tz))}</p> : <p className="n-muted">{v.root_cause?.confirmed_at ? t.fixEmpty : t.fixLocked}</p>}
      {owner && (
        <div>
          <div role="radiogroup" aria-label={t.fixTitle}>
            {([["fixed", t.fixed], ["workaround", t.workaround]] as [string, string][]).map(([k, l]) => <label key={k} style={{ marginRight: 16, minHeight: 44, display: "inline-flex", alignItems: "center", gap: 6 }}><input type="radio" name="fixkind" checked={kind === k} onChange={() => setKind(k)} /> {l}</label>)}
          </div>
          <label style={{ display: "block" }}>{t.did}<textarea aria-label={t.did} rows={2} maxLength={2000} value={f.what} onChange={(e) => set({ what: e.target.value })} style={box} /></label>
          {who(f.by, (x) => set({ by: x }), t.by)}
          <label style={{ display: "block", marginTop: 8 }}>{t.on}<input type="date" className="ds-input" aria-label={t.on} value={f.done_at} onChange={(e) => set({ done_at: e.target.value })} style={{ minHeight: 44 }} /></label>
          {kind === "workaround" && <label style={{ display: "block", marginTop: 8 }}>{t.realFix}<input type="date" className="ds-input" aria-label={t.realFix} value={f.real_fix_by} onChange={(e) => set({ real_fix_by: e.target.value })} style={{ minHeight: 44 }} /></label>}
          <p><Button variant="primary" disabled={!f.what.trim() || !f.by || !f.done_at || (kind === "workaround" && !f.real_fix_by)}
            onClick={() => void act(url, { kind, what: f.what, by: f.by, done_at: f.done_at, real_fix_by: f.real_fix_by || null }, setError, reload)}>{t.saveFix}</Button>{" "}
            <LinkButton onClick={() => setNone(!none)}>{t.noFix}</LinkButton></p>
          {none && <div><input type="text" aria-label={t.noFixReason} placeholder={t.noFixReason} value={f.reason} onChange={(e) => set({ reason: e.target.value })} style={{ ...box, minHeight: 44 }} />
            {who(f.accepted_by, (x) => set({ accepted_by: x }), t.noFixBy)}
            <Button disabled={f.reason.trim().length < 10} onClick={() => void act(url, { kind: "accepted_no_fix", reason: f.reason, accepted_by: f.accepted_by || undefined }, setError, reload)}>{t.noFixSave}</Button></div>}
        </div>)}
    </Panel>
  );
}

export function AffectedPanel({ v, reload, setError }: Props) {
  const rows = v.affected ?? [];
  const [still, setStill] = useState(false);
  const [comment, setComment] = useState("");
  const tap = (state: string, c?: string) => act(`/api/intents/${v.id}/problem/confirm-tap`, { state, comment: c }, setError, (r) => { setStill(false); setComment(""); reload(r); });
  const label = (s: string) => (s === "fixed" ? t.stillFor : s === "still" ? t.stillWord : t.waiting);
  return (
    <SideCard title={t.affectedTitle}>
      {rows.length === 0 ? <p className="n-muted">{t.affectedEmpty}</p> : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {rows.map((r) => <li key={r.name} style={{ marginBottom: 10 }}><strong>{r.name}</strong> <Chip>{label(r.state)}</Chip> <span className="n-muted">{day(r.at, v.tz)}</span>{r.comment && <div>{r.comment}</div>}
            {r.mine && !v.fix && !v.fix_line && <div className="n-muted">{t.waitingForFix}</div>}
            {r.mine && v.fix_line && <p>{v.fix_line}</p>}
            {r.mine && v.can_resolve?.tap && r.state === "waiting" && <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button variant="primary" onClick={() => void tap("fixed")}>{t.fixedForMe}</Button><Button onClick={() => setStill(!still)}>{t.still}</Button></div>}
            {r.mine && still && <div><input type="text" aria-label={t.stillComment} placeholder={t.stillComment} value={comment} onChange={(e) => setComment(e.target.value)} style={{ ...box, minHeight: 44 }} />
              <Button disabled={!comment.trim()} onClick={() => void tap("still", comment)}>{t.send}</Button></div>}</li>)}
        </ul>)}
      {v.tally && <p><Chip>{v.tally.fixed + v.tally.still === 0 ? t.tallyNone : t.tally(v.tally.fixed, v.tally.affected)}</Chip></p>}
    </SideCard>
  );
}

export function BiggerPanel({ v }: { v: ProblemRecord }) {
  const nav = useNavigate();
  const [msg, setMsg] = useState("");
  const [asking, setAsking] = useState(false);
  const [why, setWhy] = useState("");
  const [busy, setBusy] = useState(false);
  if (!(v.me.owner || v.me.organiser) || v.state !== "open") return null;
  const go = async () => {
    setBusy(true);
    try { const r = await apiSend<{ url: string }>("POST", `/api/intents/${v.id}/problem/to-initiative`, { reason: why.trim() }); nav(r.url); } catch (e) { setMsg(e instanceof Error && e.message ? e.message : "That did not open. Try again."); }
    setBusy(false);
  };
  return (
    <SideCard title={t.bigger}><p>{t.biggerLine}</p>
      {!asking ? <Button onClick={() => setAsking(true)}>{t.biggerAsk}</Button> : (
        <div><label>{t.biggerWhat}<input type="text" aria-label={t.biggerWhat} value={why} maxLength={300} onChange={(e) => setWhy(e.target.value)} style={{ ...box, minHeight: 44 }} /></label>
          <Button variant="primary" disabled={why.trim().length < 10 || busy} onClick={() => void go()}>{t.toInitiative}</Button></div>)}
      {msg && <p role="alert" className="ds-warn">{msg}</p>}</SideCard>
  );
}

export function LinkedPanel({ v }: { v: ProblemRecord }) {
  const n = v.node;
  return (
    <SideCard title={t.linked}>
      {!n && !v.links.from ? <p className="n-muted">{t.linkedEmpty}</p> : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {n && <li>{n.found ? <Link to={`/centre/intent/map/${encodeURIComponent(n.id)}`} className="ds-link">{n.name}</Link> : t.nodeMissing}</li>}
          {v.links.from && <li><Link to={`/centre/intent/${v.links.from}`} className="ds-link">{t.fromCheckin}</Link></li>}
        </ul>)}
    </SideCard>
  );
}

/** The state `closing`: who still has to answer, the reporter's confirm or one reopen, and the organiser's door to the closure screen (file 09). */
export function ClosingBanner({ v, reload, setError }: Props) {
  const c = v.closing;
  const [reopen, setReopen] = useState(false);
  const [reason, setReason] = useState("");
  const [stage, setStage] = useState("fix");
  if (!c) return null;
  const sign = () => act(`/api/intents/${v.id}/closure/confirm`, { version: v.version }, setError, () => reload()); // the answer is the closure view, so the problem is read again
  return (
    <div className="ds-card" style={{ padding: 16 }} role="region" aria-label="Confirmation">
      <p>{t.confirmBanner(v.owner ?? "The owner", c.why ?? "", c.came_out ?? "")}</p>
      {c.waiting && !c.can_confirm_owner && !c.can_confirm_reporter && <p className="n-muted">{t.waitingReporter(c.waiting === "owner" ? v.owner ?? "the owner" : v.reporter ?? "the reporter")}</p>}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {c.can_confirm_owner && <Button variant="primary" onClick={() => void sign()}>Confirm the fix</Button>}
        {c.can_confirm_reporter && <Button variant="primary" onClick={() => void sign()}>{t.yesFixed}</Button>}
        {c.can_reopen && <Button onClick={() => setReopen(!reopen)}>{t.noReopen}</Button>}
        {c.can_finish && !c.waiting && <Link className="ds-btn ds-btn--primary" to={`/centre/intent/${v.id}/close`}>{t.finish}</Link>}
      </div>
      {c.reopened_once && v.me.reporter && <p>{t.reopenedOnce} <Link className="ds-btn" to={`/centre/intent/new?type=problem&from=${v.id}`}>{t.newProblem}</Link></p>}
      {c.can_finish && !c.waiting && <p className="n-muted">{t.finishNote}</p>}
      {reopen && <div><label>{t.reopenWhat}<textarea aria-label={t.reopenWhat} rows={2} value={reason} onChange={(e) => setReason(e.target.value)} style={box} /></label>
        <label>{t.reopenStage}<select aria-label={t.reopenStage} value={stage} onChange={(e) => setStage(e.target.value)} style={{ minHeight: 44 }}><option value="find_cause">Find the cause</option><option value="fix">Fix</option></select></label>
        <Button variant="primary" disabled={!reason.trim()} onClick={() => void act(`/api/intents/${v.id}/problem/reopen`, { reason, stage }, setError, reload)}>{t.reopenSend}</Button></div>}
    </div>
  );
}
