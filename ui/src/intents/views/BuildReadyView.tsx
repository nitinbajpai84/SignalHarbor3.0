import { useCallback, useEffect, useState } from "react";
import { Link, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import TruthScreen from "../../modules/m3_connect/truth/TruthScreen";
import { centresFor } from "../../shell/roles";
import { useSession } from "../../useSession";
import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { Button, Chip, Footnote, PageFrame, Pill, SideCard } from "../../design";
import SpanTargetCard from "../../pages/build/SpanTargetCard";
import "../phone.css";
import "./BuildReady.css";
import { brCopy as t } from "./buildReadyCopy";

// Spec 33: the build-ready check page (A), a compact panel for the charter and closure screens (B, C), and the hand-over banner of Build room 0 (D).

interface Turn { name: string; role: string }
interface Missing { kind: string; ref: string | null; label: string; turn_of: Turn | null; href: string | null; fix: string | null; state?: string; sealed?: number }
interface Line {
  n: number; key: string; title: string; group: string; ok: boolean; count: number; of: number;
  missing?: Missing[]; evidence?: { record: string; id: string | null; read_at: string }; text?: string; unavailable?: boolean; required?: boolean;
  signer?: string; signed_at?: string; version?: number | null; slots?: Record<string, string | null>; parts?: Record<string, number>; restricted?: number;
  answer?: boolean | null; answered_by?: string | null; answered_at?: string | null; reason?: string | null;
}
interface Todo { line: number; ref?: string | null; text: string; turn_of: Turn | null; href: string | null; fix: string | null; since: string | null }
interface HandProcess { id: string; name: string; owner: string | null; confirmed: boolean }
interface HandSource { id: string | null; name: string; zone: string | null; strategic: boolean; restricted?: boolean }
interface Handoff {
  by: { name: string }; at: string; catalogue_version: unknown; source_count: number; measure_count: number; definition_changed: boolean; current_catalogue_version: unknown;
  processes?: HandProcess[]; source_map?: HandSource[];
}
interface Nudged { sent: boolean; text: string; note: string }
export interface BuildReady {
  id: string; title: string; type: string; state: string; level: "full" | "counts"; time_zone: string; n_ok: number; of: number; verdict: string; checked_at: string | null;
  lines: Line[]; todo: Todo[]; build_needed: boolean | null; build_needed_reason: string | null; is_organiser: boolean; can_answer: boolean; can_hand_over: boolean; may_hand_over: boolean; may_recheck: boolean;
  stops: string | null; measure_count: number; source_count: number; catalogue_version: unknown; handoff: Handoff | null; assessment_id: string | null;
  gap_analysis_href: string; message?: string;
}

const fetchCheck = (id: string) => apiGet<BuildReady>(`/api/intents/${id}/build-ready`);

/** 2026-10-07T09:14:03+00:00 -> "7 October 2026" or "14:05" in the company's time zone, else UTC. */
function when(iso: string | null | undefined, tz: string, time = false): string {
  if (!iso) return "Not available yet";
  try {
    return new Date(iso).toLocaleString("en-GB", time ? { hour: "2-digit", minute: "2-digit", timeZone: tz } : { day: "numeric", month: "long", year: "numeric", timeZone: tz });
  } catch {
    return new Date(iso).toLocaleString("en-GB", time ? { hour: "2-digit", minute: "2-digit", timeZone: "UTC" } : { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  }
}

const withBack = (href: string) => `${href}${href.includes("?") ? "&" : "?"}back=build-ready`; // the destination offers "Back to the check"
const OPEN_HREF: Record<number, (id: string) => string | null> = {
  1: (id) => `/centre/intent/${id}/charter`, 2: (id) => `/centre/intent/${id}/define?tab=glossary`, 3: (id) => `/centre/intent/${id}/define?tab=catalogue`,
  4: (id) => `/centre/intent/${id}/define?tab=process-map`, 5: (id) => `/centre/intent/${id}/define?tab=data-sources`, 6: (id) => `/centre/intent/${id}/charter`, 7: () => null,
};
const narrow = () => typeof window !== "undefined" && window.matchMedia?.("(max-width: 700px)").matches === true;

function apiMessage(e: unknown): string {
  return e instanceof ApiError && e.message ? e.message : t.failed;
}

function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="br-scrim" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="ds-card br-dlg" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: 0 }}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

function AnswerDialog({ id, onClose, onDone }: { id: string; onClose: () => void; onDone: (d: BuildReady, no: boolean) => void }) {
  const [no, setNo] = useState(false);
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async (value: boolean) => {
    if (!value && !reason.trim()) { setProblem(t.reasonNeeded); return; }
    setBusy(true);
    try { onDone(await apiSend<BuildReady>("PUT", `/api/intents/${id}/build-needed`, { build_needed: value, reason: value ? null : reason.trim() }), !value); }
    catch (e) { setProblem(apiMessage(e)); setBusy(false); }
  };
  return (
    <Dialog title={t.dlgTitle} onClose={onClose}>
      <Button variant="primary" disabled={busy} onClick={() => void save(true)}>{t.yes}</Button>
      {no ? (
        <>
          <label className="br-note">{t.reasonLabel}<textarea value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} /></label>
          <Button disabled={busy} onClick={() => void save(false)}>{t.no}</Button>
        </>
      ) : <Button onClick={() => setNo(true)}>{t.no}</Button>}
      {problem ? <p role="alert" className="br-err">{problem}</p> : null}
      <Button onClick={onClose}>{t.notNow}</Button>
    </Dialog>
  );
}

