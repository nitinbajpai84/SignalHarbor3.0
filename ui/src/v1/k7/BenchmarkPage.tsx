import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, day, PageFrame, Pill } from "../../design";
import { getPortfolios } from "../k4/api";
import { getComparison, getDefinitions, pct, pts, type Comparison, type Definition, type MonthComponent } from "./api";

// K7: /centre/consume/benchmark. Portfolio return against its benchmark, one row per month. Every figure is worked out on the server; nothing here.
// "Where is this from?" is drawn here from the signed definition (the trail, A2, has no kind for a benchmark return).
// ponytail: series names are a small map of the known index keys; a series table with names would replace it.
const SERIES: Record<string, string> = { "IDX:GLEQ:SYN": "Global equity index", "IDX:GLBD:SYN": "Global bond index" };
export const seriesName = (k: string) => SERIES[k] ?? (/EQ/i.test(k) ? "Equity index" : /BO?N?D/i.test(k) ? "Bond index" : k);
const share = (w: string) => `${+(Number(w) * 100).toFixed(2)}%`;
export const monthName = (m: string) => new Date(`${m}-01T00:00:00Z`).toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
/** "Global equity index, 42%: 3.5002%"; a component with a spread is the private-markets sleeve. */
export function componentLine(c: MonthComponent, bps?: string) {
  const sleeve = c.spread_return && Number(c.spread_return.value) !== 0;
  const name = sleeve ? `Private-markets sleeve (${seriesName(c.series_key).toLowerCase()}${bps && Number(bps) ? ` + ${+bps} bps a year` : " plus a spread"})` : seriesName(c.series_key);
  return `${name}, ${share(c.weight)}: ${pct(c.return)}`;
}
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const lastMonth = () => { const d = new Date(); d.setDate(0); return d.toISOString().slice(0, 7); };

