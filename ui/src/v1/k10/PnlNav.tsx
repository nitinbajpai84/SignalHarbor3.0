import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DataTable, Footnote, day } from "../../design";
import DailyNumbers from "../k9/DailyNumbers";
import { getPnl, type Pnl } from "./api";
import { Figure, Grid, Loading, NOT_YET, Status, money, pct, plain, signed, word } from "./format";

// E2: what the last report said when it was issued, what we know now, and why the two differ. Read from k4_office through k10_note.
export default function PnlNav({ ccy }: { ccy: string }) {
  const [p, setP] = useState<Pnl | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setP(null); setError("");
    getPnl(ccy).then((r) => { if (live) setP(r); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [ccy]);
  if (error) return <p role="alert">{error}</p>;
  if (!p) return <Loading what="the P&L and NAV" />;
  const rep = p.issued.report, lines = p.issued.lines ?? [];
  const ordered = [...lines.filter((l) => l.label !== "Total"), ...lines.filter((l) => l.label === "Total")];
  const lb = p.liquid_book;
  return (
    <>
      <p className="ds-muted" style={{ letterSpacing: 1, fontSize: "0.8rem", margin: 0 }}>AS OF {day(p.as_of).toUpperCase()} · {p.currency}</p>
      <h2 style={{ margin: "4px 0" }}>Daily P&amp;L and NAV</h2>
      <p>What the last report said when it was issued, what we know now, and why the two differ. Every difference has a named cause.</p>
      <section aria-label="Issued against known now">
        <h3>{rep ? `${rep.name}: issued against known now` : "Issued against known now"}</h3>
        {!rep ? <p className="ds-muted">{p.issued.message ?? NOT_YET}</p> : (
          <>
            <p className="ds-muted">{rep.when}.</p>
            <DataTable columns={[{ key: "line", label: "Line" }, { key: "issued", label: `Issued ${day(rep.issued_at)}` }, { key: "now", label: "Known now" }, { key: "change", label: "Change" }, { key: "status", label: "Now" }]}
              rows={ordered.map((l) => ({
                line: l.label === "Total" ? <strong>Total</strong> : l.label, issued: money(l.issued), now: money(l.known_now),
                change: Number(l.difference) === 0 ? "0" : signed(l.difference), status: <Status s={word(l.status)} />,
              }))} />
            {p.other_total && p.rate ? (
              <p className="ds-muted">In {p.other_currency} at {p.rate.pair} {p.rate.rate.replace(/0+$/, "")} ({day(p.rate.date)} fixing): {money(p.other_total.issued)} issued, {money(p.other_total.known_now)} known now.</p>
            ) : null}
            {p.issued.banner ? <p>{p.issued.banner}</p> : null}
            {p.issued.brief_link ? <p><Link className="ds-link" to={p.issued.brief_link}>See the report versions</Link></p> : null}
          </>
        )}
      </section>
      <section aria-label="Liquid book P&L">
        <h3>Liquid book P&amp;L</h3>
        <Grid>
          <Figure label="Day" value="" unavailable={lb.day.message} />
          <Figure label={`Month · ${lb.month.label}`} value={signed(lb.month.change)} note={lb.month.available ? `${pct(lb.month.percent)} of the opening value` : lb.month.message} unavailable={lb.month.available ? null : lb.month.message ?? NOT_YET}
            where={lb.month.where} />
          <Figure label="Year to date" value={pct(lb.ytd.percent)} unavailable={lb.ytd.available ? null : lb.ytd.message} />
        </Grid>
        {lb.month.available && lb.month.movers.length ? <p className="ds-muted">{lb.month.label}: {lb.month.movers.map((m) => `${m.name} ${signed(m.amount)}`).join(" and ")} led.</p> : null}
      </section>
      <section aria-label="By portfolio">
        <h3>By portfolio: administrator against our view</h3>
        {p.bridge.length === 0 ? <p className="ds-muted">Nothing you can see has an administrator figure yet.</p> : (
          <DataTable columns={[{ key: "pf", label: "Portfolio" }, { key: "admin", label: "Administrator" }, { key: "ours", label: "Our view" }, { key: "diff", label: "Difference" }, { key: "why", label: "Why" }]}
            rows={[...p.bridge.map((b) => ({
              pf: <>{b.portfolio}<div className="ds-muted" style={{ fontSize: "0.85rem" }}>{b.entity}</div></>,
              admin: b.available ? money(b.administrator) : NOT_YET, ours: b.available ? money(b.ours) : NOT_YET,
              diff: b.available ? (Number(b.difference) === 0 ? "0" : signed(b.difference)) : NOT_YET, why: b.why,
            })), ...(p.bridge_total ? [{ pf: <strong>All {p.bridge.length} portfolios</strong>, admin: money(p.bridge_total.administrator), ours: money(p.bridge_total.ours), diff: signed(p.bridge_total.difference), why: "" }] : [])]} />
        )}
        {p.bridge.length ? <details><summary>Where is this from?</summary>{p.bridge.map((b) => <p key={b.trail_id} className="ds-muted" data-trail-id={b.trail_id}>{b.where?.text}</p>)}</details> : null}
      </section>
      <section aria-label="By entity">
        <h3>By entity</h3>
        {p.by_entity.length === 0 ? <p className="ds-muted">Nothing you can see is valued yet.</p> : (
          <ul style={{ listStyle: "none", padding: 0 }}>{p.by_entity.map((e) => <li key={e.trail_id} data-trail-id={e.trail_id}>{e.name} <strong>{money(e.value)}</strong></li>)}
            {p.total !== null && !p.partial ? <li><strong>Total {money(p.total)}</strong></li> : null}</ul>
        )}
        <Footnote>Includes funds outside the monthly report. Values still on an estimate or not confirmed carry their status word in the key numbers below.</Footnote>
      </section>
      <DailyNumbers />
    </>
  );
}
