import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { apiGet, Refused } from "../api/client";
import {
  BuildIcon, Button, Chip, ConsumeIcon, EmptyState, Footnote, IntentIcon, MapColumns, MapIcon, PageFrame, PhoneTabBar, PulseIcon, SideCard,
  type MapColumn, type MapEdge, type MapNode, type TabItem,
} from "../design";
import { shellText } from "../shell/copy";
import { centresFor } from "../shell/roles";
import { useSession } from "../useSession";
import { graphText as t } from "./graphCopy";
import { kmText as K } from "./knowledgeMapCopy";
import { GROUPS, LINEAGE_TYPES, LIVES, groupOf, lineageIds, useOverview, whereRows, type Check, type Overview } from "./knowledgeMap";

// How my organisation connects (Desk-Graph, Phone-Graph): GET /api/company/graph, the viewer's gated map, names and links only.
// The route serves the five columns, what each wall produced, the holes and what is new; trace and filters are worked out here.

interface GNode { id: string; type: string; label: string; restricted?: boolean }
interface GEdge { from: string; to: string; type: string }
interface WallRow { wall: string; problems: string[]; measures: string[] }
export interface GraphDoc {
  nodes: GNode[]; edges: GEdge[];
  columns: { walls: { id: string; label: string }[]; problems: string[]; measures: string[]; systems: string[]; owners: string[] };
  by_wall: WallRow[]; new_this_week: string[]; new_detail?: Record<string, { what: string; by: string; at: string }[]>; holes: string[];
  summary: { things: number; links: number; walls: number; charters: number; baselines: number };
}
type View = "whole" | "wall" | "trace" | "holes" | "fresh" | "lineage";
type ColKey = keyof GraphDoc["columns"];
const COLS: ColKey[] = ["walls", "problems", "measures", "systems", "owners"];
const FRESH_MAX = 8;
const PHONE = "(max-width: 480px)";
const TAB_ICON = { pulse: PulseIcon, intent: IntentIcon, build: BuildIcon, consume: ConsumeIcon, map: MapIcon } as const;
type TabId = keyof typeof TAB_ICON;

function usePhone(): boolean {
  const [phone, setPhone] = useState(() => { try { return window.matchMedia(PHONE).matches; } catch { return false; } });
  useEffect(() => {
    try {
      const mq = window.matchMedia(PHONE);
      const on = () => setPhone(mq.matches);
      mq.addEventListener("change", on);
      return () => mq.removeEventListener("change", on);
    } catch { return undefined; } // no matchMedia: the desktop layout
  }, []);
  return phone;
}

/** Every node and line of the map, with the wall-to-problem lines from by_wall. */
/** The scan result as words, in the card's own label so it never rests on colour alone. */
function tagOf(c: Check | undefined): string {
  if (!c) return "";
  if (c.result === "found_elsewhere") return K.tag.found(c.found_in?.label ?? null) + (c.confirmed_by ? K.tag.confirmed(c.confirmed_by) : "");
  return c.result === "available" ? K.tag.Available : K.tag.Missing;
}

function model(doc: GraphDoc, checks: Record<string, Check> = {}) {
  const nodes = new Map<string, MapNode>(doc.nodes.map((n) => [n.id, { id: n.id, label: n.restricted || !checks[n.id] ? n.label : `${n.label} · ${tagOf(checks[n.id])}`, kind: n.type, restricted: n.restricted }]));
  doc.columns.walls.forEach((w) => nodes.set(w.id, { id: w.id, label: w.label, kind: "wall" }));
  const all: MapEdge[] = [...doc.edges.map((e) => ({ from: e.from, to: e.to })), ...doc.by_wall.flatMap((b) => b.problems.map((p) => ({ from: b.wall, to: p })))];
  const edges = [...new Map(all.map((e) => [`${e.from}>${e.to}`, e])).values()]; // one line per pair: the drawing keys lines by their ends
  return { nodes, edges };
}

/** Everything reachable from the seeds along the lines, downstream (from -> to) or upstream. */
function reach(seeds: string[], edges: MapEdge[], down: boolean): Set<string> {
  const seen = new Set(seeds), todo = [...seeds];
  while (todo.length) {
    const cur = todo.pop()!;
    for (const e of edges) {
      const [a, b] = down ? [e.from, e.to] : [e.to, e.from];
      if (a === cur && !seen.has(b)) { seen.add(b); todo.push(b); }
    }
  }
  return seen;
}