export default function BenchmarkPage() {
  const [q, setQ] = useSearchParams();
  const [defs, setDefs] = useState<Definition[] | null>(null);
  const [error, setError] = useState("");
  const [portfolio, setPortfolio] = useState(q.get("portfolio") ?? "");
  const [code, setCode] = useState(q.get("code") ?? "");
  const [start, setStart] = useState(q.get("start") ?? q.get("end") ?? lastMonth());
  const [end, setEnd] = useState(q.get("end") ?? q.get("start") ?? lastMonth());
  const [result, setResult] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [pfs, setPfs] = useState<{ id: string; name: string }[] | null>(null); // null while the list loads; [] when it could not be read

  async function show(p = portfolio, c = code, s = start, e = end) {
    setBusy(true); setError(""); setResult(null); setQ({ portfolio: p, code: c, start: s, end: e }, { replace: true });
    try {
      const r = await getComparison(p, c, s, e);
      setResult(r);
      if (r.portfolio.code === p) setPortfolio(r.portfolio.id); // a link may carry the code (EG-LIQUID); the list is keyed by id, so show its name
    } catch (err) { setError(plain(err)); } finally { setBusy(false); }
  }

  // JUC4A-02: the list is a picker from the start (a slow answer never leaves a typed box); retried once, then the typed box is the fallback
  useEffect(() => { getPortfolios().catch(() => getPortfolios()).then(setPfs, () => setPfs([])); }, []);

  useEffect(() => {
    getDefinitions().then((d) => {
      setDefs(d.definitions);
      const c = q.get("code") || d.definitions.find((x) => x.status === "approved")?.benchmark_code || d.definitions[0]?.benchmark_code || "";
      setCode(c);
      if (q.get("portfolio") && c) void show(q.get("portfolio") ?? "", c, start, end);
    }, (err) => { setDefs([]); setError(plain(err)); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const inProgress = (defs ?? []).filter((d) => d.status !== "approved");
  const used = result && defs?.find((d) => d.benchmark_code === result.benchmark_code && d.version === result.version_used?.version);
  const bpsOf = (c: MonthComponent) => used?.components.find((x) => x.series_key === c.series_key && Number(x.weight) === Number(c.weight))?.spread_bps;
  return (
    <PageFrame title="Portfolio against benchmark" subline="Month by month, from the signed benchmark definition. Figures are worked out by the system, never by the assistant.">
      {error ? <p role="alert">{error}</p> : null}
      {defs === null ? <p className="ds-muted" role="status">Loading the benchmarks.</p> : null}
      {defs && !defs.length && !error ? <p className="ds-muted">No benchmark has been defined yet.</p> : null}
      {inProgress.map((d) => (
        <section key={`${d.benchmark_code}-${d.version}`} className="ds-card" style={{ padding: 16, marginBottom: 12 }} aria-label={`${d.benchmark_name} version ${d.version}`}>
          <strong>{d.benchmark_name}, version {d.version}</strong> <Pill tone="draft">In progress</Pill>
          <p style={{ margin: "6px 0" }}>{d.notice}</p>
          <p className="ds-muted" style={{ margin: 0 }}>{d.policy_question?.question}{d.policy_question?.case ? <>{" "}
            <Link className="ds-link" to={`/centre/action/cases/${encodeURIComponent(d.policy_question.case.case_id)}`}>Open the question on the {d.benchmark_name}</Link></> : null}</p>
        </section>))}
      {defs?.length ? (
        <form className="ds-card" style={{ padding: 16, marginBottom: 16, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }} onSubmit={(ev) => { ev.preventDefault(); void show(); }}>
          <label>Portfolio<br />{pfs === null || pfs.length ? (
            <select className="ds-input" value={portfolio} disabled={pfs === null} onChange={(ev) => setPortfolio(ev.target.value)}>
              <option value="">{pfs === null ? "Loading the portfolios" : "Choose a portfolio"}</option>
              {portfolio && !(pfs ?? []).some((p) => p.id === portfolio) && result?.portfolio.code !== portfolio ? <option value={portfolio}>{portfolio}</option> : null}
              {(pfs ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
          ) : <input className="ds-input" value={portfolio} onChange={(ev) => setPortfolio(ev.target.value)} placeholder="Portfolio code" />}</label>
          <label>Benchmark<br /><select className="ds-input" value={code} onChange={(ev) => setCode(ev.target.value)}>
            {[...new Set(defs.map((d) => d.benchmark_code))].map((c) => <option key={c} value={c}>{defs.find((d) => d.benchmark_code === c)?.benchmark_name ?? c}</option>)}</select></label>
          <label>From<br /><input className="ds-input" type="month" value={start} onChange={(ev) => setStart(ev.target.value)} /></label>
          <label>To<br /><input className="ds-input" type="month" value={end} onChange={(ev) => setEnd(ev.target.value)} /></label>
          <Button type="submit" disabled={busy || !portfolio || !code}>Show</Button>
        </form>) : null}
      {busy ? <p className="ds-muted" role="status">Working out the returns.</p> : null}
      {result ? (
        <section aria-label="Monthly comparison">
          <p className="ds-muted">
            {result.version_used ? `Benchmark version ${result.version_used.version} (${result.version_used.status.replace("_", " ")}).` : "No benchmark version was in force."}
            {result.version_used?.notice ? ` ${result.version_used.notice}` : ""}
          </p>
          <div className="ds-table-wrap">{/* analyst-uc4-02: at phone width the table scrolls inside its box, not the page */}
          <table className="ds-table" style={{ width: "100%" }}>
            <thead><tr><th>Month</th><th>Portfolio</th><th>Benchmark</th><th>Difference</th><th>Status</th></tr></thead>
            <tbody>
              {result.months.map((m) => (
                <tr key={m.month}>
                  <td>{monthName(m.month)}</td>
                  <td>{pct(m.portfolio)}</td>
                  <td>{pct(m.benchmark)}
                    <ul className="ds-muted" style={{ margin: 0, paddingLeft: 16 }}>
                      {m.components.map((c, i) => <li key={`${c.series_key}-${i}`}>{componentLine(c, bpsOf(c))}</li>)}
                    </ul>
                    {m.liquid_sleeve ? <div className="ds-muted">Liquid sleeve alone: {m.liquid_sleeve.pct}%</div> : null}
                  </td>
                  <td>{pts(m.difference)}
                    {m.liquid_sleeve?.difference ? <div className="ds-muted">Against the liquid sleeve: {pts(m.liquid_sleeve.difference)}</div> : null}
                  </td>
                  <td>{m.certified ? <Pill tone="signed">Certified</Pill> : <Pill tone="draft">Not certified</Pill>}
                    {m.problems.map((p) => <div key={p} className="ds-muted">{p}</div>)}</td>
                </tr>))}
            </tbody>
          </table></div>
          {used ? <details style={{ marginTop: 12 }}>
            <summary className="ds-link">Where is this from?</summary>
            <p>The {used.benchmark_name}, version {used.version} ({used.status.replace("_", " ")}), in force from {day(used.effective_from)}, in {used.currency}:</p>
            <ul>{used.components.map((c, i) => <li key={`${c.series_key}-${i}`}>{Number(c.spread_bps) ? `Private-markets sleeve: ${seriesName(c.series_key).toLowerCase()} + ${+c.spread_bps} bps a year` : seriesName(c.series_key)} ({c.series_key}), {share(c.weight)}</li>)}</ul>
            <p className="ds-muted">Each index return is its level at the closing month end over its level at the opening month end ({result.months.map((m) => `${day(m.period_start)} to ${day(m.period_end)}`).join("; ")}),
              from the market data recorded by then; a spread adds a twelfth of its yearly rate a month. The portfolio return is its closing value less its opening value and confirmed flows, over the opening value.</p>
          </details> : null}
        </section>) : null}
    </PageFrame>
  );
}
