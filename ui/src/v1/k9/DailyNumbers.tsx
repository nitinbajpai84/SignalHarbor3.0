import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Chip, Pill, type PillTone } from "../../design";
import { day as day0, money as money0 } from "../k4/api";
import { getDaily, type Daily, type Where } from "./api";

// CS1: the daily key numbers band at the top of Consume. Six large figures, each with a small change line, a status word and "Where is this from?".
// Every figure arrives from the server (GET /api/v1/consume/daily); this file only formats them.
const NOT_YET = "Not available yet";
const CURRENCIES = ["USD", "SGD"];
// Cycle 2 (UC1-C2-12): one date style ("30 Sep", never "Sept") and money in whole units or two decimals, never one.
// ponytail: local wrappers; move into ../k4/api.ts with its next owner.
const day = (iso: string | null | undefined) => day0(iso).replace("Sept", "Sep");
const money = (v: string | null | undefined, ccy: string | null | undefined) => {
  const n = v === null || v === undefined ? NaN : Number(v);
  return Number.isNaN(n) || Number.isInteger(n) ? money0(v, ccy) : `${ccy ?? ""} ${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim();
};
const monthOf = (iso: string | null | undefined) => (iso ? day(iso).replace(/^\d+ /, "") : "");
const num = (v: string | null | undefined) => (v === null || v === undefined || v === "" ? null : Number(v));
const compact = (v: string | null | undefined, ccy: string) => {
  const n = num(v);
  return n === null || Number.isNaN(n) ? NOT_YET : `${ccy} ${new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 }).format(n)}`;
};
const signed = (v: string | null | undefined, ccy: string) => {
  const n = num(v);
  return n === null || Number.isNaN(n) ? NOT_YET : `${n > 0 ? "+" : n < 0 ? "-" : ""}${money(String(Math.abs(n)), ccy)}`;
};
const pct = (v: string | null | undefined, plus = true) => {
  const n = num(v);
  return n === null || Number.isNaN(n) ? NOT_YET : `${plus && n > 0 ? "+" : ""}${n.toFixed(2)}%`;
};
const tone = (s: string | undefined): PillTone => {
  const w = (s ?? "").toLowerCase();
  if (/^(official|certified|covered|fully explained|matches)/.test(w)) return "ok";
  if (/^(stale|short|unverified|some unexplained|not certified)/.test(w)) return "late";
  return "draft";
};
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "The key numbers could not be loaded. Please try again.");

function Card({ id, label, big, change, status, where, unavailable, children }: {
  id: string; label: string; big: string; change?: string; status?: string; where?: Where; unavailable?: string | null; children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const sources = (where?.sources ?? []).filter((s) => s.text);
  return (
    <article className="ds-card" aria-label={label} style={{ padding: 16, minWidth: 0 }}>
      <div className="ds-muted" style={{ fontSize: "0.85rem" }}>{label}</div>
      <div style={{ fontSize: "1.75rem", fontWeight: 600, lineHeight: 1.2, overflowWrap: "anywhere" }}>{unavailable ? NOT_YET : big}</div>
      {unavailable ? <p className="ds-muted" role="status" style={{ margin: "4px 0" }}>{unavailable}</p> : (
        <>
          <div className="ds-muted" style={{ fontSize: "0.85rem", margin: "4px 0" }}>{change}</div>
          {status ? <Pill tone={tone(status)}>{status}</Pill> : null}
          {children ? <div style={{ fontSize: "0.85rem", marginTop: 8 }}>{children}</div> : null}
        </>
      )}
      {where ? (
        <>
          <button type="button" className="ds-link" style={{ marginTop: 8 }} aria-expanded={open} aria-label={`${label}: Where is this from?`} onClick={() => setOpen(!open)}>Where is this from?</button>
          {open ? (
            <div className="ds-muted" style={{ fontSize: "0.85rem", marginTop: 4 }} data-trail-id={id}>
              <p style={{ margin: "0 0 4px" }}>{where.text}</p>
              {sources.length ? <ul style={{ margin: 0, paddingLeft: 18 }}>{sources.slice(0, 5).map((s, i) => <li key={i}>{s.text}</li>)}</ul> : null}
              {sources.length > 5 ? <p style={{ margin: "4px 0 0" }}>and {sources.length - 5} more records.</p> : null}
            </div>
          ) : null}
        </>
      ) : null}
    </article>
  );
}

const Row = ({ id, children }: { id: string; children: ReactNode }) => <div data-trail-id={id} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>{children}</div>;

export default function DailyNumbers() {
  const [ccy, setCcy] = useState("USD");
  const [d, setD] = useState<Daily | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setError("");
    setD(null);
    getDaily(ccy).then((r) => { if (live) setD(r); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [ccy]);
  const n = d?.nav, i = d?.issued, r = d?.returns, l = d?.levers, m = d?.markets, q = d?.liquidity;
  const month = r?.periods?.[0], ytd = r?.periods?.[1];
  const eq = m?.series?.find((s) => s.kind === "index_level" && /equity/i.test(s.name)) ?? m?.series?.find((s) => s.kind === "index_level");
  const fx = m?.series?.find((s) => s.kind === "fx");
  const diff = month?.difference ?? null;
  return (
    <section aria-label="Key numbers" style={{ marginBottom: 24 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, justifyContent: "space-between", marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>Key numbers{d ? <span className="ds-muted" style={{ fontSize: "0.9rem", fontWeight: 400 }}> as of {day(d.as_of)}</span> : null}</h2>
        <div role="group" aria-label="Currency" style={{ display: "flex", gap: 8 }}>
          {CURRENCIES.map((c) => <Chip key={c} tone={c === ccy ? "active" : "default"} onClick={() => setCcy(c)}>{c}</Chip>)}
        </div>
      </div>
      {error ? <p role="alert">{error}</p> : null}
      {!d && !error ? <p className="ds-muted" role="status">Loading the key numbers.</p> : null}
      {d && n && i && r && l && m && q ? (
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 230px), 1fr))" }}>
          <Card id={n.trail_id ?? "nav"} label="Total value" big={compact(n.total, ccy)} unavailable={n.available ? (n.total === null && !n.by_entity?.length ? "Nothing you can see is valued yet." : null) : n.message}
            change={n.partial ? "Only the entities you can see" : `${n.by_entity?.length ?? 0} entities`} status={n.status} where={n.where}>
            {n.by_entity?.map((e) => <Row key={e.trail_id} id={e.trail_id}><span>{e.name}</span><span>{money(e.value, ccy)}</span></Row>)}
          </Card>
          <Card id={i.trail_id ?? "issued"} label="Known now against the issued report" big={compact(i.known_now, ccy)} unavailable={i.available ? null : i.message}
            change={`${signed(i.difference, ccy)} since the report of ${day(i.issued_at ?? i.period_end)}`} status={i.status} where={i.where}>
            <div>Issued {money(i.issued, ccy)}</div>
            {i.banner ? <div>{i.banner}</div> : null}
            {i.brief_link ? <Link className="ds-link" to={i.brief_link}>Open the CIO Brief</Link> : null}
          </Card>
          <Card id={r.trail_id ?? "returns"} label={month?.end ? `Return for ${monthOf(month.end)}` : "Return for the last month"} big={pct(month?.portfolio, false)} unavailable={r.available && month?.portfolio !== null ? null : r.message ?? month?.message ?? NOT_YET}
            change={`Benchmark ${pct(month?.benchmark, false)}, ${diff === null ? NOT_YET : `${(Number(diff) > 0 ? "+" : "") + Number(diff).toFixed(2)} points`}`} status={r.status} where={r.where}>
            <Row id={ytd?.trail_id ?? "ytd"}><span>Year to date</span><span>{!ytd || ytd.portfolio === null ? (ytd?.message ?? NOT_YET) : `${pct(ytd.portfolio, false)} against ${pct(ytd.benchmark, false)}`}</span></Row>
            <div className="ds-muted">{r.portfolio} against {r.benchmark_code}</div>
          </Card>
          <Card id={l.trail_id ?? "levers"} label="What moved the liquid book" big={pct(l.percent)} unavailable={l.available ? null : l.message}
            change={l.movers?.[0] ? `Biggest mover ${l.movers[0].name} ${signed(l.movers[0].amount, ccy)}` : "No mover to show"} status={l.status} where={l.where}>
            {l.parts?.map((p) => <Row key={p.trail_id} id={p.trail_id}><span>{p.label}</span><span>{signed(p.amount, ccy)}</span></Row>)}
            {l.movers?.map((x) => <Row key={x.trail_id} id={x.trail_id}><span>{x.name}</span><span>{signed(x.amount, ccy)}</span></Row>)}
            <Link className="ds-link" to="/centre/consume/office#why-moved">Why did this move</Link>
          </Card>
          <Card id={m.trail_id ?? "markets"} label="Markets this month" big={eq ? pct(eq.month_change_pct) : NOT_YET} unavailable={m.available ? null : m.message}
            change={fx ? `${fx.name} ${num(fx.level)?.toFixed(4)}, ${fx.day_change_pct === null ? "no last-day move" : `${pct(fx.day_change_pct)} on the last day`}` : ""} status={m.status} where={m.where}>
            {m.series?.map((s) => <Row key={s.trail_id} id={s.trail_id}><span>{s.name}</span><span>{pct(s.month_change_pct)} month{s.day_change_pct === null ? "" : `, ${pct(s.day_change_pct)} day`}</span></Row>)}
          </Card>
          <Card id={q.trail_id ?? "liquidity"} label="Cash after confirmed calls" big={compact(q.cash_after_confirmed, ccy)} unavailable={q.available ? null : q.message}
            change={`Calls due in 30 days ${money(q.calls_30, ccy)}`} status={q.status} where={q.where}>
            {q.partial ? <div className="ds-muted">Some amounts have no signed exchange rate and are left out.</div> : null}
            {q.entities?.map((e) => <Row key={e.trail_id} id={e.trail_id}><span>{e.name}</span><span>{money(e.cash_after_confirmed, ccy)}{e.unconfirmed ? ` (${e.unconfirmed} call not confirmed)` : ""}</span></Row>)}
          </Card>
        </div>
      ) : null}
    </section>
  );
}
