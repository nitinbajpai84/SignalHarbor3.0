import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { DataTable, PageFrame, day } from "../../design";
import Comments from "../n2/Comments";
import AskLumen from "./AskLumen";
import { getSections, getToday, type Tag, type Tile, type Today } from "./api";
import { Figure, Grid, Loading, Status, compact, money, plain, pts, signed } from "./format";

// Today: the Morning Note. One sentence, four key numbers, what moved, the markets in a line. The detail lives on Financial health and Markets.
// Everything arrives worded and worked out by the server from the company's own records; a figure that cannot be worked out says so.
function tileValue(t: Tile): string {
  if (!t.available || t.value === null) return "";
  return t.kind === "points" ? `${pts(t.value)} pts` : t.kind === "change" ? signed(t.value) : compact(t.value);
}

export const TagPill = ({ tag }: { tag: Tag | null | undefined }) => tag
  ? <span style={{ font: "500 11px var(--ds-mono, monospace)", border: `1px solid ${tag === "LIVE API" ? "var(--ds-teal-bright)" : "var(--ds-ink-muted)"}`, borderRadius: 999, padding: "2px 8px",
    color: tag === "LIVE API" ? "var(--ds-teal-bright)" : "var(--ds-ink-soft)", whiteSpace: "nowrap" }}>{tag}</span> : null;

export default function MorningNote({ ccy }: { ccy: string }) {
  const [n, setN] = useState<Today | null>(null);
  const [error, setError] = useState("");
  const [sections, setSections] = useState<{ title: string; lines: string[] }[]>([]);
  useEffect(() => { void getSections().then(setSections); }, []);
  useEffect(() => {
    let live = true;
    setN(null); setError("");
    getToday(ccy).then((r) => { if (live) setN(r); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [ccy]);
  if (error) return <PageFrame title="Today"><p role="alert">{error}</p></PageFrame>;
  if (!n) return <PageFrame title="Today"><Loading what="the Morning Note" /></PageFrame>;
  const rows = n.moved.map((m, i) => ({
    what: <><strong>{m.label}</strong><div className="ds-muted" style={{ fontSize: "0.85rem" }} data-trail-id={m.trail_id}>{m.detail}</div></>,
    amount: m.amount === null ? "–" : <span className={m.unconfirmed ? "ds-muted" : undefined}>{m.unconfirmed ? money(m.amount) : signed(m.amount)}</span>, status: <Status s={m.status} />, key: i,
  }));
  return (
    <PageFrame crumbs={<>MORNING NOTE · {n.dateline.toUpperCase()}</>} title={n.headline} subline={n.built + " Every figure opens to its source."}>
      <section aria-label="Key figures"><Grid>
        {n.tiles.map((t) => (
          <Figure key={t.key} label={t.label} value={tileValue(t)} note={t.note} status={t.status} where={t.where} id={t.trail_id} unavailable={t.available ? null : t.note ?? "Not available yet"} />
        ))}
      </Grid></section>
      <section aria-label="What moved" style={{ marginTop: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: "0 0 8px", fontSize: 18 }}>What moved</h2>
          <Link className="ds-link" to="/centre/consume/health">See every portfolio and fund</Link>
        </div>
        {rows.length ? <DataTable columns={[{ key: "what", label: "What happened" }, { key: "amount", label: n.currency }, { key: "status", label: "Value is" }]} rows={rows} />
          : <p className="ds-muted">Nothing has moved since the last report.</p>}
      </section>
      {sections.map((x) => (
        <section key={x.title} aria-label={x.title}>
          <h3>{x.title}</h3>
          <ul>{x.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
        </section>
      ))}
      <section aria-label="Markets in one line" className="ds-card" style={{ padding: "14px 18px", marginTop: 18, display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>Markets in one line</h2>
          {n.markets ? (
            <p style={{ margin: 0 }}>{n.markets.text}{" "}
              <span className="ds-muted">Source: {n.markets.sources.map((s, i) => <span key={i}>{i ? "; " : ""}{s.label ?? "source not recorded"}{s.date ? `, ${day(s.date)}` : ""} <TagPill tag={s.tag} /></span>)}.</span></p>
          ) : <p className="ds-muted" style={{ margin: 0 }}>Not available yet.</p>}
        </div>
        <Link className="ds-link" to="/centre/consume/markets">Open Markets</Link>
      </section>
      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", marginTop: 18, alignItems: "start" }}>
        <section aria-label="Comments on today's note">
          <h3 style={{ marginTop: 0 }}>Comments on today's note</h3>
          <Comments target={n.comment_target} />
        </section>
        <AskLumen title="Ask Lumen about this note" />
      </div>
      <p className="ds-footnote">This note also arrives by email and in Slack. <Link className="ds-link" to="/centre/operations#deliveries">See the deliveries</Link>. Market figures are outside material.</p>
    </PageFrame>
  );
}
