import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button, Chip, EmptyState, Footnote, PageFrame, Pill, Sparkline, StatGrid } from "../design";
import { apiGet } from "../api/client";

// Feeds (SHAPES section 6): a card per governed measure with its latest gold value, a sparkline, the owner and a range warning.

export interface Point { period: string; value: number }
export interface Feed {
  code: string; name: string; owner: string | null; latest: Point | null; trend: Point[]; range_break: boolean; may_see: boolean;
  mine?: boolean; governed?: boolean; restricted?: string | null;
}

const NA = "Not available yet";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"];
/** "2026-09" is "Sept 2026"; a full date or timestamp is "1 Sept 2026"; anything else passes through. */
export const day = (p: string) => {
  const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(p);
  return m && Number(m[2]) >= 1 && Number(m[2]) <= 12 ? `${m[3] ? `${Number(m[3])} ` : ""}${MONTHS[Number(m[2]) - 1]} ${m[1]}` : p;
};


/** Governed measures first, then the marts not governed yet (`governed: false`); the route's order is kept within each group. */
export const sortFeeds = (fs: Feed[]): Feed[] => [...fs].sort((a, b) => Number(a.governed === false) - Number(b.governed === false));

export function FeedCard({ f }: { f: Feed }) {
  const warn = f.may_see && f.range_break;
  return (
    <Link to={`/centre/consume/feeds/${encodeURIComponent(f.code)}`} className="ds-card ds-stat">
      <span className="ds-stat__label">{f.code !== f.name ? `${f.code} · ` : ""}<span>{f.name}</span></span>
      {!f.may_see ? <span className="ds-stat__value ds-stat__value--text ds-muted">{f.restricted ?? `Restricted: ask ${f.owner ?? "the owner"}`}</span>
        : f.latest === null ? <span className="ds-stat__value ds-stat__value--text ds-muted">{NA}</span>
        : <>
            <strong className={`ds-stat__value${warn ? " ds-stat__value--warn" : ""}`}>{f.latest.value.toLocaleString()}</strong>
            <span className="ds-stat__note ds-stat__note--muted">{day(f.latest.period)}</span>
            {f.trend.length > 1 ? <Sparkline points={f.trend.map((t) => t.value)} /> : null}
            {warn ? <span className="ds-stat__note ds-stat__note--warn">Outside its usual range</span> : null}
          </>}
      {f.owner ? <span className="ds-stat__note">Owner: {f.owner}</span> : null}
      {f.governed === false ? <span><Pill tone="draft">Not governed yet</Pill></span> : null}
    </Link>
  );
}

export default function FeedsPage() {
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [feeds, setFeeds] = useState<Feed[]>([]);
  const [mine, setMine] = useState(false);
  const [n, setN] = useState(0);
  const retry = useCallback(() => { setState("loading"); setN((x) => x + 1); }, []);

  useEffect(() => {
    let live = true;
    apiGet<{ measures: Feed[] }>("/api/company/feeds")
      .then((d) => { if (live) { setFeeds(sortFeeds(d.measures)); setState("ready"); } })
      .catch(() => { if (live) setState("error"); });
    return () => { live = false; };
  }, [n]);

  const shown = mine ? feeds.filter((f) => f.mine) : feeds;
  const outside = feeds.filter((f) => f.may_see && f.range_break);
  const subline = state === "ready" && feeds.length
    ? <>{feeds.length} measures · {outside.length
      ? <span className="ds-warn">{outside.map((f) => f.code).join(", ")} outside {outside.length === 1 ? "its" : "their"} usual range</span>
      : "all inside the usual range"}</>
    : "The governed measures with their latest values.";
  return (
    <div className="ds-screen">
      <PageFrame
        crumbs={<Link to="/centre/consume">Consume centre</Link>}
        title="Feeds"
        subline={subline}
        actions={<div role="group" aria-label="Filter" className="ds-frame__actions">
          <Chip tone={mine ? "active" : "default"} onClick={() => setMine(true)}>Mine</Chip>
          <Chip tone={mine ? "default" : "active"} onClick={() => setMine(false)}>All</Chip>
        </div>}
      >
        {state === "loading" ? <p role="status" className="ds-muted">Reading the governed measures.</p>
          : state === "error" ? <div role="alert"><EmptyState title="Feeds could not be loaded" lines={["Please try again."]} /><Button onClick={retry}>Try again</Button></div>
          : feeds.length === 0 ? <EmptyState title="No measures are governed yet" lines={["A measure appears here once its definition is signed and its pipeline has run."]} links={[{ label: "Open the map", href: "/centre/map" }]} />
          : shown.length === 0 ? <EmptyState title="None of these measures are yours" lines={["Choose All to see every measure you may read."]} />
          : <section aria-label="Feeds"><StatGrid>{shown.map((f) => <FeedCard key={f.code} f={f} />)}</StatGrid></section>}
        <Footnote>Values reach only the people on each measure's access list; everyone else sees who to ask.</Footnote>
      </PageFrame>
    </div>
  );
}
