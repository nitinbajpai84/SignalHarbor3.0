import { useCallback, useEffect, useState, type ReactNode } from "react";

import { apiGet, apiSend, Refused } from "../../api/client";
import LiveCard from "../p5/LiveCard";
import { Button, DataTable, EmptyState, Footnote, PageFrame, Pill, SideCard, StatCard, StatGrid, Strip } from "../../design";

// B5, the ops manager: per source the last run, rows and on time or late (GET /api/v1/ops), and the Loaded / Not loaded act per period
// (POST /api/v1/ops/loaded). Copied from 2.0 ui/src/pages/OpsPage.tsx, slimmed to 1.0: no opportunities, no Span incident notes.
type State = "on_time" | "late" | "failed" | "missing";
interface Source { source_id: string; owner: string | null; state: State; last_run: string | null; arrived: string | null; rows: number | null }
interface Alert { id: string; source: string; kind: string; owner: string | null; ask: string | null; state: "open" | "acknowledged"; by: string | null; note: string | null }
interface Mark { period: string; source_id: string; state: "loaded" | "not_loaded"; reason: string | null; by: string; at: string }
interface Ops { date: string; period: string; sources: Source[]; alerts: Alert[]; loaded: Mark[] }
type Load = "loading" | "error" | "refused" | "ready";

