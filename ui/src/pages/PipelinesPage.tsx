import DialectPanel from "./build/DialectPanel";
import FlowRunNote, { SetAside } from "./build/FlowRunNote";
import type { Quarantined } from "./build/flowCopy";
import HandOverStrip from "./build/HandOverStrip";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { apiGet, apiSend, Refused } from "../api/client";
import {
  Button, Chip, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard, StatCard, StatGrid, Strip, type PillTone,
} from "../design";
import { useSession } from "../useSession";

// Room 2, Build the data: the source cards, today's plan and the run log. Shapes: docs/plan/SHAPES.md sections 3 and 4.
interface Pipeline { source: string; title?: string; lands_at: string; pattern: string; expected: string; sla: string; depends_on: string[]; owner: string; marts: string[] }
interface Run {
  id: string; source: string; started: string; ended?: string; on_time: boolean; rows: number; schema_ok?: boolean;
  rules: { rule: string; passed: boolean; count: number }[]; marts_ready: string | null; sla_met: boolean | null; owner: string; status: "ok" | "late" | "failed";
  quarantined?: Quarantined[];
}
interface Plan { source: string; expected: string; state: string }
interface RunDue { ran: Run[]; skipped: { source: string; reason: string }[] }
type Load = "loading" | "error" | "refused" | "ready";

const NA = "Not available yet";
// Run status and the schedule's states (sh_platform/build/schedule.py state_of): ok, failed, late, due, waiting.
const TONE: Record<string, PillTone> = { ok: "ok", late: "late", failed: "failed", due: "open", waiting: "draft" };
const toBase64 = (f: File) => new Promise<string>((ok, no) => {
  const r = new FileReader();
  r.onload = () => ok(String(r.result).split(",")[1] ?? "");
  r.onerror = () => no(r.error);
  r.readAsDataURL(f);
});
// The route may answer a bare list or a list under a key; accept both.
function list<T>(d: unknown, key: string): T[] {
  return Array.isArray(d) ? (d as T[]) : ((d as Record<string, T[]> | null)?.[key] ?? []);
}
const yn = (v: boolean | null) => (v === null ? NA : v ? "Yes" : "No");
// Plain words for a screen: a source's file-style name, a contract's time, an ISO stamp, a mart's table name.
const name = (p: Pipeline) => p.title || plain(p.source);
const plain = (s: string) => (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ");
const STAMP = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }); // the browser's own time zone
const when = (iso: string | null) => {
  const d = iso ? new Date(iso) : null;
  return d && !Number.isNaN(d.getTime()) ? STAMP.format(d) : NA;
};
const WORD = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
const ORD = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth"];
const expects = (e: string) => { // "D+1 09:00" is 09:00, one day after month end
  const m = /^D\+(\d+)\s+(\d{1,2}:\d{2})$/.exec(e.trim());
  const [, n = "", t = ""] = m ?? [];
  return m ? `${t.padStart(5, "0")}, ${WORD[+n] ?? n} ${n === "1" ? "day" : "days"} after month end` : e;
};
const limit = (sla: string) => { // "WD8" is by the eighth working day
  const m = /^WD(\d+)$/.exec(sla.trim());
  const n = m?.[1] ?? "";
  return m ? `By the ${ORD[+n] ?? `${n}th`} working day` : /^not stated$/i.test(sla) ? "No deadline set" : sla;
};
const MONTH = (k: string) => new Date(`${k}-01T00:00:00Z`).toLocaleString("en-GB", { month: "short", timeZone: "UTC" });
const RANK = { ok: 0, late: 1, failed: 2 } as const;
// The six months a card's strip shows: ending at the latest month in which at least half the sources ran.
function months(runs: Run[], n: number): string[] {
  const by = new Map<string, Set<string>>();
  runs.forEach((r) => by.set(r.started.slice(0, 7), (by.get(r.started.slice(0, 7)) ?? new Set()).add(r.source)));
  const end = [...by.keys()].sort().filter((k) => (by.get(k)?.size ?? 0) * 2 >= n).pop();
  if (!end) return [];
  const [y = 0, m = 1] = end.split("-").map(Number);
  return Array.from({ length: 6 }, (_, i) => { const d = new Date(Date.UTC(y, m - 1 - (5 - i), 1)); return d.toISOString().slice(0, 7); });
}
const mart = (m: string) => plain(m.replace(/^gold\./, ""));
const SHOWN = 12;
const failedRules = (r: Run) => r.rules.filter((x) => !x.passed).length;

