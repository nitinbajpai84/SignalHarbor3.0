import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { apiGet, apiSend, ApiError } from "../api/client";
import ScreenState from "../components/ScreenState";
import { Button, Chip, EmptyState, PageFrame, Pill } from "../design";
import { OpportunityDrawer, SuggestedCard, type Opportunity } from "./OpportunitiesPanel";
import ParkForm from "./ParkForm";
import { backlogCopy as t, typeName } from "./pastCopy";
import "./past.css";

/** The backlog (/centre/intent/backlog, spec 21 Screens A to F). Lists, counts and who may act come from GET /api/intents/backlog. */

interface Item {
  id: string; title: string; kind: string; area: string | null; raised_at: string; review_date: string; status: string; merged_into: string | null;
  merged_from: string[]; opened_intent: string | null; raised_by: string; why_it_matters: { text: string; edited_by: string | null }; taps: number;
  tapped: boolean; can_tap: boolean; actor: boolean; reason: string | null;
  source: { intent_id: string; title: string; type: string; closed_at: string | null; week_key: string | null; may_open: boolean } | null;
  source_quote?: string | null; tap_names?: string[] | null; history?: { at: string; by: string; action: string; note: string }[];
  related?: { id: string; title: string }[]; similar?: { id: string; title: string } | null; merge_choices?: { id: string; title: string }[];
  suggest_type?: string; default_review?: string;
}
interface Counter { area: string | null; open: number; parked?: number; due?: number; oldest_days?: number | null; median_days?: number | string;
  became_intent?: number; became_share?: string }
interface Doc { items: Item[]; areas: { area: string | null; open: number }[]; kinds: Record<string, number>; due: number; counters: Counter[];
  leadish: boolean; tagged: boolean; any: boolean; lead_note: string; opportunities: boolean }

const today = () => new Date().toISOString().slice(0, 10);
const areaName = (a: string | null) => a ?? t.companyWide;

function FeelButton({ it, onDone }: { it: Item; onDone: () => void }) {
  if (!it.can_tap) return <span className="ds-muted">{t.feel} · {t.feelCount(it.taps)}</span>;
  return (
    <Button aria-pressed={it.tapped} onClick={(e) => { e.stopPropagation(); void apiSend("POST", `/api/intents/backlog/${it.id}/tap`).then(onDone, onDone); }}>
      <span aria-hidden>✋</span> {t.feel} · {t.feelCount(it.taps)}
    </Button>
  );
}

function ItemCard({ it, onOpen, onStart, reload }: { it: Item; onOpen: () => void; onStart: () => void; reload: () => void }) {
  const late = it.review_date && it.review_date < today();
  return (
    <article className="ds-card pi-stack" style={{ padding: 14, cursor: "pointer" }} aria-label={it.title} onClick={onOpen}>
      <div className="pi-row"><strong>{it.title}</strong><Chip>{areaName(it.area)}</Chip><Chip>{t.kinds[it.kind]}</Chip>
        {it.status !== "open" ? <Pill tone="draft">{t.statuses[it.status]}</Pill> : null}</div>
      <span className="ds-muted">{it.source ? t.from(it.source.title, it.source.type) : t.sourceGone} · {t.raised(it.raised_by, it.raised_at)}</span>
      <span>{it.why_it_matters.text || t.noWhy}</span>
      {it.reason ? <span className="ds-muted">{t.reasonLine(it.reason)}</span> : null}
      <div className="pi-row">
        <FeelButton it={it} onDone={reload} />
        {it.status === "open" || it.status === "parked"
          ? <span className={!it.review_date || late ? "pi-warn" : "ds-muted"}>{t.review(it.review_date, today())}</span> : null}
        {it.actor && (it.status === "open" || it.status === "parked")
          ? <Button variant="primary" onClick={(e) => { e.stopPropagation(); onStart(); }}>{t.openIntent}</Button>
          : it.status === "open" ? <span className="ds-muted">{t.ask}</span> : null}
      </div>
    </article>
  );
}

