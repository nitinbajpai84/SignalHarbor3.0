import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { Button, Chip, EmptyState, Footnote, PageFrame, Pill, SideCard, Strip } from "../design";
import { apiGet } from "../api/client";
import { FeedCard } from "./FeedsPage";
import { LENS_ASKS, LENS_NAMES, VIEW_NOTE, wire, type LensDetail } from "./consumeLens";

// Business view page (spec 60 Screen B): market, our data, what we are building, what to consider next. It adds no figure.

const NA = "Not available yet";

/** "My line of work" / "Everything" (spec 60 Screens A and B). Disabled with a hint when the viewer has no line of work. */
export function LineOfWork({ mine, set, none }: { mine: boolean; set: (m: boolean) => void; none?: boolean }) {
  return (
    <>
      {none ? <span className="ds-chip" aria-disabled="true" title="No area or measure is linked to you yet">My line of work</span>
        : <Chip tone={mine ? "active" : "default"} onClick={() => set(true)}>My line of work</Chip>}
      <Chip tone={mine ? "default" : "active"} onClick={() => set(false)}>Everything</Chip>
    </>
  );
}

/** Three items, then "Show all (n)". */
function Strip3<T>({ label, items, empty, row }: { label: string; items: T[]; empty: string; row: (t: T) => ReactNode }) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, 3);
  return (
    <Strip label={label}>
      {items.length === 0 ? <p className="ds-muted">{empty}</p> : shown.map((t, i) => <div key={i}>{row(t)}</div>)}
      {items.length > 3 && !all ? <span><Button onClick={() => setAll(true)}>{`Show all (${items.length})`}</Button></span> : null}
    </Strip>
  );
}

export default function LensPage() {
  const { lens = "" } = useParams();
  const key = wire(lens);
  const [mine, setMine] = useState(false);
  const [state, setState] = useState<"loading" | "error" | "ready">("loading");
  const [d, setD] = useState<LensDetail | null>(null);
  const [n, setN] = useState(0);
  const retry = useCallback(() => { setState("loading"); setN((x) => x + 1); }, []);

  useEffect(() => {
    let live = true;
    apiGet<LensDetail>(`/api/company/consume/lenses/${encodeURIComponent(lens)}${mine ? "?mine=1" : ""}`)
      .then((x) => { if (live) { setD(x); setState("ready"); } }).catch(() => { if (live) setState("error"); });
    return () => { live = false; };
  }, [key, mine, n]);

  const name = LENS_NAMES[key] ?? d?.name ?? lens;
  const crumbs = <><Link to="/centre/consume">Consume centre</Link> / {name}</>;
  if (state !== "ready" || !d) {
    return (
      <div className="ds-screen">
        <PageFrame crumbs={crumbs} title={name}>
          {state === "loading" ? <p role="status" className="ds-muted">Reading this business view.</p>
            : <div role="alert"><EmptyState title="This business view could not be loaded" lines={["Please try again."]} /><Button onClick={retry}>Try again</Button></div>}
        </PageFrame>
      </div>
    );
  }

  const feeds = d.feeds ?? [], rows = d.measure_rows ?? [];
  return (
    <div className="ds-screen">
      <PageFrame
        crumbs={crumbs}
        title={`${name}: ${(d.question ?? LENS_ASKS[key] ?? "").replace(/\?$/, "")}`}
        subline={VIEW_NOTE}
        actions={<LineOfWork mine={mine} set={setMine} />}
        aside={<>
          <SideCard title="Measures in this view">
            {rows.length ? rows.map((r) => (
              <p key={r.code}><Link to={`/centre/consume/feeds/${encodeURIComponent(r.code)}`}>{r.name}</Link>{" "}
                <Pill tone="draft">{r.mark === "stated" ? `Confirmed by ${r.confirmed_by ?? "its owner"}` : "Lens draft"}</Pill></p>
            )) : <p>No measure assigned yet. Lens drafts the list once a baseline exists.</p>}
          </SideCard>
          <SideCard title="How this view is drawn">
            <p>Measures come from the view list. Briefs are outside material. Initiatives and opportunities carry their own view.</p>
          </SideCard>
        </>}
      >
        <Strip3 label="What the market is doing" items={d.briefs ?? []} empty="No outside material touches this view yet."
          row={(b) => (
            <SideCard title={b.title}>
              <div><Pill tone="open">Outside material</Pill></div>
              <p>{b.summary}</p>
              <div>{(b.measure_moves ?? []).map((m) => <Chip key={m.code} href={`/centre/consume/feeds/${encodeURIComponent(m.code)}`}>{m.name}</Chip>)}</div>
              <Footnote>Source: {b.source}</Footnote>
            </SideCard>
          )} />
        <p><Link to="/centre/consume/market">All briefs</Link></p>

        <Strip label="What our data says">
          {feeds.length === 0 ? <p className="ds-muted">{d.empty ?? `No measure in this view has a value yet. ${NA}: no gold table holds one.`}</p> : <>
            {d.outside_line ? <p>{d.outside_line}</p> : null}
            {feeds.slice(0, 6).map((f) => <FeedCard key={f.code} f={f} />)}
          </>}
        </Strip>

        <Strip3 label="What we are building" items={d.building ?? []} empty="Nothing is being built for this view."
          row={(b) => (
            <p>{b.href ? <Link to={b.href}>{b.title}</Link> : b.title}{" "}
              <Pill tone="open">{b.stage ?? "In Build"}</Pill>{" "}
              <Pill tone="draft">{b.verdict ?? "No report yet"}</Pill>
              {b.organiser ? <span className="ds-muted"> Organiser: {b.organiser}</span> : null}
              {b.measure ? <span className="ds-muted"> Aims to move {b.measure}</span> : null}</p>
          )} />

        <Strip3 label="What we should consider next" items={d.consider ?? []} empty="Nothing suggested for this view yet."
          row={(o) => (
            <p><Link to={o.href ?? `/centre/intent/backlog?opportunity=${encodeURIComponent(o.id)}`}>{o.title}</Link>{" "}
              {o.state ? <Pill tone="draft">{o.state.replace(/_/g, " ")}</Pill> : null}
              {o.line ? <span className="ds-muted"> {o.line}</span> : null}</p>
          )} />
        <p><Link to={`/centre/consume/what-if?lens=${encodeURIComponent(lens)}`}>Try a what-if</Link></p>
      </PageFrame>
    </div>
  );
}