/** The ids a view keeps; null is the whole map. */
function keep(doc: GraphDoc, view: View, selected: string | null, wall: string | null, edges: MapEdge[]): Set<string> | null {
  if (view === "trace" && selected) return new Set([...reach([selected], edges, true), ...reach([selected], edges, false)]);
  if (view === "holes") return reach(doc.holes, edges, false);
  if (view === "fresh") return new Set(doc.new_this_week); // exactly the chip's list, no neighbours
  if (view === "wall" && wall) {
    const row = doc.by_wall.find((b) => b.wall === wall);
    return new Set([wall, ...reach([...(row?.problems ?? []), ...(row?.measures ?? [])], edges.filter((e) => !e.from.startsWith("problem:")), true)]);
  }
  return null;
}

function columnsOf(doc: GraphDoc, nodes: Map<string, MapNode>, pass: (id: string) => boolean, cols: ColKey[] = COLS): MapColumn[] {
  return cols.map((c) => {
    const ids = c === "walls" ? doc.columns.walls.map((w) => w.id) : doc.columns[c];
    return { title: t.columns[c], nodes: ids.filter(pass).map((id) => nodes.get(id)).filter((n): n is MapNode => !!n) };
  });
}

/** The names under a column: "Trust NAV · Fees Charged · 6 more". Names only, never the scan tag. A silhouette is never named. */
function names(col: MapColumn, plain: (id: string) => string | undefined): string {
  const short = (x: string) => (x.length > 26 ? `${x.slice(0, 25)}…` : x); // a long title must not run into the next column
  const named = col.nodes.filter((n) => !n.restricted).map((n) => short(plain(n.id) ?? n.label));
  const rest = col.nodes.length - Math.min(2, named.length);
  return [...named.slice(0, 2), ...(rest > 0 ? [t.more(rest)] : [])].join(" · ");
}

/** The trail sentence for a measure: the wall and problem that asked, the baseline, the system that supplies it, the owner. */
function trail(doc: GraphDoc, id: string, nodes: Map<string, MapNode>, edges: MapEdge[]): string {
  if (nodes.get(id)?.kind !== "Measure") return t.trail.links(edges.filter((e) => e.from === id || e.to === id).length);
  const ends = (type: string, toMe: boolean, of: string[]) =>
    doc.edges.filter((e) => e.type === type && of.includes(toMe ? e.to : e.from)).map((e) => (toMe ? e.from : e.to));
  const named = (xs: string[]) => [...new Set(xs.filter((x) => !nodes.get(x)?.restricted).map((x) => nodes.get(x)?.label ?? "").filter(Boolean))];
  const problems = ends("measured_by", true, [id]);
  const walls = doc.by_wall.filter((b) => b.problems.some((p) => problems.includes(p))).map((b) => b.wall);
  const sources = ends("fed_by", false, [id]);
  const owners = ends("owned_by", false, [id]);
  return [t.trail.asked(named(walls), named(problems)), t.trail.defined, t.trail.supplied(named(sources).map((s) => `the ${s} system`)),
    t.trail.owned(named(owners.length ? owners : ends("owned_by", false, sources)))].join(" ");
}

/** One true sentence for a node that changed this week, from its versions of the week; a silhouette is never named. */
function freshLine(doc: GraphDoc, id: string, nodes: Map<string, MapNode>): string {
  const node = nodes.get(id);
  return !node || node.restricted ? "" : t.fresh.say(node.label, doc.new_detail?.[id] ?? []);
}