function LineCard({ line, d, onAnswer, onChange }: { line: Line; d: BuildReady; onAnswer: () => void; onChange: () => void }) {
  const full = d.level === "full";
  const missing = line.missing ?? [];
  const [fold, setFold] = useState(narrow());
  const open = OPEN_HREF[line.n]?.(d.id);
  const notRequired = line.required === false;
  const first = missing.find((m) => m.turn_of);
  const detail = (
    <>
      {line.text && !line.ok ? <p className="br-line__text">{line.text}</p> : null}
      {notRequired ? <p className="br-line__text">{line.text}</p> : null}
      {missing.length ? <span className="br-row">{missing.map((m) => (m.href ? <Chip key={`${m.kind}${m.ref}`} href={withBack(m.href)}>{m.label}</Chip> : <Chip key={`${m.kind}${m.ref}`}>{m.label}</Chip>))}</span> : null}
    </>
  );
  return (
    <li id={`line-${line.n}`} className={`ds-card br-line${line.ok ? "" : " br-line--fail"}`} style={{ listStyle: "none" }}>
      <div className="br-line__head">
        <h3 className="br-line__title">{line.n}. {line.title}</h3>
        <Pill tone={line.ok ? "ok" : "draft"}>{line.ok ? t.pass : t.fail}</Pill>
      </div>
      {!line.unavailable && !notRequired ? <p className="br-note">{line.n === 7 ? (line.answer === true ? "Yes" : line.answer === false ? "No" : "Not answered") : `${line.count} of ${line.of}`}
        {line.n === 7 && line.answered_by ? `, answered by ${line.answered_by} on ${when(line.answered_at, d.time_zone)}` : ""}</p> : null}
      {line.n === 7 && line.answer === false && line.reason && full ? <p className="br-note">Reason: {line.reason}</p> : null}
      {line.n === 3 && line.parts ? <p className="br-note">Technical {line.parts.technical}, catalogue {line.parts.catalogue}, governed state {line.parts.governed}, of {line.of}</p> : null}
      {line.n === 5 && line.restricted ? <p className="br-note">{line.restricted} restricted source{line.restricted === 1 ? "" : "s"}, counted</p> : null}
      {line.n === 6 && line.slots ? <p className="br-note">{Object.entries(line.slots).map(([k, v]) => `${k.charAt(0).toUpperCase()}${k.slice(1)}: ${v ?? "Not named"}`).join(" · ")}</p> : null}
      {line.n === 1 && line.ok && line.signer ? <p className="br-note">Signed by {line.signer} on {when(line.signed_at, d.time_zone)}, version {line.version ?? "Not available yet"}</p> : null}
      {full && !line.ok && !notRequired && (missing.length || line.text) ? (
        narrow() ? (
          <>
            <Button onClick={() => setFold(!fold)}>{fold ? t.showMissing : t.hideMissing}</Button>
            {fold ? null : detail}
          </>
        ) : detail
      ) : null}
      {full && notRequired ? detail : null}
      {full && !line.ok && !notRequired ? (
        <span className="br-row">
          {first?.turn_of ? <Chip>{t.turn(first.turn_of.name.split(" ")[0] ?? first.turn_of.name, first.turn_of.role)}</Chip> : <Chip>{t.noOne}</Chip>}
          {line.n === 7 && d.can_answer ? <Button onClick={onAnswer}>{t.answerIt}</Button>
            : missing[0]?.href ? <Link className="ds-link" to={withBack(missing[0].href)}>{missing[0].fix ?? t.fixIt}</Link> : null}
        </span>
      ) : null}
      {full && line.ok && open ? <Link className="ds-link" to={open}>{t.open}</Link> : null}
      {line.n === 7 && line.answer !== null && line.answer !== undefined && d.can_answer ? <button type="button" className="ds-link" style={{ alignSelf: "flex-start", background: "none", border: 0, padding: 0, cursor: "pointer" }} onClick={onChange}>{t.change}</button> : null}
      {full && line.evidence ? (
        <p className="br-evidence">{line.unavailable && line.text ? line.text : t.evidence(line.evidence.record, when(line.evidence.read_at, d.time_zone, true))}</p>
      ) : null}
    </li>
  );
}

