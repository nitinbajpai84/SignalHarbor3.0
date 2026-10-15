import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DataTable, Footnote, PageFrame, day } from "../../design";
import AskLumen from "./AskLumen";
import { TagPill } from "./MorningNote";
import { getSignals, type IndexRow, type Period, type Signals } from "./api";
import { Loading, NOT_YET, Status, WhereLink, level, pct, plain, pts } from "./format";

// Markets: their trend next to ours. Outside figures are context for reading our numbers, never the source of them. Every outside line says where it came from,
// on what date, and whether it arrived as a FILE or from a LIVE API; all of that is read from the warehouse, none of it is written here.
const Num = ({ children }: { children: string }) => <span style={{ fontVariantNumeric: "tabular-nums" }}>{children}</span>;

function levelText(r: IndexRow): string {
  if (r.kind === "proxy") return "Calculated";
  if (!r.latest) return NOT_YET;
  return r.kind === "fx" ? Number(r.latest.level).toFixed(4) : level(r.latest.level);
}

function changeText(r: IndexRow, period: Period): string {
  const c = r.periods[period];
  if (r.kind === "yield" || r.kind === "macro") return c.change_abs ? `${pts(c.change_abs)} pts` : NOT_YET;
  return c.change_pct === null ? NOT_YET : pct(c.change_pct, true);
}

function Source({ r }: { r: IndexRow }) {
  if (r.kind === "placeholder") return <span className="ds-muted">{r.where.text}</span>;
  const p = r.provenance;
  if (!p) return <span className="ds-muted">Source not recorded</span>;
  return <><TagPill tag={p.tag} /> {p.label ?? "Source not recorded"}{p.date ? ` · ${day(p.date)}` : ""}</>;
}

export default function MarketSignals({ ccy, period }: { ccy: string; period: Period }) {
  const [s, setS] = useState<Signals | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setS(null); setError("");
    getSignals(ccy, period).then((r) => { if (live) setS(r); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [ccy, period]);
  const frame = { title: "Markets: their trend next to ours", subline: "Outside figures are context for reading our numbers, never the source of them. Every line says where it came from and when." };
  if (error) return <PageFrame title={frame.title}><p role="alert">{error}</p></PageFrame>;
  if (!s) return <PageFrame title={frame.title}><Loading what="the markets" /></PageFrame>;
  const monthName = new Date(s.period_end).toLocaleString("en-GB", { month: "long", timeZone: "UTC" });
  const heading = period === "month" ? monthName : period === "ytd" ? "year to date" : "since inception";
  const watch = s.news.length + s.headlines.length;
  return (
    <PageFrame {...frame}>
      <section aria-label="The market">
        <h2 style={{ fontSize: 17 }}>The market</h2>
        <DataTable columns={[{ key: "m", label: "Series" }, { key: "lv", label: "Level" }, { key: "ch", label: "Change" }, { key: "src", label: "Source" }]}
          rows={s.indexes.map((r) => ({
            m: <>{r.name}<div><WhereLink label={r.name} where={r.where} id={r.trail_id} /></div></>, lv: <Num>{levelText(r)}</Num>, ch: <Num>{changeText(r, period)}</Num>, src: <Source r={r} />,
          }))} />
      </section>
      <section aria-label="Our portfolios against their benchmarks">
        <h2 style={{ fontSize: 17 }}>Ours against it, {heading}</h2>
        {s.portfolios.length === 0 ? <p className="ds-muted">Nothing you can see has a return to compare yet.</p> : (
          <DataTable columns={[{ key: "p", label: "Portfolio" }, { key: "w", label: "Compared with" }, { key: "r", label: "Ours" }, { key: "b", label: "Theirs" }, { key: "a", label: "Ahead, pts" }]}
            rows={s.portfolios.map((r) => ({
              p: <>{r.portfolio}{r.status ? <div><Status s={r.status} /></div> : null}<div><WhereLink label={`${r.portfolio} against ${r.benchmark_label}`} where={r.where} id={r.trail_id} /></div></>,
              w: r.benchmark_label ?? NOT_YET, r: <Num>{pct(r.return_pct)}</Num>, b: <Num>{pct(r.benchmark_pct)}</Num>, a: <Num>{pts(r.ahead_pts)}</Num>,
            }))} />
        )}
        {s.read ? <p style={{ margin: "8px 0 0" }}>{s.read} <span className="ds-muted">Worked out from the figures above.</span></p> : null}
        {s.benchmark_note ? <Footnote>{s.benchmark_note}</Footnote> : null}
      </section>
      <section aria-label="To watch" style={{ display: "grid", gap: 10 }}>
        <h2 style={{ fontSize: 17, margin: "16px 0 0" }}>To watch</h2>
        <p className="ds-muted" style={{ margin: 0 }}>From managers' own letters and questionnaires, and from news headlines. Shown as written; no judgement.</p>
        {watch === 0 ? <p className="ds-muted">No manager letters have been added to the library yet, and no news API is connected.</p> : null}
        {s.news.map((n) => (
          <article key={n.trail_id} className="ds-card" style={{ padding: "14px 16px" }} data-trail-id={n.trail_id}>
            <div className="ds-muted" style={{ fontSize: 12, letterSpacing: 0.4 }}><TagPill tag="FILE" /> {n.source.toUpperCase()} · {n.manager.toUpperCase()} · {day(n.date).toUpperCase()}</div>
            <div style={{ fontWeight: 600, marginTop: 6 }}>{n.text ?? "You do not have access to read this."}</div>
            <Link className="ds-link" to={n.href}>Open the library</Link>
          </article>
        ))}
        {s.headlines.map((h) => (
          <article key={h.trail_id} className="ds-card" style={{ padding: "14px 16px" }} data-trail-id={h.trail_id}>
            <div className="ds-muted" style={{ fontSize: 12, letterSpacing: 0.4 }}><TagPill tag={h.tag} /> {h.source.toUpperCase()}{h.date ? ` · ${day(h.date).toUpperCase()}` : ""}</div>
            <div style={{ fontWeight: 600, marginTop: 6 }}>{h.title}</div>
          </article>
        ))}
      </section>
      <section aria-label="Outside data and insights">
        <nav aria-label="Outside data and insights" style={{ display: "flex", gap: 16, flexWrap: "wrap", margin: "16px 0" }}>
          <Link className="ds-link" to="/centre/consume/views">Business views, feeds, market, what-if</Link>
          <Link className="ds-link" to="/centre/consume/offers">Offers</Link>
        </nav>
      </section>
      <AskLumen />
    </PageFrame>
  );
}
