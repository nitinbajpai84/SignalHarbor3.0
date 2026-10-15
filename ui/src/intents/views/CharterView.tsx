import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { ApiError, apiGet, apiSend } from "../../api/client";
import Panel from "../../components/Panel";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, PageFrame, Pill, SideCard, Signature, VersionList } from "../../design";
import "../phone.css";
import { chCopy as t, rolesCopy } from "../charter/charterCopy";
import RolesPanel, { RoleRequest, type RoleRequestData } from "../charter/RolesPanel";
import "./Charter.css";
import { BuildReadyPanel } from "./BuildReadyView";

// Files 32 and 34: the charter in ten pages, the sponsor's signature, the version history and who does what. Everything shown comes from
// GET /api/intents/<id>/charter; the pages say "Not available yet" and name the file they wait for when a record is missing.

interface Problem {
  id: string; title: string; kind?: string; priority_label: string | null; so_that: string | null; so_that_draft?: boolean; so_that_note?: string | null;
  tie: string | null; tied_options?: { id: string; label: string }[]; note_count: number; so_that_proposal?: string | null; details?: { label: string; values: string[] }[];
}
interface Measure { id: string; name: string; business: string | null; technical: string | null; state: string; confirmed_by: string | null; confirmed_at: string | null; href: string; catalogue_href: string }
interface Fig { value: number | null; unit?: string | null; by?: string | null }
interface Success { label: string; measure?: { name: string } | null; baseline?: Fig | null; target?: Fig | null; review_date?: string | null; text?: string | null }
interface Page {
  n: number; key: string; title: string; status: "ok" | "empty" | "missing"; text: string | null;
  // 1
  purpose?: string | null; opened_by?: { name: string | null; role: string; date: string | null }; why?: string | null; areas?: string[]; time_box?: { starts: string | null; ends: string | null };
  // 2
  lanes?: { lane: string; count: number; cards: { text: string | null; author: string | null }[] }[]; total?: number; took_part?: string[]; anonymous?: number; sealed?: number; href?: string;
  // 3
  lists?: { heading: string; kind: string; items: Problem[] }[];
  // 4 to 10
  rows?: Record<string, unknown>[]; confirmed?: number; removed?: number; named?: number; restricted?: number; accept?: boolean;
  success?: Success;
  needed?: boolean | null; reason?: string | null; by?: string | null; at?: string | null; lines?: { key: string; label: string; ok: boolean }[]; passing?: number | null;
  not_answered?: string | null; not_checked?: string | null; handoff?: { at?: string; measure_count?: number; source_count?: number } | null;
}
interface VersionRow { version: number; state: string; created_by: string; created_at: string; signed_by: string | null; signed_at: string | null; comment: string | null; discarded: { reason: string } | null; current: boolean }
interface Charter {
  version: number; edited_at: string | null; of: number; state: string; status: string; editable: boolean; current: boolean; session_id: string; problems: Problem[];
  approver: { name: string | null; link: string; expires_at: string | null }; returned: { comment: string; by: string } | null;
  signature: { needed: string | null; signed_by: string | null; signed_at: string | null; how: string | null };
  can_sign: boolean; sign_block: string | null; can_new_version: boolean; can_discard: boolean; can_download: boolean; north: string | null; handoff: { at?: string; measure_count?: number; source_count?: number } | null;
}
export interface CharterData {
  intent: { id: string; title: string; purpose: string | null; state: string }; tier: "content" | "card" | "named"; available: boolean; message?: string | null;
  viewer?: { organiser: boolean; closer: boolean; company_admin: boolean; name: string }; sponsor?: string | null; organiser?: string | null;
  charter: Charter | null; pages?: Page[]; versions?: VersionRow[]; roles?: { can_edit: boolean }; role_request?: RoleRequestData | null; outcome_line?: string | null;
}
interface Sent { link_path: string }

const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "");
const dayOf = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "");
const problemText = (e: unknown) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : t.failed);
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));

const fig = (f?: Fig | null) => (f && f.value != null ? `${f.value.toLocaleString("en-GB")}${f.unit ? ` ${f.unit}` : ""}` : t.notAvailable);