function todoItems(d: BuildReady, all: boolean, nudge?: (x: Todo) => void, nudged?: Record<string, Nudged>) {
  const items = all ? d.todo : d.todo.slice(0, 3);
  return items.map((x, i) => {
    const sent = nudged?.[`${x.line}:${x.ref ?? ""}`];
    return (
      <li key={i}>
        {x.text}
        <small>
          {x.since ? t.since(when(x.since, d.time_zone)) : null}
          {x.href ? <> · <Link className="ds-link" to={withBack(x.href)}>{x.fix ?? t.fixIt}</Link></> : null}
          {d.is_organiser && nudge ? <> · <button type="button" className="ds-link" disabled={!x.turn_of} title={x.turn_of ? undefined : t.nudgeNoOne} onClick={() => nudge(x)}
            style={{ background: "none", border: 0, padding: 0, minHeight: 44 }}>{t.nudge}</button></> : null}
        </small>
        {sent ? <small role="status"><Chip>{t.draftBy}</Chip> {sent.sent ? t.nudged(when(new Date().toISOString(), d.time_zone)) : sent.note} “{sent.text}”</small> : null}
      </li>
    );
  });
}

function HandButton({ d, onHand }: { d: BuildReady; onHand: () => void }) {
  const nav = useNavigate();
  if (d.build_needed === false) return d.is_organiser ? <Button variant="primary" onClick={() => nav(`/centre/intent/${d.id}/close`)}>{t.goClosure}</Button> : null; // nothing to hand over
  const why = !d.may_hand_over ? t.onlySponsor : d.stops;
  return (
    <>
      <Button variant="primary" disabled={!d.can_hand_over} onClick={onHand}>{t.handTo}</Button>
      {!d.can_hand_over && why ? <span className="br-note" role="status">{why}</span> : null}
    </>
  );
}