function OpenDialog({ it, done, cancel }: { it: Item; done: (href: string) => void; cancel: () => void }) {
  const [type, setType] = useState(it.suggest_type ?? "initiative");
  const [title, setTitle] = useState(it.title);
  const [areas, setAreas] = useState(it.area ?? "");
  const [error, setError] = useState("");
  const go = async () => {
    try {
      const r = await apiSend<{ href: string }>("POST", `/api/intents/backlog/${it.id}/open`, { type, title, areas: areas ? [areas] : [] });
      done(r.href);
    } catch (e) { setError(e instanceof ApiError && e.message ? e.message : t.saveError); }
  };
  return (
    <div className="pi-dialog" role="presentation">
      <form className="ds-card df-park" role="dialog" aria-label={t.openTitle} onSubmit={(e) => { e.preventDefault(); void go(); }}>
        <strong>{t.openTitle}</strong>
        <div className="pi-chips" role="group" aria-label={t.openTitle}>
          {["initiative", "brainstorm", "problem", "decision"].map((k) => (
            <Chip key={k} tone={type === k ? "active" : "default"} onClick={() => setType(k)}>{typeName[k]}{k === it.suggest_type ? ` · ${t.suggests}` : ""}</Chip>
          ))}
        </div>
        <label>{t.intentTitle} <span className="ds-muted">{t.fromItem}</span><input type="text" value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <label>{t.purpose} <span className="ds-muted">{t.fromItem}</span><input type="text" value={it.why_it_matters.text} readOnly /></label>
        <label>{t.areasLabel} <span className="ds-muted">{t.fromItem}</span><input type="text" value={areas} onChange={(e) => setAreas(e.target.value)} /></label>
        <span className="ds-muted">{t.raisedNotice(it.raised_by)}</span>
        {error ? <p role="alert" className="df-alert">{error}</p> : null}
        <div className="df-row"><Button type="submit" variant="primary" disabled={!title.trim() || !areas.trim()}>{t.openIt}</Button><Button onClick={cancel}>{t.cancel}</Button></div>
      </form>
    </div>
  );
}