const STATE: Record<State, string> = { on_time: "On time", late: "Late", failed: "Checks failed", missing: "Not arrived" };
const TONE: Record<State, "ok" | "late" | "failed"> = { on_time: "ok", late: "late", failed: "failed", missing: "late" };
const plain = (s: string) => (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ");
const STAMP = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
const when = (iso: string | null) => { if (!iso) return "Not available yet"; const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso : STAMP.format(d); };

function AlertCard({ a, onDone }: { a: Alert; onDone: () => void }) {
  const [note, setNote] = useState("");
  const [failed, setFailed] = useState(false);
  const act = (what: "ack" | "close") => {
    apiSend("POST", `/api/company/build/alerts/${encodeURIComponent(a.id)}/${what}`, { note }).then(onDone).catch(() => setFailed(true));
  };
  const acked = a.state === "acknowledged";
  return (
    <SideCard title={`${plain(a.source)}: ${a.kind === "missing" ? "not arrived" : a.kind.replace(/_/g, " ")}`}>
      <p>
        <Pill tone={acked ? "signed" : "open"}>{acked ? "Acknowledged" : "Open"}</Pill>{" "}
        Source owner: {a.owner ?? "not named"}{acked ? `. Acknowledged by ${a.by ?? "someone"}${a.note ? `: ${a.note}` : ""}` : ""}
      </p>
      {a.ask && <p className="ds-soft">Drafted ask: {a.ask}</p>}
      <div className="ds-comment__decide">
        <input aria-label={`Note for ${a.source}`} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What you are doing about it" />
        {!acked && <Button variant="primary" onClick={() => act("ack")}>Acknowledge</Button>}
        <Button onClick={() => act("close")}>Close</Button>
      </div>
      {failed && <p role="alert" className="ds-warn">Could not save. Try again.</p>}
    </SideCard>
  );
}

function LoadedAct({ period, source, mark, onDone }: { period: string; source: string; mark?: Mark; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [failed, setFailed] = useState(false);
  const send = (state: Mark["state"]) => {
    setFailed(false);
    apiSend("POST", "/api/v1/ops/loaded", { period, source_id: source, state, reason }).then(onDone).catch(() => setFailed(true));
  };
  return (
    <div className="ds-comment__decide">
      {mark && <Pill tone={mark.state === "loaded" ? "signed" : "late"}>{mark.state === "loaded" ? "Loaded" : `Not loaded: ${mark.reason ?? ""}`}</Pill>}
      <Button variant={mark?.state === "loaded" ? undefined : "primary"} onClick={() => send("loaded")}>Loaded</Button>
      <input aria-label={`Why ${source} is not loaded`} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why not loaded" />
      <Button disabled={!reason.trim()} onClick={() => send("not_loaded")}>Not loaded</Button>
      {failed && <span role="alert" className="ds-warn">Could not save. Try again.</span>}
    </div>
  );
}

export default function OpsPage() {
  const [load, setLoad] = useState<Load>("loading");
  const [data, setData] = useState<Ops | null>(null);
  const [period, setPeriod] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    apiGet<Ops>("/api/v1/ops")
      .then((o) => { if (live) { setData(o); setPeriod((p) => p || o.period); setLoad("ready"); } })
      .catch((e: unknown) => { if (live) setLoad(e instanceof Refused ? "refused" : "error"); });
    return () => { live = false; };
  }, [attempt]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  const frame = (body: ReactNode, aside?: ReactNode) => (
    <div className="ds-screen">
      <PageFrame title="Ops" crumbs="Build · Ops manager" aside={aside}
        subline={data ? `Report for ${when(data.date)} · confirm what is loaded per period` : "Each source's last run, and what is loaded per period."}>
        {body}
      </PageFrame>
    </div>
  );
  if (load === "loading") return frame(<EmptyState title="Reading the ops report" lines={["Runs and alerts are on their way."]} />);
  if (load === "error") return frame(<><EmptyState title="The ops report could not be read" lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={retry}>Try again</Button></>);
  if (load === "refused" || !data) return frame(<EmptyState title="Ops is for the ops manager" lines={["The analyst or the company admin confirms loads."]} />);
  if (!data.sources.length) return frame(<EmptyState title="Nothing has run yet" lines={["When Span loads a source, its runs show here."]} />);

  const late = data.sources.filter((s) => s.state !== "on_time");
  const marks = data.loaded.filter((m) => m.period === period);
  const done = marks.filter((m) => m.state === "loaded").length;
  return frame(
    <>
      <Strip label="Sources" tone={late.length ? "amber" : "teal"}>
        <div className="ds-card ds-side">
          <StatGrid cols={3}>
            <StatCard bare label="On time" value={`${data.sources.length - late.length} of ${data.sources.length}`} />
            <StatCard bare label="Late, failed or not arrived" value={String(late.length)} valueTone={late.length ? "warn" : undefined} />
            <StatCard bare label={`Loaded for ${period}`} value={`${done} of ${data.sources.length}`} />
          </StatGrid>
        </div>
        <p>
          <label>Period <input type="month" aria-label="Period" value={period} onChange={(e) => setPeriod(e.target.value)} /></label>
        </p>
        <DataTable columns={[{ key: "s", label: "Source" }, { key: "o", label: "Owner" }, { key: "a", label: "Last run" }, { key: "r", label: "Rows" }, { key: "t", label: "State" }, { key: "l", label: `Loaded for ${period}` }]}
          rows={data.sources.map((s) => ({
            s: plain(s.source_id), o: s.owner ?? "not named", a: when(s.arrived), r: s.rows === null ? "Not available yet" : String(s.rows),
            t: <Pill tone={TONE[s.state]}>{STATE[s.state]}</Pill>,
            l: !period ? "Pick a period" : s.state !== "on_time" || marks.some((m) => m.source_id === s.source_id && m.state === "not_loaded")
              ? <LoadedAct period={period} source={s.source_id} mark={marks.find((m) => m.source_id === s.source_id)} onDone={retry} />
              : <details><summary>Daily state: on time. Give a word for {period}</summary><LoadedAct period={period} source={s.source_id} mark={marks.find((m) => m.source_id === s.source_id)} onDone={retry} /></details>,
          }))} />
      </Strip>
      <Strip label="Alerts" tone={data.alerts.some((a) => a.state === "open") ? "amber" : "teal"}>
        {data.alerts.length ? data.alerts.map((a) => <AlertCard key={a.id} a={a} onDone={retry} />)
          : <EmptyState title="Nothing needs anyone today" lines={["When a file is late or a check fails, the watcher names the owner here and tells the project."]} />}
      </Strip>
    </>,
    <>
      <LiveCard />
      <SideCard title="What Loaded means">
        <p>Marking a source Loaded for a period opens its figures in the Consume centre. Not loaded keeps them back, with your reason.</p>
      </SideCard>
      <Footnote>Run states come from the run log; no figure here is typed by a person. Late sources are raised by the watcher as comments on the project.</Footnote>
    </>,
  );
}