export default function BuildReadyView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const nav = useNavigate();
  const { state, data, message, retry } = useLoad(() => fetchCheck(intentId), intentId);
  const [fresh, setFresh] = useState<BuildReady | null>(null);
  const [dlg, setDlg] = useState<"answer" | "hand" | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [nudged, setNudged] = useState<Record<string, Nudged>>({});
  const [params] = useSearchParams();
  const d = fresh ?? data;
  const inBuild = centresFor(useSession().user?.roles).has("build"); // the sponsor hands over (file 14 row 23) but may not open the Build centre

  const recheck = useCallback(async () => {
    setProblem(null);
    try { setFresh(await apiSend<BuildReady>("POST", `/api/intents/${intentId}/build-ready/check`)); } catch (e) { setProblem(apiMessage(e)); }
  }, [intentId]);
  const nudge = async (x: Todo) => {
    try { setNudged({ ...nudged, [`${x.line}:${x.ref ?? ""}`]: await apiSend<Nudged>("POST", `/api/intents/${intentId}/build-ready/nudge`, { line: x.line, ref: x.ref ?? null }) }); }
    catch (e) { setProblem(apiMessage(e)); }
  };
  const hand = async () => {
    try {
      const r = await apiSend<BuildReady>("POST", `/api/intents/${intentId}/handoff`);
      setFresh(r);
      setDlg(null);
      if (inBuild) nav(r.gap_analysis_href);
    } catch (e) { setProblem(apiMessage(e)); setDlg(null); }
  };

  // North checks when Define has a charter draft: the first time the organiser opens the page, the check is recorded.
  // "Back to the check" arrives with ?recheck=1: the check is recorded again.
  const never = d !== null && d.may_recheck && (!d.checked_at || params.get("recheck") === "1") && !fresh && d.lines.length > 0 && d.verdict !== "handed_over";
  useEffect(() => { if (never) void recheck(); }, [never, recheck]);

  if (!d) return <PageFrame title="Build-ready check"><ScreenState state={state} message={message} onRetry={retry} /></PageFrame>;
  const first = d.lines.find((l) => !l.ok);
  const groups = t.groups.map((g) => ({ g, lines: d.lines.filter((l) => l.group === g) }));
  const green = d.verdict === "ready" || d.verdict === "handed_over";
  const asideTodo = (
    <>
      <SideCard title={t.todo}>
        {d.level !== "full" ? <p className="br-note">{t.verdict[d.verdict] ?? t.verdict.incomplete}</p>
          : d.todo.length === 0 ? <p className="br-note">{d.checked_at ? t.todoGreen(when(d.checked_at, d.time_zone, true)) : t.notChecked}</p>
            : <ol className="br-todo" aria-label={t.todo}>{todoItems(d, showAll, (x) => void nudge(x), nudged)}</ol>}
        {d.todo.length > 3 ? <Button onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer" : t.showAll}</Button> : null}
      </SideCard>
    </>
  );
  const asideNext = (
    <>
      <SideCard title={t.next}>{t.nextLines.map((s) => <p key={s} className="br-note">{s}</p>)}</SideCard>
      <Footnote>{t.sealed}</Footnote>
    </>
  );
  return (
    <div className="ic-phone br-page">
      <PageFrame
        crumbs={t.crumbs}
        title={d.title ?? "Build-ready check"}
        subline={d.message ?? t.verdict[d.verdict]}
        actions={d.lines.length ? (
          <>
            <Chip>Initiative</Chip>
            <Chip tone={green ? "active" : "default"} onClick={() => first && document.getElementById(`line-${first.n}`)?.scrollIntoView({ behavior: "smooth" })}>{t.chip(d.n_ok, d.of)}</Chip>
            {d.verdict === "handed_over" ? (inBuild ? <Link className="ds-btn" to={d.gap_analysis_href}>Open the gap analysis</Link> : <Chip tone="active">{t.verdict.handed_over}</Chip>) : (narrow() ? null : <HandButton d={d} onHand={() => setDlg("hand")} />)}
          </>
        ) : undefined}
      >
        {d.lines.length === 0 ? <ScreenState state="empty" message={d.message ?? t.notChecked} /> : (
          <div className="br-cols">
            <div className="br-main">
              <div className="br-row">
                {d.may_recheck && d.verdict !== "handed_over" ? <Button onClick={() => void recheck()}>{t.recheck}</Button> : null}
                <span className="br-note">{d.checked_at ? t.checkedAt(when(d.checked_at, d.time_zone, true)) : t.neverChecked}</span>
              </div>
              {problem ? <p role="alert" className="br-err">{problem}</p> : null}
              {d.level !== "full" ? <p className="br-note">{t.verdict[d.verdict]}</p> : null}
              {groups.map(({ g, lines }) => (
                <section key={g} aria-label={g}>
                  <h2 className="br-group">{g}</h2>
                  <ul style={{ margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "var(--ds-s2)" }}>
                    {lines.map((l) => <LineCard key={l.n} line={l} d={d} onAnswer={() => setDlg("answer")} onChange={() => setDlg("answer")} />)}
                  </ul>
                </section>
              ))}
            </div>
            <div className="br-side">{asideTodo}</div>
            <div className="br-next">{asideNext}</div>
          </div>
        )}
      </PageFrame>
      {d.lines.length && d.verdict !== "handed_over" && window.matchMedia?.("(max-width: 700px)").matches ? (
        <div className="ic-bar"><HandButton d={d} onHand={() => setDlg("hand")} /></div>
      ) : null}
      {dlg === "answer" ? <AnswerDialog id={d.id} onClose={() => setDlg(null)} onDone={(r, no) => { setFresh(r); setDlg(null); if (no) setProblem(null); }} /> : null}
      {dlg === "hand" ? (
        <Dialog title={t.confirmTitle} onClose={() => setDlg(null)}>
          <p className="br-note">{t.confirmBody(t.versionOf(d.catalogue_version), d.source_count ?? "Not available yet:")}</p>
          <Button variant="primary" onClick={() => void hand()}>{t.handTo}</Button>
          <Button onClick={() => setDlg(null)}>{t.notNow}</Button>
        </Dialog>
      ) : null}
    </div>
  );
}

