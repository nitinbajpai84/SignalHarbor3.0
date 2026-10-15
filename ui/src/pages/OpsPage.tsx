import FlowIncidentNotes from "./build/FlowIncidentNote";
import HandOverStrip from "./build/HandOverStrip";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { Link, useSearchParams } from "react-router-dom";

import { apiGet, apiSend, Refused } from "../api/client";
import {
  ActionCard, Button, ClockIcon, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard, StatCard, StatGrid, Strip, WarningIcon,
} from "../design";
import { OpportunitiesPanel, OpportunityDrawer } from "../intents/OpportunitiesPanel";

// Room 3, the Ops manager: today's arrivals, failed checks, alerts, range breaks, the run book and seven days. All from GET /api/company/build/ops.
interface Alert { id: string; source: string; kind: string; owner: string | null; ask: string; state: "open" | "acknowledged"; by: string | null; note: string | null }
interface Ops {
  date: string;
  arrivals: { source: string; state: "on_time" | "late" | "missing"; owner: string | null; arrived: string | null; rows: number | null }[];
  failed_checks: { source: string; rule: string; count: number }[];
  range_breaks: { mart: string; owner: string | null; latest: number | null; mean: number | null; margin: number }[];
  alerts: Alert[];
  run_book: { source: string; expected: string; sla: string; depends_on: string[]; marts: string[]; owner: string | null }[];
  history: { date: string; ok: number; late: number; failed: number }[];
}
interface Pipe { source: string; title?: string; owner?: string }
interface RunDay { source: string; started: string; status: "ok" | "late" | "failed" }
type Load = "loading" | "error" | "refused" | "ready";

const NA = "Not available yet";
const STATE = { on_time: "On time", late: "Late", missing: "Not arrived" } as const;
// Alert kinds written by sh_platform/build/ops.py build().
const KIND: Record<string, string> = { late: "late", missing: "not arrived", failed: "checks failed", outside_range: "outside its usual range" };
const plain = (s: string) => (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ");
const label = (mart: string): string => plain(mart.replace(/^gold\./, ""));
const WORD = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const ORD = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"];
const expects = (e: string) => {
  const m = /^D\+(\d+)\s+(\d{1,2}:\d{2})$/.exec(e.trim());
  const [, n = "", t = ""] = m ?? [];
  return m ? `${t.padStart(5, "0")}, ${WORD[+n] ?? n} ${n === "1" ? "day" : "days"} after month end` : e;
};
const limit = (sla: string) => {
  const m = /^WD(\d+)$/.exec(sla.trim());
  const n = m?.[1] ?? "";
  return m ? `By the ${ORD[+n] ?? `${n}th`} working day` : /^not stated$/i.test(sla) ? "No deadline set" : sla;
};
const STAMP = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }); // the browser's own time zone
const DAY = new Intl.DateTimeFormat("en-CA"); // 2026-10-07, in the browser's own time zone
const words = (iso: string) => { // "2026-09-01" or a full stamp, as "1 September 2026"
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (iso.length !== 10 && !Number.isNaN(d.getTime())) return STAMP.format(d);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
};
const num = (v: number | null) => (v === null ? NA : String(v));

function AlertCard({ a, onDone, nameOf }: { a: Alert; onDone: () => void; nameOf: (s: string) => string }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [note, setNote] = useState("");
  const [failed, setFailed] = useState(false);
  const act = (what: "ack" | "close") => {
    apiSend("POST", `/api/company/build/alerts/${encodeURIComponent(a.id)}/${what}`, { note }).then(onDone).catch(() => setFailed(true));
  };
  const copy = () => { void navigator.clipboard?.writeText(a.ask).then(() => setCopied(true)); };
  const acked = a.state === "acknowledged";
  return (
    <SideCard title={`${nameOf(a.source)}: ${KIND[a.kind] ?? a.kind.replace(/_/g, " ")}`}>
      <p>
        <Pill tone={acked ? "signed" : "open"}>{acked ? "Acknowledged" : "Open"}</Pill>{" "}
        Source owner: {a.owner ?? "not named"}{acked ? `. Acknowledged by ${a.by ?? "someone"}${a.note ? `: ${a.note}` : ""}` : ""}
      </p>
      <div className="ds-frame__actions">
        <Button aria-expanded={open} onClick={() => setOpen(!open)}>Ask the owner</Button>
      </div>
      {open && <p>{a.ask} <Button onClick={copy}>{copied ? "Copied" : "Copy"}</Button></p>}
      <div className="ds-comment__decide">
        <input aria-label={`Note for ${a.source}`} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What you are doing about it" />
        {!acked && <Button variant="primary" onClick={() => act("ack")}>Acknowledge</Button>}
        <Button onClick={() => act("close")}>Close</Button>
        <Link className="ds-btn" to={`/centre/intent/new?type=problem&alert=${encodeURIComponent(a.id)}`}>Start a problem</Link>
      </div>
      {failed && <p role="alert" className="ds-warn">Could not save. Try again.</p>}
    </SideCard>
  );
}

