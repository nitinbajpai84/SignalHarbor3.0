import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill } from "../../design";
import { WhereFrom } from "../a5/TrailHost";
import ConsumeBar from "../k10/ConsumeBar";
import { getPortfolios } from "../k4/api";
import { getDefinitions, pct, pts } from "../k7/api";
import { getAttribution, type Attribution } from "./api";

// K11: Consume > What if. Where the return came from, against the signed benchmark: allocation, selection and interaction per sleeve, contribution by fund.
// Every figure is worked out on the server from recorded values; each fund figure opens its own trail. Nothing is calculated here.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");
const lastMonth = () => { const d = new Date(); d.setDate(0); return d.toISOString().slice(0, 7); };

export default function AttributionTab() {
  const [q, setQ] = useSearchParams();
  const [portfolio, setPortfolio] = useState(q.get("portfolio") ?? "");
  const [code, setCode] = useState(q.get("code") ?? "");
  const [month, setMonth] = useState(q.get("month") ?? lastMonth());
  const [codes, setCodes] = useState<string[]>([]);
  const [pfs, setPfs] = useState<{ id: string; name: string }[] | null>(null);
  const [res, setRes] = useState<Attribution | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function show(p = portfolio, c = code, m = month) {
    setBusy(true); setError(""); setRes(null); setQ({ portfolio: p, code: c, month: m }, { replace: true });
    try { setRes(await getAttribution(p, c, m)); } catch (e) { setError(plain(e)); } finally { setBusy(false); }
  }
  useEffect(() => { getPortfolios().then(setPfs, () => setPfs([])); }, []);
  useEffect(() => {
    getDefinitions().then((d) => {
      const list = [...new Set(d.definitions.map((x) => x.benchmark_code))];
      setCodes(list);
      const c = q.get("code") || d.definitions.find((x) => x.status === "approved")?.benchmark_code || list[0] || "";
      setCode(c);
      if (q.get("portfolio") && c) void show(q.get("portfolio") ?? "", c, month);
    }, (e) => setError(plain(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const t = res?.totals;
  return (
    <>
    <ConsumeBar here="whatif" />
    <PageFrame title="What if: where the return came from" subline="Against the signed benchmark, sleeve by sleeve. Figures are worked out by the system from recorded values, never by the assistant.">
      {error ? <p role="alert">{error}</p> : null}
      <form className="ds-card" style={{ padding: 16, marginBottom: 16, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }} onSubmit={(ev) => { ev.preventDefault(); void show(); }}>
        <label>Portfolio<br />{pfs && pfs.length ? (
          <select className="ds-input" value={portfolio} onChange={(ev) => setPortfolio(ev.target.value)}>
            <option value="">Choose a portfolio</option>
            {portfolio && !pfs.some((p) => p.id === portfolio) ? <option value={portfolio}>{portfolio}</option> : null}
            {pfs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select>
        ) : <input className="ds-input" value={portfolio} onChange={(ev) => setPortfolio(ev.target.value)} placeholder="Portfolio code" />}</label>
        <label>Benchmark<br /><select className="ds-input" value={code} onChange={(ev) => setCode(ev.target.value)}>
          {codes.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
        <label>Month<br /><input className="ds-input" type="month" value={month} onChange={(ev) => setMonth(ev.target.value)} /></label>
        <Button type="submit" disabled={busy || !portfolio || !code}>Show</Button>
      </form>
      {busy ? <p className="ds-muted" role="status">Working out the attribution.</p> : null}
      {res ? (
        <section aria-label="Attribution">
          <p className="ds-muted">
            {res.version_used ? `Benchmark ${res.version_used.name}, version ${res.version_used.version} (${res.version_used.status.replace("_", " ")}).` : "No benchmark version was in force."}{" "}
            {res.certified ? <Pill tone="signed">Certified</Pill> : <Pill tone="draft">Not certified</Pill>}
          </p>
          {res.problems.map((p) => <p key={p} role="status">{p}</p>)}
          {t ? <>
            {t.partial ? <p>Benchmark {pct(t.benchmark_return)}. {t.note} In those sleeves: allocation {pts(t.allocation)}, selection {pts(t.selection)} and interaction {pts(t.interaction)}.</p> : (
            <p>Portfolio {pct(t.portfolio_return)} against benchmark {pct(t.benchmark_return)}: active return <strong>{pts(t.active_return)}</strong>, of which allocation {pts(t.allocation)},
              selection {pts(t.selection)} and interaction {pts(t.interaction)}.{t.reconciles ? "" : ` ${pts(t.unexplained)} could not be placed.`}</p>)}
            <h2>By sleeve</h2>
            <div className="ds-table-wrap"><table className="ds-table" style={{ width: "100%" }}>
              <thead><tr><th>Sleeve</th><th>Weight</th><th>Benchmark weight</th><th>Active weight</th><th>Return</th><th>Benchmark return</th><th>Allocation</th><th>Selection</th><th>Interaction</th><th>Total</th></tr></thead>
              <tbody>{res.sleeves.map((s) => s.masked ? (
                <tr key={s.sleeve}><td>{s.label}</td><td className="ds-muted">Not shown</td><td>{pct(s.benchmark_weight)}</td><td colSpan={2} className="ds-muted">{s.note}</td>
                  <td>{pct(s.benchmark_return)}</td><td colSpan={4} className="ds-muted">Not shown</td></tr>
              ) : (
                <tr key={s.sleeve}><td>{s.label}</td><td>{pct(s.portfolio_weight)}</td><td>{pct(s.benchmark_weight)}</td><td>{pts(s.active_weight)}</td>
                  <td>{s.portfolio_return ? pct(s.portfolio_return) : "Not held"}</td><td>{pct(s.benchmark_return)}</td>
                  <td>{pts(s.allocation)}</td><td>{pts(s.selection)}</td><td>{pts(s.interaction)}</td><td>{pts(s.total)}</td></tr>))}</tbody>
            </table></div>
            <h2>By fund</h2>
            <div className="ds-table-wrap"><table className="ds-table" style={{ width: "100%" }}>
              <thead><tr><th>Fund</th><th>Sleeve</th><th>Weight</th><th>Return</th><th>Contribution</th><th>Source</th></tr></thead>
              <tbody>{res.funds.map((f, i) => f.visible ? (
                <tr key={f.instrument_id ?? `x${i}`}><td>{f.name}</td><td>{res.sleeves.find((s) => s.sleeve === f.sleeve)?.label ?? f.sleeve}</td><td>{pct(f.weight ?? null)}</td>
                  <td>{pct(f.return ?? null)}</td><td>{pts(f.contribution ?? null)}</td>
                  <td>{f.trail?.length ? f.trail.map((r) => <span key={r.id}>{r.as_of}: <WhereFrom kind={r.kind} id={r.id} /> </span>) : "Not recorded"}</td></tr>
              ) : <tr key={`h${i}`}><td colSpan={6} className="ds-muted">{f.name}</td></tr>)}</tbody>
            </table></div>
            <h2>Cap size and region</h2>
            {Object.entries(res.splits).map(([k, s]) => (
              <p key={k} className="ds-muted">{s.available ? `${k.replace("_", " ")}: ${Object.entries(s.groups).map(([g, v]) => `${g} ${pct(v.weight)}`).join("; ")}` : s.missing}</p>))}
          </> : null}
        </section>) : null}
    </PageFrame>
    </>
  );
}
