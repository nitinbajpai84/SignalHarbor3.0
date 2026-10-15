import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiGet, apiSend } from "../../api/client";
import ScreenState from "../../components/ScreenState";
import { Button, Chip } from "../../design";
import BottomBar from "../BottomBar";
import "./checkin.css";
import { clockText, dateWords, entryCopy as t, kindName, severityName } from "./checkinCopy";
import { usePhone } from "./SeriesFields";

// Spec 39 Screen A: the reporter's entry. Three questions (and the organiser's own), North's drafts marked guessed, one card per line.

export interface Ref { kind: "measure" | "process"; id: string; label: string; intent: string | null }
export interface Item {
  id: string; kind: string; extra: boolean; text: string; anonymous: boolean; mark: "stated" | "guessed"; severity: string | null; count: number | null;
  unit: string | null; amount: { value: number; currency: string } | null; ref: Ref | null; fate: string | null; fate_reason: string | null; sent: boolean;
}
interface Prompt { kind: string; lead: string; extra?: boolean }
interface Entry {
  week: { week_key: string; opens: string; answers_close: string; review_day: string; closes: string; state: string }; title: string; area: string; prompts: Prompt[];
  participant: boolean; can_edit: boolean; status: string; submitted_at: string | null; skipped: string[]; active_seconds: number; items: Item[]; withdrawn: number;
  guessed: number; next_week_opens: string | null; has_newer: boolean; series_status: string;
}
interface Draft { id: string; kind: string; text: string; evidence: string; label: string; from: { record: string; at: string | null }[] }
interface Measure { code: string; name: string }

const lineOf = (p: Prompt) => (p.extra ? "extra" : p.kind);

function Sheet({ item, onSave, onRemove, onClose, measures }: { item: Item; onSave: (b: Record<string, unknown>) => void; onRemove: () => void; onClose: () => void; measures: Measure[] | null }) {
  const [text, setText] = useState(item.text);
  const [count, setCount] = useState(item.count === null ? "" : String(item.count));
  const [unit, setUnit] = useState(item.unit ?? "times");
  const [amount, setAmount] = useState(item.amount ? String(item.amount.value) : "");
  const [cur, setCur] = useState(item.amount?.currency ?? "");
  const [tab, setTab] = useState<"measure" | "process">("measure");
  const [find, setFind] = useState("");
  const [asking, setAsking] = useState(false);
  const found = (measures ?? []).filter((m) => `${m.name} ${m.code}`.toLowerCase().includes(find.toLowerCase())).slice(0, 8);
  return (
    <div className="ck-sheet" role="dialog" aria-label={kindName[item.kind]}>
      {!(typeof window !== "undefined" && window.matchMedia?.("(max-width: 700px)").matches) ? null : <span className="ic-sheet__handle" aria-hidden="true" />}
      <div className="ck-field">
        <label htmlFor={`w-${item.id}`}>{t.words}</label>
        <textarea id={`w-${item.id}`} value={text} maxLength={600} onChange={(e) => setText(e.target.value)} onBlur={() => text.trim() && text !== item.text && onSave({ text })} />
      </div>
      {item.kind === "broke" && (
        <>
          <div className="ck-field">
            <span className="ck-label" id={`s-${item.id}`}>{t.severity}</span>
            <div className="ck-seg" role="group" aria-labelledby={`s-${item.id}`}>
              {Object.entries(severityName).map(([k, n]) => (
                <Button key={k} aria-pressed={item.severity === k} onClick={() => onSave({ severity: item.severity === k ? null : k })}>{n}</Button>
              ))}
            </div>
          </div>
          {item.severity === "cost" ? (
            <div className="ck-field">
              <label htmlFor={`a-${item.id}`}>{t.amount}</label>
              <div className="ck-row">
                <input id={`a-${item.id}`} type="number" min={0} style={{ flex: "1 1 120px" }} value={amount} placeholder={t.blank} onChange={(e) => setAmount(e.target.value)}
                  onBlur={() => onSave({ amount: amount === "" ? null : { value: Number(amount), currency: cur } })} />
                <input type="text" aria-label={t.currency} style={{ flex: "1 1 120px" }} value={cur} maxLength={4} placeholder={t.currency} onChange={(e) => setCur(e.target.value)}
                  onBlur={() => amount !== "" && onSave({ amount: { value: Number(amount), currency: cur } })} />
              </div>
            </div>
          ) : (
            <div className="ck-field">
              <label htmlFor={`c-${item.id}`}>{t.count}</label>
              <div className="ck-row">
                <input id={`c-${item.id}`} type="number" min={0} style={{ flex: "1 1 120px" }} value={count} placeholder={t.blank} onChange={(e) => setCount(e.target.value)}
                  onBlur={() => onSave({ count: count === "" ? null : Number(count), unit })} />
                <select aria-label={t.count} style={{ flex: "1 1 120px" }} value={unit} onChange={(e) => { setUnit(e.target.value); count !== "" && onSave({ count: Number(count), unit: e.target.value }); }}>
                  <option value="times">{t.times}</option><option value="hours">{t.hours}</option>
                </select>
              </div>
            </div>
          )}
        </>
      )}
      <div className="ck-field">
        <span className="ck-label">{t.linksTo}</span>
        {item.ref ? <div className="ck-row"><span className="ck-tag">{item.ref.label}</span><Button aria-label="Remove the link" onClick={() => onSave({ ref: null })}>x</Button></div> : <p className="ck-muted">{t.noLink}</p>}
        <div className="ck-row">
          <Chip tone={tab === "measure" ? "active" : "default"} onClick={() => setTab("measure")}>{t.tabMeasure}</Chip>
          <Chip tone={tab === "process" ? "active" : "default"} onClick={() => setTab("process")}>{t.tabProcess}</Chip>
        </div>
        {tab === "process" ? <p className="ck-muted">{t.noProcess}</p> : measures && measures.length === 0 ? <p className="ck-muted">{t.noMeasures}</p> : (
          <>
            <input type="text" aria-label={t.searchMeasure} placeholder={t.searchMeasure} value={find} onChange={(e) => setFind(e.target.value)} />
            <div className="ck-row">{found.map((m) => <Chip key={m.code} onClick={() => onSave({ ref: { kind: "measure", id: m.code, label: m.name, intent: null } })}>{m.name}</Chip>)}</div>
          </>
        )}
      </div>
      <label className="ck-row" style={{ gap: 12 }}>
        <input type="checkbox" checked={item.anonymous} onChange={(e) => onSave({ anonymous: e.target.checked })} />
        <span>{t.hideName}<br /><span className="ck-muted">{t.hideNote}</span></span>
      </label>
      <div className="ck-row">
        <Button variant="primary" onClick={onClose}>{t.done}</Button>
        {asking ? (
          <><span>{t.removeAsk}</span><Button onClick={() => setAsking(false)}>{t.keep}</Button><Button onClick={onRemove}>{t.remove}</Button></>
        ) : <Button onClick={() => setAsking(true)}>{t.remove}</Button>}
      </div>
    </div>
  );
}