/** Panels B and C: the compact check for the charter and closure screens. Their cards place it; it links to the full page. */
export function BuildReadyPanel({ intentId, strip = false }: { intentId: string; strip?: boolean }) {
  const { state, data, message, retry } = useLoad(() => fetchCheck(intentId), `panel-${intentId}`);
  const [all, setAll] = useState(false);
  if (!data) return <ScreenState state={state} message={message} onRetry={retry} />;
  const d = data;
  const green = d.verdict === "ready" || d.verdict === "handed_over";
  const items = strip || all ? d.todo : d.todo.slice(0, 3);
  const head = strip ? (d.verdict === "ready" ? t.verdict.ready : d.verdict === "not_needed" ? t.verdict.not_needed : d.lines.length ? `Not build-ready: ${d.of - d.n_ok} items missing` : t.verdict.not_checked) : "Build-ready";
  return (
    <section className={`ds-card br-panel${green ? " br-panel--green" : " br-panel--open"}`} aria-label="Build-ready">
      <strong>{head}</strong>
      {!strip && d.lines.length ? <span><Chip tone={green ? "active" : "default"}>{t.chip(d.n_ok, d.of)}</Chip></span> : null}
      {!d.lines.length ? <p className="br-note">{d.message ?? "Not checked yet."}</p> : d.level === "full" ? (
        items.length ? <ol className="br-todo">{todoItems(d, true).slice(0, items.length)}</ol> : <p className="br-note">Build-ready. Nothing is missing.</p>
      ) : null}
      {d.todo.length > 3 && !strip ? <Button onClick={() => setAll(!all)}>{all ? "Show fewer" : t.showAll}</Button> : null}
      <Link className="ds-link" to={`/centre/intent/${intentId}/build-ready`}>See every line</Link>
    </section>
  );
}

/** What Build received at hand-over: the processes, and the source map with its strategic and not strategic sources (R16). */
function Received({ h }: { h: Handoff }) {
  const procs = h.processes ?? [];
  const map = h.source_map ?? [];
  const group = (title: string, rows: HandSource[]) => (
    <section aria-label={title}>
      <h3 className="br-group">{title}</h3>
      {rows.length ? <ul className="br-recv">{rows.map((r, i) => <li key={r.id ?? `r${i}`} className="br-note">{r.name}{r.zone ? `, ${r.zone.replace(/_/g, " ")}` : ""}</li>)}</ul> : <p className="br-note">{t.noneHere}</p>}
    </section>
  );
  return (
    <section className="ds-card br-banner" aria-label={t.received}>
      <h2 style={{ margin: 0 }}>{t.received}</h2>
      <section aria-label={t.processesH}>
        <h3 className="br-group">{t.processesH}</h3>
        {procs.length ? <ul className="br-recv">{procs.map((p) => <li key={p.id} className="br-note">{p.name}, {t.ownerOf(p.owner)}, {t.confirmedWord(p.confirmed)}</li>)}</ul> : <p className="br-note">{t.noProcesses}</p>}
      </section>
      {group(t.strategicH, map.filter((r) => r.strategic))}
      {group(t.notStrategicH, map.filter((r) => !r.strategic))}
    </section>
  );
}

interface Room0Row { id: string | null; title: string; organiser: string | null; state: string; handed_over: boolean; n_ok: number | null; of: number; assessment_id: string | null; may_start: boolean; href: string | null }
interface Room0List { initiatives: Room0Row[]; build_ready_href: string }

