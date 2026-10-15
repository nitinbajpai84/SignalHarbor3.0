import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button, Chip, PageFrame, Pill, Signature } from "../../design";
import BottomBar from "../BottomBar";
import { peopleCopy } from "../PeoplePanel";
import { OutcomeUsed, RatingPrompt, RatingSummary, type Rating } from "../RatingPrompt";
import { LateThoughts, WhatNext, type NextChoice } from "../session/OutcomeCard";
import { closeCopy as t } from "./closeCopy";
import "./CloseView.css";

// Specs 09 and 10: the closure screen at /centre/intent/<id>/close. The same screen reads as the closed view once the intent is closed.

interface Sentence { slot: string; text: string; sources: { label: string; ref: string }[]; by: string; edited_at: string | null }
interface NextRow { kind: string; title: string; ref: string | null; reason: string; answers?: Record<string, Record<string, string | string[]>> }
interface Closure {
  id: string; type: string; title: string; state: string; version: number; tier: string; purpose: string; time_zone: string; ends: string; late: boolean;
  opened_by: string; opened_on: string; outcome: { lines: { label: string; value: string; items?: string[] }[]; missing: string[] }; strip: string | null;
  cancelled: boolean; cancel: { reason: string; by: string; on: string } | null; closed_on: string | null; why_it_happened: string;
  send_back: { by: string; at: string; comment: string } | null; asked_again?: { by: string; at: string; roles: string[] } | null; next: NextRow[]; links: { from: string | null; to: string[] }; rated: boolean;
  you: { organiser: boolean; can_start: boolean; can_back: boolean; can_edit: boolean; can_draft: boolean; can_sign: boolean; sign_label: string; can_send: boolean;
    has_link: boolean; can_close: boolean; blocked_by: string | null; can_close_incomplete: boolean; can_cancel: boolean };
  signature: { role: string; name: string; state: "waiting" | "signed"; at: string; how: string | null }[]; link_out: { role: string; expires_at: string } | null;
  sentences?: Sentence[]; drafted?: boolean; people?: { name: string; role: string; label: string; count: number | null }[]; anonymous_count?: number;
  panels?: Record<string, { label: string; value: string }[]>; rating?: Rating | null; sent?: { link: string; expires_at: string; name: string };
  build_link?: string | null;
  build_ready?: { requirements: { key: string; label: string; done: boolean; href: string }[]; text: string; n_ok: number; of: number; handed: boolean; href: string; can_skip: boolean; skipped_reason: string | null } | null;
}

const fail = (e: unknown) => (e instanceof Error && e.message ? e.message : t.failed);
const HOW: Record<string, string> = { approver: "by the approver link", charter: "by the charter signature", room: "in the room" };
const ROLE = { sponsor: "Sponsor", decider: "Decider", owner: "Owner", reporter: "Reporter" } as Record<string, string>;
const useNarrow = () => {
  const q = typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 700px)") : null;
  const [narrow, set] = useState(q?.matches ?? false);
  useEffect(() => { if (!q) return; const f = () => set(q.matches); q.addEventListener("change", f); return () => q.removeEventListener("change", f); }, [q]);
  return narrow;
};

function Block({ title, children, actions, id }: { title: string; children: ReactNode; actions?: ReactNode; id?: string }) {
  return (
    <section className="ds-card close-block" aria-label={title} id={id}>
      <div className="close-block__head"><h2>{title}</h2>{actions}</div>
      {children}
    </section>
  );
}