function SourceCard({ p, last, mine, span, canRun, onRun, onDrop }: {
  p: Pipeline; last?: Run; mine: Run[]; span: string[]; canRun: boolean; onRun: () => void; onDrop: (f: File | undefined) => void;
}) {
  const file = useRef<HTMLInputElement>(null);
  return (
    <SideCard title={name(p)}>
      <p>
        {last ? <Pill tone={TONE[last.status] ?? "draft"}>{last.status}</Pill> : <Pill tone="draft">No run yet</Pill>}{" "}
        {last ? `Latest run: ${last.rows} rows, ${when(last.started)}${failedRules(last) ? `, ${failedRules(last)} checks failed` : ""}` : NA}
      </p>
      <SetAside held={last?.quarantined} />
      {span.length > 0 && (
        <p aria-label={`Last six months for ${name(p)}`}>
          {span.map((k) => {
            const worst = mine.filter((x) => x.started.startsWith(k)).sort((a, b) => RANK[b.status] - RANK[a.status])[0];
            return <span key={k}><Pill tone={worst ? TONE[worst.status] ?? "draft" : "draft"}>{MONTH(k)}: {worst ? worst.status : "no run"}</Pill>{" "}</span>;
          })}
        </p>
      )}
      <StatGrid cols={3}>
        <StatCard bare text label="File name" value={<span style={{ overflowWrap: "anywhere" }}>{p.pattern}</span>} />
        <StatCard bare text label="Arrives" value={expects(p.expected)} />
        <StatCard bare text label="Deadline" value={limit(p.sla)} />
        <StatCard bare text label="After" value={p.depends_on.map(plain).join(", ") || "Nothing"} />
        <StatCard bare text label="Feeds" value={p.marts.map(mart).join(", ") || "Nothing yet"} />
        <StatCard bare text label="Source owner" value={p.owner} />
      </StatGrid>
      {canRun && (
        <div className="ds-frame__actions">
          <Button variant="primary" onClick={onRun}>Run now</Button>
          <Button onClick={() => file.current?.click()}>Drop a file</Button>
          <input ref={file} hidden type="file" accept=".csv,.xlsx" aria-label={`Drop a file for ${p.source}`}
            onChange={(e) => { onDrop(e.target.files?.[0]); e.target.value = ""; }} />
        </div>
      )}
    </SideCard>
  );
}