function SuccessBlock({ s, editable, busy, save }: { s: Success; editable: boolean; busy: boolean; save: (b: { target?: number | null; review_date?: string }) => void }) {
  const [target, setTarget] = useState(s.target?.value != null ? String(s.target.value) : "");
  const [date, setDate] = useState(s.review_date ?? "");
  useEffect(() => { setTarget(s.target?.value != null ? String(s.target.value) : ""); setDate(s.review_date ?? ""); }, [s.target?.value, s.review_date]);
  const dirty = target !== (s.target?.value != null ? String(s.target.value) : "") || date !== (s.review_date ?? "");
  return (
    <div className="ds-card ch-problem" aria-label={t.successHead}>
      <div className="ch-row"><strong>{t.successHead}</strong><Chip>{s.label}</Chip></div>
      <p className="ds-soft" style={{ margin: 0 }}>{t.successMeasure}: {s.measure?.name ?? t.notAvailable}</p>
      <p className="ds-soft" style={{ margin: 0 }}>{t.successBaseline}: {fig(s.baseline)}</p>
      {editable ? (
        <>
          <label className="ch-field">{t.successTarget}{s.target?.unit ? ` (${s.target.unit})` : ""}
            <input type="number" step="any" value={target} onChange={(e) => setTarget(e.target.value)} />
          </label>
          <label className="ch-field">{t.successReview}
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <div><Button disabled={busy || !dirty || (!date && !target)} onClick={() => save({ ...(target !== (s.target?.value != null ? String(s.target.value) : "") && target !== "" ? { target: Number(target) } : {}), ...(date && date !== (s.review_date ?? "") ? { review_date: date } : {}) })}>{t.successSave}</Button></div>
        </>
      ) : (
        <>
          <p className="ds-soft" style={{ margin: 0 }}>{t.successTarget}: {fig(s.target)}</p>
          <p className="ds-soft" style={{ margin: 0 }}>{t.successReview}: {s.review_date ? dayOf(s.review_date) : t.notAvailable}</p>
        </>
      )}
      {s.text ? <p className="ds-muted" style={{ margin: 0 }}>{s.text}</p> : null}
    </div>
  );
}

function PageBox({ p, children }: { p: Page; children: ReactNode }) {
  return (
    <Panel title={`Page ${p.n}. ${p.title}`} className="ch-page" actions={p.status === "ok" ? undefined : <Chip>{t.empty}</Chip>}>
      <div id={`page-${p.n}`} className="ch-body">{p.status !== "ok" && p.text ? <p className="ds-muted" style={{ margin: 0 }}>{p.text}</p> : children}</div>
    </Panel>
  );
}

