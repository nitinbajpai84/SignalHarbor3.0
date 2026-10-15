import { useEffect, useState, type ComponentType } from "react";

import { Pill } from "../../design";
import Chart from "./Chart";
import { tileData, type TileData, type Tile } from "./api";

// UX-22: the trail opens from a small text link here, not a full button. Same panel as a5/TrailHost.
const found = import.meta.glob<{ default: ComponentType<{ kind: string; id: string; onClose: () => void }> }>("../a5trail/TrailPanel.tsx", { eager: true });
const Panel = Object.values(found)[0]?.default;

const when = (at: string | null) => {
  const d = at ? new Date(at) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "not refreshed yet";
};

// a10.9: business users see plain words, never table or column names: axis titles from the field names, and a note that names a table is not shown.
const plain = (f: string) => f.replace(/_/g, " ").replace(/\b(usd|sgd|eur|gbp|hkd)\b/gi, (m) => m.toUpperCase()).replace(/^./, (c) => c.toUpperCase());
const TECH = /\b(gold|silver|bronze)_\w+/;

export function titled(d: TileData): TileData {
  const enc = (d.spec.encoding ?? {}) as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(enc)) {
    const ch = v as { field?: unknown; title?: unknown } | null;
    out[k] = ch && typeof ch.field === "string" && ch.title === undefined ? { ...ch, title: plain(ch.field) } : v;
  }
  return { ...d, spec: { ...d.spec, encoding: out } };
}

/** One tile: the chart, its status word, and (when the person may decide) Accept / Not this and Why did this move. */
export default function TileCard({ pid, did, tile, onDecide, onWhy, load, inGrid = false }: {
  pid: string; did: string; tile: Tile; onDecide?: (how: "accept" | "reject") => void; onWhy?: () => void;
  /** DS1: where the numbers come from when it is not the Consume route (the studio preview); `inGrid`: a widget on the studio or Consume grid (no status word, no outer margin). */
  load?: () => Promise<TileData>; inGrid?: boolean;
}) {
  const [data, setData] = useState<TileData | null>(null);
  const [error, setError] = useState(false);
  const [trail, setTrail] = useState(false);
  useEffect(() => {
    let live = true;
    (load ? load() : tileData(pid, did, tile.id)).then((d) => { if (live) setData(d); }, () => { if (live) setError(true); });
    return () => { live = false; };
  }, [pid, did, tile.id]); // `load` is new on every render: the tile id says when to read again
  return (
    <article className="ds-card" aria-label={tile.title} style={{ padding: 12, marginBottom: inGrid ? 0 : 12, height: inGrid ? "100%" : undefined, ...(inGrid ? { display: "flex", flexDirection: "column", minHeight: 0, boxSizing: "border-box" } : {}) }}>
      <header style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between" }}>
        <strong>{tile.title}</strong>
        {inGrid ? null : <Pill tone={tile.state === "accepted" ? "signed" : "draft"}>{tile.state === "accepted" ? "Accepted" : "Proposed"}</Pill>}
      </header>
      {tile.note && !TECH.test(tile.note) ? <p className="ds-muted" style={{ margin: "4px 0" }}>{tile.note}</p> : null}
      {error ? <p role="alert">This tile&apos;s numbers could not be loaded. Please try again.</p>
        : data ? <Chart data={titled(data)} label={tile.title} fill={inGrid} /> : <p className="ds-muted">Loading the numbers…</p>}
      {data ? <p className="ds-muted" style={{ margin: "4px 0" }}>Last refreshed {when(data.data_used.last_refresh)}.</p> : null}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span>
          <button type="button" className="ds-link" style={{ background: "none", border: 0, padding: 0, cursor: "pointer", font: "inherit", fontSize: 13 }} aria-expanded={trail} onClick={() => setTrail(!trail)}>Where is this from? ↗</button>
          {trail ? (Panel ? <Panel kind="tile" id={tile.id} onClose={() => setTrail(false)} /> : <p className="ds-muted" role="status">The trail for this is not available yet.</p>) : null}
        </span>
        {tile.state === "proposed" && onDecide ? <>
          <button type="button" className="ds-btn" onClick={() => onDecide("accept")}>Accept</button>
          <button type="button" className="ds-btn" onClick={() => onDecide("reject")}>Not this</button>
        </> : null}
        {tile.state === "accepted" && onWhy ? <button type="button" className="ds-btn" onClick={onWhy}>Why did this move</button> : null}
      </div>
    </article>
  );
}
