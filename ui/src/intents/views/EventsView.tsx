import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiGet, Refused } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Chip, PageFrame, Pill } from "../../design";

// What happened (spec 16): the read-only timeline of one intent, cut on the server to what this viewer may see.
// The server filters (kind, person, stage) and pages; the browser only groups the lines under day headings.

interface Line {
  seq: number; at: string; kind: string; group: string; status: "act" | "draft"; stage: string; who: string | null; person?: string | null;
  anonymous: boolean; agent: string | null; sentence: string; stub: string | null; confirms: number | null; corrects: number | null; superseded: boolean;
  confirmed_by?: { seq: number; name: string; at: string } | null;
}
interface Page {
  items: Line[]; total: number; visible: number; next: number | null; last_seq: number; mode: "full" | "milestones"; zone: string; download: boolean;
  groups: { key: string; name: string; count: number }[]; stages: { key: string; name: string; count: number }[];
  summary: { by_group: Record<string, number>; people: { name: string; count: number | null; few: boolean }[]; anonymous: number; drafts: number; acts: number };
  intent: { title: string; state: string; type: string; closed_at?: string | null; created_at?: string | null };
}
interface TranscriptFiles { files: { format: string; filename: string; mime: string; content: string }[] }

const T = {
  title: "What happened", note: "This is a record. It cannot be changed.", none: "Nothing has happened in this intent yet.",
  noOne: "No one has said or done anything yet.", closedOnly: "Available when the intent is closed", milestones: "Milestones and counts only.",
  shut: "The history is open to the people in this intent.", missing: "We could not find that.", failed: "The history did not load. Nothing was changed. Try again in a moment.",
};
const FIRST = 100, MORE = 50, POLL_MS = 30000;

const CSS = `
.ev-grid{display:grid;grid-template-columns:220px minmax(0,720px) 240px;gap:20px;align-items:start}
.ev-link{background:none;border:0;padding:0;color:var(--ds-teal-bright);text-decoration:underline;cursor:pointer;text-align:left;font:inherit}
.ev-panel{display:flex;flex-direction:column;gap:8px}.ev-row{display:flex;flex-wrap:wrap;gap:6px}
.ev-line{display:grid;grid-template-columns:3.5rem 1fr;gap:4px 12px;padding:8px 0;border-bottom:1px solid var(--ds-line,#e3e6e8)}
.ev-line--hit{background:var(--ds-soft-bg,#eef6f6)}.ev-kind{grid-column:2}.ev-day{display:flex;justify-content:space-between;width:100%;margin:16px 0 4px;font-weight:600;background:none;border:0;padding:0;cursor:pointer;text-align:left}
.ev-strip,.ev-filter-btn{display:none}.ev-bar{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:8px;padding:8px 0}
.ev-sheet{background:var(--ds-surface);color:var(--ds-ink);width:100%;max-width:none;margin:auto 0 0;border:0;border-radius:16px 16px 0 0;padding:16px}.ev-sheet::backdrop{background:rgba(0,0,0,.4)}
@media (max-width:900px){.ev-grid{grid-template-columns:1fr}.ev-filters,.ev-summary{display:none}.ev-filter-btn,.ev-strip{display:block}.ev-strip{flex:1 1 100%;white-space:normal;text-align:left;border-radius:12px}
.ev-line{grid-template-columns:1fr}.ev-kind{grid-column:1;order:-1}}`;

// The server's wording is cut to the viewer; these tidy what older logs left (a raw key, a kind with no wording) until the kinds table has it.
const LEGACY: Record<string, (who: string) => string> = {
  closure_signed: (w) => `${w} signed the closing summary`, closed_incomplete: (w) => `${w} closed the intent with what we have`, intent_opened: (w) => `${w} opened this intent`,
};
export const tidy = (l: { kind: string; who: string | null; sentence: string }) => {
  const who = l.who ?? "Someone";
  const raw = l.sentence === `${who}: ${l.kind.replace(/_/g, " ")}` ? LEGACY[l.kind]?.(who) : undefined;
  return (raw ?? l.sentence).replace(/([a-z]+)_([a-z_]+)/g, (m) => (m === "no_decision" ? "no decision" : m.replace(/_/g, " ")));
};
/** The screen that holds what a line was about; the stage view when none fits better. */
export const openPath = (l: { kind: string; sentence: string }, id: string) => {
  const k = l.kind, base = `/centre/intent/${encodeURIComponent(id)}`;
  const sub = /^(person_|joined|join_)/.test(k) ? "people" : /^(definition|shelf|cluster|define|lens_)/.test(k) ? "define" : /^(build_ready|handed_to_build)/.test(k) ? "build-ready"
    : /^(shared|share_)/.test(k) ? "share" : /^(closing|closure|closed|cancelled)/.test(k) || (k === "signed" && /closing summary|closure/.test(l.sentence)) ? "close" : "";
  return sub ? `${base}/${sub}` : base;
};