function MergeDialog({ it, other, done, cancel }: { it: Item; other: string | null; done: () => void; cancel: () => void }) {
  const [pick, setPick] = useState(other ?? "");
  const [keep, setKeep] = useState<"this" | "other" | "">("");
  const [why, setWhy] = useState(it.why_it_matters.text);
  const [error, setError] = useState("");
  const choices = it.merge_choices ?? [];
  const go = async () => {
    try { await apiSend("POST", `/api/intents/backlog/${it.id}/merge`, { other: pick, keep, why }); done(); } catch (e) { setError(e instanceof ApiError && e.message ? e.message : t.saveError); }
  };
  return (
    <div className="pi-dialog" role="presentation">
      <form className="ds-card df-park" role="dialog" aria-label={t.mergeTitle} onSubmit={(e) => { e.preventDefault(); void go(); }}>
        <strong>{t.mergeTitle}</strong>
        {choices.length === 0 ? <p className="ds-muted">{t.noOther}</p> : (
          <label>{t.pick}<select className="pi-field" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="" />{choices.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label>
        )}
        <div className="pi-two">
          <div className="pi-section"><h3>{it.title}</h3><span>{it.why_it_matters.text}</span><span className="ds-muted">{t.feel} · {it.taps}</span></div>
          <div className="pi-section"><h3>{choices.find((c) => c.id === pick)?.title ?? ""}</h3></div>
        </div>
        <label className="pi-row" style={{ flexDirection: "row" }}><input type="radio" name="keep" checked={keep === "this"} onChange={() => setKeep("this")} /> {t.keepThis}</label>
        <label className="pi-row" style={{ flexDirection: "row" }}><input type="radio" name="keep" checked={keep === "other"} onChange={() => setKeep("other")} /> {t.keepOther}</label>
        <label>{t.combined}<input type="text" value={why} onChange={(e) => setWhy(e.target.value)} /></label>
        {error ? <p role="alert" className="df-alert">{error}</p> : null}
        <div className="df-row"><Button type="submit" variant="primary" disabled={!keep || !pick}>{t.mergeIt}</Button><Button onClick={cancel}>{t.cancel}</Button></div>
      </form>
    </div>
  );
}

function Drawer({ id, start, close, reload }: { id: string; start: boolean; close: () => void; reload: () => void }) {
  const [it, setIt] = useState<Item | null | "failed">(null);
  const [form, setForm] = useState<"park" | "drop" | "open" | "merge" | null>(start ? "open" : null);
  const [mergeWith, setMergeWith] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [why, setWhy] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();
  const load = useCallback(() => { apiGet<Item>(`/api/intents/backlog/${id}`).then(setIt, () => setIt("failed")); }, [id]);
  useEffect(load, [load]);
  const send = async (act: string, body: object = {}) => {
    setError("");
    try { await apiSend("POST", `/api/intents/backlog/${id}/${act}`, body); setForm(null); setEditing(false); load(); reload(); }
    catch (e) { setError(e instanceof ApiError && e.message ? e.message : t.saveError); }
  };
  return (
    <div className="pi-sheet" role="presentation" onClick={close}>
      <aside className="pi-sheet__body" role="dialog" aria-label={typeof it === "object" && it ? it.title : t.title} onClick={(e) => e.stopPropagation()}>
        <div className="pi-row" style={{ justifyContent: "space-between" }}><Button onClick={close}>{t.back}</Button></div>
        {it === null ? <ScreenState state="loading" /> : it === "failed" ? <ScreenState state="error" message={t.loadError} /> : (
          <>
            <div className="pi-row"><strong style={{ fontSize: 18 }}>{it.title}</strong><Chip>{areaName(it.area)}</Chip><Chip>{t.kinds[it.kind]}</Chip>
              <Pill tone="draft">{t.statuses[it.status]}</Pill></div>
            {it.reason ? <span className="ds-muted">{t.reasonLine(it.reason)}</span> : null}
            {it.similar ? (
              <div className="ds-card pi-agent pi-stack"><span>{t.same(it.similar.title)}</span>
                <div className="df-row"><Button onClick={() => { setMergeWith(it.similar!.id); setForm("merge"); }}>{t.mergeWith(it.similar.title)}</Button>
                  <Button onClick={() => void send("not-same", { other: it.similar!.id })}>{t.notSame}</Button></div></div>
            ) : null}
            <section className="pi-section"><h3>{t.why}</h3>
              {editing ? (
                <div className="df-park" style={{ padding: 0 }}><input type="text" value={why} onChange={(e) => setWhy(e.target.value)} aria-label={t.why} />
                  <div className="df-row"><Button variant="primary" onClick={() => void send("edit", { why })}>{t.save}</Button><Button onClick={() => setEditing(false)}>{t.cancel}</Button></div></div>
              ) : <span>{it.why_it_matters.text || t.noWhy}</span>}
              <span className="ds-muted">{t.draftedBy(it.why_it_matters.edited_by)}</span>
              {it.actor && !editing && (it.status === "open" || it.status === "parked") ? <span><Button onClick={() => { setWhy(it.why_it_matters.text); setEditing(true); }}>{t.edit}</Button></span> : null}
            </section>
            <section className="pi-section"><h3>{t.cameFrom}</h3>
              {it.source ? (
                <span>{it.source.may_open ? <Link className="ds-link" to={`/centre/intent/${it.source.intent_id}`}>{it.source.title}</Link> : it.source.title}
                  {" · "}{typeName[it.source.type]}{it.source.week_key ? ` · ${t.week(it.source.week_key)}` : ""}</span>
              ) : <span className="ds-muted">{t.sourceGone}</span>}
              <span className="ds-muted">{it.source_quote ? `"${it.source_quote}"` : t.quoteHidden}</span>
              <span className="ds-muted">{t.raised(it.raised_by, it.raised_at)}</span>
            </section>
            <section className="pi-section"><h3>{t.feelList}</h3>
              <span>{it.taps ? `${it.taps}${it.tap_names ? ` · ${it.tap_names.join(", ")}` : ""}` : t.noTaps}</span>
              <FeelButton it={it} onDone={() => { load(); reload(); }} />
            </section>
            {it.status === "open" || it.status === "parked" ? (
              <section className="pi-section"><h3>{t.reviewDate}</h3>
                {it.actor ? <input className="pi-field" type="date" value={it.review_date} aria-label={t.reviewDate}
                  onChange={(e) => e.target.value && void send("edit", { review_date: e.target.value })} /> : <span>{t.review(it.review_date, today())}</span>}
                {!it.review_date ? <span className="pi-warn">{t.setReview}</span> : null}
              </section>
            ) : null}
            <section className="pi-section"><h3>{t.related}</h3>
              {it.related && it.related.length ? it.related.map((r) => <Link key={r.id} className="ds-link" to={`/centre/intent/backlog?item=${r.id}`}>{r.title}</Link>) : <span className="ds-muted">{t.nothingMerged}</span>}
              {it.merged_into ? <Link className="ds-link" to={`/centre/intent/backlog?item=${it.merged_into}`}>{t.actions.merged}</Link> : null}
              {it.opened_intent ? <Link className="ds-link" to={`/centre/intent/${it.opened_intent}`}>{t.became_link}</Link> : null}
            </section>
            <section className="pi-section"><h3>{t.history}</h3>
              {it.history && it.history.length ? it.history.map((h, i) => <span key={i}>{t.actions[h.action] ?? h.action} · {h.by} · {new Date(h.at).toLocaleDateString("en-GB")}{h.note && h.action !== "not_same" ? ` · ${h.note}` : ""}</span>) : <span className="ds-muted">{t.noHistory}</span>}
            </section>
            {error ? <p role="alert" className="df-alert">{error}</p> : null}
            {it.actor ? (
              <div className="df-row" style={{ position: "sticky", bottom: 0, background: "var(--ds-ground)", paddingTop: 8 }}>
                {it.status === "open" || it.status === "parked" ? <Button variant="primary" onClick={() => setForm("open")}>{t.openIntent}</Button> : null}
                {it.status === "open" ? <Button disabled={!(it.merge_choices ?? []).length} onClick={() => { setMergeWith(null); setForm("merge"); }}>{t.merge}</Button> : null}
                {it.status === "open" ? <Button onClick={() => setForm("park")}>{t.park}</Button> : null}
                {it.status === "open" || it.status === "parked" ? <Button onClick={() => setForm("drop")}><span className="pi-warn">{t.drop}</span></Button> : null}
                {it.status === "parked" || it.status === "dropped" ? <Button onClick={() => void send("bring-back")}>{t.bringBack}</Button> : null}
              </div>
            ) : null}
            {it.actor && it.status === "open" && !(it.merge_choices ?? []).length ? <span className="ds-muted">{t.noOther}</span> : null}
            {form === "park" || form === "drop" ? (
              <div className="pi-dialog" role="presentation">
                <ParkForm title={form === "park" ? t.parkTitle(it.title) : t.dropTitle(it.title)} reasonLabel={form === "park" ? t.parkReason : t.dropReason}
                  needMessage={form === "park" ? t.parkNeed : t.dropNeed} saveLabel={form === "park" ? t.parkIt : t.dropIt} cancelLabel={t.cancel}
                  review={form === "park" ? { value: it.default_review ?? "", line: t.remindOn } : undefined} footer={t.footer}
                  onSave={(reason, review_date) => send(form, { reason, review_date })} onCancel={() => setForm(null)} />
              </div>
            ) : null}
            {form === "open" ? <OpenDialog it={it} cancel={() => setForm(null)} done={(href) => nav(href)} /> : null}
            {form === "merge" ? <MergeDialog it={it} other={mergeWith} cancel={() => setForm(null)} done={() => { setForm(null); load(); reload(); }} /> : null}
          </>
        )}
      </aside>
    </div>
  );
}

function Numbers({ counters, note }: { counters: Counter[]; note: string }) {
  if (!counters.length) return <p className="ds-muted">{t.numbersNotYet}</p>;
  return (
    <section id="numbers" className="pi-counters" aria-label={t.counters} style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
      <div className="ds-card pi-counter"><span>{t.perArea}</span>{counters.map((c) => <span key={c.area ?? ""}>{areaName(c.area)}: {t.open(c.open)}
        {c.parked !== undefined ? `, ${t.parked(c.parked)}, ${t.dueN(c.due ?? 0)}` : ""}</span>)}<span className="ds-muted">{note}</span></div>
      {counters[0]?.oldest_days !== undefined ? (
        <>
          <div className="ds-card pi-counter"><span>{t.age}</span>{counters.map((c) => <span key={c.area ?? ""}>{areaName(c.area)}: {t.oldest(c.oldest_days ?? null)}, {t.median(c.median_days ?? "")}</span>)}</div>
          <div className="ds-card pi-counter"><span>{t.became}</span>{counters.map((c) => <span key={c.area ?? ""}>{areaName(c.area)}: {t.becameN(c.became_intent ?? 0, c.became_share ?? "")}</span>)}</div>
        </>
      ) : null}
    </section>
  );
}

export default function IntentBacklog() {
  const [params, setParams] = useSearchParams();
  const [doc, setDoc] = useState<Doc | null | "failed">(null);
  const [more, setMore] = useState(false);
  const qs = ["area", "kind", "status", "due"].map((k) => (params.get(k) ? `${k}=${encodeURIComponent(params.get(k)!)}` : "")).filter(Boolean).join("&");
  const load = useCallback(() => { apiGet<Doc>(`/api/intents/backlog${qs ? `?${qs}` : ""}`).then(setDoc, () => setDoc("failed")); }, [qs]);
  useEffect(load, [load]);
  // Spec 56: proposed opportunities sit as dashed cards at the top of the list; the server only returns what the viewer may see.
  const [sugg, setSugg] = useState<Opportunity[]>([]);
  const [suggAgain, setSuggAgain] = useState(0);
  const oppsAllowed = doc !== null && doc !== "failed" && doc.opportunities;
  useEffect(() => {
    if (!oppsAllowed) return;
    let live = true;
    apiGet<{ opportunities: Opportunity[] }>("/api/intents/opportunities")
      .then((r) => { if (live) setSugg(r.opportunities.filter((o) => o.state === "proposed")); }, () => { if (live) setSugg([]); });
    return () => { live = false; };
  }, [suggAgain, oppsAllowed]);
  const set = (k: string, v: string | null) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); setParams(p, { replace: true }); };
  const item = params.get("item");
  const opportunity = params.get("opportunity");

  if (doc === null) return <PageFrame title={t.title} subline={t.subline}><ScreenState state="loading" /></PageFrame>;
  if (doc === "failed") return <PageFrame title={t.title} subline={t.subline}><ScreenState state="error" message={t.loadError} /></PageFrame>;
  const area = params.get("area");
  const status = params.get("status") ?? "open";
  const kinds = (params.get("kind") ?? "").split(",").filter(Boolean);
  const areaKey = (a: string | null) => a ?? "company";
  const cards = status === "open" || status === "suggested"
    ? sugg.filter((o) => !area || (area === "company" ? !o.areas.length : o.areas.includes(area))) : [];
  const rail = (
    <div className="pi-rail">
      <span className="ds-rail__group">{t.areaSwitch}</span>
      {!doc.tagged ? <p className="ds-muted">{t.noArea}</p> : null}
      {doc.areas.map((a) => (
        <button key={areaKey(a.area)} type="button" className="ds-rail__item" aria-current={area === areaKey(a.area)}
          onClick={() => set("area", area === areaKey(a.area) ? null : areaKey(a.area))}>{areaName(a.area)} ({a.open})</button>
      ))}
    </div>
  );
  return (
    <PageFrame title={t.title} subline={t.subline} rail={rail}>
      <div className="pi-stack">
        <div className="pi-chips" role="group" aria-label={t.areaSwitch}>
          {Object.entries(doc.kinds).map(([k, n]) => (
            <span key={k} className={n ? "" : "pi-dim"}><Chip tone={kinds.includes(k) ? "active" : "default"}
              onClick={() => set("kind", (kinds.includes(k) ? kinds.filter((x) => x !== k) : [...kinds, k]).join(",") || null)}>{t.kinds[k]} {n}</Chip></span>
          ))}
        </div>
        <div className="pi-chips" role="group" aria-label={t.statuses.open}>
          {Object.entries(t.statuses).map(([k, w]) => <Chip key={k} tone={status === k ? "active" : "default"} onClick={() => set("status", k === "open" ? null : k)}>{w}</Chip>)}
          {doc.leadish ? (doc.due ? <Chip tone={params.get("due") ? "active" : "default"} onClick={() => set("due", params.get("due") ? null : "1")}>{t.due} {doc.due}</Chip>
            : <span className="ds-chip pi-dim">{t.noneDue}</span>) : null}
        </div>
        {doc.any ? (
          <div className="pi-stack">
            <Button onClick={() => setMore(!more)}>{more ? t.backToList : t.openNumbers}</Button>
            {more ? <Numbers counters={doc.counters} note={doc.lead_note} /> : (
              <span className="ds-muted">{doc.counters.map((c) => `${areaName(c.area)}: ${t.open(c.open)}`).join(" · ")}</span>
            )}
          </div>
        ) : <span className="ds-muted">{t.numbersNotYet}</span>}
        {cards.length ? (
          <div className="pi-row" style={{ flexWrap: "wrap", alignItems: "stretch" }} aria-label={t.statuses.suggested}>
            {cards.map((o) => <SuggestedCard key={o.id} o={o} onOpen={(id) => set("opportunity", id)} />)}
          </div>
        ) : null}
        {doc.items.length === 0
          ? (cards.length ? null : status === "open" && !params.get("due") && !kinds.length
            ? <EmptyState title={t.title} lines={[t.empty(area ? areaName(area === "company" ? null : area) : t.yourAreas)]}
                links={[{ label: t.startBrainstorm, href: "/centre/intent/new?type=brainstorm" }]} />
            : <p className="ds-muted">{t.nothingHere}</p>)
          : doc.items.map((it) => <ItemCard key={it.id} it={it} reload={load} onOpen={() => set("item", it.id)}
              onStart={() => { const p = new URLSearchParams(params); p.set("item", it.id); p.set("open", "1"); setParams(p, { replace: true }); }} />)}
      </div>
      {item ? <Drawer key={item} id={item} start={params.get("open") === "1"} reload={load}
        close={() => { const p = new URLSearchParams(params); p.delete("item"); p.delete("open"); setParams(p, { replace: true }); }} /> : null}
      {opportunity ? <OpportunityDrawer key={opportunity} id={opportunity} onChanged={() => setSuggAgain((n) => n + 1)} onClose={() => set("opportunity", null)} /> : null}
    </PageFrame>
  );
}