function Pages({ pages, c, intentId, busy, run }: { pages: Page[]; c: Charter; intentId: string; busy: boolean; run: (w: () => Promise<CharterData>) => Promise<void> }) {
  const [values, setValues] = useState<Record<string, string>>({});
  useEffect(() => setValues(Object.fromEntries(c.problems.map((p) => [p.id, p.so_that ?? ""]))), [c.version, c.status, c.problems.length]);
  const changed = c.problems.filter((p) => (values[p.id] ?? "") !== (p.so_that ?? ""));
  const url = `/api/intents/${intentId}/charter`;
  const put = (body: unknown) => run(() => apiSend<CharterData>("PUT", url, body));
  const useLine = (id: string) => run(async () => {
    if (!c.problems.some((p) => p.id === id && p.so_that_draft)) throw new ApiError(t.nothingToConfirm, 409);
    return apiSend<CharterData>("PUT", url, { confirm_so_that: [id] });
  });
  return (
    <>
      {pages.map((p) => {
        const rows = p.rows ?? [];
        switch (p.key) {
          case "intent":
            return (
              <PageBox key={p.n} p={p}>
                <p style={{ margin: 0 }}>{p.purpose ?? t.notWritten}</p>
                <p className="ds-soft" style={{ margin: 0 }}>{t.openedBy}: {p.opened_by?.name ?? t.notWritten}, {p.opened_by?.role}{p.opened_by?.date ? `, ${p.opened_by.date}` : ""}</p>
                <p className="ds-soft" style={{ margin: 0 }}>{t.why}: {p.why ?? t.notWritten}</p>
                <p className="ds-soft" style={{ margin: 0 }}>{t.areas}: {(p.areas ?? []).join(", ") || t.notWritten}</p>
                <p className="ds-soft" style={{ margin: 0 }}>{t.timeBox}: {p.time_box?.starts ? `${dayOf(p.time_box.starts)} to ${dayOf(p.time_box.ends)}` : t.notWritten}</p>
              </PageBox>
            );
          case "wall":
            return (
              <PageBox key={p.n} p={p}>
                <p style={{ margin: 0 }}>{t.wallCounts(p.total ?? 0, p.anonymous ?? 0, p.sealed ?? 0)}</p>
                {(p.lanes ?? []).map((l) => <p key={l.lane} className="ds-soft" style={{ margin: 0 }}><strong>{l.lane}</strong>: {l.count}</p>)}
                <p className="ds-soft" style={{ margin: 0 }}>{t.tookPart}: {(p.took_part ?? []).join(", ") || "Not available yet"}</p>
                {p.href ? <Link className="ds-link" to={p.href}>{t.wallLink}</Link> : null}
              </PageBox>
            );
          case "problems":
            return (
              <PageBox key={p.n} p={p}>
                {(p.lists ?? []).map((l) => (
                  <div key={l.kind} className="ch-list">
                    <strong>{l.heading}</strong>
                    {l.items.length === 0 ? <p className="ds-muted" style={{ margin: 0 }}>{t.empty}</p> : l.items.map((q) => (
                      <div key={q.id} className="ds-card ch-problem">
                        <div className="ch-row"><strong>{q.title}</strong>{q.priority_label ? <Pill tone="ok">{q.priority_label}</Pill> : q.tie ? <Pill tone="draft">{q.tie}</Pill> : null}<Chip>{l.heading}</Chip><span className="ds-muted">{t.noteCount(q.note_count)}</span></div>
                        {c.editable ? (
                          <label className="ch-field">{t.soThatLabel(q.title)}
                            <input type="text" aria-label={t.soThatLabel(q.title)} value={values[q.id] ?? ""} placeholder={t.soThatNone} onChange={(e) => setValues({ ...values, [q.id]: e.target.value })} />
                          </label>
                        ) : <p style={{ margin: 0 }}>{q.so_that ? t.soThat(q.so_that) : t.soThatNone}</p>}
                        {q.so_that_draft ? <div className="ch-row"><Pill tone="draft">{t.draftByNorth}</Pill>{c.editable ? <Button aria-label={`${t.useLine}: ${q.title}`} disabled={busy} onClick={() => void useLine(q.id)}>{t.useLine}</Button> : null}</div> : null}
                        {c.editable && q.tie && (q.tied_options ?? []).length > 0 ? (
                          <select aria-label={t.tied} className="ds-btn" defaultValue="" onChange={(e) => e.target.value && void put({ priority: { [q.id]: e.target.value } })}>
                            <option value="">{t.tiedNone}</option>
                            {(q.tied_options ?? []).map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                          </select>
                        ) : null}
                        {(q.details ?? []).map((d) => <p key={d.label} className="ds-soft" style={{ margin: 0 }}>{d.label}: {d.values.join(", ")}</p>)}
                      </div>
                    ))}
                  </div>
                ))}
                {c.editable ? <div><Button disabled={busy || changed.length === 0} onClick={() => void put({ so_that: Object.fromEntries(changed.map((q) => [q.id, values[q.id] ?? ""])) })}>{t.saveLines}</Button></div> : null}
              </PageBox>
            );
          case "measures":
            return (
              <PageBox key={p.n} p={p}>
                {p.success ? <SuccessBlock s={p.success} editable={c.editable} busy={busy} save={(b) => void put({ success: b })} /> : null}
                {rows.map((r, i) => {
                  const ms = (r.measures ?? []) as Measure[];
                  return (
                    <div key={i} className="ch-list">
                      <strong>{str(r.problem)}</strong>
                      {ms.length === 0 ? <p className="ds-muted" style={{ margin: 0 }}>{str(r.empty)}</p> : ms.map((m) => (
                        <div key={m.id} className="ds-card ch-problem">
                          <div className="ch-row"><strong>{m.name}</strong><Pill tone={m.state === "Confirmed" ? "signed" : "draft"}>{t.governed(m.state, m.confirmed_by, m.confirmed_at)}</Pill></div>
                          <p className="ds-soft" style={{ margin: 0 }}>{t.businessDef}: {m.business ?? t.notWritten}</p>
                          <p className="ds-soft" style={{ margin: 0 }}>{t.technicalDef}: {m.technical ?? t.notWritten}</p>
                          <div className="ch-row"><Link className="ds-link" to={m.href}>{t.openGlossary}</Link><Link className="ds-link" to={m.catalogue_href}>{t.openCatalogue}</Link></div>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </PageBox>
            );
          case "processes":
            return (
              <PageBox key={p.n} p={p}>
                <p style={{ margin: 0 }}><strong>{t.confirmedOf(p.confirmed ?? 0, rows.length)}</strong></p>
                {rows.map((r) => (
                  <div key={str(r.id)} className="ds-card ch-problem">
                    <div className="ch-row"><Link className="ds-link" to={str(r.href)}>{str(r.name)}</Link><Pill tone={r.status === "confirmed" ? "signed" : "draft"}>{str(r.chip)}</Pill></div>
                    <p className="ds-soft" style={{ margin: 0 }}>{t.businessOwner}: {str(r.owner) || t.notNamed}. {t.steps(Number(r.steps))}, {t.breaks(Number(r.breaks))}.</p>
                    {r.note ? <p className="ds-warn" style={{ margin: 0 }}>{str(r.note)}</p> : null}
                  </div>
                ))}
                {(p.removed ?? 0) > 0 ? <p className="ds-muted" style={{ margin: 0 }}>{t.removedNote(p.removed ?? 0)}</p> : null}
                {p.href ? <Link className="ds-link" to={p.href}>{t.openMap}</Link> : null}
              </PageBox>
            );
          case "sources":
            return (
              <PageBox key={p.n} p={p}>
                <p style={{ margin: 0 }}><strong>{t.sourcesHead(p.named ?? 0, p.confirmed ?? 0)}</strong></p>
                {rows.map((r) => (
                  <div key={str(r.id)} className="ds-card ch-problem">
                    <div className="ch-row"><Link className="ds-link" to={str(r.href)}>{str(r.name)}</Link><Chip>{str(r.system) || t.notWritten}</Chip><Chip>{str(r.format) || t.notWritten}</Chip><Pill tone={r.state === "Confirmed by source owner" ? "signed" : "draft"}>{str(r.state)}</Pill></div>
                    <p className="ds-soft" style={{ margin: 0 }}>{t.sourceOwner}: {str(r.source_owner) || t.notNamed}</p>
                    <p className="ds-soft" style={{ margin: 0 }}>{t.dataOwner}: {str(r.data_owner) || t.notNamed}</p>
                    <p className="ds-soft" style={{ margin: 0 }}>{t.businessOwner}: {str(r.business_owner) || t.notNamed}</p>
                  </div>
                ))}
                {(p.restricted ?? 0) > 0 ? <p className="ds-muted" style={{ margin: 0 }}>{t.restricted(p.restricted ?? 0)}</p> : null}
                <div className="ch-row">{(p as unknown as { areas: string[] }).areas?.map((a) => <Chip key={a}>{a}</Chip>)}</div>
                {p.href ? <Link className="ds-link" to={p.href}>{t.openSources}</Link> : null}
              </PageBox>
            );
          case "roles":
            return (
              <PageBox key={p.n} p={p}>
                {rows.map((r) => (
                  <div key={str(r.role)} className="ch-row">
                    <span className="ds-muted">{str(r.label)}</span><strong>{str(r.person) || t.notNamed}</strong>
                    {r.person ? <><Chip>{str(r.mark)}</Chip><Chip>{({ not_asked: "Not asked yet", waiting: "Waiting", accepted: "Accepted", declined: "Declined", seen: "Seen" } as Record<string, string>)[str((r.answer as { state: string }).state)]}</Chip></> : null}
                  </div>
                ))}
              </PageBox>
            );
          case "build":
            return (
              <PageBox key={p.n} p={p}>
                <p style={{ margin: 0 }}><strong>{t.buildNeeded(p.needed ?? null)}</strong></p>
                {p.needed !== null && p.needed !== undefined ? <p className="ds-soft" style={{ margin: 0 }}>{[p.reason, t.answeredBy(p.by ?? null, p.at ? dayOf(p.at) : null)].filter(Boolean).join(". ")}</p> : null}
                {p.not_answered ? <p className="ds-warn" style={{ margin: 0 }}>{p.not_answered}</p> : null}
                {p.not_checked ? <p className="ds-muted" style={{ margin: 0 }}>{p.not_checked}</p> : (
                  <>
                    <p style={{ margin: 0 }}><strong>{t.buildReadyCount(p.passing ?? 0)}</strong></p>
                    {(p.lines ?? []).map((l) => <div key={l.key} className="ch-row"><Pill tone={l.ok ? "ok" : "draft"}>{l.ok ? "Passes" : "Not yet"}</Pill><span>{l.label}</span></div>)}
                  </>
                )}
                <div className="ch-row">{p.needed === null || p.needed === undefined ? <Link className="ds-btn" to={p.href ?? "#"}>{t.answerIt}</Link> : null}{p.href ? <Link className="ds-link" to={p.href}>{t.openCheck}</Link> : null}</div>
              </PageBox>
            );
          case "parked":
            return (
              <PageBox key={p.n} p={p}>
                {rows.map((r, i) => <p key={i} style={{ margin: 0 }}><strong>{str(r.title)}</strong>. {str(r.kind)}: {str(r.reason)}{r.review_date ? `. Review by ${str(r.review_date)}` : ""}</p>)}
              </PageBox>
            );
          default:
            return (
              <PageBox key={p.n} p={p}>
                {!p.accept && rows.length ? <p className="ds-muted" style={{ margin: 0 }}>{t.openItems}</p> : null}
                {rows.map((r) => (
                  <label key={str(r.text)} className="ch-risk">
                    {p.accept && c.editable ? <input type="checkbox" aria-label={`${t.acceptRisk}: ${str(r.text)}`} checked={Boolean(r.accepted_by)} disabled={busy}
                      onChange={(e) => void run(() => apiSend<CharterData>("PUT", `${url}/risks`, e.target.checked ? { accept: [r.text] } : { unaccept: [r.text] }))} /> : null}
                    <span>{str(r.text)}{r.accepted_by ? ` ${t.acceptedBy(str(r.accepted_by))}.` : ""}</span>
                  </label>
                ))}
              </PageBox>
            );
        }
      })}
    </>
  );
}

function SignModal({ who, title, busy, onYes, onNo }: { who: string; title: string; busy: boolean; onYes: () => void; onNo: () => void }) {
  return (
    <div className="ch-scrim" onClick={onNo}>
      <div role="dialog" aria-modal="true" aria-label={t.modalTitle} className="ds-card ch-dlg" onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: 0 }}>{t.modalTitle}</h2>
        <p style={{ margin: 0 }}>{t.modalText(who, title)}</p>
        <Button variant="primary" disabled={busy} onClick={onYes}>{t.modalYes}</Button>
        <Button onClick={onNo}>{t.modalNo}</Button>
      </div>
    </div>
  );
}

function Download({ sessionId, enabled }: { sessionId: string; enabled: boolean }) {
  const [problem, setProblem] = useState<string | null>(null);
  const fetchFiles = () => apiGet<{ files: { format: string; filename: string; mime: string; content: string }[] }>(`/api/modules/m1_intent/sessions/${sessionId}/charter/download`);
  const markdown = async () => {
    try {
      const f = (await fetchFiles()).files.find((x) => x.format === "markdown");
      if (!f) throw new Error("none");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([f.content], { type: f.mime }));
      a.download = f.filename;
      a.click();
      setProblem(null);
    } catch (e) { setProblem(e instanceof ApiError && e.status === 403 ? t.downloadRefused : t.downloadFailed); }
  };
  const pdf = async () => {
    try {
      const f = (await fetchFiles()).files.find((x) => x.format === "html");
      const w = window.open("", "_blank");
      if (!f || !w) throw new Error("none");
      w.document.open();
      w.document.write(f.content);
      w.document.close();
      w.focus();
      w.print();
      setProblem(null);
    } catch (e) { setProblem(e instanceof ApiError && e.status === 403 ? t.downloadRefused : t.downloadFailed); }
  };
  return (
    <details className="ch-menu">
      <summary className="ds-btn">{t.download}</summary>
      <div className="ds-card ch-menu__items">
        {enabled ? (
          <>
            <Button onClick={() => void pdf()}>{t.downloadPdf}</Button>
            <Button onClick={() => void markdown()}>{t.downloadMd}</Button>
          </>
        ) : <p className="ds-muted" style={{ margin: 0 }}>{t.downloadWaits}</p>}
        {problem ? <p role="alert" className="ds-warn" style={{ margin: 0 }}>{problem}</p> : null}
      </div>
    </details>
  );
}

/** /centre/intent/<id>/charter: the charter as ten pages, with Signature, Build-ready, Who does what and Version history beside it. */
export default function CharterView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const [params] = useSearchParams();
  const [page, setPage] = useState<CharterData | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "populated">("loading");
  const [message, setMessage] = useState<string | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [sure, setSure] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [reason, setReason] = useState("");
  const [link, setLink] = useState<Sent | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const version = params.get("version");
  const nav = useNavigate();

  useEffect(() => {
    let live = true;
    apiGet<CharterData>(`/api/intents/${intentId}/charter${version ? `?version=${encodeURIComponent(version)}` : ""}`)
      .then((d) => { if (live) { setPage(d); setState("populated"); } })
      .catch((e: unknown) => { if (live && e instanceof ApiError && e.status === 404) { nav(`/centre/intent/${encodeURIComponent(intentId)}/sign`, { replace: true }); return; }  // FIXE1: an intent of work has no charter; its signing page is /sign
        if (live) { setMessage(e instanceof ApiError && e.status !== 0 && e.status < 500 ? e.message : undefined); setState(e instanceof ApiError && e.status === 403 ? "refused" : "error"); } });
    return () => { live = false; };
  }, [intentId, version, attempt, nav]);

  const reload = useCallback(() => setAttempt((a) => a + 1), []);
  const run = useCallback(async (work: () => Promise<CharterData>) => {
    setBusy(true);
    setProblem(null);
    try { setPage(await work()); } catch (e) { setProblem(problemText(e)); } finally { setBusy(false); }
  }, []);

  if (state !== "populated" || !page) return <PageFrame title="Charter" crumbs={t.crumbs}><ScreenState state={state === "loading" ? "loading" : state} message={state === "loading" ? t.loading : message} onRetry={reload} /></PageFrame>;
  const { intent, charter: c } = page;
  const pages = page.pages ?? [];
  const base = `/api/intents/${intentId}/charter`;

  if (page.tier === "named" && page.role_request) {
    return <PageFrame title={intent.title} crumbs={t.crumbs}><RoleRequest intentId={intentId} data={page.role_request} onAnswered={reload} /><Link className="ds-link" to="/centre/action">{rolesCopy.notNow}</Link></PageFrame>;
  }
  if (page.tier === "card") {
    return (
      <PageFrame title={intent.title} subline={intent.purpose ?? t.noPurpose} crumbs={t.crumbs}>
        <ScreenState state="empty" message={page.message ?? t.card} />
        {page.outcome_line ? <p role="status">{page.outcome_line}</p> : null}
      </PageFrame>
    );
  }
  const organiser = Boolean(page.viewer?.organiser);
  const signed = c?.status === "signed";
  const sendRoute = c ? `/api/modules/m1_intent/sessions/${c.session_id}/charter` : "";
  const request = params.get("role") ? page.role_request ?? null : null; // a link from a Pulse line opens the request for that role

  return (
    <div className="ch-page-wrap">
      <PageFrame
        crumbs={t.crumbs}
        title={intent.title}
        subline={intent.purpose ?? t.noPurpose}
        actions={c ? (
          <>
            <Pill tone={c.state === "Signed" ? "signed" : c.state === "Superseded" ? "late" : "draft"}>{t.state[c.state] ?? c.state}</Pill>
            <Chip href="#version-history">{t.version(c.version, c.of)}</Chip>
            {page.viewer?.closer && c.current && c.status === "draft" ? <Button className="ch-head-sign" variant="primary" disabled={busy || !c.can_sign} title={c.sign_block ?? undefined} onClick={() => setSure(true)}>{t.sign}</Button> : null}
            <Download sessionId={c.session_id} enabled={c.can_download} />
            {c.can_new_version ? <Button disabled={busy} onClick={() => void run(() => apiSend<CharterData>("POST", `${base}/versions`, {}))}>{t.newVersion}</Button> : null}
            {c.can_discard ? <Button disabled={busy} onClick={() => setDiscarding(true)}>{t.discard}</Button> : null}
          </>
        ) : undefined}
        aside={c ? (
          <>
            <SideCard title={t.signature}>
              {c.signature.signed_by ? (
                <Signature state="signed" by={c.signature.signed_by} at={`${when(c.signature.signed_at)} · ${c.signature.how ?? ""}`} />
              ) : (
                <>
                  <p className="ds-muted" style={{ margin: 0 }}>{t.needsOne(c.signature.needed)}</p>
                  <div className="ch-sigline"><span>{t.waitingFor(c.signature.needed)}</span></div>
                </>
              )}
              {page.viewer?.closer && c.current && c.status === "draft" ? (
                <div className="ch-sign">
                  <Button variant="primary" disabled={busy || !c.can_sign} onClick={() => setSure(true)}>{t.sign}</Button>
                  {!c.can_sign && c.sign_block ? <p role="status" className="ds-muted" style={{ margin: 0 }}>{c.sign_block}</p> : null}
                </div>
              ) : null}
              {organiser && c.current && c.status === "draft" && c.approver.link === "none" && c.approver.name ? (
                <Button disabled={busy} onClick={() => void (async () => { try { const s = await apiSend<CharterData & Sent>("POST", `${sendRoute}/send`, {}); setLink(s); reload(); } catch (e) { setProblem(problemText(e)); } })()}>{t.send}</Button>
              ) : null}
              {organiser && c.current && c.status === "draft" && !c.approver.name ? <p className="ds-muted" style={{ margin: 0 }}>{t.noApprover}</p> : null}
              {c.status === "awaiting_approver" && organiser ? (
                <>
                  <p className="ds-muted" style={{ margin: 0 }}>{t.linkOut(c.approver.name ?? "the approver")}</p>
                  {link ? <Button onClick={() => void navigator.clipboard.writeText(`${window.location.origin}${link.link_path}`).then(() => setNotice(t.copied))}>{t.copyLink}</Button> : null}
                  <Button disabled={busy} onClick={() => void (async () => { try { await apiSend("POST", `${sendRoute}/withdraw`, {}); setLink(null); reload(); } catch (e) { setProblem(problemText(e)); } })()}>{t.withdraw}</Button>
                </>
              ) : null}
              {notice ? <p role="status" className="ds-muted" style={{ margin: 0 }}>{notice}</p> : null}
            </SideCard>
            <BuildReadyPanel intentId={intentId} />
            <RolesPanel intentId={intentId} canEdit={Boolean(page.roles?.can_edit)} onChange={reload} />
            <div id="version-history">
              <SideCard title={t.versions}>
                {(page.versions ?? []).length <= 1 && !signed ? <p className="ds-muted" style={{ margin: 0 }}>{t.draftOnly}</p> : (
                  <>
                    <VersionList versions={(page.versions ?? []).map((v) => ({ v: v.version, what: `${t.state[v.state] ?? v.state}${v.current ? ` (${t.thisVersion.toLowerCase()})` : ""}${v.discarded ? `: ${v.discarded.reason}` : ""}${v.comment ? `. ${v.comment}` : ""}`, by: v.signed_by ? `signed by ${v.signed_by}` : v.created_by, at: when(v.signed_at ?? v.created_at) }))} />
                    {(page.versions ?? []).filter((v) => !v.current && !v.discarded).map((v) => <Link key={v.version} className="ds-link" to={`?version=${v.version}`}>{t.openThisVersion} {v.version}</Link>)}
                  </>
                )}
              </SideCard>
            </div>
          </>
        ) : undefined}
      >
        {request ? <RoleRequest intentId={intentId} data={request} onAnswered={reload} /> : null}
        {!c ? <ScreenState state="empty" message={page.message ?? t.noCharter} /> : (
          <>
            {c.returned ? <p role="status" className="ds-card ch-banner">{t.returned(c.returned.by, c.returned.comment)}</p> : null}
            {signed && c.signature.signed_by ? <p role="status" className="ds-card ch-banner">{t.signedBanner(c.signature.signed_by, dayOf(c.signature.signed_at))}</p> : null}
            {!c.current ? <p role="status" className="ds-card ch-banner">{t.oldVersion}</p> : null}
            {c.north && organiser ? <p role="status" className="ds-card ch-banner"><strong>North</strong>: {c.north}</p> : null}
            {signed && c.handoff?.at ? <p className="ds-muted" style={{ margin: 0 }}>{t.handoff(dayOf(c.handoff.at), c.handoff.measure_count ?? 0, c.handoff.source_count ?? 0)}</p> : null}
            {problem ? <p role="alert" className="ds-warn" style={{ margin: 0 }}>{problem}</p> : null}
            <details className="ch-index" open>
              <summary>{t.pagesBar}</summary>
              <ol>{pages.map((p) => <li key={p.n}><a href={`#page-${p.n}`}>{p.title}</a>{p.status === "ok" ? <span aria-label="Has content"> ✓</span> : <span className="ds-muted"> {t.empty}</span>}</li>)}</ol>
            </details>
            <Pages pages={pages} c={c} intentId={intentId} busy={busy} run={run} />
          </>
        )}
      </PageFrame>
      {c && page.viewer?.closer && c.current && c.status === "draft" ? (
        <div className="ch-sticky"><Button variant="primary" disabled={busy || !c.can_sign} onClick={() => setSure(true)}>{t.sign}</Button>{!c.can_sign && c.sign_block ? <span className="ds-muted">{c.sign_block}</span> : null}</div>
      ) : null}
      {sure && c ? <SignModal who={page.viewer?.name ?? ""} title={intent.title} busy={busy} onNo={() => setSure(false)}
        onYes={() => { setSure(false); void run(() => apiSend<CharterData>("POST", `${base}/sign`, { confirm_sponsor: true, version: c.version, edited_at: c.edited_at })); }} /> : null}
      {discarding && c ? (
        <div className="ch-scrim" onClick={() => setDiscarding(false)}>
          <div role="dialog" aria-modal="true" aria-label={t.discard} className="ds-card ch-dlg" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ margin: 0 }}>{t.discard}</h2>
            <label className="ch-field">{t.discardWhy}<input type="text" value={reason} maxLength={300} onChange={(e) => setReason(e.target.value)} /></label>
            <Button variant="primary" disabled={busy || !reason.trim()} onClick={() => { setDiscarding(false); void run(() => apiSend<CharterData>("POST", `${base}/versions/${c.version}/discard`, { reason })); }}>{t.discardGo}</Button>
            <Button onClick={() => setDiscarding(false)}>{t.cancel}</Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
