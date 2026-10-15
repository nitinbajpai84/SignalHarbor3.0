import { useEffect, useState } from "react";

import { Chip, Footnote, PageFrame, RoomTile } from "../design";
import { apiGet } from "../api/client";
import type { Feed } from "./FeedsPage";
import { LENS_ASKS, LENS_NAMES, VIEW_NOTE, slug, type LensList } from "./consumeLens";
import { LineOfWork } from "./LensPage";

// Consume centre home (Consume preview artboard): three rooms, each lit when it has data.

const NA = "Not available yet";

export default function ConsumeCentre() {
  const [feeds, setFeeds] = useState<Feed[] | null>(null);
  const [briefs, setBriefs] = useState<number | null>(null);
  const [kept, setKept] = useState<number | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<{ measures: Feed[] }>("/api/company/feeds").then((d) => { if (live) setFeeds(d.measures); }).catch(() => undefined);
    apiGet<{ briefs: unknown[] }>("/api/company/market").then((d) => { if (live) setBriefs(d.briefs.length); }).catch(() => undefined);
    apiGet<{ scenarios: unknown[] }>("/api/company/whatif/scenarios").then((d) => { if (live) setKept(d.scenarios.length); }).catch(() => undefined);
    return () => { live = false; };
  }, []);

  const [mine, setMine] = useState(false);
  const [lenses, setLenses] = useState<LensList | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<LensList>(`/api/company/consume/lenses${mine ? "?mine=1" : ""}`).then((d) => { if (live) setLenses(d); }).catch(() => { if (live) setLenses({ lenses: [] }); });
    return () => { live = false; };
  }, [mine]);
  const views = Object.keys(LENS_NAMES).map((key) => {
    const l = lenses?.lenses.find((x) => x.key === key), c = l?.counts, plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
    const counts: (string | { text: string; tone: "amber" })[] = !c || !c.measures ? [] : [plural(c.measures, "measure"), ...(c.outside ? [{ text: `${c.outside} outside their usual range`, tone: "amber" as const }] : []),
      plural(c.briefs ?? 0, "brief"), `${c.building ?? 0} building`, `${c.proving ?? 0} proving`, `${c.consider ?? 0} to consider`];
    return { key, counts };
  });

  const valued = feeds?.filter((m) => m.latest).length ?? 0;
  const outside = (feeds ?? []).filter((m) => m.may_see && m.range_break).map((m) => ({ text: `${m.code} outside its usual range`, tone: "amber" as const }));
  const rooms = [
    { to: "/centre/consume/market", name: "Market forces", line: "Outside signals set against your own measures, shown as context, never as your figure. Starts from the Watch lane.",
      counts: briefs ? [`${briefs} ${briefs === 1 ? "brief" : "briefs"}`] : [] },
    { to: "/centre/consume/what-if", name: "What-if", line: "Move a lever from the Levers lane and see the measure move. Every assumption is shown and can be changed.",
      counts: valued || kept ? [`${valued} measures to move`, `${kept ?? 0} ${kept === 1 ? "scenario" : "scenarios"} kept`] : [] },
    { to: "/centre/consume/feeds", name: "Feeds", line: "The right number to the right person, in plain words. Restricted measures reach only their list.",
      counts: valued ? [`${valued} with a value`, ...outside] : [] },
  ];
  return (
    <div className="ds-screen">
      <PageFrame
        crumbs="Consume centre"
        title="Use the numbers to look ahead."
        subline="The questions here are not new. They come from the wall's Watch and Levers lanes and from the pains people named in their interviews. Nobody is asked again."
        actions={<><Chip>from: live measures, the wall</Chip><Chip>to: what is likely next</Chip></>}
      >
        {/* ponytail: inline auto-fit grid so the rooms stack to one column at 390 (StatGrid keeps two there) */}
        <h2>Business views</h2>
        <div><LineOfWork mine={mine} set={setMine} none={lenses?.has_line_of_work === false} /></div>
        <section aria-label="Business views" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
          {views.map((v, i) => (
            <RoomTile key={v.key} number={i + 1} name={LENS_NAMES[v.key]!} state={v.counts.length ? "open" : "dim"} line={LENS_ASKS[v.key]!}
              counts={v.counts.length ? v.counts : [`${NA}: no measure assigned to this view`]} action={{ label: `Open ${LENS_NAMES[v.key]}`, href: `/centre/consume/lens/${slug(v.key)}` }} />
          ))}
        </section>
        <Footnote>{VIEW_NOTE}</Footnote>
        <h2>Tools</h2>
        <section aria-label="Tools" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
          {rooms.map((r, i) => (
            <RoomTile key={r.name} number={i + 1} name={r.name} state={r.counts.length ? "open" : "dim"} line={r.line}
              counts={r.counts.length ? r.counts : [NA]} action={{ label: `Open ${r.name}`, href: r.to }} />
          ))}
        </section>
        <Footnote>Every figure is read from the company's own measures. Anything from outside is labelled as such; it can sit next to a measure, never become one.</Footnote>
      </PageFrame>
    </div>
  );
}