/** Room 0's list (GET /api/company/build/gap-analysis): every Initiative Build may start from, or only `only`. Never sends a person back to this page to start. */
export function Room0Picker({ only, onStarted }: { only?: string; onStarted?: () => void }) {
  const nav = useNavigate();
  const { state, data, message, retry } = useLoad(() => apiGet<Room0List>("/api/company/build/gap-analysis"), `room0-${only ?? ""}`);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  if (!data) return <ScreenState state={state} message={message} onRetry={retry} />;
  const all = data.initiatives ?? [];
  const rows = only ? all.filter((r) => r.id === only) : all;
  const start = (id: string) => {
    setBusy(id); setErr("");
    apiSend<{ href: string }>("POST", `/api/company/build/gap-analysis/${id}/start`)
      .then((r) => (onStarted ? onStarted() : nav(r.href)))
      .catch((e: unknown) => setErr(apiMessage(e)))
      .finally(() => setBusy(""));
  };
  if (!rows.length) return (
    <section className="ds-card br-banner" aria-label={t.pickTitle}>
      <p>{only ? t.notReadyHere : t.noneHanded}</p>
      <Link className="ds-link" to={only ? `/centre/intent/${only}/build-ready` : data.build_ready_href}>{only ? t.openCheck : t.seeBuildReady}</Link>
    </section>
  );
  return (
    <section className="ds-card br-banner" aria-label={t.pickTitle}>
      {only ? <p>{t.noAssessment}</p> : <><h2 style={{ margin: 0 }}>{t.pickTitle}</h2><p className="br-note">{t.pickLine}</p></>}
      <ul className="br-recv">
        {rows.map((r, i) => (
          <li key={r.id ?? `hidden-${i}`} style={{ display: "flex", flexWrap: "wrap", gap: "var(--ds-s2)", alignItems: "center", justifyContent: "space-between" }}>
            <span><strong>{r.title}</strong><br /><span className="br-note">{t.rowLine(r.organiser, r.n_ok, r.of, r.state === "closed", r.handed_over)}</span></span>
            {r.id && r.assessment_id && !only ? <Link className="ds-btn" to={r.href ?? "#"}>{t.openGap}</Link>
              : r.id && r.may_start ? <Button variant="primary" disabled={busy === r.id} onClick={() => start(r.id as string)}>{busy === r.id ? t.starting : t.startGapNow}</Button>
              : r.id && !r.assessment_id ? <span className="br-note">{t.waitsFor}</span> : null}
          </li>
        ))}
      </ul>
      {err ? <p role="alert" className="ds-warn">{err}</p> : null}
    </section>
  );
}

/** Room 0 of the Build centre: the hand-over banner and the reads strip above the Moment of truth. Route /centre/build/gap-analysis?from=<intent id>.
 * With no `from`, the Initiatives Build may start from. */
export function GapAnalysisRoom() {
  const [params] = useSearchParams();
  const from = params.get("from") ?? "";
  const { state, data, message, retry } = useLoad(() => (from ? fetchCheck(from) : Promise.reject(new ApiError(t.noAssessment, 404))), `gap-${from}`);
  const [more, setMore] = useState(false);
  if (!from) return <PageFrame crumbs="Build centre / Room 0" title={t.room0.name} subline={t.room0.line}><Room0Picker /></PageFrame>;
  if (!data) return <PageFrame title={t.room0.name}><ScreenState state={state} message={message} onRetry={retry} /></PageFrame>;
  const h = data.handoff;
  const signed = data.lines.find((l) => l.n === 1);
  const reads = h ? (
    <>
      <Chip href={`/centre/intent/${from}/define?tab=catalogue`}>{t.reads(h.catalogue_version, h.source_count)}</Chip>
      {h.definition_changed && h.current_catalogue_version !== h.catalogue_version ? <Chip>{t.readsNow(h.current_catalogue_version)}</Chip> : null}
    </>
  ) : <span className="br-note">{t.noCatalogue}</span>;
  const truth = data.assessment_id ? ( // the existing step list (trial, scan, source map, plan, accept), as built
    <Routes location={`/centre/build/gap-analysis/${data.assessment_id}`}><Route path=":assessmentId" element={<TruthScreen />} /></Routes>
  ) : null;
  return (
    <>
    <PageFrame crumbs="Build centre / Room 0" title={t.room0.name} subline={t.room0.line}>
      {h ? (
        <section className="ds-card br-banner" aria-label="Hand-over">
          <p>{t.banner(data.title, when(h.at, data.time_zone), h.by.name)}</p>
          {more || !narrow() ? (
            <>
              {signed?.signer ? <p>{t.bannerSigned(signed.signer, when(signed.signed_at, data.time_zone))}</p> : null}
              <p>{t.bannerCounts(h.measure_count, h.source_count)}</p>
              {h.definition_changed ? <p><Pill tone="late">{t.changedAfter}</Pill></p> : null}
              <Link className="ds-link" to={`/centre/intent/${from}`}>{t.openIntent}</Link>
            </>
          ) : <button type="button" className="ds-link" style={{ alignSelf: "flex-start", background: "none", border: 0, padding: 0 }} onClick={() => setMore(true)}>{t.showMore}</button>}
        </section>
      ) : null}
      <div className="br-row" aria-label="Reads">{reads}</div>
      {h ? <Received h={h} /> : null}
      <SpanTargetCard intentId={from} />
      {data.assessment_id ? null : <Room0Picker only={from} onStarted={retry} />}
    </PageFrame>
    {truth}
    </>
  );
}
