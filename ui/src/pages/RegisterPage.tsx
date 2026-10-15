import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { apiGet, Refused } from "../api/client";
import { Button, Chip, DataTable, day, EmptyState, Footnote, PageFrame, Pill, SideCard } from "../design";
import { useSession } from "../useSession";

// The signed register (SHAPES 11): every measure and definition in a signed record, with who signed each stage. Names and links only.

const STAGES = ["charter", "baseline", "blueprint", "uat", "release"] as const;
const LABEL: Record<(typeof STAGES)[number], string> = { charter: "Charter", baseline: "Baseline", blueprint: "Blueprint", uat: "UAT", release: "Release" };
type Sign = { by: string | null; at: string | null } | null;
interface Row { code: string; name: string; kind: "measure" | "definition"; owner: string | null; pipeline: string | null; source: { name: string; kind: string; href: string } | null; signed: Record<string, Sign>; version: number; href: string }
// PF2: the signed records of Intent, rules and Build: each signed intent of work and its measures, approved rules and approved plans.
interface Rec { kind: "intent" | "measure" | "rule" | "plan" | "run" | "knowledge"; name: string; by: string | null; at: string | null; of: string | null; href: string }
const KIND: Record<Rec["kind"], string> = { intent: "Intent of work", measure: "Measure", rule: "Rule", plan: "Build plan", run: "Run", knowledge: "Teaching" };
const REC_COLUMNS = [{ key: "name", label: "Record" }, { key: "kind", label: "Kind" }, { key: "by", label: "By" }, { key: "at", label: "Date" }, { key: "open", label: "" }];
type Filter = "all" | "full" | "missing" | "mine";
type State = "loading" | "error" | "refused" | "ready";

const FILTERS: [Filter, string][] = [["all", "All"], ["full", "Signed at every stage"], ["missing", "Missing a stage"], ["mine", "Mine"]];
const COLUMNS = [
  { key: "name", label: "Name" }, { key: "owner", label: "Owner" }, { key: "source", label: "Came from" }, { key: "pipeline", label: "Pipeline" },
  { key: "signed", label: "Signed" }, { key: "version", label: "Version" }, { key: "open", label: "" },
];

const count = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
const full = (r: Row) => STAGES.every((s) => r.signed[s]);

function Signatures({ signed }: { signed: Record<string, Sign> }) {
  return (
    <span className="ds-frame__actions">
      {STAGES.map((s) => {
        const g = signed[s];
        const hover = g ? `${LABEL[s]}: ${g.by ?? "signed"}${g.at ? `, ${day(g.at)}` : ""}` : `${LABEL[s]}: not signed yet`;
        return <span key={s} title={hover} aria-label={hover} data-signed={g ? "yes" : "no"}><Pill tone={g ? "signed" : "draft"}>{LABEL[s]}</Pill></span>;
      })}
    </span>
  );
}