function Mic({ onText }: { onText: (s: string) => void }) {
  const W = window as unknown as { SpeechRecognition?: new () => { lang: string; onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void; start: () => void }; webkitSpeechRecognition?: unknown };
  const Rec = W.SpeechRecognition ?? (W.webkitSpeechRecognition as typeof W.SpeechRecognition);
  if (!Rec) return null;
  return <Button aria-label={t.speak} onClick={() => { const r = new Rec(); r.lang = "en-GB"; r.onresult = (e) => onText(e.results[0]?.[0]?.transcript ?? ""); r.start(); }}>{t.speak}</Button>;
}

export default function WeekEntry({ intentId }: { intentId: string }) {
  const [params] = useSearchParams();
  const week = params.get("week");
  const q = week ? `?week=${week}` : "";
  const phone = usePhone();
  const [entry, setEntry] = useState<Entry | null | "failed" | { refused: string }>(null);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [past, setPast] = useState<{ week_key: string; opens: string; counts: Record<string, number> }[]>([]);
  const [measures, setMeasures] = useState<Measure[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [block, setBlock] = useState("ran");
  const [draftText, setDraftText] = useState<Record<string, string>>({});
  const [err, setErr] = useState(false);
  const [saved, setSaved] = useState(false);
  const [ask, setAsk] = useState(false);
  const [sent, setSent] = useState(false);
  const [sources, setSources] = useState(false);
  const [mineOpen, setMineOpen] = useState(false);
  const pending = useRef(0);
  const last = useRef<{ op: Record<string, unknown> } | null>(null);

  const loadDrafts = useCallback(() => apiGet<{ drafts: Draft[] }>(`/api/intents/${intentId}/pulse/prefill${q}`).then((r) => setDrafts(r.drafts), () => setDrafts([])), [intentId, q]);
  const load = useCallback(() => {
    apiGet<Entry & { measures?: Measure[] }>(`/api/intents/${intentId}/pulse/entry${q}`).then((e) => { setEntry(e); setMeasures(e.measures ?? []); if (e.can_edit) void loadDrafts(); },
      (e: { message?: string }) => setEntry(e?.message ? { refused: e.message } : "failed"));
  }, [intentId, q, loadDrafts]);
  useEffect(load, [load]);
  useEffect(() => {
    apiGet<{ weeks: { week_key: string; opens: string; counts: Record<string, number> }[] }>(`/api/intents/${intentId}/pulse/mine`).then((r) => setPast(r.weeks.filter((w) => w.week_key !== week).slice(0, 4)), () => undefined);
  }, [intentId, week]);

  const can = typeof entry === "object" && entry !== null && "can_edit" in entry && entry.can_edit;
  const put = useCallback(async (op: Record<string, unknown>) => {
    last.current = { op };
    try {
      const e = await apiSend<Entry>("PUT", `/api/intents/${intentId}/pulse/entry${q}`, op);
      setEntry(e); setErr(false); setSaved(true); setSent(false);
      if (op.op === "keep_draft" || op.op === "keep_all" || op.op === "drop_draft") void loadDrafts();
      return e;
    } catch { setErr(true); return null; }
  }, [intentId, q, loadDrafts]);

  // Active time: counted while the screen is in view, saved in small steps (spec 39, the minutes strip).
  useEffect(() => {
    if (!can) return;
    void apiSend("PUT", `/api/intents/${intentId}/pulse/entry${q}`, { op: "tick", seconds: 0 }).catch(() => undefined);
    const id = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      pending.current += 1;
      if (pending.current >= 15) {
        pending.current -= 15;
        setEntry((o) => (o && typeof o === "object" && "active_seconds" in o ? { ...o, active_seconds: o.active_seconds + 15 } : o));
        void apiSend("PUT", `/api/intents/${intentId}/pulse/entry${q}`, { op: "tick", seconds: 15 }).catch(() => undefined);
      }
    }, 1000);
    return () => window.clearInterval(id);
  }, [can, intentId, q]);

  if (entry === null) return <ScreenState state="loading" />;
  if (entry === "failed") return <ScreenState state="error" message={t.loadFailed} onRetry={load} />;
  if ("refused" in entry) return (
    <div className="ck"><ScreenState state="empty" message={entry.refused} />
      <div><Link className="ds-btn" to={`/centre/intent/${intentId}/review${q}`}>{t.readWeek}</Link></div></div>
  );

  const e = entry;
  const closesWords = dateWords(e.week.closes);
  const submitted = !!e.submitted_at;
  const live = e.items;
  const answeredLine = (p: Prompt) => live.some((i) => (p.extra ? i.extra : i.kind === p.kind && !i.extra)) || (!p.extra && e.skipped.includes(p.kind));
  const ready = e.prompts.some(answeredLine);
  const send = async () => {
    try {
      if (pending.current > 0) { const sec = pending.current; pending.current = 0; await apiSend("PUT", `/api/intents/${intentId}/pulse/entry${q}`, { op: "tick", seconds: sec }).catch(() => undefined); }
      const out = await apiSend<Entry>("POST", `/api/intents/${intentId}/pulse/entry/submit${q}`, {});
      setEntry(out); setSent(true); setAsk(false); setErr(false);
    } catch { setErr(true); }
  };
  const onSend = () => (e.guessed > 0 && !ask ? setAsk(true) : void send());
  const confirmAll = async () => { for (const i of live.filter((x) => x.mark === "guessed")) await put({ op: "confirm", id: i.id }); await send(); };
  const cur = open ? live.find((i) => i.id === open) : undefined;
  const used = clockText(e.active_seconds + pending.current);

  const header = (
    <div>
      <p>{e.area} · {t.weekOf(dateWords(e.week.opens, true))} · {t.closes(closesWords)}</p>
      {can && <p className="ck-muted">{t.answersClose(dateWords(e.week.answers_close))}</p>}
    </div>
  );

  if (!can) {
    const notOpen = e.week.state === "collect" && new Date(`${e.week.opens}T00:00:00`) > new Date();
    return (
      <div className="ck">
        {header}
        {notOpen ? <ScreenState state="empty" message={t.notYet(dateWords(e.week.opens))} /> : (
          <div className="ds-card ck-panel">
            <h3>{e.week.state === "closed" ? t.closedHead : t.answersClosedHead}</h3>
            {e.week.state !== "closed" && <p>{t.answersClosedLine(dateWords(e.week.answers_close), closesWords)}</p>}
            {!submitted && e.participant && <p>{t.late}</p>}
            {!submitted && e.has_newer && <div><Link className="ds-btn ds-btn--primary" to={`/centre/intent/${intentId}/week`}>{t.addNext}</Link></div>}
            {!submitted && !e.has_newer && e.next_week_opens && <p className="ck-muted">{t.nextOpens(dateWords(e.next_week_opens))}</p>}
            {submitted && <p>{e.week.state === "closed" ? t.recordLine(dateWords(e.week.closes)) : t.recordLineOpen(dateWords(e.week.answers_close))}</p>}
            <div><Link className="ds-btn" to={`/centre/intent/${intentId}/week?view=record${week ? `&week=${week}` : ""}`}>{t.record}</Link></div>
          </div>
        )}
        {live.map((i) => <div key={i.id} className={`ck-card ck-card--${i.kind}`}><span>{i.text}</span><span className="ck-row"><span className="ck-tag">{kindName[i.kind]}</span></span></div>)}
      </div>
    );
  }

  const north = (
    <div className="ds-card ck-panel">
      <strong>North</strong>
      <p>{drafts.length ? t.northLine(drafts.length) : t.northNothing}</p>
      {drafts.length > 1 && <div><Button onClick={() => void put({ op: "keep_all" })}>{t.keepAll}</Button></div>}
      {drafts.map((d) => (
        <div key={d.id} className="ck-draft">
          <span>{d.text}</span>
          <span className="ck-muted">{d.evidence}</span>
          <span className="ck-row"><span className="ck-tag ck-tag--guess">{d.label}</span><span className="ck-tag">{kindName[d.kind]}</span></span>
          <span className="ck-row">
            <Button onClick={() => void put({ op: "keep_draft", draft_id: d.id })}>{t.keep}</Button>
            <Button onClick={async () => { const out = await put({ op: "keep_draft", draft_id: d.id }); const mine = out?.items.find((i) => i.text === d.text && i.mark === "guessed"); if (mine) setOpen(mine.id); }}>{t.edit}</Button>
            <Button onClick={() => void put({ op: "drop_draft", draft_id: d.id })}>{t.drop}</Button>
          </span>
        </div>
      ))}
      {drafts.length > 0 && <Button onClick={() => setSources(!sources)}>{t.sources}</Button>}
      {sources && <ul className="ck-list">{drafts.flatMap((d) => d.from.map((f) => <li key={f.record} className="ck-muted">{f.record.replace("warehouse/runs.json#", "Run ").replace("build/alerts.json#", "Alert ")}{f.at ? `, ${f.at.slice(0, 10)}` : ""}</li>))}</ul>}
    </div>
  );

  const rail = (
    <div className="ck">
      {phone ? <Button aria-expanded={mineOpen} onClick={() => setMineOpen(!mineOpen)}>{t.lastWeeks}</Button> : <strong>{t.lastWeeks}</strong>}
      {(!phone || mineOpen) && (past.filter((w) => w.week_key !== e.week.week_key).length === 0 ? <p className="ck-muted">{t.noWeeks}</p> : (
        <ul className="ck-list">{past.filter((w) => w.week_key !== e.week.week_key).map((w) => <li key={w.week_key} className="ck-muted">{`Week of ${dateWords(w.opens, true)}: ${w.counts.ran ?? 0} ran, ${w.counts.broke ?? 0} broke, ${w.counts.thought ?? 0} thought`}</li>)}</ul>
      ))}
      <Link to={`/centre/intent/${intentId}/week?view=mine`} className="ds-link">{t.allWeeks}</Link>
    </div>
  );

  return (
    <div className={`ck ic-phone${phone ? " ic-bar-pad" : ""}`}>
      {header}
      <p className="ck-muted" role="status">{t.minutes(used)}</p>
      <div className="ck-grid">
        <div className="ck">
          {phone ? <details><summary style={{ minHeight: 44 }}>North: {drafts.length ? t.northLine(drafts.length) : t.northNothing}</summary>{north}</details> : null}
          {e.prompts.map((p, n) => {
            const line = lineOf(p);
            const mine = live.filter((i) => (p.extra ? i.extra : i.kind === p.kind && !i.extra));
            const shut = phone && block !== line;
            return (
              <div key={line} className="ds-card ck-panel ck-block">
                <button type="button" className="ck-head" aria-expanded={!shut} onClick={() => setBlock(line)}>
                  <span>{phone && !p.extra ? t.oneOf(n + 1, p.lead) : p.lead}</span><span className="ck-muted">{mine.length || (e.skipped.includes(line) ? "0" : "")}</span>
                </button>
                {!shut && (
                  <>
                    {mine.length === 0 && <p className="ck-muted">{e.skipped.includes(line) ? t.nothingSaid : p.extra ? t.empty.extra : drafts.some((d) => d.kind === p.kind) ? t.emptyDrafts : t.empty[line]}</p>}
                    {mine.map((i) => (
                      <div key={i.id}>
                        <button type="button" className={`ck-card ck-card--${i.kind}`} onClick={() => setOpen(open === i.id ? null : i.id)} aria-expanded={open === i.id}>
                          <span>{i.text}</span>
                          <span className="ck-row">
                            <span className="ck-tag">{kindName[i.kind]}</span>
                            {i.kind === "broke" && <span className="ck-tag">{i.severity ? severityName[i.severity] : t.howBad}</span>}
                            {i.ref && <span className="ck-tag">{i.ref.label}</span>}
                            <span className={`ck-tag${i.mark === "guessed" ? " ck-tag--guess" : ""}`}>{i.mark === "guessed" ? t.guessed : t.stated}</span>
                            {i.anonymous && <span className="ck-tag">{t.anonymous}</span>}
                            {submitted && i.sent && <span className="ck-tag">Sent</span>}
                          </span>
                        </button>
                        {i.mark === "guessed" && <div style={{ marginTop: 6 }}><Button onClick={() => void put({ op: "confirm", id: i.id })}>{t.yesRight}</Button></div>}
                        {cur?.id === i.id && <Sheet key={i.id + i.text + i.severity} item={i} measures={measures} onSave={(b) => void put({ op: "update", id: i.id, ...b })} onClose={() => setOpen(null)}
                          onRemove={() => { void put({ op: "remove", id: i.id }); setOpen(null); }} />}
                      </div>
                    ))}
                    <div className="ck-row">
                      <input type="text" style={{ flex: "1 1 200px", width: "auto" }} aria-label={p.lead} enterKeyHint="next" placeholder={t.placeholder} maxLength={600} value={draftText[line] ?? ""}
                        onChange={(ev) => setDraftText({ ...draftText, [line]: ev.target.value })}
                        onKeyDown={(ev) => { if (ev.key === "Enter" && (draftText[line] ?? "").trim()) { void put({ op: "add", kind: line, text: draftText[line] }); setDraftText({ ...draftText, [line]: "" }); } }} />
                      <Mic onText={(s) => setDraftText({ ...draftText, [line]: `${draftText[line] ?? ""} ${s}`.trim() })} />
                      <Button disabled={!(draftText[line] ?? "").trim()} onClick={() => { void put({ op: "add", kind: line, text: draftText[line] }); setDraftText({ ...draftText, [line]: "" }); }}>{t.add}</Button>
                    </div>
                    {!p.extra && mine.length === 0 && <div><Button onClick={() => void put({ op: e.skipped.includes(line) ? "unskip" : "skip", kind: line })}>{e.skipped.includes(line) ? t.undo : t.nothing}</Button></div>}
                  </>
                )}
              </div>
            );
          })}
          {ask && (
            <div className="ck-ask" role="alertdialog" aria-label={t.guessedAsk(e.guessed)}>
              <p>{t.guessedAsk(e.guessed)}</p>
              <div className="ck-row"><Button onClick={() => void send()}>{t.keepDrafts}</Button><Button variant="primary" onClick={() => void confirmAll()}>{t.confirmAll}</Button></div>
            </div>
          )}
          {sent && !err && <p role="status" ref={(n) => n?.scrollIntoView?.({ block: "center" })}><strong>{t.sent(dateWords(e.week.answers_close))}</strong></p>}
          {err && <p role="alert" className="ck-err">{t.saveFailed} <Button onClick={() => (last.current ? void put(last.current.op) : load())}>{t.retry}</Button></p>}
          {saved && !err && <p className="ck-muted">{t.saved}</p>}
          {!ready && <p className="ck-muted">{t.needOne}</p>}
          {phone ? <BottomBar label="Send"><Button variant="primary" disabled={!ready} onClick={onSend}>{submitted ? t.update : t.send}</Button></BottomBar>
            : <div><Button variant="primary" disabled={!ready} onClick={onSend}>{submitted ? t.update : t.send}</Button></div>}
        </div>
        <div className="ck">{!phone && north}{rail}</div>
      </div>
    </div>
  );
}