function NextList({ c, save, start }: { c: Closure; save: (rows: NextRow[]) => Promise<void>; start?: () => void }) {
  const edit = c.you.can_edit;
  const [adding, setAdding] = useState(false);
  const [row, setRow] = useState<NextRow>({ kind: "backlog", title: "", ref: null, reason: "" });
  const [draft, setDraft] = useState<Record<number, string>>({});
  return (
    <Block id="close-next" title={t.next} actions={edit && <Button onClick={() => setAdding(true)}>{t.addNext}</Button>}>
      {c.next.length === 0 && <p className="n-muted">{t.nextNone}</p>}
      <ul className="close-list">
        {c.next.map((n, i) => {
          const reason = draft[i] ?? n.reason;
          return (
            <li key={i} className="close-row">
              <Chip>{t.kind[n.kind] ?? n.kind}</Chip>
              <div className="close-row__main">
                {n.title && <strong>{n.title}</strong>}
                {edit ? (
                  <input className="ds-input" value={reason} maxLength={300} aria-label={`${t.reasonField} ${i + 1}`} onChange={(e) => setDraft({ ...draft, [i]: e.target.value })}
                    onBlur={() => reason !== n.reason && save(c.next.map((x, j) => (j === i ? { ...x, reason } : x)))} />
                ) : <span>{n.reason}</span>}
                {!n.reason.trim() && <span className="ds-warn" role="alert">{t.addReason}</span>}
                {n.ref && (n.ref.startsWith("bk-") ? <small className="n-muted">{t.onBacklog}</small> : <Link to={`/centre/intent/${n.ref}`}>{t.openLinked}</Link>)}
                {!n.ref && n.kind === "initiative" && start && <Button variant="primary" onClick={start}>{t.startInitiative}</Button>}
              </div>
              {edit && <button type="button" className="ds-btn" aria-label={`${t.remove} ${i + 1}`} onClick={() => save(c.next.filter((_, j) => j !== i))}>{t.remove}</button>}
            </li>
          );
        })}
      </ul>
      {adding && (
        <form className="close-form" onSubmit={async (e) => { e.preventDefault(); if (!row.reason.trim()) return; await save([...c.next, row]); setAdding(false); setRow({ kind: "backlog", title: "", ref: null, reason: "" }); }}>
          <select className="ds-input" aria-label="Kind" value={row.kind} onChange={(e) => setRow({ ...row, kind: e.target.value })}>
            {Object.entries(t.kind).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input className="ds-input" aria-label={t.titleField} placeholder={t.titleField} value={row.title} onChange={(e) => setRow({ ...row, title: e.target.value })} />
          <input className="ds-input" aria-label={t.reasonField} placeholder={t.reasonField} value={row.reason} required onChange={(e) => setRow({ ...row, reason: e.target.value })} />
          <div className="close-actions"><Button variant="primary" type="submit">{t.saveRow}</Button><Button onClick={() => setAdding(false)}>{t.cancel}</Button></div>
        </form>
      )}
    </Block>
  );
}

function Summary({ c, act, source, reload }: { c: Closure; act: (b: object) => Promise<void>; source: (ref: string) => void; reload: () => void }) {
  const [editing, setEditing] = useState<string | null>(null);
  const [text, setText] = useState("");
  const list = c.sentences ?? [];
  const saveAll = (rows: Sentence[]) => act({ action: "edit", summary_sentences: rows });
  return (
    <Block id="close-summary" title={t.summary} actions={c.you.can_draft && <Button onClick={() => act({ action: "draft" })}>{list.length ? t.draftAgain : t.draftIt}</Button>}>
      {list.length === 0 && <p className="n-muted">{c.outcome.lines.length ? t.notDrafted : t.nothingRecorded}</p>}
      {list.map((s) => (
        <p key={s.slot} className="close-sentence">
          {editing === s.slot ? (
            <>
              <textarea className="ds-input" aria-label={t.editSentence} value={text} onChange={(e) => setText(e.target.value)} />
              <Button variant="primary" onClick={async () => { await saveAll(list.map((x) => (x.slot === s.slot ? { ...x, text } : x))); setEditing(null); }}>{t.saveSentence}</Button>
            </>
          ) : (
            <>
              <span>{s.text}</span>{" "}
              {s.sources.map((r, i) => <Chip key={i} onClick={() => source(r.ref)}>{r.label}</Chip>)}{" "}
              <small className="n-muted">{s.by === "north" ? t.draftMark : t.editedBy(s.by)}</small>
              {c.you.can_edit && (
                <span className="close-inline">
                  <button type="button" className="ds-btn" onClick={() => { setEditing(s.slot); setText(s.text); }}>{t.editSentence}</button>
                  <button type="button" className="ds-btn" onClick={() => saveAll(list.filter((x) => x.slot !== s.slot))}>{t.removeSentence}</button>
                </span>
              )}
            </>
          )}
        </p>
      ))}
    </Block>
  );
}

function Dialog({ title, lead, label, confirm, onConfirm, onClose, children }: {
  title: string; lead?: ReactNode; label: string; confirm: string; onConfirm: (reason: string) => Promise<void>; onClose: () => void; children?: ReactNode;
}) {
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  return (
    <form className="ds-card close-dialog" aria-label={title} onSubmit={async (e) => { e.preventDefault(); try { await onConfirm(reason); } catch (x) { setErr(fail(x)); } }}>
      <h2>{title}</h2>
      {lead}{children}
      <label>{label}<textarea className="ds-input" value={reason} onChange={(e) => setReason(e.target.value)} aria-label={label} /></label>
      {err && <p role="alert" className="ds-warn">{err}</p>}
      <div className="close-actions"><Button variant="primary" type="submit" disabled={!reason.trim()}>{confirm}</Button><Button onClick={onClose}>{t.cancel}</Button></div>
    </form>
  );
}

export default function CloseView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const nav = useNavigate();
  const narrow = useNarrow();
  const [tick, setTick] = useState(0);
  const { state, data, message, retry } = useLoad(() => apiGet<Closure>(`/api/intents/${intentId}/closure`), `${intentId}:${tick}`);
  const [local, setLocal] = useState<Closure | null>(null);
  const [err, setErr] = useState("");
  const [dialog, setDialog] = useState<"incomplete" | "cancel" | "nohand" | null>(null);
  const [panel, setPanel] = useState<string | null>(null);
  const [reasonEdit, setReasonEdit] = useState<string | null>(null);
  const [seen, setSeen] = useState(typeof IntersectionObserver === "undefined");
  const [copied, setCopied] = useState(false);
  const choice = useRef<NextChoice | null>(null);
  const watch = useRef<HTMLDivElement>(null);
  useEffect(() => setLocal(data), [data]);
  // the home card lands on #rate; the panel only exists once the closure has loaded, so scroll to it then
  useEffect(() => { if (local && window.location.hash === "#rate") document.getElementById("rate")?.scrollIntoView({ block: "start" }); }, [local?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (seen || !watch.current) return;
    const o = new IntersectionObserver((es) => es.some((e) => e.isIntersecting) && setSeen(true));
    o.observe(watch.current);
    return () => o.disconnect();
  }, [seen, local?.id]);
  const c = local;
  const act = async (body: object) => {
    setErr("");
    try { setLocal(await apiSend<Closure>("PUT", `/api/intents/${intentId}/closure`, { ...body, version: c?.version })); } catch (e) { setErr(fail(e)); throw e; }
  };
  const run = (body: object) => act(body).catch(() => undefined);
  const pickChoice = () => {
    const ch = choice.current;
    if (!c || !ch?.kind || !ch.reason.trim()) return;
    run({ action: "edit", next: [{ kind: ch.kind, title: "", ref: null, reason: ch.reason.trim(), answers: ch.answers }, ...c.next.slice(1)] });
  };
  const moveTo = async (to: string) => {
    setErr("");
    try { await apiSend("PUT", `/api/intents/${intentId}/state`, { to, version: c?.version }); setTick((x) => x + 1); } catch (e) { setErr(fail(e)); }
  };
  if (state !== "populated" || !c) {
    return <PageFrame title={t.title}><ScreenState state={state} message={state === "refused" ? t.refused : message} onRetry={retry}>{null}</ScreenState></PageFrame>;
  }
  const closed = c.state === "closed" || c.state === "cancelled";
  const closing = c.state === "closing";
  const full = c.tier === "content";
  const you = c.you;
  const sign = c.signature;
  const nextOpen = c.next.some((n) => !n.reason.trim());
  const organiserName = (c.people ?? []).find((p) => p.role === "organiser")?.name ?? "";
  const lookAtOutcome = () => { document.getElementById("close-outcome")?.scrollIntoView({ behavior: "smooth", block: "center" }); setSeen(true); };
  const stateLabel = closed ? `${t.states[c.state]} ${c.closed_on ?? ""}`.trim() : t.states[c.state] ?? c.state;
  const secondary = (
    <>
      {you.can_close_incomplete && <Button onClick={() => setDialog("incomplete")}>{t.incompleteBtn}</Button>}
      {c.build_ready?.can_skip && <Button onClick={() => setDialog("nohand")}>{t.noHandoffBtn}</Button>}
      {you.can_cancel && <Button onClick={() => setDialog("cancel")}>{t.cancelBtn}</Button>}
    </>
  );
  const head = (
    <>
      <Pill tone={closed ? "signed" : "open"}>{stateLabel}</Pill>
      {!closed && (you.can_cancel || you.can_close_incomplete || c.build_ready?.can_skip) && (narrow ? <details className="close-more"><summary>{t.more}</summary><div aria-label={t.moreLabel}>{secondary}</div></details> : secondary)}
    </>
  );
  const reload = () => setTick((x) => x + 1);
  // W2F2: the organiser of a closed brainstorm whose chosen idea has no Initiative yet starts it here (POST /next writes the pre-filled draft)
  const startInitiative = closed && you.organiser && c.type === "brainstorm" && c.outcome.lines.some((l) => l.label === "Chosen idea")
    ? async () => {
      setErr("");
      try {
        const r = await apiSend<{ created: { target: { kind: string; id: string } }[] }>("POST", `/api/intents/${intentId}/next`, {});
        const made = r.created.find((x) => x.target.kind === "initiative");
        if (made) nav(`/centre/intent/new?type=initiative&draft=${made.target.id}&from=${c.id}`); else reload();
      } catch (e) { setErr(fail(e)); }
    }
    : undefined;
  const rating = c.rating ?? null;
  const right = (
        <div className="close-aside">
          {panel && c.panels?.[panel] && (
            <Block title={t.sourceTitle} actions={<Button onClick={() => setPanel(null)}>{t.closeSource}</Button>}>
              <dl>{c.panels[panel].map((r, i) => <div key={i}><dt>{r.label}</dt><dd>{r.value || "Not available yet"}</dd></div>)}</dl>
            </Block>
          )}
          <Block id="close-signature" title={t.signature}>
            {sign.length === 0 ? <p className="n-muted">{t.noSignature(c.strip?.match(/by (.+?) on/)?.[1] ?? "the organiser")}</p> : sign.map((s) => (
              <div key={s.role}>
                <p><strong>{ROLE[s.role] ?? s.role}: {s.name || "Not named yet"}</strong></p>
                <Signature state={s.state} by={s.name} at={s.state === "signed" ? [s.at, HOW[s.how ?? "room"] ?? HOW.room].filter(Boolean).join(", ") : undefined} />
              </div>
            ))}
            {you.can_sign && (
              <>
                {c.asked_again && <p role="status">{t.askedAgain(c.asked_again.by)}</p>}
                <Button variant="primary" disabled={nextOpen || !seen} onClick={() => run({ action: "sign" })}>{you.sign_label}</Button>
                {nextOpen ? <p className="n-muted">{t.waitNext(organiserName)}</p>
                  : !seen && <button type="button" className="ds-btn" onClick={lookAtOutcome}>{t.checkFirst}</button>}
              </>
            )}
            {you.can_send && !you.has_link && <Button onClick={() => run({ action: "send" })}>{t.sendTo(sign.find((s) => s.state === "waiting")?.name || "them")}</Button>}
            {you.has_link && you.organiser && <Button onClick={() => run({ action: "withdraw" })}>{t.withdraw}</Button>}
            {c.sent && (
              <div role="status">
                <p>{t.linkOnce}</p>
                <code className="close-link">{`${window.location.origin}${c.sent.link}`}</code>
                <Button onClick={async () => { await navigator.clipboard?.writeText(`${window.location.origin}${c.sent!.link}`); setCopied(true); }}>{copied ? t.copied : t.copy}</Button>
                <p className="n-muted">{t.linkEnds(new Date(c.sent.expires_at).toLocaleString("en-GB"))}</p>
              </div>
            )}
          </Block>
          {full && (
            <Block title={t.people}>
              {(c.people ?? []).length === 0 && <p className="n-muted">{t.noPeople}</p>}
              <ul className="close-list">{(c.people ?? []).map((p, i) => <li key={i}><strong>{p.name}</strong> <small>{peopleCopy.role[p.role] ?? p.role}</small> {p.count != null && <Chip>{p.label}</Chip>}</li>)}</ul>
              {(c.anonymous_count ?? 0) > 0 && <p className="n-muted">{t.anon(c.anonymous_count ?? 0)}</p>}
            </Block>
          )}
          {closed && c.rated && rating && (
            <>
              {(rating.can_rate || rating.mine || rating.waived || rating.dropped) && <Block id="rate" title="Rate it"><RatingPrompt intentId={c.id} rating={rating} onChange={reload} /></Block>}
              {rating.summary && <Block title="Ratings"><RatingSummary rating={rating} /></Block>}
              {rating.used && <Block title="Was the outcome used"><OutcomeUsed intentId={c.id} rating={rating} onChange={reload} /></Block>}
            </>
          )}
        </div>
  );
  return (
    <PageFrame
      title={c.title}
      crumbs={<Link to={`/centre/intent/${c.id}`}>{t.backToIntent}</Link>}
      subline={<><Chip>{t.kind[c.type] ?? c.type}</Chip> {t.endsOn(c.ends, c.time_zone)}</>}
      actions={<div className="close-head">{head}</div>}
    >
      <div className={`close-page ic-phone${narrow && closing ? " ic-bar-pad" : ""}`}>
      <div className="close-grid"><div className="close-left">
        {err && !dialog && <p role="alert" className="ds-warn">{err}</p>}
        {c.strip && <div className="ds-card close-strip" role="status">{c.strip}</div>}
        {c.build_ready && (
          <div className="ds-card close-strip" role="status" aria-label="Build-ready">
            <strong>{c.build_ready.text}</strong> <small className="n-muted">{t.buildCount(c.build_ready.n_ok, c.build_ready.of)}</small>{" "}
            <Link to={c.build_ready.href}>{t.seeCheck}</Link>
            {c.build_ready.skipped_reason && <p className="n-muted">{t.noHandoffKept(c.build_ready.skipped_reason)}</p>}
          </div>
        )}
        {c.cancel && <Block title={t.whyCancelled}><p>{c.cancel.reason}</p><p className="n-muted">{t.cancelledBy(c.cancel.by, c.cancel.on)}</p></Block>}
        {c.send_back && <Block title={t.sendBack}><p>{c.send_back.comment}</p><p className="n-muted">{c.send_back.by}</p></Block>}
        {c.late && !closed && (
          <div className="ds-card close-banner" role="status">
            <p><strong>North:</strong> {t.banner}</p>
            <Link to={`/centre/intent/${c.id}`}>{t.extend}</Link>
          </div>
        )}
        {you.can_start && <Block title={t.title}><p>{t.startNote}</p><Button variant="primary" onClick={() => run({ action: "start" })}>{t.start}</Button></Block>}
        {dialog === "incomplete" && (
          <Dialog title={t.incompleteTitle} label={t.incompleteReason} confirm={t.confirm} onClose={() => setDialog(null)}
            lead={<><p>{t.missingLead}</p><ul>{c.outcome.missing.map((m) => <li key={m}>{m}</li>)}</ul></>}
            onConfirm={async (reason) => { await act({ action: "close_incomplete", reason }); setDialog(null); }} />
        )}
        {dialog === "nohand" && (
          <Dialog title={t.noHandoffTitle} lead={<><p>{t.noHandoffLead}</p><p>{t.needsLead}</p>
              <ul aria-label="What closing needs">{(c.build_ready?.requirements ?? []).map((r) => (
                <li key={r.key}>{r.done ? t.needsDone : t.needsTodo}: {r.href.startsWith("#") ? <a href={r.href} onClick={() => setDialog(null)}>{r.label}</a> : <Link to={r.href}>{r.label}</Link>}</li>
              ))}</ul></>} label={t.noHandoffReason} confirm={t.confirm} onClose={() => setDialog(null)}
            onConfirm={async (reason) => { await act({ action: "close", no_handoff: true, reason }); setDialog(null); }} />
        )}
        {dialog === "cancel" && (
          <Dialog title={t.cancelTitle} label={t.cancelReason} confirm={t.confirm} onClose={() => setDialog(null)}
            onConfirm={async (reason) => { await act({ action: "cancel", cancel_reason: reason }); setDialog(null); }} />
        )}
        {full && !c.cancelled && <Summary c={c} act={run} source={setPanel} reload={reload} />}
        {!full && <p className="n-muted">{t.cardOnly}</p>}
        <Block title={t.why}>
          <p>{c.why_it_happened || c.purpose || t.noPurpose}</p>
          <p className="n-muted">{t.openedBy(c.opened_by, c.opened_on)}</p>
          {you.can_edit && (reasonEdit === null
            ? <Button onClick={() => setReasonEdit(c.why_it_happened || c.purpose)}>{t.editReason}</Button>
            : <><input className="ds-input" aria-label={t.editReason} value={reasonEdit} onChange={(e) => setReasonEdit(e.target.value)} /><Button variant="primary" onClick={async () => { await run({ action: "edit", why_it_happened: reasonEdit }); setReasonEdit(null); }}>{t.saveReason}</Button></>)}
        </Block>
        {!c.cancelled && (
          <Block id="close-outcome" title={closed ? t.closedTitle : t.came}>
            {c.outcome.lines.length === 0 && <p className="n-muted">{t.noOutcome}</p>}
            <dl className="close-dl">{c.outcome.lines.map((l, i) => <div key={i}><dt>{l.label}</dt><dd>{l.items ? <ul>{l.items.map((x, j) => <li key={j}>{x}</li>)}</ul> : l.value}</dd></div>)}</dl>
            {!closed && c.outcome.missing.length > 0 && <p className="ds-warn">{c.outcome.missing.join(", ")}</p>}
            {you.can_edit && c.outcome.missing.length > 0 && <Link className="ds-btn" to={`/centre/intent/${c.id}`}>{t.editOutcome}</Link>}
            <div ref={watch} aria-hidden="true" />
          </Block>
        )}
        {c.type === "brainstorm" && closing && you.can_edit && (
          <>
            <WhatNext intentId={c.id} onChange={(ch) => { choice.current = ch; }} />
            <Button onClick={pickChoice}>{t.pickChoice}</Button>
          </>
        )}
        {(c.next.length > 0 || closing) && !c.cancelled && <NextList c={c} save={(rows) => act({ action: "edit", next: rows })} start={startInitiative} />}
        {c.type === "brainstorm" && (closing || closed) && full && <LateThoughts intentId={c.id} />}
        {c.build_link && <Link className="ds-btn" to={c.build_link}>{t.openInBuild}</Link>}
        {closed && (
          <Block title={t.linked}>
            {!c.links.from && c.links.to.length === 0 && <p className="n-muted">{t.noLinked}</p>}
            <ul>{[...(c.links.from ? [c.links.from] : []), ...c.links.to].map((id, i) => <li key={id}><Link to={`/centre/intent/${id}`}>{i === 0 && c.links.from === id ? t.linkedFrom : t.openLinked}</Link></li>)}</ul>
          </Block>
        )}
        </div>
        {right}
      </div>
        {closing && you.organiser && !narrow && (
          <div className="close-footer">
            <Button onClick={() => moveTo("open").then(() => nav(`/centre/intent/${c.id}`))}>{t.backToIntent}</Button>
            <span className="n-muted">{you.blocked_by}</span>
            <Button variant="primary" disabled={!you.can_close} onClick={() => run({ action: "close" })}>{t.closeBtn}</Button>
          </div>
        )}
        {closing && you.organiser && narrow && (
          <BottomBar label={t.closing}>
            <Button variant="primary" disabled={!you.can_close} onClick={() => run({ action: "close" })}>{t.closeBtn}</Button>
          </BottomBar>
        )}
        {closing && narrow && you.blocked_by && <p className="n-muted">{you.blocked_by}</p>}
      </div>
    </PageFrame>
  );
}