export default function RegisterPage() {
  const { user } = useSession();
  const [rows, setRows] = useState<Row[]>([]);
  const [records, setRecords] = useState<Rec[]>([]);
  const [state, setState] = useState<State>("loading");
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");

  const load = () => {
    setState("loading");
    apiGet<{ rows: Row[]; records?: Rec[] }>("/api/company/register")
      .then((d) => { setRows(d.rows); setRecords(d.records ?? []); setState("ready"); })
      .catch((e) => setState(e instanceof Refused ? "refused" : "error"));
  };
  useEffect(load, []);

  const measureNames = new Set(rows.filter((r) => r.kind === "measure").map((r) => r.name.toLowerCase()));
  // a definition that only repeats its measure's name is the same line twice; show it only when it stands alone
  const shown = rows.filter((r) => r.kind === "measure" || !(measureNames.has(r.name.toLowerCase()) || r.name.startsWith("A restricted"))).filter((r) =>
    (filter === "all" || (filter === "full" && full(r)) || (filter === "missing" && !full(r)) || (filter === "mine" && !!user && r.owner === user.display_name))
    && r.name.toLowerCase().includes(q.trim().toLowerCase()));

  let body;
  if (state === "loading") body = <div role="status"><EmptyState title="Reading the register" lines={["Every signed measure and definition, with who signed it."]} /></div>;
  else if (state === "refused") body = <EmptyState title="The register is not open to you" lines={["Ask your company admin for a seat in this company."]} />;
  else if (state === "error") body = <div role="alert"><EmptyState title="The register did not load" lines={["Nothing was changed. Try again in a moment."]} /><Button onClick={load}>Try again</Button></div>;
  else if (rows.length === 0 && records.length === 0) body = <EmptyState title="Nothing has been signed yet." lines={["An intent of work and its measures appear here when they are signed."]} links={[{ label: "Open the map", href: "/centre/intent/graph" }]} />;
  else body = (
    <>
      {records.length ? <section aria-label="Activity records">
        <DataTable columns={REC_COLUMNS} rows={records.map((r) => ({
          name: <><strong>{r.name}</strong>{r.of ? <><br /><span className="ds-soft">In {r.of}</span></> : null}</>,
          kind: KIND[r.kind] ?? r.kind,
          by: r.by ?? <span className="ds-muted">Not named</span>,
          at: day(r.at, "Not available yet"),
          open: r.href ? <Link className="ds-link" to={r.href}>Open</Link> : null,
        }))} />
      </section> : null}
      {rows.length ? <>
      <div className="ds-frame__actions" role="group" aria-label="Filters">
        {FILTERS.map(([k, t]) => <Chip key={k} tone={filter === k ? "active" : "default"} onClick={() => setFilter(k)}>{t}</Chip>)}
        <input type="search" className="ds-chip" style={{ flex: "0 1 16rem" }} aria-label="Search the register" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {shown.length === 0
        ? <EmptyState title="No measure matches" lines={["Clear the search or choose All."]} />
        : <DataTable columns={COLUMNS} rows={shown.map((r) => ({
            name: <><strong>{r.name}</strong><br /><span className="ds-soft">{r.kind}</span></>,
            owner: r.owner ?? <span className="ds-muted">Not named</span>,
            source: r.source ? <Link className="ds-link" to={r.source.href} title={`A ${r.source.kind} from the charter`}>{r.source.name}</Link> : <span className="ds-muted">Not linked</span>,
            pipeline: r.pipeline ?? <span className="ds-muted">None yet</span>,
            signed: <Signatures signed={r.signed} />,
            version: `v${r.version}`,
            open: <Link className="ds-link" to={r.href}>Open</Link>,
          }))} />}
      </> : null}
    </>
  );

  return (
    <PageFrame
      title="Activity trail"
      subline={state === "ready" ? `${count(records.filter((r) => r.kind === "intent").length, "signed intent")}, ${count(rows.filter((r) => r.kind === "measure").length + records.filter((r) => r.kind === "measure").length, "measure")} aligned, ${rows.filter(full).length} fully released` : "Every recorded action"}
      aside={
        <>
          <SideCard title="The company's aligned truth">
            <p>The data team sees every recorded action: signatures, approvals and runs. Everyone else sees their own. Each measure row is one measure or definition the company signed: who owns it, which pipeline feeds it and which of the five signatures it has. Hover a signature to see who signed and when.</p>
          </SideCard>
          <SideCard title="The five signatures">
            <ul>
              <li>Charter: the question is agreed</li>
              <li>Baseline: the definition is confirmed</li>
              <li>Blueprint: the design is signed</li>
              <li>UAT: the checks are accepted</li>
              <li>Release: the measure is released</li>
            </ul>
          </SideCard>
          <Footnote>Names and links only. Figures sit behind each measure's access list.</Footnote>
        </>
      }
    >
      {body}
    </PageFrame>
  );
}
