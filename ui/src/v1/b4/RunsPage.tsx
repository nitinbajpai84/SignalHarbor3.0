// B4 Span loads: the intent's runs, one per source of the mapping sheet, with rows in and out, failed checks and Span's note per run.
// Slimmed from the 2.0 PipelinesPage (run log table, pills, set-aside line).
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";

import { ApiError, apiGet, apiSend, Refused } from "../../api/client";
import { Button, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard, Strip, type PillTone } from "../../design";
import { SetAside } from "../../pages/build/FlowRunNote";
import type { Quarantined } from "../../pages/build/flowCopy";
import { useSession } from "../../useSession";

interface Rule { rule: string; passed: boolean; count: number }
interface Note { lines: string[]; text: string | null; fallback: boolean; sentence: string | null }
export interface Run {
  id: string; source: string; title: string; started: string; rows: number; schema_ok?: boolean; status: "ok" | "late" | "failed";
  rules: Rule[]; quarantined?: Quarantined[]; marts_ready: string | null; note: Note | null;
}
interface Contract { source: string; title: string; owner: string; schema: { field: string }[]; rules: string[]; marts: string[] }
interface Runs { contracts: Contract[]; runs: Run[] }
interface Loaded { runs: Run[]; missing: { title: string; reason: string }[]; rows_left_out: number }
type Load = "loading" | "error" | "refused" | "absent" | "ready";

const NA = "Not available yet";
const TONE: Record<string, PillTone> = { ok: "ok", late: "late", failed: "failed" };
const STAMP = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
const when = (iso: string | null) => { const d = iso ? new Date(iso) : null; return d && !Number.isNaN(d.getTime()) ? STAMP.format(d) : NA; };
const check = (rule: string) => { const [field = "", ...t] = rule.split(":"); return t.length ? `${t.join(":").trim()} (${field})` : rule; };
const failed = (r: Run) => r.rules.filter((x) => !x.passed);

function FlowNote({ run }: { run: Run }) {
  const n = run.note;
  if (!n) return <p>{NA}</p>;
  return (
    <div aria-label={`Span's note on ${run.title}`}>
      {n.text ? <p>{n.text}</p> : <ul>{n.lines.map((l) => <li key={l}>{l}</li>)}</ul>}
      {n.sentence && <p className="ds-soft">{n.sentence}</p>}
    </div>
  );
}

export default function RunsPage() {
  const { iid = "" } = useParams();
  const { user } = useSession();
  const canRun = !!user?.roles.some((r) => r === "company_admin" || r === "analyst");
  const [data, setData] = useState<Runs>({ contracts: [], runs: [] });
  const [load, setLoad] = useState<Load>("loading");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const base = `/api/v1/build/${encodeURIComponent(iid)}`;

  const read = useCallback(async () => {
    try {
      setData(await apiGet<Runs>(`${base}/runs`));
      setLoad("ready");
    } catch (e) {
      setLoad(e instanceof Refused ? "refused" : e instanceof ApiError && e.status === 404 ? "absent" : "error");
    }
  }, [base]);
  useEffect(() => { void read(); }, [read]);

  async function runAll() {
    setBusy(true);
    try {
      const r = await apiSend<Loaded>("POST", `${base}/load`);
      const bad = r.runs.filter((x) => x.status === "failed").length;
      setMsg([`Ran ${r.runs.length} source${r.runs.length === 1 ? "" : "s"}${bad ? `, ${bad} failed` : ""}.`,
        ...r.missing.map((m) => m.reason), r.rows_left_out ? `${r.rows_left_out} mapping rows are not mapped yet and were left out.` : ""].filter(Boolean).join(" "));
      await read();
    } catch (e) {
      setMsg(e instanceof Error && e.message ? e.message : "The load could not be started.");
    } finally {
      setBusy(false);
    }
  }

  const frame = (body: ReactNode) => (
    <div className="ds-screen">
      <PageFrame title="Loads" crumbs="Build · Span loads"
        subline="Span loads each source from the mapping sheet, checks it and logs the run. Failed checks and missing files go to the project as comments."
        actions={canRun && load === "ready" ? <Button variant="primary" disabled={busy} onClick={() => void runAll()}>{busy ? "Loading…" : "Run the load"}</Button> : undefined}
        aside={<Footnote>Every figure here is read from the run log. Nothing is typed by a person.</Footnote>}>
        {body}
      </PageFrame>
    </div>
  );

  if (load === "loading") return frame(<EmptyState title="Reading the runs" lines={["The mapping sheet and the run log are on their way."]} />);
  if (load === "refused") return frame(<EmptyState title="Loads are for the data team" lines={["Ask your company admin if you need to run a load."]} />);
  if (load === "absent") return frame(<EmptyState title="No mapping sheet yet" lines={["Span writes the mapping sheet once the scope is agreed."]} links={[{ label: "Open the mapping sheet", href: `/centre/build/${iid}/mapping` }]} />);
  if (load === "error") return frame(<><EmptyState title="The runs could not be read" lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={() => void read()}>Try again</Button></>);

  const { contracts, runs } = data;
  const latest = contracts.map((c) => runs.find((r) => r.source === c.source));
  return frame(
    <>
      {msg && <p role="status" className="ds-soft">{msg}</p>}
      <Strip label="Sources">
        {contracts.length === 0 ? <EmptyState title="Nothing mapped yet" lines={["No mapping row is marked mapped."]} /> : contracts.map((c, i) => {
          const last = latest[i];
          return (
            <SideCard key={c.source} title={c.title}>
              <p>
                {last ? <Pill tone={TONE[last.status] ?? "draft"}>{last.status}</Pill> : <Pill tone="draft">No run yet</Pill>}{" "}
                {last ? `${last.rows} rows, ${when(last.started)}` : NA}
              </p>
              <p className="ds-soft">{c.schema.length} fields, {c.rules.length} checks, feeds {c.marts.map((m) => m.replace(/^gold\./, "")).join(", ") || "nothing yet"}. Owner: {c.owner}.</p>
              {last && failed(last).length > 0 && <ul aria-label={`Failed checks for ${c.title}`}>{failed(last).map((x) => <li key={x.rule}>{check(x.rule)}: {x.count} rows</li>)}</ul>}
              <SetAside held={last?.quarantined} />
              {last && <FlowNote run={last} />}
            </SideCard>
          );
        })}
      </Strip>
      <Strip label="Run log">
        {runs.length === 0 ? <EmptyState title="No runs yet" lines={["Each run appears here with its rows, checks and Span's note."]} /> : (
          <>
            <DataTable
              columns={[{ key: "source", label: "Source" }, { key: "started", label: "Started" }, { key: "status", label: "Status" }, { key: "rows", label: "Rows out" },
                { key: "rules", label: "Checks" }, { key: "note", label: "Span" }]}
              rows={runs.map((r) => ({
                source: r.title, started: when(r.started), status: <Pill tone={TONE[r.status] ?? "draft"}>{r.status}</Pill>, rows: r.rows,
                rules: <span className={failed(r).length ? "ds-warn" : undefined}>{r.rules.length - failed(r).length} passed, {failed(r).length} failed</span>,
                note: <Button aria-label={`Span's note on the ${r.title} run of ${when(r.started)}`} onClick={() => setOpen(open === r.id ? null : r.id)}>Note</Button>,
              }))}
            />
            {open && (() => { const r = runs.find((x) => x.id === open); return r ? <SideCard title={`${r.title}, ${when(r.started)}`}><FlowNote run={r} /></SideCard> : null; })()}
          </>
        )}
      </Strip>
    </>,
  );
}
