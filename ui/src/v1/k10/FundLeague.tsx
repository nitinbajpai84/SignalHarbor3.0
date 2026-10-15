import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Chip, DataTable, Footnote, SideCard, StatCard, StatGrid, day } from "../../design";
import { getLeague, type League } from "./api";
import { Loading, NOT_YET, Status, WhereLink, money, pct, plain, pts } from "./format";

// E4: each fund against the index that fits it, how far ahead or behind it is, and how much we trust its latest value.
export default function FundLeague({ embedded = false }: { embedded?: boolean }) {
  const [rank, setRank] = useState<"alpha" | "value">("alpha");
  const [l, setL] = useState<League | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setL(null); setError("");
    getLeague(rank).then((r) => { if (live) setL(r); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [rank]);
  if (error) return <p role="alert">{error}</p>;
  if (!l) return <Loading what="the fund league" />;
  const s = l.summary;
  const month = new Date(l.period_end).toLocaleString("en-GB", { month: "long", timeZone: "UTC" });
  return (
    <>
      {embedded ? <p className="ds-muted" style={{ margin: 0 }}>Ahead of their index: {s.ahead === null ? `${NOT_YET}${s.ahead_note ? ` (${s.ahead_note.toLowerCase()})` : ""}` : s.ahead}.</p> : (
      <>
      <p className="ds-muted" style={{ letterSpacing: 1, fontSize: "0.8rem", margin: 0 }}>{month.toUpperCase()} · {s.total} FUNDS · {l.managers} MANAGERS</p>
      <h2 style={{ margin: "4px 0" }}>Fund performance league</h2>
      <p>Each fund against the index that fits it, with how far ahead or behind it is and how much we trust its latest value. A fund on an estimate or an old statement is ranked, but flagged.</p>
      <StatGrid cols={4}>
        <StatCard label="Funds on official values" value={`${s.official} of ${s.total}`} note={s.revised ? `Plus ${s.revised} revised to final` : undefined} />
        <StatCard label="On estimates" value={String(s.estimated)} />
        <StatCard label="Old or unconfirmed" value={String(s.old)} tone="warn" />
        <StatCard label="Ahead of their index" value={s.ahead === null ? NOT_YET : String(s.ahead)} note={s.ahead_note ?? undefined} />
      </StatGrid>
      </>)}
      <div role="group" aria-label="Rank by" style={{ display: "flex", gap: 8, alignItems: "center", margin: "12px 0" }}>
        <span className="ds-muted">Rank by</span>
        <Chip tone={rank === "alpha" ? "active" : "default"} onClick={() => setRank("alpha")}>Alpha, {month}</Chip>
        <Chip tone={rank === "value" ? "active" : "default"} onClick={() => setRank("value")}>Value</Chip>
      </div>
      <DataTable columns={[{ key: "n", label: "#" }, { key: "f", label: "Fund and manager" }, { key: "v", label: "Value" }, { key: "c", label: "Compared with" }, { key: "fr", label: "Fund" }, { key: "ix", label: "Index" },
        { key: "al", label: "Alpha, pts" }, { key: "st", label: "Statement" }]}
        rows={l.funds.map((f) => ({
          n: f.rank, f: <><strong>{f.fund}</strong><div className="ds-muted" style={{ fontSize: "0.85rem" }}>{f.manager}</div><WhereLink label={f.fund} where={f.where} id={f.trail_id} /></>,
          v: f.value === null ? NOT_YET : `${f.currency ?? ""} ${money(f.value)}`.trim(), c: f.compared_with ?? NOT_YET, fr: f.fund_return === null ? NOT_YET : pct(f.fund_return),
          ix: pct(f.index_return, true), al: f.alpha === null ? NOT_YET : pts(f.alpha),
          st: <><Status s={f.status} /><div className="ds-muted" style={{ fontSize: "0.85rem" }}>{f.note}</div></>,
        }))} />
      <Footnote>{l.note} Values are as at {day(l.as_of)}.</Footnote>
      {l.worst ? <SideCard title={l.worst.fund} tone="amber" action={{ label: "See the follow-up in Action", href: l.worst.href }}><p>{l.worst.text}</p></SideCard> : null}
      <p><Link className="ds-link" to="/centre/consume/markets">Read the manager news</Link> · <Link className="ds-link" to="/centre/consume/reports">Open the reports</Link></p>
    </>
  );
}
