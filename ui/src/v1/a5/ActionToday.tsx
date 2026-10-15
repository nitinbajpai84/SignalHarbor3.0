import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "../../design";
import { day } from "../../design/dates";
import { useSession } from "../../useSession";
import { act, askTally, getCase, listCases, type CaseRow } from "../e4/api";
import { dueText, kindName, money } from "../e4/CasesPage";
import { getPulse, takeCase, type PulseItem } from "../e5/api";
import { getShared, type Shared } from "../cxui/api";
import { draftFollowup, getInbox, money as amountOf, type Followup, type Inbox } from "../k5/api";
import { finishAssignment, getLanding, type Landing } from "../p2/api";
import { listTickets, STATE_NAMES, type TicketRow } from "../t2/api";
import { Raise } from "../t2/TicketsPage";
import { getReview } from "../k3/api";
import { accept, fileName, getExtraction, getQueue, type Extraction } from "../x5/api";
import { ACTION, hello, KIND, Lead, Mine, plain, things } from "./ActionLanding";
import { CHECKS, listRuns } from "./api";
import PulseFull from "./PulseFull";
import type { Run } from "./ReconPage";

// ACT1: /centre/action is one page, not six tabs. Every group is built from the existing typed clients; every line links to its full page.
const CLOSED = ["resolved", "rejected"];
const FRESH_DAYS = 14;
const ghost = { style: { alignSelf: "center" as const } };

interface ReconLine { id: string; label: string; headline: string; text: string; caseId: string; timing: boolean }
interface ChaseLine { id: string; manager: string; managerId: string; label: string; headline: string; text: string }
interface FigureLine { x: Extraction; headline: string; text: string }