export default function GraphPage() {
  const { user } = useSession();
  const phone = usePhone();
  const [params, setParams] = useSearchParams();
  const ovr = useOverview();
  const ov: Overview | null = ovr && ovr !== "failed" ? ovr : null;
  const [doc, setDoc] = useState<GraphDoc | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "refused" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const [view, setView] = useState<View>(() => (params.get("view") === "lineage" && params.get("focus") ? "lineage" : params.get("view") === "fresh" ? "fresh" : "whole"));
  const [selected, setSelected] = useState<string | null>(() => params.get("focus"));
  const [off, setOff] = useState<Set<string>>(new Set());
  const [scanOnly, setScanOnly] = useState(false);
  const [wallAt, setWallAt] = useState(0);

  useEffect(() => {
    let live = true;
    setState("loading");
    apiGet<GraphDoc>("/api/company/graph?view=map")
      .then((d) => { if (live) { setDoc(d); setState("ready"); } })
      .catch((e: unknown) => { if (live) setState(e instanceof Refused ? "refused" : "error"); });
    return () => { live = false; };
  }, [attempt]);

  const tagged = scanOnly || view === "lineage"; // the whole map's columns carry names only; scan tags show under the scan chip and on the lineage cards
  const m = useMemo(() => (doc ? model(doc, tagged ? ov?.checks : undefined) : null), [doc, ov, tagged]);
  const centres = centresFor(user?.roles);
  const tabs: TabItem[] = shellText.bar.filter((b) => b.id in TAB_ICON && centres.has(b.id as TabId)).map((b) => {
    const Icon = TAB_ICON[b.id as TabId];
    return { label: t.tabs[b.id as TabId], href: b.to, icon: <Icon />, active: b.id === "map" };
  });

  const frame = (subline: string | undefined, actions: ReactNode, body: ReactNode, aside?: ReactNode) => (
    <div className="ds-screen">
      <PageFrame title={t.title} subline={subline} actions={actions} aside={aside}>{body}</PageFrame>
      <PhoneTabBar items={tabs} />
    </div>
  );

  if (state !== "ready" || !doc || !m) {
    const s = state === "refused" ? t.refused : state === "error" ? t.error : t.loading;
    return frame(undefined, null, (
      <>
        <EmptyState title={s.title} lines={[...s.lines]} />
        {state === "error" && <Button onClick={() => setAttempt((a) => a + 1)}>{t.error.retry}</Button>}
      </>
    ));
  }
  if (doc.nodes.length === 0 && doc.columns.walls.length === 0) return frame(undefined, null, <EmptyState title={t.empty.title} lines={[...t.empty.lines]} />);

  const wallIds = doc.columns.walls.map((w) => w.id);
  const shown: View = phone && view === "whole" ? "wall" : view; // the phone has no whole map: one wall at a time
  const wall = wallIds[wallAt % Math.max(1, wallIds.length)] ?? null;
  const only = keep(doc, shown === "lineage" ? "whole" : shown, selected, wall, m.edges);
  const checked = new Set(Object.keys(ov?.checks ?? {}));
  const pass = (id: string) => (!only || only.has(id)) && (!scanOnly || checked.has(id)) && !off.has(groupOf(m.nodes.get(id)?.kind ?? "") ?? "");
  const pick = (id: string) => {
    setSelected(id === selected ? null : id);
    if (!phone && m.nodes.get(id)?.kind === "Measure") setView((v) => (v === "whole" ? "trace" : v));
  };
  const go = (v: View) => () => {
    setView(v);
    if (v !== "trace" && v !== "lineage") setSelected(null);
    setParams(v === "lineage" && selected ? { view: "lineage", focus: selected } : v === "fresh" ? { view: "fresh" } : {}, { replace: true });
  };
  const count = (g: string) => doc.nodes.filter((n) => GROUPS[g]!.includes(n.type) && !n.restricted).length;
  const chip = (v: View, label: string) => <Chip key={v} tone={shown === v ? "active" : "default"} onClick={go(v)}>{label}</Chip>;
  const sel = selected ? m.nodes.get(selected) : undefined;
  const selName = doc.nodes.find((n) => n.id === selected)?.label ?? sel?.label ?? ""; // the plain name: the card label may carry a scan tag
  const map = (cols: MapColumn[]) => (cols.some((c) => c.nodes.length)
    ? <MapColumns columns={cols} edges={m.edges} onSelect={pick} selectedId={selected ?? undefined} holeIds={doc.holes} />
    : <p>{t.noneInView}</p>);

  const rank = (id: string) => ({ Measure: 0, Problem: 1, System: 2, Source: 2, Person: 3 })[m.nodes.get(id)?.kind ?? ""] ?? 4;
  const lines = [...doc.new_this_week].sort((a, b) => rank(a) - rank(b)).map((id) => [id, m.nodes.get(id)?.kind ?? "", freshLine(doc, id, m.nodes)] as const).filter(([, , l]) => l);
  const shownLines = lines.slice(0, FRESH_MAX);
  const groups = [...new Set(shownLines.map(([, k]) => t.fresh.groups[k] ?? ""))];
  // the card follows the chip: the list when New this week is on, the plain line when nothing is new, otherwise the selected thing's trail only
  const freshCard = shown === "fresh" || lines.length === 0 ? (
    <SideCard title={t.fresh.title}>
      {lines.length ? (
        <>
          {groups.map((g) => (
            <div key={g}>
              {g && <p><strong>{g}</strong></p>}
              <ul>{shownLines.filter(([, k]) => (t.fresh.groups[k] ?? "") === g).map(([id, , line]) => <li key={id}>{line}</li>)}</ul>
            </div>
          ))}
          {lines.length > FRESH_MAX && <p>{t.fresh.andMore(lines.length - FRESH_MAX)}</p>}
        </>
      ) : <p>{t.fresh.none}</p>}
    </SideCard>
  ) : null;

  const lineage = view === "lineage" && selected ? lineageIds(doc.nodes, doc.edges, selected) : null;
  const lcols = lineage ? LINEAGE_TYPES.map((ts, i) => ({ title: K.lineage.columns[i] ?? "", nodes: [...lineage].map((id) => m.nodes.get(id)).filter((n): n is MapNode => !!n && ts.includes(n.kind)) })) : [];
  const lives: MapColumn = { title: K.where.column, nodes: doc.nodes.filter((n) => LIVES.includes(n.type) && pass(n.id)).map((n) => m.nodes.get(n.id)).filter((n): n is MapNode => !!n) };
  const lineageChip = selected && sel?.kind !== "wall"
    ? <Chip key="lineage" tone={view === "lineage" ? "active" : "default"} onClick={go("lineage")}>{K.chips.lineage}</Chip>
    : <span key="lineage" className="ds-chip" aria-disabled="true" title={K.chips.lineageHint}>{K.chips.lineage}</span>;
  const scanChip = checked.size
    ? <Chip key="scan" tone={scanOnly ? "active" : "default"} onClick={() => { setView("whole"); setScanOnly((x) => !x); }}>{K.chips.checked(checked.size)}</Chip> : null;
  const kindChips = Object.keys(GROUPS).map((g) => (count(g) === 0
    ? <span key={g} className="ds-chip" aria-disabled="true" title={K.chips.noneYet}>{K.chips.groups[g as keyof typeof K.chips.groups]} · {K.chips.noneYet}</span>
    : <Chip key={g} tone={off.has(g) ? "default" : "active"} onClick={() => setOff((o) => { const n = new Set(o); if (n.has(g)) n.delete(g); else n.add(g); return n; })}>{K.chips.groups[g as keyof typeof K.chips.groups]}</Chip>));
  const where = sel && !sel.restricted ? whereRows(doc.nodes, doc.edges, sel.id).heldIn.map((n) => n.label) : [];
  const lastCard = (
    <SideCard title={K.last.title} action={ov?.last_update ? { label: K.last.see, href: "/centre/intent/graph?view=fresh" } : undefined}>
      <p>{ov?.last_update ? ov.last_update.line : K.last.none}</p>
    </SideCard>
  );

  if (phone) {
    const row = doc.by_wall.find((b) => b.wall === wall);
    const phoneLineage = lineage ? lcols.filter((c) => c.nodes.length) : null;
    const title = shown === "wall" && wall ? t.wallTitle(m.nodes.get(wall)?.label ?? "")
      : shown === "holes" ? t.chips.holes(doc.holes.length) : shown === "fresh" ? t.fresh.title : t.chips.trace;
    return frame(t.phoneSubline(doc.summary), [
      chip("wall", t.chips.wall), chip("trace", t.chips.phoneTrace), chip("holes", t.chips.holes(doc.holes.length)), lineageChip, ...(scanChip ? [scanChip] : []), ...kindChips,
      ...(doc.new_this_week.length ? [chip("fresh", t.chips.phoneFresh(doc.new_this_week.length))] : []),
    ], (
      <>
        {phoneLineage ? (
          <SideCard title={K.lineage.title}>
            <p>{K.lineage.of(selName)}</p>
            {phoneLineage.length ? phoneLineage.map((c) => (
              <div key={c.title}>
                <p><strong>{c.title}</strong></p>
                <ul>{c.nodes.map((n) => <li key={n.id}>{n.restricted ? K.lineage.restricted : <Link className="ds-link" to={`/centre/intent/map/${encodeURIComponent(n.id)}`}>{n.label}</Link>}</li>)}</ul>
              </div>
            )) : <p>{K.lineage.empty}</p>}
            <Chip onClick={go("whole")}>{K.lineage.back}</Chip>
          </SideCard>
        ) : (
        <SideCard title={title}>
          {shown === "wall" && <p>{t.wallCounts(row?.problems.length ?? 0, row?.measures.length ?? 0)}</p>}
          {map(scanOnly ? [lives] : columnsOf(doc, m.nodes, pass, ["walls", "problems", "measures", "systems"]))}{/* the scan checks fields: under this filter the phone shows only where they live */}
          <Footnote>{t.legend}</Footnote>
          {shown === "wall" && wallIds.length > 1 && <Chip onClick={() => { setWallAt((i) => i + 1); setSelected(null); }}>{t.nextWall}</Chip>}
        </SideCard>
        )}
        <SideCard title={t.phoneTraceTitle}>
          <p>{sel?.kind === "Measure" ? `${sel.label}: ${trail(doc, sel.id, m.nodes, m.edges)}` : t.phoneTraceHint}</p>
        </SideCard>
        {freshCard}
        {lastCard}
        <Footnote>{t.phoneFoot}</Footnote>
      </>
    ));
  }

  const cols = [...columnsOf(doc, m.nodes, pass), lives];
  return frame(t.subline(doc.summary), [
    chip("whole", t.chips.whole), chip("wall", t.chips.wall), chip("trace", t.chips.trace),
    chip("holes", t.chips.holes(doc.holes.length)), lineageChip, ...(scanChip ? [scanChip] : []),
    ...(doc.new_this_week.length ? [chip("fresh", t.chips.fresh(doc.new_this_week.length))] : []), ...kindChips,
  ], (
    <div className="ds-card ds-side">
      {view === "wall" && wallIds.length > 1 && (
        <div className="ds-frame__actions">
          {doc.columns.walls.map((w, i) => <Chip key={w.id} tone={w.id === wall ? "active" : "default"} onClick={() => setWallAt(i)}>{t.wallTitle(w.label)}</Chip>)}
        </div>
      )}
      {lineage ? (
        <>
          <p>{K.lineage.of(selName)}</p>
          {lcols.some((c) => c.nodes.length) ? <MapColumns columns={lcols} edges={m.edges} onSelect={pick} selectedId={selected ?? undefined} /> : <p>{K.lineage.empty}</p>}
        </>
      ) : <>{map(cols)}
      {/* ponytail: the names row borrows the column-head grid; a ds-map__names class in design.css would drop this inline override */}
      <div className="ds-map__heads" style={{ "--ds-cols": cols.length, textTransform: "none", letterSpacing: 0 } as CSSProperties}>
        {cols.map((c) => <span key={c.title} style={{ minWidth: 0, overflow: "hidden", overflowWrap: "anywhere" }}>{names(c, (id) => doc?.nodes.find((n) => n.id === id)?.label)}</span>)}
      </div>
      </>}
      <Footnote>{t.howTo}</Footnote>
    </div>
  ), (
    <>
      {sel
        ? <SideCard title={t.selected(selName)} action={sel.kind === "wall" ? undefined : { label: t.openDefinition, href: `/centre/intent/map/${encodeURIComponent(sel.id)}` }}>
            <p>{trail(doc, sel.id, m.nodes, m.edges)}{where.length ? ` ${K.selected.lives(where.join(" and "))}` : ""}</p>
            {ov?.checks?.[sel.id] && <p>{tagOf(ov.checks[sel.id])}</p>}
          </SideCard>
        : <SideCard title={t.chips.trace}><p>{t.traceHint}</p></SideCard>}
      {freshCard}
      {lastCard}
      <SideCard title={t.keptOut.title}><p>{t.keptOut.body}</p></SideCard>
    </>
  ));
}
