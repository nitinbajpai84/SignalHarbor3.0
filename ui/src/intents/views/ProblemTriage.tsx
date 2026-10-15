import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import Panel from "../../components/Panel";
import { Button, Chip, SideCard } from "../../design";
import { BITES, KIND_WORDS, problemViewCopy as t } from "../problemCopy";
import type { Person, ProblemRecord, Row } from "./problemTypes";

// Screen B (spec 41): the problem as reported, North's plain triage note, and the decision card for the proposed owner.

export const day = (iso: string | null | undefined, tz: string): string =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00Z` : iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: tz }) : "";

/** One call that changes the problem; the answer is the new record. Refusals are said in the server's own words. */
export async function act(path: string, body: unknown, setError: (m: string) => void, done: (v: ProblemRecord) => void): Promise<boolean> {
  setError("");
  try { done(await apiSend<ProblemRecord>("POST", path, body ?? {})); return true; }
  catch (e) { setError(e instanceof ApiError && e.message ? e.message : "That did not save. Try again."); return false; }
}

export function LinkButton({ children, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" {...rest} style={{ background: "none", border: 0, padding: "0 4px", cursor: "pointer", color: "var(--ds-teal-bright)", font: "inherit", minHeight: 44 }}>{children}</button>;
}

export function AsReported({ v }: { v: ProblemRecord }) {
  const a = v.as_reported;
  if (!a) return <Panel title={t.asReported}><p className="n-muted">{t.cardOnly}</p></Panel>;
  const b = a.bites;
  return (
    <Panel title={t.asReported}>
      <p className="n-muted">{t.reportedBy(v.reporter ?? "", day(a.reported_at, v.tz))}</p>
      <dl style={{ margin: 0 }}>
        {([[t.what, a.what], [t.saw, a.saw], [t.bites, BITES[b.kind] ?? ""], [t.count, b.count === null ? t.notKnown : String(b.count)],
          ...(b.kind === "cost_money" ? [[t.amount, b.amount === null ? t.notKnown : `${b.amount} ${b.unit ?? ""}`.trim()]] : []),
          [t.about, a.about.name ?? t.notSure], [t.areas, a.areas.join(", ")], [t.affected, a.affected.join(", ")]] as string[][]).map(([k, val]) => (
          <div key={k} style={{ marginBottom: 8 }}><dt className="n-muted">{k}</dt><dd style={{ margin: 0 }}>{val}</dd></div>
        ))}
      </dl>
    </Panel>
  );
}

function RowList({ rows, empty }: { rows: Row[]; empty: string }) {
  if (rows.length === 0) return <p className="n-muted">{empty}</p>;
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
      {rows.map((r) => (
        <li key={r.id} style={{ marginBottom: 10 }}>
          <strong>{r.title}</strong> <Chip>{r.type}</Chip> <Chip>{r.state}</Chip>
          <div className="n-muted">{r.why}{r.owner ? `. Owner: ${r.owner}` : ""}{r.closed_at ? `. Closed ${r.closed_at.slice(0, 10)}` : ""}</div>
          {r.can_open && r.root_cause && <div>{t.rootCause}: {r.root_cause}</div>}
          {r.can_open && r.fix && <div>{t.fixLine}: {r.fix}</div>}
          {r.can_open && <Link to={`/centre/intent/${r.id}`} className="ds-link">{t.open}</Link>}
        </li>
      ))}
    </ul>
  );
}

export function TriagePanels({ v, reload, setError }: { v: ProblemRecord; reload: (v: ProblemRecord) => void; setError: (m: string) => void }) {
  const n = v.triage_note;
  const [why, setWhy] = useState(false);
  if (!n) return null;
  const noAbout = !v.as_reported || v.as_reported.about.kind === "unknown";
  const opsEmpty = n.alerts.length === 0 && n.range_breaks.length === 0;
  return (
    <>
      <p role="status" className="ds-card" style={{ padding: 12 }}><strong>North.</strong> {n.drafted_plainly ? t.plain : t.triageBanner} <span className="n-muted">{n.drafted_at ? t.drafted(day(n.drafted_at, v.tz)) : ""}</span>{n.summary && <><br />{n.summary}</>}</p>
      <Panel title={t.similar} actions={<Chip>{t.suggestedBy}</Chip>}><RowList rows={n.similar} empty={t.similarEmpty} /></Panel>
      <Panel title={t.related} actions={<Chip>{t.suggestedBy}</Chip>}><RowList rows={n.related} empty={t.relatedEmpty} /></Panel>
      <Panel title={t.ops} actions={<Chip>{t.fromOps}</Chip>}>
        {n.ops_unreadable ? <p className="n-muted">{t.opsUnreadable}</p> : opsEmpty ? <p className="n-muted">{noAbout ? t.opsPick : t.opsEmpty}</p> : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {n.alerts.map((a) => <li key={a.id}><strong>{(a.source ?? "").replace(/_/g, " ")}: {KIND_WORDS[a.kind] ?? a.kind}</strong> <Chip>{a.state}</Chip>
              <div className="n-muted">{a.opened ? `Opened ${day(a.opened, v.tz)}` : ""}{a.by ? `. Acknowledged by ${a.by}${a.note ? `: ${a.note}` : ""}` : ""}</div></li>)}
            {n.range_breaks.map((b) => <li key={b.mart}><strong>{b.mart.replace(/^gold\./, "")}</strong> {b.hidden || b.latest === null ? t.hidden : `Latest ${b.latest}`}
              <div className="n-muted">{b.basis ? `${t.usual}: ${b.basis}` : ""}</div></li>)}
          </ul>)}
        <p><Link to="/centre/build/ops" className="ds-link">{t.openOps}</Link></p>
      </Panel>
      {n.terms.length > 0 && <Panel title={t.terms} actions={<Chip>{t.suggestedBy}</Chip>}><ul>{n.terms.map((x) => <li key={x}>{x}</li>)}</ul></Panel>}
      <p><LinkButton aria-expanded={why} onClick={() => setWhy(!why)}>{t.whyThese}</LinkButton>{" "}
        {v.can.redraw && <Button disabled={!n.can_redraw} onClick={() => void act(`/api/intents/${v.id}/triage/refresh`, {}, setError, reload)}>{t.redraw}</Button>}</p>
      {why && <p className="n-muted">Matched on the same process or measure first, then on a shared area and similar wording. These are plain matches over the company's own records.</p>}
    </>
  );
}

export function DecisionCard({ v, reload, setError }: { v: ProblemRecord; reload: (v: ProblemRecord) => void; setError: (m: string) => void }) {
  const [step, setStep] = useState<"" | "accept" | "pass" | "extend">("");
  const [people, setPeople] = useState<Person[]>([]);
  const [to, setTo] = useState("");
  const [reason, setReason] = useState("");
  const [days, setDays] = useState("2");
  const ends = day(v.clock?.ends, v.tz);
  useEffect(() => {
    if ((v.can.pass || v.can.assign) && people.length === 0) apiGet<{ people: Person[] }>("/api/intents/problem/start").then((r) => setPeople(r.people.filter((p) => p.can_own)), () => undefined);
  }, [v.can.pass, v.can.assign, people.length]);
  const close = () => { setStep(""); setReason(""); };
  const eligible = people.filter((p) => p.name !== v.reporter && !(v.can.pass && p.name === v.proposed_owner?.name));

  return (
    <SideCard title={t.decide}>
      <p className="n-muted">{v.reporter ? `Reported by ${v.reporter}` : ""}</p>
      {v.proposed_owner && <p><strong>{t.proposed}:</strong> {v.proposed_owner.name}<br /><span className="n-muted">{v.proposed_owner.label}{v.proposed_owner.picked_by_reporter ? `. ${t.reporterPick}` : ""}</span></p>}
      {!v.proposed_owner && v.triage === "waiting" && <p className="n-muted">{t.noProposed}</p>}
      {v.can.accept && step === "" && <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Button variant="primary" onClick={() => setStep("accept")}>{t.accept}</Button>{v.can.pass && <Button onClick={() => setStep("pass")}>{t.pass}</Button>}</div>}
      {step === "accept" && <div role="group" aria-label={t.accept}><p>{t.acceptAsk(ends)}</p>
        <Button variant="primary" onClick={() => void act(`/api/intents/${v.id}/triage/accept`, {}, setError, (r) => { close(); reload(r); })}>{t.acceptYes}</Button> <Button onClick={close}>{t.cancel}</Button></div>}
      {step === "pass" && <div role="group" aria-label={t.pass}><p className="n-muted">{t.passHelp}</p>
        <label>{t.passPerson}<select aria-label={t.passPerson} value={to} onChange={(e) => setTo(e.target.value)} style={{ display: "block", width: "100%", minHeight: 44 }}>
          <option value="">Pick a person</option>{eligible.map((p) => <option key={p.id} value={p.name}>{p.name}{p.team ? `, ${p.team}` : ""}</option>)}</select></label>
        <label style={{ display: "block", marginTop: 8 }}>{t.passReason}<input type="text" aria-label={t.passReason} value={reason} maxLength={300} placeholder={t.passMin} onChange={(e) => setReason(e.target.value)} style={{ display: "block", width: "100%", minHeight: 44, boxSizing: "border-box" }} /></label>
        <p><Button variant="primary" disabled={!to || reason.trim().length < 10} onClick={() => void act(`/api/intents/${v.id}/triage/pass`, { to, reason }, setError, (r) => { close(); reload(r); })}>{t.passSend}</Button> <Button onClick={close}>{t.cancel}</Button></p></div>}
      {v.escalated && <p role="status">{t.escalation}</p>}
      {v.can.assign && <div role="group" aria-label={t.adminCard}><label>{t.adminCard}<select aria-label={t.adminCard} value={to} onChange={(e) => setTo(e.target.value)} style={{ display: "block", width: "100%", minHeight: 44 }}>
        <option value="">Pick a person</option>{eligible.map((p) => <option key={p.id} value={p.name}>{p.name}{p.team ? `, ${p.team}` : ""}</option>)}</select></label>
        <p><Button variant="primary" disabled={!to} onClick={() => void act(`/api/intents/${v.id}/triage/assign`, { to }, setError, reload)}>{t.assign}</Button></p></div>}
      {v.can.extend && step === "" && <Button onClick={() => setStep("extend")}>{t.extend}</Button>}
      {step === "extend" && <div role="group" aria-label={t.extend}>
        <label>{t.extendDays}<select aria-label={t.extendDays} value={days} onChange={(e) => setDays(e.target.value)} style={{ display: "block", minHeight: 44 }}>{[1, 2, 3, 5].map((d) => <option key={d} value={d}>{d}</option>)}</select></label>
        <label style={{ display: "block", marginTop: 8 }}>{t.extendReason}<input type="text" aria-label={t.extendReason} value={reason} maxLength={300} placeholder={t.passMin} onChange={(e) => setReason(e.target.value)} style={{ display: "block", width: "100%", minHeight: 44, boxSizing: "border-box" }} /></label>
        <p><Button variant="primary" disabled={reason.trim().length < 10} onClick={() => void act(`/api/intents/${v.id}/problem/extend`, { days: Number(days), reason }, setError, (r) => { close(); reload(r); })}>{t.extend}</Button> <Button onClick={close}>{t.cancel}</Button></p></div>}
      {v.extended && <p className="n-muted">{t.extended(day(v.extended.on, v.tz), v.extended.reason)}</p>}
      <h3 style={{ margin: "12px 0 4px" }}>{t.passHistory}</h3>
      {(v.passes ?? []).length === 0 ? <p className="n-muted">{t.notPassed}</p> : <ul style={{ paddingLeft: 18 }}>{v.passes!.map((p) => <li key={p.at}>{p.from} passed this to {p.to} on {day(p.at, v.tz)}: {p.reason}</li>)}</ul>}
    </SideCard>
  );
}

/** "Also acknowledge the Ops alert?" Nothing is acknowledged without the click; the existing alert route is called unchanged. */
export function AlertLine({ v, reload }: { v: ProblemRecord; reload: () => void }) {
  const [hidden, setHidden] = useState(false);
  const [msg, setMsg] = useState("");
  if (!v.alert_line || hidden) return null;
  const ack = async () => {
    try { await apiSend("POST", `/api/company/build/alerts/${encodeURIComponent(v.alert_line!.id)}/ack`, { note: t.ackNote(v.title) }); setHidden(true); reload(); }
    catch { setMsg(t.ackFailed); }
  };
  return (
    <div className="ds-card" style={{ padding: 12 }} role="group" aria-label={t.alertLine}>
      <p>{t.alertLine}</p>
      <Button variant="primary" onClick={() => void ack()}>{t.ack}</Button> <Button onClick={() => setHidden(true)}>{t.notNow}</Button>
      {msg && <p role="alert" className="ds-warn">{msg}</p>}
    </div>
  );
}