function Line({ label, hot, headline, text, primary, secondary, children }: { label: string; hot?: boolean; headline: string; text: string; primary: ReactNode; secondary?: ReactNode; children?: ReactNode }) {
  return (
    <article className="ds-card" style={{ padding: "16px 18px", display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center" }}>
      <div style={{ flex: "1 1 420px", minWidth: 0 }}>
        <p className="ds-eyebrow" style={hot ? { color: "var(--ds-amber)" } : { color: "var(--ds-muted, inherit)" }}>{label}</p>
        <h3 style={{ margin: "4px 0 2px", fontSize: 16 }}>{headline}</h3>
        <p className="ds-muted" style={{ margin: 0, lineHeight: 1.5 }}>{text}</p>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{primary}{secondary}</div>
      {children ? <div style={{ flexBasis: "100%" }}>{children}</div> : null}
    </article>
  );
}

function Group({ id, title, count, note, children }: { id: string; title: string; count: number; note: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`h-${id}`} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h2 id={`h-${id}`} style={{ margin: 0, fontSize: 19 }}>{title} <span className="ds-muted">· {count}</span></h2>
        <span className="ds-muted" style={{ fontSize: 13 }}>{note}</span>
      </div>
      {count === 0 ? <p className="ds-muted" style={{ margin: 0 }}>Nothing to clear.</p> : children}
    </section>
  );
}

const lnk = (to: string, label: string, primary = false) => <Link className={primary ? "ds-btn ds-btn--primary" : "ds-btn"} to={to}>{label}</Link>;

export default function ActionToday() {
  const { user } = useSession();
  const [landing, setLanding] = useState<Landing | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [lines, setLines] = useState<ReconLine[]>([]);
  const [inbox, setInbox] = useState<(Inbox & { can_draft?: boolean }) | null>(null);
  const [figures, setFigures] = useState<FigureLine[]>([]);
  const [tickets, setTickets] = useState<TicketRow[]>([]);
  const [pulse, setPulse] = useState<PulseItem[]>([]);
  const [shared, setShared] = useState<Shared[]>([]);
  const [mapWaiting, setMapWaiting] = useState(0);   // map items from finished projects that wait for the head of data
  const [error, setError] = useState("");
  const [mine, setMine] = useState<string[]>([]);       // what this person finished on this page, shown under Done today
  const [draft, setDraft] = useState<{ id: string; d: Followup } | null>(null);
  const [raising, setRaising] = useState(false);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState("");

  const roles = user?.roles ?? [];
  const has = (...r: string[]) => r.some((x) => roles.includes(x));
  const canRecon = has("company_admin", "analyst", "sponsor", "approver", "participant"); // ROLE1: what the server lets each role read; the business owner has no checks to clear
  const canFigures = has("company_admin", "analyst", "sponsor");
  const canMapReview = has("company_admin", "analyst");
  const load = useCallback(() => {
    const quiet = () => undefined;  // a source the person may not read leaves its group at "Nothing to clear"
    getLanding().then(setLanding, (e) => setError(plain(e)));
    listCases().then((r) => setCases(r.cases), (e) => setError(plain(e)));
    (canRecon ? listRuns() : Promise.resolve([] as Run[])).then(async (r) => {
      setRuns(r as Run[]);
      const out: ReconLine[] = [];
      for (const c of CHECKS.filter((c) => c.code !== "limits")) {  // a breached limit is a case, so it shows under Cases
        const mineRuns = (r as Run[]).filter((x) => x.recon_code === c.code);  // newest first
        const last = mineRuns[0];
        const shown = last && !last.checked ? mineRuns.find((x) => x.checked) ?? last : last;
        if (!shown?.breaks) continue;
        const breached = (shown.results ?? []).filter((x) => x.breached && x.case_id);
        const rows = breached.length ? breached.map((x) => ({ caseId: x.case_id as string, words: x.words, cause: x.cause ?? "" }))
          : shown.opened.map((id) => ({ caseId: id, words: `${c.title}: a difference to look at`, cause: "" }));
        for (const x of rows) out.push({ id: `${c.code}:${x.caseId}`, label: `${c.title} · difference`, headline: x.words, caseId: x.caseId,
          text: x.cause || "Over the allowance. Open the case to see both sides.", timing: /timing/i.test(`${x.cause} ${x.words}`) });
      }
      // closing a break is the case's own dismiss action, so the button shows only when the server lets this person press it
      const allowed = await Promise.all(out.map((l) => getCase(l.caseId).then((k) => !!k.can.dismiss, () => false)));
      setLines(out.map((l, i) => ({ ...l, timing: l.timing && allowed[i]! })));
    }, quiet);
    (canMapReview ? getReview() : Promise.reject(new Error("not for this role"))).then((r) => setMapWaiting(r.allowed && r.can_review ? r.totals.waiting ?? 0 : 0), quiet);
    getInbox().then(setInbox, quiet);
    (canFigures ? getQueue() : Promise.reject(new Error("not for this role"))).then((qq) => Promise.all(qq.items.map((i) => getExtraction(i.doc_id).catch(() => null))), quiet).then((xs) => setFigures((xs ?? []).filter((x): x is Extraction => !!x).map((x) => ({
      x, headline: `${fileName(x.file)}: ${Object.entries(x.values).slice(0, 2).map(([k, v]) => `${k} ${v.value}`).join(", ")}`,
      text: x.checks.filter((c) => !c.ok).map((c) => c.why).join(" ") || "Read from the page; nothing is used until you confirm." }))), quiet);
    Promise.all([listTickets({ assignee: "me", state: "active" }), listTickets({ raised_by: "me", state: "active" })]).then(([a, b]) =>
      setTickets([...a.tickets, ...b.tickets.filter((t) => !a.tickets.some((u) => u.id === t.id))]), quiet);
    getPulse("").then((d) => setPulse(d.items.filter((i) => !i.needs_me)), quiet);
    getShared().then((r) => setShared(r.dashboards.filter((d) => Date.now() - new Date(d.shared_at).getTime() <= FRESH_DAYS * 864e5)), quiet);
  }, [canRecon, canFigures, canMapReview]);
  useEffect(load, [load]);

  const run = async (fn: () => Promise<unknown>, done?: string) => {
    setError("");
    try { await fn(); if (done) setMine((m) => [done, ...m]); load(); } catch (e) { setError(plain(e)); }
  };

  const reconIds = new Set(lines.map((l) => l.caseId));
  const open_ = cases.filter((c) => !CLOSED.includes(c.state) && !reconIds.has(c.id));
  // closed on the company's day (the server decides, so a case closed here or on its own page counts the same)
  const closedToday = cases.filter((c) => CLOSED.includes(c.state) && c.closed_today);
  const late = (inbox?.managers ?? []).flatMap((m) => m.funds.flatMap((f) => {
    const miss = f.state === "late" ? { period_end: f.period_end, due: f.due ?? "", days_late: f.days_late ?? 0 } : f.earlier_missing?.[0];
    return miss ? [{ m, f, miss }] : [];
  }));
  const chase: ChaseLine[] = late.map(({ m, f, miss }) => ({ id: f.fund_id, manager: m.name, managerId: m.manager_id,
    label: `${m.name} · ${miss.days_late} business day${miss.days_late === 1 ? "" : "s"} late`,
    headline: `${f.fund_name}: statement for ${day(miss.period_end)} still missing`,
    text: `${miss.due ? `Due ${day(miss.due)}. ` : ""}${f.last_value ? `Last value ${amountOf(f.last_value)} on ${day(f.last_value.valuation_date)} may be stale.` : "No value is recorded yet."}` }));
  const managers = inbox?.managers ?? [];
  const onTime = managers.filter((m) => !m.counts.late && !m.counts.missing_earlier).length;
  const waiting = landing?.waiting_approval ?? [];
  const assigned = landing?.assigned_to_me ?? [];
  const total = open_.length + lines.length + chase.length + figures.length + waiting.length + mapWaiting + assigned.length;
  const first = (user?.display_name ?? landing?.viewer ?? "").split(" ")[0];
  const chips: [string, string, number][] = [["cases", "Cases to handle", open_.length], ...(canRecon ? [["recon", "Reconciliations to clear", lines.length] as [string, string, number]] : []), ["chase", "Statements to chase", chase.length],
    ...(canFigures ? [["confirm", "Figures to confirm", figures.length] as [string, string, number]] : []), ["approve", "Waiting for my approval", waiting.length + mapWaiting], ...(assigned.length ? [["assigned", "Assigned to me", assigned.length] as [string, string, number]] : [])];
  const askAbout = lines[0]?.caseId ?? open_[0]?.id;
  const stamp = new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" }).toUpperCase() + " · " + new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  const drafted = (id: string) => draft?.id === id ? (
    draft.d.draft ? (
      <div>
        <label>Draft email (not sent)<textarea className="ds-input" readOnly rows={8} style={{ width: "100%" }} value={draft.d.draft} /></label>
        <Button variant="primary" onClick={() => void navigator.clipboard.writeText(draft.d.draft ?? "").catch(() => setError("Copying did not work here. Select the text and copy it yourself."))}>Copy the draft</Button>
        <p className="ds-muted">{draft.d.note}</p>
      </div>) : <p role="status">{draft.d.message}</p>) : null;

  return (
    <main className="ds-frame" style={{ display: "flex", flexWrap: "wrap", gap: 28, alignItems: "flex-start" }}>
      <section aria-label="Things to do" style={{ flex: "999 1 640px", minWidth: 0, display: "flex", flexDirection: "column", gap: 22 }}>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "flex-end", gap: 16 }}>
          <div>
            <p className="ds-eyebrow">{stamp}</p>
            <h1 className="ds-serif" style={{ margin: "6px 0 0", fontSize: 34 }}>{hello()}{first ? `, ${first}` : ""}. {landing ? things(total) : "Loading today."}</h1>
            <p className="ds-muted" style={{ margin: "6px 0 0" }}>One list. Each line says what happened and the one thing to do. Done items leave the list.</p>
            {assigned.length ? <Lead a={[...assigned].sort((x, y) => y.at.localeCompare(x.at))[0]!} /> : null}
          </div>
          <a className="ds-btn" href="#raise" onClick={() => setRaising(true)}>Raise a ticket</a>
        </div>
        {error ? <p role="alert">{error}</p> : null}

        <nav aria-label="Jump to a group" style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
          {chips.map(([id, name, n]) => <a key={id} href={`#${id}`} className="ds-chip" style={{ borderRadius: 999, padding: "10px 16px", display: "inline-flex", gap: 8 }}>{name} <strong style={{ color: "var(--ds-amber)" }}>{n}</strong></a>)}
        </nav>

        <Group id="cases" title="Cases to handle" count={open_.length} note={<>Breaches and deadlines Tally opened for you. <Link className="ds-link" to="/centre/action/cases">All cases</Link></>}>
          {open_.map((c) => (
            <Line key={c.id} hot={c.materiality === "high"} label={[kindName((c as CaseRow & { exception_type?: string }).exception_type) || "Case", c.materiality, dueText(c.due)].join(" · ")}
              headline={c.title} text={[c.number, money(c.amount, c.currency), c.state === "new" ? "Nobody has taken it yet" : ""].filter(Boolean).join(". ") + "."}
              primary={c.state === "new" ? <Button variant="primary" onClick={() => void run(() => takeCase(c.id))}>Take the case</Button> : lnk(`/centre/action/cases/${encodeURIComponent(c.id)}`, "Open the case", true)}
              secondary={lnk(`/centre/action/cases/${encodeURIComponent(c.id)}`, "Ask Tally")} />))}
        </Group>

        {canRecon ? (
        <Group id="recon" title="Reconciliations to clear" count={lines.length} note={<>Where two sources disagree this morning. <Link className="ds-link" to="/centre/action/reconciliations">All checks</Link></>}>
          {lines.map((l) => {
            const view = lnk("/centre/action/reconciliations", "See both sides");
            return <Line key={l.id} hot label={l.label} headline={l.headline} text={l.text}
              primary={l.timing ? <Button variant="primary" onClick={() => void run(() => act(l.caseId, "dismiss", "A timing difference that clears by itself."))}>Close as timing</Button>
                : lnk(`/centre/action/cases/${encodeURIComponent(l.caseId)}`, "Open the case", true)}
              secondary={l.timing ? view : lnk(`/centre/action/cases/${encodeURIComponent(l.caseId)}`, "See both sides")} />;
          })}
        </Group>
        ) : null}

        <Group id="chase" title="Statements to chase" count={chase.length} note={`Only late ones. ${onTime} of ${managers.length} manager${managers.length === 1 ? " is" : "s are"} on time`}>
          {chase.map((c) => (
            <Line key={c.id} hot label={c.label} headline={c.headline} text={c.text}
              primary={inbox?.can_draft === false ? lnk(`/centre/consume/managers/${c.managerId}`, "Open the manager", true)
                : <Button variant="primary" onClick={() => { setError(""); draftFollowup(c.managerId, c.id).then((d) => setDraft({ id: c.id, d }), (e) => setError(plain(e))); }}>Draft a follow-up</Button>}
              secondary={<Link className="ds-link" to="/centre/action/managers" {...ghost}>All managers</Link>}>{drafted(c.id)}</Line>))}
        </Group>

        {canFigures ? (
        <Group id="confirm" title="Figures to confirm" count={figures.length} note={<>Read from PDFs; nothing is used until you confirm. <Link className="ds-link" to="/centre/extract/review">Review queue</Link></>}>
          {figures.map(({ x, headline, text }) => (
            <Line key={x.doc_id} hot={x.checks.some((c) => !c.ok)} label={`${x.type_name} · needs a look`} headline={headline} text={text}
              primary={<Button variant="primary" onClick={() => void run(() => accept(x.doc_id, {}), `${headline} confirmed, by you`)}>Confirm</Button>}
              secondary={lnk("/centre/extract/review", "Correct it")} />))}
        </Group>
        ) : null}

        <Group id="approve" title="Waiting for my approval" count={waiting.length + mapWaiting} note="Someone else built it; you sign">
          <div className="ds-card" style={{ padding: "6px 18px" }}>
            {mapWaiting ? (
              <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "12px 0", borderBottom: "1px solid var(--ds-line, #ddd)" }}>
                <span>Map review · {mapWaiting} new item{mapWaiting === 1 ? "" : "s"} from finished projects stay off the signed map until you approve them</span>
                <Link className="ds-link" style={{ fontWeight: 600 }} to="/centre/map/review">Review {mapWaiting}</Link>
              </div>) : null}
            {waiting.map((w) => (
              <div key={w.link + w.title} style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 10, padding: "12px 0", borderBottom: "1px solid var(--ds-line, #ddd)" }}>
                <span>{w.title} · {KIND[w.kind]} from {w.from ?? "the project team"} on {w.project}</span>
                <Link className="ds-link" style={{ fontWeight: 600 }} to={w.link}>{ACTION[w.kind] ?? "Review and approve"}</Link>
              </div>))}
          </div>
        </Group>

        {assigned.length ? (
          <section id="assigned" aria-label="Assigned to me" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <h2 style={{ margin: 0, fontSize: 19 }}>Assigned to me <span className="ds-muted">· {assigned.length}</span></h2>
            {assigned.map((a) => <Mine key={a.id} a={a} onDone={(id) => void run(() => finishAssignment(id, "done"))} />)}
          </section>) : null}

        {landing?.assigned_by_me.length ? (
          <details style={{ padding: "14px 18px" }} className="ds-card"><summary>Waiting on others · {landing.assigned_by_me.length}</summary>
            <ul>{landing.assigned_by_me.map((a) => <li key={a.id}>{a.to}: {a.steps.join(", ")} <span className="ds-muted">{a.title ?? "A project"}{a.due ? `, due ${day(a.due, a.due)}` : ""}</span> <Link className="ds-link" to={a.link}>Open project</Link></li>)}</ul>
          </details>) : null}

        <details className="ds-card" style={{ padding: "14px 18px" }}>
          <summary>Done today · {closedToday.length + mine.length}</summary>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            {mine.map((m) => <span key={m}>{m}</span>)}
            {closedToday.map((c) => <span key={c.id}>{c.number}: {c.title} · {c.state === "rejected" ? "dismissed" : "closed"}</span>)}
            {closedToday.length + mine.length === 0 ? <span className="ds-muted">Nothing finished yet today.</span> : null}
          </div>
        </details>

        <details className="ds-card" style={{ padding: "14px 18px" }} onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
          <summary>Everything Tally flagged (the full Pulse)</summary>
          {open ? <PulseFull /> : null}
        </details>
      </section>

      <aside style={{ flex: "1 1 300px", minWidth: 0, display: "flex", flexDirection: "column", gap: 16 }}>
        <section aria-label="Ask Tally" className="ds-card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Ask Tally</h2>
          <form onSubmit={(e) => { e.preventDefault(); if (q.trim() && askAbout) askTally(askAbout, q.trim()).then((r) => { setAnswer(r.answer ?? r.summary); setQ(""); }, (err) => setError(plain(err))); }}>
            <label htmlFor="ask" className="ds-muted" style={{ fontSize: 13 }}>{askAbout ? "About the first case on this page" : "No case to ask about yet"}</label>
            <input id="ask" className="ds-input" style={{ width: "100%" }} disabled={!askAbout} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Is the first break timing?" />
          </form>
          {answer ? <p role="status" style={{ margin: 0 }}>{answer}</p> : null}
        </section>
        <section id="raise" aria-label="My tickets" className="ds-card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 10 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>My tickets</h2>
          <p className="ds-muted" style={{ margin: 0, lineHeight: 1.5 }}>Only what you raised or were given. A ticket is for asking someone else to fix something.</p>
          {tickets.map((t) => (
            <div key={t.id} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "8px 0", borderTop: "1px solid var(--ds-line, #ddd)" }}>
              <Link className="ds-link" to={`/centre/tickets/${t.id}`}>{t.title} · with {t.assigned_name}</Link><span className="ds-muted">{STATE_NAMES[t.state].toLowerCase()}</span>
            </div>))}
          {raising ? <Raise project="" done={() => { setRaising(false); load(); }} /> : null}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <Button onClick={() => setRaising(!raising)}>Raise a ticket</Button><Link className="ds-link" to="/centre/tickets">All tickets</Link>
          </div>
        </section>
        <section aria-label="Since yesterday" className="ds-card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 8 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Since yesterday</h2>
          <div className="ds-muted" style={{ lineHeight: 1.6 }}>
            {pulse.slice(0, 3).map((i) => <div key={i.id}>{i.link ? <Link className="ds-link" to={i.link}>{i.headline}</Link> : i.headline}</div>)}
            {shared.map((d) => <div key={d.id}><Link className="ds-link" to={d.link}>{d.title}</Link> shared by {d.shared_by} on {day(d.shared_at, d.shared_at.slice(0, 10))}</div>)}
            {!pulse.length && !shared.length ? <div>Nothing new since yesterday.</div> : null}
          </div>
          <Link className="ds-link" to="/centre/consume">Read it in Consume</Link>
        </section>
      </aside>
    </main>
  );
}