export default function OpsPage() {
  const [load, setLoad] = useState<Load>("loading");
  const [data, setData] = useState<Ops | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [pipes, setPipes] = useState<Pipe[]>([]);
  const [runs, setRuns] = useState<RunDay[]>([]);
  const [params, setParams] = useSearchParams();
  const [opened, setOpened] = useState<string | null>(params.get("opportunity")); // the opportunity panel (spec 56); the backlog shows it at ?opportunity= too
  const [again, setAgain] = useState(0);
  const [owners, setOwners] = useState<Record<string, string>>({}); // measure code (lowercase) -> its business owner, the same as Feeds shows

  useEffect(() => {
    let live = true;
    apiGet<Ops>("/api/company/build/ops")
      .then((o) => { if (live) { setData(o); setLoad("ready"); } })
      .catch((e: unknown) => { if (live) setLoad(e instanceof Refused ? "refused" : "error"); });
    // Source names, owners and the run log come from the pipelines; if they cannot be read the report still shows.
    Promise.all([apiGet<{ pipelines: Pipe[] }>("/api/company/build/pipelines"), apiGet<{ runs: RunDay[] }>("/api/company/build/runs")])
      .then(([p, r]) => { if (live) { setPipes(p.pipelines ?? []); setRuns(r.runs ?? []); } }).catch(() => undefined);
    apiGet<{ measures: { code: string; owner: string | null }[] }>("/api/company/feeds")
      .then((f) => { if (live) setOwners(Object.fromEntries((f.measures ?? []).filter((m) => m.owner).map((m) => [m.code.toLowerCase(), m.owner as string]))); }).catch(() => undefined);
    return () => { live = false; };
  }, [attempt]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const known = new Set(pipes.map((p) => p.source));
  const keep = <T extends { source: string }>(xs: T[]) => (known.size ? xs.filter((x) => known.has(x.source)) : xs); // a source with no pipeline (a sealed payroll file) is not listed
  const nameOf = (s: string) => { const p = pipes.find((x) => x.source === s); return p?.title || plain(s); };
  const ownerOf = (s: string, o: string | null) => { const v = pipes.find((x) => x.source === s)?.owner; return v && v !== NA ? v : o && o !== NA ? o : null; };
  const open = data?.alerts.filter((a) => a.state === "open").length ?? 0;
  const frame = (body: ReactNode, aside?: ReactNode) => (
    <div className="ds-screen">
      <PageFrame title="Ops" crumbs="Build · Room 3: Ops manager"
        subline={data ? `Report for ${words(data.date)} · ${open} open ${open === 1 ? "alert" : "alerts"}` : "The operations monitor checks every run and names who must act."}
        aside={aside}>
        <HandOverStrip />
        {body}
      </PageFrame>
    </div>
  );

  if (load === "loading") return frame(<EmptyState title="Reading today's ops report" lines={["Arrivals, checks and alerts are on their way."]} />);
  if (load === "error") return frame(<><EmptyState title="The ops report could not be read" lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={retry}>Try again</Button></>);
  if (load === "refused" || !data) return frame(<EmptyState title="Ops is for the data team" lines={["Alerts for you appear in Action."]} links={[{ label: "Open Action", href: "/centre/action" }]} />);
  if (data.arrivals.length === 0 && data.run_book.length === 0) {
    return frame(<EmptyState title="Nothing is scheduled yet" lines={["When pipelines are built, today's arrivals show here."]} links={[{ label: "Open the pipelines", href: "/centre/build/pipelines" }]} />);
  }

  const arrivals = keep(data.arrivals);
  const alerts = keep(data.alerts);
  const failedChecks = keep(data.failed_checks);
  const due = arrivals.filter((a) => a.state !== "on_time");
  // The last seven days on which the log has runs, up to the report date; days with no runs are left out.
  const day = (iso: string) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso.slice(0, 10) : DAY.format(d); };
  const last = [data.date, DAY.format(new Date())].sort().pop() ?? data.date;
  const days = [...new Set(keep(runs).map((r) => day(r.started)).filter((d) => d <= last))].sort().slice(-7).reverse();
  const history = days.map((d) => { const st = keep(runs).filter((r) => day(r.started) === d).map((r) => r.status); return { date: d, ok: st.filter((x) => x === "ok").length, late: st.filter((x) => x === "late").length, failed: st.filter((x) => x === "failed").length }; });
  return frame(
    <>
      <Strip label="Ops report" tone="amber">
        <div className="ds-card ds-side">
          <StatGrid cols={4}>
            <StatCard bare label="Loads on time" value={`${arrivals.length - due.length} of ${arrivals.length}`} />
            <StatCard bare label="Late or not arrived" value={String(due.length)} valueTone={due.length ? "warn" : undefined} />
            <StatCard bare label="Checks failed" value={String(failedChecks.length)} valueTone={failedChecks.length ? "warn" : undefined} />
            <StatCard bare label="Outside usual range" value={String(data.range_breaks.length)} valueTone={data.range_breaks.length ? "warn" : undefined} />
          </StatGrid>
          {due.map((a) => (
            <ActionCard key={a.source} inset tone="amber" icon={<ClockIcon />} title={`${nameOf(a.source)}: ${STATE[a.state]}`}
              detail={`Source owner: ${ownerOf(a.source, a.owner) ?? "not named"}. ${a.arrived ? `Arrived ${words(a.arrived)}${a.rows !== null ? `, ${a.rows} rows` : ""}.` : "The file is not in yet."}`}
              action="Drop the file" href="/centre/build/pipelines" />
          ))}
          {failedChecks.map((f) => (
            <ActionCard key={f.source + f.rule} inset tone="amber" icon={<WarningIcon />} title={`${nameOf(f.source)}: check ${f.rule} failed`}
              detail={`${f.count} rows failed the check in that day's run.`} action="Open the run log" href="/centre/build/pipelines" />
          ))}
          {!due.length && !failedChecks.length && <p>Every file arrived on time and no check failed today.</p>}
        </div>
      </Strip>
      <Strip label="Alerts" tone={open ? "amber" : "teal"}>
        {alerts.length ? alerts.map((a) => <AlertCard key={a.id} a={a} onDone={retry} nameOf={nameOf} />)
          : <EmptyState title="Nothing needs anyone today" lines={["When a file is late or a check fails, the operations monitor names the owner here."]} />}
      </Strip>
      <Strip label="Flow's notes on the alerts"><FlowIncidentNotes onDone={retry} /></Strip>
      <OpportunitiesPanel variant="ops" reload={again} onOpen={(id) => { setOpened(id); setParams({ opportunity: id }); }} />
      {opened && <OpportunityDrawer id={opened} onChanged={() => setAgain((n) => n + 1)} onClose={() => { setOpened(null); setParams({}); }} />}
      <Strip label="Measures outside their usual range">
        {data.range_breaks.length ? (
          <DataTable columns={[{ key: "m", label: "Measure" }, { key: "o", label: "Owner" }, { key: "l", label: "Latest" }, { key: "u", label: "Usual" }]}
            rows={data.range_breaks.map((b) => ({ m: label(b.mart), o: owners[b.mart.replace(/^gold\./, "").split(".")[0] ?? ""] ?? "not named", l: <span className="ds-warn">{num(b.latest)}</span>, u: num(b.mean) }))} />
        ) : <p className="ds-soft">No measure is outside its usual range.</p>}
      </Strip>
      <Strip label="Run book">
        <DataTable columns={[{ key: "s", label: "Source" }, { key: "e", label: "Arrives" }, { key: "l", label: "Deadline" }, { key: "a", label: "After" }, { key: "f", label: "Feeds" }, { key: "o", label: "Source owner" }]}
          rows={keep(data.run_book).map((r) => ({ s: nameOf(r.source), e: expects(r.expected), l: limit(r.sla), a: r.depends_on.map(nameOf).join(", ") || "Nothing", f: r.marts.map(label).join(", ") || "Nothing yet", o: ownerOf(r.source, r.owner) ?? "not named" }))} />
      </Strip>
    </>,
    <>
      <SideCard title={`Arrivals, ${words(data.date)}`}>
        <ul>{arrivals.map((a) => (
          <li key={a.source}>{nameOf(a.source)} <Pill tone={a.state === "on_time" ? "ok" : "late"}>{STATE[a.state]}</Pill>{a.rows !== null ? ` ${a.rows} rows` : ""}</li>
        ))}</ul>
      </SideCard>
      <SideCard title="Last seven run days">
        {history.length ? (<>
          <p className="ds-soft">Days with no runs are left out.</p>
          <ul aria-label="Seven-day history">{history.map((h) => (
            <li key={h.date}>{words(h.date)}: {h.ok} ok{h.late ? <span className="ds-warn">, {h.late} late</span> : ", 0 late"}{h.failed ? <span className="ds-warn">, {h.failed} failed</span> : ", 0 failed"}</li>
          ))}</ul></>
        ) : <p>{NA}</p>}
      </SideCard>
      <SideCard title="Who gets told">
        <p>Each alert goes to the source owner named on the source's contract, never to a list. The operations monitor drafts the ask; you send it.</p>
      </SideCard>
      <Footnote>The ops report is written by the operations monitor from the run log. No figure here is typed by a person.</Footnote>
    </>,
  );
}