/** The "What happened (n)" link for a stage view. Nothing shows for a person the history is not open to. */
export function EventsLink({ intentId }: { intentId: string }) {
  const [n, setN] = useState<number | null>(null);
  useEffect(() => { apiGet<{ visible: number }>(`/api/intents/${encodeURIComponent(intentId)}/events?limit=1`).then((d) => setN(d.visible), () => setN(null)); }, [intentId]);
  if (n === null) return null;
  return <Link className="ds-link" style={{ display: "inline-flex", alignItems: "center", minHeight: 44 }} to={`/centre/intent/${encodeURIComponent(intentId)}/events`}>{`${T.title} (${n})`}</Link>;
}

const hhmm = (at: string, zone: string) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: zone }).format(new Date(at));
const dayOf = (at: string, zone: string) => new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: zone }).format(new Date(at));

export default function EventsView() {
  const { intentId = "" } = useParams<{ intentId: string }>();
  const [data, setData] = useState<Page | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [state, setState] = useState<"loading" | "error" | "refused" | "missing" | "ready">("loading");
  const [off, setOff] = useState<string[]>([]);
  const [by, setBy] = useState("");
  const [stage, setStage] = useState<string[]>([]);
  const [shut, setShut] = useState<string[]>([]);
  const [fresh, setFresh] = useState(0);
  const [hit, setHit] = useState<number | null>(null);
  const [sheet, setSheet] = useState(false);
  const [sum, setSum] = useState(false);
  const [dl, setDl] = useState(false);
  const [born, setBorn] = useState("");
  const sheetRef = useRef<HTMLDialogElement>(null);

  const query = useCallback((extra: Record<string, string | number>) => {
    const p = new URLSearchParams();
    if (off.length && data) p.set("kind", data.groups.map((g) => g.key).filter((k) => !off.includes(k)).join(",") || "none");
    if (by) p.set("by", by);
    if (stage.length === 1) p.set("stage", stage[0]!);
    Object.entries(extra).forEach(([k, v]) => p.set(k, String(v)));
    return `/api/intents/${encodeURIComponent(intentId)}/events?${p}`;
  }, [intentId, off, by, stage, data]);

  const load = useCallback(() => {
    apiGet<Page>(query({ limit: FIRST })).then((d) => { setData(d); setLines(d.items); setFresh(0); setState("ready"); })
      .catch((e) => setState(e instanceof Refused || (e instanceof ApiError && e.status === 403) ? "refused" : e instanceof ApiError && e.status === 404 ? "missing" : "error"));
  }, [query]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setState((s) => (s === "ready" ? s : "loading")); load(); }, [intentId, off, by, stage]);

  useEffect(() => {  // a poll, not a push: a bar says how many lines arrived
    if (!data) return;
    const id = window.setInterval(() => {
      apiGet<Page>(query({ after: data.last_seq, limit: 100 })).then((d) => setFresh(d.total)).catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [data, query]);

  useEffect(() => {  // an intent with no log: say when its history starts
    if (state !== "ready" || !data || data.visible > 0) return;
    (data.intent.created_at ? Promise.resolve({ created_at: data.intent.created_at }) : apiGet<{ created_at?: string }>(`/api/intents/${encodeURIComponent(intentId)}`)).then((r) => setBorn(r.created_at ? new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: data.zone }).format(new Date(r.created_at)) : ""), () => setBorn(""));
  }, [state, data, intentId]);

  useEffect(() => {
    const d = sheetRef.current;
    if (!d) return;
    if (sheet && !d.open) d.showModal?.();
    if (!sheet && d.open) d.close?.();
  }, [sheet]);

  const more = () => data?.next && apiGet<Page>(query({ before: data.next, limit: MORE })).then((d) => { setLines((l) => [...l, ...d.items]); setData({ ...d, items: [] }); });
  const toggle = (g: string) => setOff((o) => (o.includes(g) ? o.filter((x) => x !== g) : [...o, g]));
  const only = (g: string) => setOff(data!.groups.map((x) => x.key).filter((k) => k !== g));
  const clear = () => { setOff([]); setBy(""); setStage([]); };
  const filtered = off.length > 0 || by !== "" || stage.length > 0;
  const jump = (seq: number) => { setHit(seq); document.getElementById(`ev-${seq}`)?.scrollIntoView({ block: "center" }); };

  let body;
  if (state === "loading") body = <ScreenState state="loading" />;
  else if (state === "refused") body = <ScreenState state="refused" message={T.shut} />;
  else if (state === "missing") body = <ScreenState state="refused" message={T.missing} />;
  else if (state === "error" || !data) body = <ScreenState state="error" message={T.failed} onRetry={load} />;
  else {
    const milestones = data.mode === "milestones";
    const days = lines.reduce<Record<string, Line[]>>((m, l) => { (m[dayOf(l.at, data.zone)] ||= []).push(l); return m; }, {});
    const sm = data.summary;
    const filters = (
      <div className="ev-panel">
        <strong>Kind of line</strong>
        <div className="ev-row" role="group" aria-label="Kind of line">
          {data.groups.map((g) => <span key={g.key} style={g.count === 0 ? { opacity: 0.45, pointerEvents: "none" } : undefined}><Chip tone={off.includes(g.key) ? "default" : "active"} onClick={() => toggle(g.key)}>{`${g.name} ${g.count}`}</Chip></span>)}
        </div>
        {!milestones && <>
          <strong>Person</strong>
          <label className="ds-muted" htmlFor="ev-by">Show lines by</label>
          <select id="ev-by" className="ds-input" value={by} onChange={(e) => setBy(e.target.value)}>
            <option value="">Everyone</option>
            {sm.people.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
            {sm.anonymous > 0 && <option value="anonymous">{`Anonymous (${sm.anonymous})`}</option>}
          </select>
          {sm.people.length === 0 && sm.anonymous === 0 && <p className="ds-muted">{T.noOne}</p>}
        </>}
        <strong>Stage</strong>
        <div className="ev-row" role="group" aria-label="Stage">
          {data.stages.map((s) => <span key={s.key} style={s.count === 0 ? { opacity: 0.45, pointerEvents: "none" } : undefined}><Chip tone={stage.includes(s.key) ? "active" : "default"} onClick={() => setStage((c) => (c.includes(s.key) ? [] : [s.key]))}>{`${s.name} ${s.count}`}</Chip></span>)}
        </div>
        {filtered && <Button onClick={clear}>Clear filters</Button>}
      </div>
    );
    const kinds = data.groups.filter((g) => g.count > 0);
    const summary = (
      <div className="ev-panel">
        <strong>What kind of talk happened</strong>
        {kinds.length === 0 ? <p className="ds-muted">Not available yet: nothing has been recorded.</p>
          : kinds.map((g) => <button key={g.key} type="button" className="ds-chip" onClick={() => only(g.key)}>{`${g.name}: ${g.count}`}</button>)}
        {milestones ? <p className="ds-muted">{T.milestones}</p> : <>
          {sm.people.length > 0 && <><strong>By person</strong>{sm.people.map((p) => <button key={p.name} type="button" className="ds-chip" onClick={() => setBy(p.name)}>{`${p.name}: ${p.few ? "Fewer than five" : p.count}`}</button>)}</>}
          {sm.anonymous > 0 && <span className="ds-chip">{`Anonymous: ${sm.anonymous}`}</span>}
        </>}
        <p>{`Drafted by agents: ${sm.drafts}. Done by people: ${sm.acts}.`}</p>
      </div>
    );
    body = (
      <>
        <style>{CSS}</style>
        <p className="ds-muted">{T.note}</p>
        <div className="ev-bar">
          <button type="button" className="ev-strip ds-chip" aria-expanded={sum} onClick={() => setSum(!sum)}>{`${data.visible} recorded: ${kinds.map((g) => `${g.count} ${g.name.toLowerCase()}`).join(", ") || "nothing yet"}`}</button>
          <button type="button" className="ev-filter-btn ds-btn" onClick={() => setSheet(true)}>Filter</button>
          {!milestones && (data.download
            ? <Button variant="primary" onClick={() => setDl(true)}>Download transcript</Button>
            : <Button disabled title={T.closedOnly}>Download transcript</Button>)}
        </div>
        {sum && <div className="ds-card">{summary}</div>}
        {fresh > 0 && <button type="button" className="ds-btn ds-btn--primary" onClick={load}>{`${fresh} new event${fresh === 1 ? "" : "s"}`}</button>}
        <div className="ev-grid">
          <div className="ev-filters ds-card">{filters}</div>
          <div>
            {lines.length === 0
              ? <ScreenState state="empty" message={filtered ? "No line matches these filters." : born ? `History starts on ${born}; earlier steps were not recorded.` : T.none} />
              : Object.entries(days).map(([day, ls]) => (
                <section key={day} aria-label={day}>
                  <button type="button" className="ev-day" aria-expanded={!shut.includes(day)} onClick={() => setShut((s) => (s.includes(day) ? s.filter((x) => x !== day) : [...s, day]))}>
                    <span>{day}</span><span className="ds-muted">{ls.length}</span>
                  </button>
                  {!shut.includes(day) && <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>{ls.map((l) => (
                    <li key={l.seq} id={`ev-${l.seq}`} className={`ev-line${hit === l.seq ? " ev-line--hit" : ""}`} style={l.superseded ? { opacity: 0.6 } : undefined}>
                      <span className="ds-muted">{hhmm(l.at, data.zone)}</span>
                      <span>{l.stub ? l.stub : tidy(l)}{!l.stub && <> <Link className="ev-link" style={{ display: "inline-flex", alignItems: "center", minHeight: 44 }} to={openPath(l, intentId)}>Open</Link></>}</span>
                      <span className="ev-kind ev-row">
                        {l.status === "draft" && <span title={l.confirmed_by ? `Confirmed by ${l.confirmed_by.name}, ${hhmm(l.confirmed_by.at, data.zone)}` : "Not confirmed yet"}><Pill tone="draft">{`Draft by ${l.agent === "lens" ? "Lens" : "North"}`}</Pill></span>}
                        {l.status === "draft" && l.confirmed_by && <button type="button" className="ev-link" onClick={() => jump(l.confirmed_by!.seq)}>{`Confirmed by ${l.confirmed_by.name}`}</button>}
                        {l.confirms !== null && lines.find((x) => x.seq === l.confirms) && <button type="button" className="ev-link" onClick={() => jump(l.confirms!)}>{`Confirms the draft from ${hhmm(lines.find((x) => x.seq === l.confirms)!.at, data.zone)}`}</button>}
                        {l.superseded && <span className="ds-muted">Superseded</span>}
                      </span>
                    </li>))}</ul>}
                </section>))}
            {data.next !== null && <Button onClick={more}>{`Show ${MORE} more`}</Button>}
            <p className="ds-muted">{`Times are in ${data.zone}.`}</p>
          </div>
          <aside className="ev-summary ds-card">{summary}</aside>
        </div>
        <dialog ref={sheetRef} className="ev-sheet" onClose={() => setSheet(false)} aria-label="Filter">
          {sheet && <>{filters}<Button variant="primary" onClick={() => setSheet(false)}>Show lines</Button></>}
        </dialog>
        {dl && <Download id={intentId} title={data.intent.title} closed={data.intent.closed_at ? dayOf(data.intent.closed_at, data.zone) : ""} count={data.visible} drafts={sm.drafts} onClose={() => setDl(false)} />}
      </>
    );
  }
  return <PageFrame title={T.title} subline={data?.intent.title}>{body}</PageFrame>;
}

/** Screen 2: the transcript dialog. Markdown is a file; PDF is the printable page through the browser's print dialog. */
export function Download({ id, title, closed = "", count, drafts, onClose }: { id: string; title: string; closed?: string; count: number; drafts: number; onClose: () => void }) {
  const [withDrafts, setWithDrafts] = useState(true);
  const [err, setErr] = useState("");
  const fetchFiles = () => apiGet<TranscriptFiles>(`/api/intents/${encodeURIComponent(id)}/transcript/download?drafts=${withDrafts ? 1 : 0}`);
  const fail = () => setErr("The transcript could not be made. Nothing was changed. Try again in a moment.");
  const md = () => fetchFiles().then(({ files }) => {
    const f = files.find((x) => x.format === "md")!;
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([f.content], { type: f.mime })), download: f.filename });
    a.click();
    URL.revokeObjectURL(a.href);
  }).catch(fail);
  const pdf = () => fetchFiles().then(({ files }) => {
    const w = window.open("", "_blank");
    if (!w) return setErr("The browser blocked the new tab. Allow pop-ups for this page and try again.");
    w.document.write(files.find((x) => x.format === "html")!.content);
    w.document.close();
    w.focus();
    w.print();
  }).catch(fail);
  const shown = count - (withDrafts ? 0 : drafts);
  return (
    <div role="dialog" aria-modal="true" aria-label="Download transcript" className="ds-card" style={{ position: "fixed", inset: "auto 0 0 0", margin: "0 auto", maxWidth: 480, zIndex: 20, padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <p>{shown > 0 ? `Transcript of: ${title}${closed ? `, closed ${closed}` : ""}. ${shown} events. Cut to what you may see.` : "Nothing was recorded."}</p>
      <label><input type="checkbox" checked={withDrafts} onChange={(e) => setWithDrafts(e.target.checked)} /> Include agent drafts</label>
      {err && <p role="alert">{err}</p>}
      <div className="ev-row">
        <Button variant="primary" disabled={shown <= 0} onClick={md}>Download Markdown</Button>
        <Button disabled={shown <= 0} onClick={pdf}>Download PDF</Button>
        <Button onClick={onClose}>Close</Button>
      </div>
    </div>
  );
}