export default function PipelinesPage() {
  const { user } = useSession();
  const canRun = !!user?.roles.some((r) => r === "company_admin" || r === "analyst");
  const [pipes, setPipes] = useState<Pipeline[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [plan, setPlan] = useState<Plan[]>([]);
  const [load, setLoad] = useState<Load>("loading");
  const [filter, setFilter] = useState("");
  const [note, setNote] = useState("");
  const [all, setAll] = useState(false);
  const [noteRun, setNoteRun] = useState<string | null>(null); // the run whose Span note is open
  const canNote = canRun || !!user?.roles.includes("owner");

  const read = useCallback(async () => {
    try {
      const [p, r, sc] = await Promise.all([apiGet<unknown>("/api/company/build/pipelines"), apiGet<unknown>("/api/company/build/runs"),
        apiGet<unknown>("/api/company/build/schedule").catch(() => null)]);
      setPipes(list<Pipeline>(p, "pipelines"));
      setRuns(list<Run>(r, "runs"));
      setPlan(list<Plan>(sc, "plan"));
      setLoad("ready");
    } catch (e) {
      setLoad(e instanceof Refused ? "refused" : "error");
    }
  }, []);
  useEffect(() => { void read(); }, [read]);

  async function runNow(source: string) {
    if (!window.confirm(`Run ${nameOf(source)} now?`)) return;
    try {
      await apiSend("POST", `/api/company/build/pipelines/${encodeURIComponent(source)}/run`);
      setNote(`Run for ${nameOf(source)} started.`);
      await read();
    } catch {
      setNote(`Could not run ${nameOf(source)}.`);
    }
  }

  async function drop(source: string, file: File | undefined) {
    if (!file) return;
    try {
      const r = await apiSend<{ file: string; rows: number }>("POST", `/api/company/build/pipelines/${encodeURIComponent(source)}/upload`,
        { filename: file.name, data: await toBase64(file) });
      setNote(`${r.file} landed for ${nameOf(source)}, ${r.rows} rows. Press Run now to load it.`);
      await read();
    } catch (e) {
      setNote(e instanceof Error && e.message ? e.message : `Could not take that file for ${nameOf(source)}.`);
    }
  }

  async function runDue() {
    try {
      const r = await apiSend<RunDue>("POST", "/api/company/build/pipelines/run-due");
      setNote(`Ran ${r.ran.length}: ${r.ran.map((x) => nameOf(x.source)).join(", ") || "nothing"}. Skipped ${r.skipped.length}${r.skipped.map((x) => `. ${nameOf(x.source)}: ${x.reason}`).join("")}`);
      await read();
    } catch (e) {
      setNote(e instanceof Error && e.message ? e.message : "Could not run what is due.");
    }
  }

  const known = new Set(pipes.map((p) => p.source));
  const nameOf = (s: string) => { const p = pipes.find((x) => x.source === s); return p ? name(p) : plain(s); };
  // A run for a source with no pipeline card (for example a sealed payroll file) is not shown here.
  const newest = [...runs].filter((r) => known.has(r.source)).reverse(); // the log is oldest first
  const span = months(newest, pipes.length);
  const matching = filter ? newest.filter((r) => r.source === filter) : newest;
  const shown = all ? matching : matching.slice(0, SHOWN);
  const lastOf = (s: string) => newest.find((r) => r.source === s);
  const latest = pipes.map((p) => lastOf(p.source)).filter((r): r is Run => !!r);
  const count = (n: number) => (latest.length ? String(n) : NA);

  const frame = (body: ReactNode, aside?: ReactNode) => (
    <div className="ds-screen">
      <PageFrame title="Pipelines" crumbs="Build · Room 2: Build the data"
        subline="Each source is loaded from its contract, checked and logged. A source turns green only when its run passes."
        actions={canRun && load === "ready" && pipes.length > 0 ? <Button variant="primary" onClick={() => void runDue()}>Run everything due</Button> : undefined}
        aside={aside}>
        <HandOverStrip />
        {body}
      </PageFrame>
    </div>
  );

  if (load === "loading") return frame(<EmptyState title="Reading the pipelines" lines={["The contracts and the run log are on their way."]} />);
  if (load === "error") return frame(<><EmptyState title="The pipelines could not be read" lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={() => void read()}>Try again</Button></>);
  if (load === "refused") return frame(<EmptyState title="Pipelines are for the data team" lines={["Ask your company admin if you need to run a source."]} />);
  if (pipes.length === 0) return frame(<EmptyState title="No pipelines yet" lines={["A pipeline is drawn for each source once the blueprint is signed."]} links={[{ label: "Open the blueprint", href: "/centre/build/blueprint" }]} />);

  return frame(
    <>
      {note && <p role="status" className="ds-soft">{note}</p>}
      <Strip label="Build board">
        <div className="ds-card ds-side">
          <StatGrid cols={4}>
            <StatCard bare label="Loads on time" value={latest.length ? `${latest.filter((r) => r.on_time).length} of ${pipes.length}` : NA} text={!latest.length} />
            <StatCard bare label="Late" value={count(latest.filter((r) => r.status === "late").length)} valueTone={latest.some((r) => r.status === "late") ? "warn" : undefined} text={!latest.length} />
            <StatCard bare label="Checks failed" value={count(latest.reduce((n, r) => n + failedRules(r), 0))} valueTone={latest.some((r) => failedRules(r) > 0) ? "warn" : undefined} text={!latest.length} />
            <StatCard bare label="Marts ready" value={latest.length ? `${latest.filter((r) => r.marts_ready).length} of ${pipes.length}` : NA} text={!latest.length} />
          </StatGrid>
        </div>
      </Strip>
      <Strip label="Sources">
        {pipes.map((p) => (
          <SourceCard key={p.source} p={p} last={lastOf(p.source)} mine={newest.filter((r) => r.source === p.source)} span={span} canRun={canRun} onRun={() => void runNow(p.source)} onDrop={(f) => void drop(p.source, f)} />
        ))}
      </Strip>
      <Strip label="Run log">
        <div className="ds-frame__actions" role="group" aria-label="Filter by source">
          <Chip tone={filter === "" ? "active" : "default"} onClick={() => { setFilter(""); setAll(false); }}>All sources</Chip>
          {pipes.map((p) => <Chip key={p.source} tone={filter === p.source ? "active" : "default"} onClick={() => { setFilter(p.source); setAll(false); }}>{name(p)}</Chip>)}
        </div>
        {shown.length === 0 ? <EmptyState title="No runs yet" lines={["Each run appears here with its rows, checks and deadline."]} /> : (
          <DataTable
            columns={[{ key: "source", label: "Source" }, { key: "started", label: "Started" }, { key: "status", label: "Status" }, { key: "on_time", label: "On time" },
              { key: "rows", label: "Rows" }, { key: "rules", label: "Checks" }, { key: "marts", label: "Marts ready" }, { key: "sla", label: "Deadline met" }, ...(canNote ? [{ key: "note", label: "Span" }] : [])]}
            rows={shown.map((r) => ({
              source: nameOf(r.source), started: when(r.started), status: <Pill tone={TONE[r.status] ?? "draft"}>{r.status}</Pill>, on_time: yn(r.on_time), rows: r.rows,
              rules: <><span className={failedRules(r) ? "ds-warn" : undefined}>{r.rules.length - failedRules(r)} passed, {failedRules(r)} failed</span><SetAside held={r.quarantined} /></>,
              marts: when(r.marts_ready), sla: yn(r.sla_met),
              note: <Button aria-label={`Flow's note on the ${nameOf(r.source)} run of ${when(r.started)}`} onClick={() => setNoteRun(r.id)}>Note</Button>,
            }))}
          />
        )}
        {noteRun && (() => { const r = runs.find((x) => x.id === noteRun); return r ? <FlowRunNote key={noteRun} runId={noteRun} title={`${nameOf(r.source)}, ${when(r.started)}`} canAsk={canRun} onClose={() => setNoteRun(null)} /> : null; })()}
        {matching.length > SHOWN && <Button onClick={() => setAll(!all)}>{all ? "Show the latest only" : `Show all ${matching.length} runs`}</Button>}
      </Strip>
    </>,
    <>
      <SideCard title="Today's plan">
        {plan.length === 0 ? <p>{NA}</p> : (
          <ul>{plan.map((x) => <li key={x.source}>{nameOf(x.source)}: arrives {expects(x.expected)} <Pill tone={TONE[x.state] ?? "draft"}>{x.state}</Pill></li>)}</ul>
        )}
      </SideCard>
      {canRun && <DialectPanel />}
      <SideCard title="Next" action={{ label: "Prove and release", href: "/centre/build/prove" }}>
        <p>When a source has run, the Prover checks each measure against the reported figure.</p>
      </SideCard>
      <Footnote>Every figure here is read from the run log. Nothing is typed by a person.</Footnote>
    </>,
  );
}
