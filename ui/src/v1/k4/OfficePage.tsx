import { Fragment, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, Chip, PageFrame, Pill } from "../../design";
import Comments from "../n2/Comments";
import { statusTone } from "../e5/TodayPage";
import {
  day as day0, getBridge, getHoldings, getIssued, getLiquidity, getPortfolios, getWhyMoved, money as money0, sentence,
  type BridgeItem, type Evidence, type Holdings, type Issued, type Liquidity, type LiquidityEntity, type LiquidityItem, type NavBridge, type Where, type WhyLine, type WhyMoved,
} from "./api";

// Fields k6_liquidity.forecast sends beyond the shapes in ./api: where each call comes from, the confirmed-only cash and the shortfall in words.
type Notice = LiquidityItem & { document_id?: string | null; document_title?: string | null; received_at?: string | null; page?: number | null; line?: number | null };
type Entity = Omit<LiquidityEntity, "buckets"> & {
  warnings?: string[]; unconfirmed_distributions?: Notice[];
  buckets: (LiquidityEntity["buckets"][number] & { cash_after_confirmed_calls?: string | null; items: Notice[] })[];
};

// Cycle 2 (UC1-C2-12): one date style ("30 Sep", never "Sept") and money in whole units or two decimals, never one.
// ponytail: local wrappers; move into ./api.ts with its next owner.
const day = (iso: string | null | undefined) => day0(iso).replace("Sept", "Sep");
const money = (v: string | null | undefined, ccy: string | null | undefined) => {
  const n = v === null || v === undefined ? NaN : Number(v);
  return Number.isNaN(n) || Number.isInteger(n) ? money0(v, ccy) : `${ccy ?? ""} ${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim();
};
// Fields the server sends beyond the shapes in ./api: the rate behind converted figures, and the report's issue time and data cutoff.
type HoldingsX = Holdings & { rate_note?: string | null };
type IssuedX = Issued & { rate_note?: string | null; report: (NonNullable<Issued["report"]> & { when?: string | null }) | null };
// At phone width a table marked k4-stack shows each row as a small card, every cell labelled by its column (UC1-C2-09, UC6-08).
const STACK_CSS = `@media (max-width: 640px) {
  table.k4-stack thead { display: none; }
  table.k4-stack tr { display: block; border-bottom: 1px solid var(--ds-border, #ddd); padding: 6px 0; }
  table.k4-stack td { display: flex; justify-content: space-between; gap: 12px; border: 0; padding: 2px 0; text-align: right; }
  table.k4-stack td[data-label]::before { content: attr(data-label); font-weight: 600; text-align: left; }
  table.k4-stack td:not([data-label]) { display: block; text-align: left; }
}`;

// K2: /centre/consume/office. Holdings, the latest issued report beside what is known now, the NAV bridge and liquidity.
// Figures arrive from the server; nothing is calculated here. Every figure can answer "Where is this from?".
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const CURRENCIES = ["USD", "SGD"];

function useSection<T>(load: () => Promise<T>, deps: unknown[]): { data: T | null; error: string } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setError("");
    setData(null);
    load().then((d) => { if (live) setData(d); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error };
}

function WhereBox({ w }: { w: Where }) {
  return (
    <p className="ds-muted" style={{ margin: "4px 0 8px" }}>
      {w.text}{" "}
      {w.document_id ? <Link className="ds-link" to={`/centre/evidence/${w.document_id}`}>Open the statement</Link> : null}
    </p>
  );
}

function Section({ title, error, children, id }: { title: string; error: string; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="ds-card" style={{ padding: 16, marginBottom: 16 }} aria-label={title}>
      <h2 style={{ fontSize: "1.05rem", marginTop: 0 }}>{title}</h2>
      {error ? <p role="alert">{error}</p> : children}
    </section>
  );
}

function HoldingsSection({ currency }: { currency: string }) {
  const { data, error } = useSection<HoldingsX>(() => getHoldings(currency), [currency]);
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Section title="Holdings" error={error}>
      {!data ? <p className="ds-muted" role="status">Loading the holdings.</p> : null}
      {data && !data.entities.length ? <p className="ds-muted">No holdings to show yet.</p> : null}
      {data?.entities.map((e) => (
        <div key={e.entity_id} style={{ marginBottom: 16 }}>
          <h3 style={{ fontSize: "1rem", marginBottom: 4 }}>{e.entity_name} <span className="ds-muted">{e.total ? money(e.total, data.currency) : "Total not shown"}</span></h3>
          {e.portfolios.map((p) => (
            <div key={p.portfolio_id}>
              <h4 style={{ margin: "8px 0 4px" }}>{p.portfolio_name} <span className="ds-muted">{money(p.total, p.currency)}</span></h4>
              {p.message ? <p className="ds-muted" role="status">{p.message}</p> : null}
              <div style={{ overflowX: "auto" }}><table className="ds-table k4-stack" style={{ width: "100%" }}>
                <thead><tr><th>Holding</th><th>Asset class</th><th>Value</th><th>Status</th><th>Source</th></tr></thead>
                <tbody>{p.lines.map((l) => {
                  const k = `${p.portfolio_id}:${l.instrument_id}`;
                  return (
                    <Fragment key={k}>
                      <tr>
                        <td><button type="button" className="ds-link" aria-label={`${l.name}: Where is this from?`} aria-expanded={open === k} onClick={() => setOpen(open === k ? null : k)}>{l.name}</button></td>
                        <td data-label="Asset class">{l.asset_class ? sentence(l.asset_class.replace(/_/g, " ")) : <span className="ds-muted">Not set</span>}</td>
                        <td data-label="Value">{money(l.value, l.currency)}{l.native.currency && l.native.currency !== l.currency ? <span className="ds-muted"> ({money(l.native.amount, l.native.currency)})</span> : null}</td>
                        <td data-label="Status"><Pill tone={statusTone(l.status)}>{sentence(l.status)}</Pill></td>
                        <td data-label="Source">{l.source}</td>
                      </tr>
                      <tr><td colSpan={5}><Comments eager target={{ kind: "office_line", id: `${p.portfolio_id}/${l.instrument_id}` }} /></td></tr>
                      {open === k ? <tr><td colSpan={5}><WhereBox w={l.where} /></td></tr> : null}
                    </Fragment>);
                })}</tbody>
              </table></div>
            </div>))}
        </div>))}
      {data ? (
        <p style={{ margin: 0 }}>
          <strong>All holdings:</strong> {data.total ? money(data.total, data.currency) : "Not shown, because some portfolios are hidden from you or cannot be converted."}{" "}
          <span className="ds-muted">As of {day(data.as_of)}. Values older than {data.stale_after_days} days read Stale.{data.rate_note ? ` ${data.rate_note}` : ""}</span>
        </p>) : null}
    </Section>
  );
}

function IssuedSection({ currency }: { currency: string }) {
  const { data, error } = useSection<IssuedX>(() => getIssued(currency) as Promise<IssuedX>, [currency]);
  const [open, setOpen] = useState(false);
  return (
    <Section title="Issued versus known now" error={error}>
      {!data ? <p className="ds-muted" role="status">Loading the latest report.</p> : null}
      {data && !data.report ? <p className="ds-muted">{data.message}</p> : null}
      {data?.report ? (
        <>
          <p style={{ marginTop: 0 }}><strong>{data.report.name}</strong> <span className="ds-muted">{data.report.when ?? `issued ${day(data.report.issued_at ?? data.report.period_end)}`}</span></p>
          {data.rate_note ? <p className="ds-muted" style={{ marginTop: 0 }}>{data.rate_note}</p> : null}
          {data.currency_message ? <p className="ds-muted" role="status">{data.currency_message}</p> : null}
          {data.banner ? <p role="status" className="ds-card" style={{ padding: 12 }}>{data.banner}</p> : null}
          {data.lines?.length ? <div style={{ overflowX: "auto" }}><table className="ds-table" style={{ width: "100%" }}>
            <thead><tr><th>Line</th><th>As issued</th><th>Known now</th><th>Status</th></tr></thead>
            <tbody>{data.lines?.map((l) => (
              <tr key={l.line_key}><td>{l.label}</td><td>{money(l.issued, l.currency)}</td><td>{money(l.known_now, l.currency)}</td>
                <td><Pill tone={statusTone(l.status)}>{sentence(l.status)}</Pill></td></tr>))}</tbody>
          </table></div> : <p className="ds-muted" role="status">The lines of this report are not shown, because they belong to entities you do not have access to.</p>}
          <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
            {data.brief_link ? <Link className="ds-link" to={data.brief_link}>Open the CIO Brief</Link> : null}
            <Button onClick={() => setOpen(!open)}>Where is this from?</Button>
          </div>
          {open && data.where ? <WhereBox w={data.where} /> : null}
        </>) : null}
    </Section>
  );
}

function EvidenceList({ items }: { items: Evidence[] }) {
  return items.length
    ? <ul style={{ margin: "4px 0 8px" }}>{items.map((e, n) => <li key={n}><strong>{e.label}.</strong> {e.text}</li>)}</ul>
    : <p className="ds-muted">No records to show.</p>;
}

function BridgeCard({ b }: { b: BridgeItem }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!b.available) return <div style={{ marginBottom: 16 }}><h3 style={{ fontSize: "1rem", marginBottom: 4 }}>{b.portfolio_name}</h3><p className="ds-muted" role="status">{b.message}</p></div>;
  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: "1rem", marginBottom: 4 }}>{b.portfolio_name} <span className="ds-muted">{b.entity_name}</span></h3>
      <p style={{ margin: "0 0 8px" }}>
        Investment view {money(b.investment_total, b.currency)} · Administrator NAV for {day(b.nav_date)} {money(b.administrator_nav, b.currency)} ·{" "}
        <strong>Difference {money(b.difference, b.currency)}</strong>
      </p>
      <div style={{ overflowX: "auto" }}><table className="ds-table" style={{ width: "100%" }}>
        <thead><tr><th>Part of the difference</th><th>Amount</th><th /></tr></thead>
        <tbody>{b.parts?.map((p) => (
          <Fragment key={p.code}>
            <tr><td>{p.label}<div className="ds-muted">{p.plain}</div></td><td>{money(p.amount, b.currency)}</td>
              <td><Button onClick={() => setOpen(open === p.code ? null : p.code)}>Where is this from?</Button></td></tr>
            {open === p.code ? <tr><td colSpan={3}><EvidenceList items={p.evidence} /></td></tr> : null}
          </Fragment>))}</tbody>
      </table></div>
    </div>
  );
}

function BridgeSection({ currency }: { currency: string }) {
  const { data, error } = useSection<NavBridge>(() => getBridge(currency), [currency]);
  return (
    <Section title="Investment total against administrator NAV" error={error}>
      {!data ? <p className="ds-muted" role="status">Loading the bridge.</p> : null}
      {data && !data.portfolios.length ? <p className="ds-muted">No portfolios to compare yet.</p> : null}
      {data?.portfolios.map((b) => <BridgeCard key={b.portfolio_id} b={b} />)}
    </Section>
  );
}

const monthEnd = (back: number) => {
  const n = new Date();
  return new Date(Date.UTC(n.getUTCFullYear(), n.getUTCMonth() - back + 1, 0)).toISOString().slice(0, 10);
};

function WhyLines({ lines, ccy }: { lines: WhyLine[]; ccy: string }) {
  return (
    <ul style={{ margin: "4px 0 8px", paddingLeft: 20 }}>{lines.map((l, n) => (
      <li key={n}><strong>{l.label}</strong> {money(l.amount, ccy)}. {l.plain}{" "}
        {l.evidence.map((e, i) => (
          <span key={i} className="ds-muted">{e.text}{e.document_id ? <> <Link className="ds-link" to={`/centre/evidence/${e.document_id}`}>Open the statement</Link></> : null}{i < l.evidence.length - 1 ? "; " : ""}</span>))}
      </li>))}</ul>
  );
}

function WhyMovedSection({ currency }: { currency: string }) {
  const { hash } = useLocation();
  useEffect(() => { if (hash === "#why-moved") document.getElementById("why-moved")?.scrollIntoView?.(); }, [hash]);
  const [month, setMonth] = useState(monthEnd(1).slice(0, 7));
  const [book, setBook] = useState("liquid"); // "liquid" = the liquid book, otherwise a portfolio id
  const { data: pfs } = useSection(getPortfolios, []);
  const [y, m] = month.split("-").map(Number);
  const valid = Boolean(y && m);
  const end = valid ? new Date(Date.UTC(y!, m!, 0)).toISOString().slice(0, 10) : "";
  const start = valid ? new Date(Date.UTC(y!, m! - 1, 0)).toISOString().slice(0, 10) : "";
  const { data, error } = useSection<WhyMoved | null>(() => (valid ? getWhyMoved(currency, start, end, book === "liquid" ? "liquid" : "", book === "liquid" ? "" : book) : Promise.resolve(null)), [currency, start, end, book]);
  return (
    <Section id="why-moved" title="Why did this move" error={error}>
      <p style={{ marginTop: 0, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <label>Portfolio <select value={book} onChange={(e) => setBook(e.target.value)}>
          <option value="liquid">The liquid book</option>
          {pfs?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
        <label>Month <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} /></label>
        {valid ? <span className="ds-muted">{day(start)} to {day(end)}</span> : null}
      </p>
      {!data ? <p className="ds-muted" role="status">Loading the explanation.</p> : null}
      {data && !data.available ? <p className="ds-muted" role="status">{data.message}</p> : null}
      {data?.available ? (
        <>
          <p style={{ margin: "0 0 8px" }}>
            {money(data.start_value, data.currency)} on {day(data.start)} to {money(data.end_value, data.currency)} on {day(data.end)} ·{" "}
            <strong>Change {money(data.change, data.currency)}{data.percent ? ` (${Number(data.percent) > 0 ? "+" : ""}${data.percent}%)` : ""}</strong>
          </p>
          <p className="ds-muted" style={{ margin: "0 0 8px" }}>{data.largest ? `Largest contributor: ${data.largest}. ` : ""}{data.message}</p>
          {data.parts?.map((p) => (
            <div key={p.code}>
              <h3 style={{ fontSize: "1rem", marginBottom: 4 }}>{p.label} {p.code === "trades" ? null : <span className="ds-muted">{money(p.amount, data.currency)}</span>}</h3>
              {p.lines.length ? <WhyLines lines={p.lines} ccy={data.currency} /> : <p className="ds-muted">None in this period.</p>}
            </div>))}
        </>) : null}
    </Section>
  );
}

function NoticeLine({ i }: { i: Notice }) {
  return (
    <li>{i.fund ?? "A fund"}: {i.kind === "call" ? "capital call" : "distribution"} {money(i.own_amount, i.own_currency)} due {day(i.due_date)}, {i.confirmed ? "confirmed" : "waiting to be confirmed"}
      {i.document_id ? <>{". "}<Link className="ds-link" to={`/centre/evidence/${i.document_id}`}>{i.document_title ?? "Open the notice"}</Link>
        {i.received_at ? `, received ${day(i.received_at)}` : ""}{i.page ? `, page ${i.page}${i.line ? `, line ${i.line}` : ""}` : ""}</> : null}</li>
  );
}

function LiquidityCard({ e }: { e: Entity }) {
  const [open, setOpen] = useState(false);
  const notices = e.buckets.filter((b) => b.key !== "overdue").flatMap((b) => b.items);
  return (
    <div style={{ marginBottom: 20 }}>
      <h3 style={{ fontSize: "1rem", marginBottom: 4 }}>{e.entity_name}</h3>
      <p style={{ margin: "0 0 8px" }}>
        Available cash {money(e.available_cash, e.currency)} · Still to be called {money(e.uncalled, e.currency)}{" "}
        <Button onClick={() => setOpen(!open)}>Where is this from?</Button>
      </p>
      {(e.warnings ?? []).map((w) => <p key={w} className="ds-warn" role="alert"><strong>{w}</strong></p>)}
      {e.problems.map((p) => <p key={p} className="ds-muted" role="status">{p}</p>)}
      <div style={{ overflowX: "auto" }}><table className="ds-table k4-stack" style={{ width: "100%" }}>
        <thead><tr><th>Due</th><th>Capital calls</th><th>Distributions expected</th><th>Cash after the calls</th><th>Cash after confirmed calls only</th></tr></thead>
        <tbody>{e.buckets.map((b) => (
          <tr key={b.key}><td data-label="Due">{b.label}</td><td data-label="Capital calls">{money(b.calls, e.currency)}</td><td data-label="Distributions expected">{money(b.distributions, e.currency)}</td>
            <td data-label="Cash after the calls">{b.cash_after_calls === null ? "" : money(b.cash_after_calls, e.currency)}{b.cash_after_calls !== null && Number(b.cash_after_calls) < 0 ? <span className="ds-warn"> (shortfall)</span> : null}</td>
            <td data-label="Cash after confirmed calls only">{b.cash_after_confirmed_calls == null ? "" : money(b.cash_after_confirmed_calls, e.currency)}</td></tr>))}</tbody>
      </table></div>
      {e.unconfirmed.length ? (
        <p role="status" style={{ marginBottom: 0 }}><strong>Not confirmed yet:</strong>{" "}
          {e.unconfirmed.map((i) => `${i.fund ?? "A fund"} ${money(i.own_amount, i.own_currency)} due ${day(i.due_date)}`).join("; ")}.</p>) : null}
      {e.unconfirmed_distributions?.length ? (
        <p role="status" style={{ marginBottom: 0 }}><strong>Distributions not confirmed yet:</strong>{" "}
          {e.unconfirmed_distributions.map((i) => `${i.fund ?? "A fund"} ${money(i.own_amount, i.own_currency)} expected ${day(i.due_date)}`).join("; ")}.</p>) : null}
      {open ? (
        <div className="ds-muted">
          <p style={{ marginBottom: 4 }}>Cash is the latest cash position on or before {day(e.cash_sources[0]?.position_date)}:</p>
          <ul style={{ margin: 0 }}>{e.cash_sources.map((c) => <li key={c.position_id}>{money(c.amount, e.currency)} as at {day(c.position_date)}, {c.status}</li>)}</ul>
          {notices.length ? <>
            <p style={{ marginBottom: 4 }}>The calls and distributions in the next 90 days come from these notices:</p>
            <ul style={{ margin: 0 }}>{notices.map((i) => <NoticeLine key={i.id} i={i} />)}</ul>
          </> : <p style={{ marginBottom: 4 }}>No calls or distributions are due in the next 90 days.</p>}
        </div>) : null}
    </div>
  );
}

function LiquiditySection({ currency }: { currency: string }) {
  const { data, error } = useSection<Liquidity>(() => getLiquidity(currency), [currency]);
  return (
    <Section title="Liquidity" error={error}>
      {!data ? <p className="ds-muted" role="status">Loading the liquidity forecast.</p> : null}
      {data && !data.available ? <p className="ds-muted" role="status">{data.message}</p> : null}
      {data?.available && !data.entities?.length ? <p className="ds-muted">No entities to show yet.</p> : null}
      {data?.available ? <p className="ds-muted" style={{ marginTop: 0 }}>As of {day(data.as_of)}.</p> : null}
      {data?.available ? data.entities?.map((e) => <LiquidityCard key={e.entity_id} e={e as Entity} />) : null}
    </Section>
  );
}

export default function OfficePage() {
  const [currency, setCurrency] = useState("USD");
  return (
    <PageFrame title="Office view" subline="Holdings, reports and cash for the family office"
      actions={<div role="group" aria-label="Currency" style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span className="ds-muted">Show in</span>
        {CURRENCIES.map((c) => <Chip key={c} tone={c === currency ? "active" : "default"} onClick={() => setCurrency(c)}>{c}</Chip>)}</div>}>
      <style>{STACK_CSS}</style>
      <HoldingsSection currency={currency} />
      <IssuedSection currency={currency} />
      <BridgeSection currency={currency} />
      <WhyMovedSection currency={currency} />
      <LiquiditySection currency={currency} />
    </PageFrame>
  );
}
