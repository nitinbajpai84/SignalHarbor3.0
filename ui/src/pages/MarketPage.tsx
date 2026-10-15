import { useState, type CSSProperties } from "react";

import { apiGet, apiSend } from "../api/client";
import { useLoad, type Loaded } from "../components/useLoad";
import { ActionCard, Button, Chip, EmptyState, Footnote, PageFrame, Pill, SideCard, Strip, WarningIcon } from "../design";
import { useSession } from "../useSession";
import { getBoard, listWalls } from "../modules/m1_intent/api";

// Market forces: outside signals set beside the company's own measures, starting from the Watch lane. Every brief stays labelled outside material.

interface Brief { id: string; title: string; summary: string; measures: string[]; source: string; outside: true; moved?: { code: string; name: string }[]; moved_month?: string | null; measure_moves?: { code: string; name: string; latest_move: { period: string; from: number; to: number; change_pct: number | null } | null }[] }
interface Market { briefs: Brief[]; internet: boolean; internet_line?: string; fetched_at?: string }
interface WatchCard { id: string; text: string }

// ponytail: the design system has no form field yet; token colours only.
const FIELD: CSSProperties = { minHeight: 44, padding: "8px 12px", borderRadius: 8, border: "1px solid var(--ds-line-2)", background: "var(--ds-ground)", color: "var(--ds-ink)", font: "inherit", fontSize: 13, boxSizing: "border-box", width: "100%" };
const LABEL: CSSProperties = { display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "var(--ds-ink-soft)" };
const ROW: CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", fontSize: 13, color: "var(--ds-ink-soft)" };

const monthName = (m: string) => new Date(`${m}-01T00:00:00Z`).toLocaleString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
const num = (n: number) => Number(n.toPrecision(6));
const touched = (b: Brief) => b.measure_moves ?? b.measures.map((code) => ({ code, name: code, latest_move: null }));
const measurePage = (code: string) => `/centre/consume/feeds/${encodeURIComponent(code)}`;

const AFTER_ROOMS = ["board", "together", "signing", "closed"];

/** Watch-lane cards (future signals) from every wall the viewer may read: the board route already hides what they may not see. */
async function watchCards(): Promise<WatchCard[]> {
  const { walls } = await listWalls();
  // Only walls past the private rooms have a board; asking earlier answers 409 and puts an error in the console.
  const boards = await Promise.all(walls.filter((w) => AFTER_ROOMS.includes(w.state)).map((w) => getBoard(w.id).catch(() => null)));
  const out: WatchCard[] = [];
  for (const b of boards) {
    for (const n of [...(b?.clusters.flatMap((c) => c.notes) ?? []), ...(b?.on_its_own ?? [])]) {
      if (n.kind === "future_signal") out.push({ id: n.id, text: n.text });
    }
  }
  return out;
}

/** The first measure code a card names in its own words, as the market briefs name them. A card that names none has no measure yet. */
function answeredBy(text: string, codes: string[]): string | undefined {
  return codes.find((c) => new RegExp(`(?<![\\w])${c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![\\w])`, "i").test(text));
}

/** Loading, empty, refused and error, in the design system's words; children only when there is something to show. */
function States<T>({ load, title, empty, children }: { load: Loaded<T>; title: string; empty: string; children: React.ReactNode }) {
  if (load.state === "populated") return <>{children}</>;
  if (load.state === "loading") return <div role="status"><EmptyState title={title} lines={["Reading it now."]} /></div>;
  if (load.state === "empty") return <EmptyState title={title} lines={[empty]} />;
  return (
    <div role="alert">
      <EmptyState title={title} lines={[load.message ?? (load.state === "refused" ? "You do not have access to this." : "This could not be read just now. Try again in a moment.")]} />
      {load.state === "error" && <Button onClick={load.retry}>Try again</Button>}
    </div>
  );
}

function AddBrief({ onAdded }: { onAdded: () => void }) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [measures, setMeasures] = useState("");
  const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiSend("POST", "/api/company/market/briefs", { title, text, measures: measures.split(/[\s,]+/).filter(Boolean) });
      setTitle(""); setText(""); setMeasures(""); setErr(""); onAdded();
    } catch {
      setErr("The brief could not be added. Check the title and text and try again.");
    }
  };
  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <label style={LABEL}>Brief title <input style={FIELD} value={title} onChange={(e) => setTitle(e.target.value)} /></label>
      <label style={LABEL}>Brief text <textarea style={{ ...FIELD, minHeight: 88 }} value={text} onChange={(e) => setText(e.target.value)} /></label>
      <label style={LABEL}>Measure codes <input style={FIELD} value={measures} onChange={(e) => setMeasures(e.target.value)} placeholder="K01, K02" /></label>
      <Button type="submit" variant="primary" disabled={!title.trim() || !text.trim()}>Add brief</Button>
      {err && <p role="alert" className="ds-warn" style={{ margin: 0, fontSize: 13 }}>{err}</p>}
    </form>
  );
}

export default function MarketPage() {
  const [measure, setMeasure] = useState("");
  const { user } = useSession();
  const market = useLoad(() => apiGet<Market>("/api/company/market"), "market", (d) => d.briefs.length === 0 && !d.internet_line);
  const watch = useLoad(watchCards, "watch", (d) => d.length === 0);
  const briefs = market.data?.briefs ?? [];
  const codes = [...new Set(briefs.flatMap((b) => [...b.measures, ...(b.moved ?? []).map((m) => m.code)]))].sort();
  const shown = measure ? briefs.filter((b) => b.measures.includes(measure)) : briefs;
  const internetLine = market.data?.internet
    ? `Internet is on for this company. Public briefs fetched ${market.data.fetched_at ? new Date(market.data.fetched_at).toLocaleString() : ""}.`
    : market.data?.internet_line;

  return (
    <PageFrame
      title="Market forces"
      subline="Outside signals set against your own measures, shown as context, never as your figure. Starts from the Watch lane."
      actions={codes.length > 0 && (
        <label style={{ ...LABEL, flexDirection: "row", alignItems: "center", gap: 8 }}>Measure
          <select style={{ ...FIELD, width: "auto" }} value={measure} onChange={(e) => setMeasure(e.target.value)}>
            <option value="">All measures</option>
            {codes.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      )}
      aside={<>
        <SideCard title="Outside material">
          <p>Anything from outside is labelled as such. It can sit next to a measure; it can never become one. Internet is a per-company switch, off by default.</p>
          {internetLine && <p><Pill tone={market.data?.internet ? "ok" : "draft"}>{market.data?.internet ? "Internet on" : "Internet off"}</Pill> {internetLine}</p>}
        </SideCard>
        {user?.roles.includes("company_admin") && (
          <SideCard title="Add a brief">
            <p>Added by you, shown to everyone as outside material.</p>
            <AddBrief onAdded={market.retry} />
          </SideCard>
        )}
      </>}
    >
      <Strip label="From the Watch lane" tone="amber">
        <States load={watch} title="Watch lane" empty="No watch cards on your walls yet.">
          {watch.data?.map((c) => {
            const code = answeredBy(c.text, codes);
            return (
              <ActionCard key={c.id} tone="amber" icon={<WarningIcon />} title={c.text}
                detail={code ? `Answered by ${code}` : "No measure named on this card yet"}
                action={code ? "Open the measure" : "See your measures"} href={code ? measurePage(code) : "/centre/consume/feeds"} />
            );
          })}
        </States>
      </Strip>

      <Strip label="Briefs" tone="teal">
        <States load={market} title="Briefs" empty="No market material comes with your industry yet.">
          {shown.length === 0 && <EmptyState title="No brief for this measure" lines={["Pick another measure or show all measures."]} />}
          {shown.map((b) => (
            <SideCard key={b.id} title={b.title} action={{ label: "Feeds", href: "/centre/consume/feeds" }}>
              <div><Pill tone="open">Outside material</Pill></div>
              <p>{b.summary}</p>
              <div style={{ ...ROW, flexDirection: "column", alignItems: "flex-start" }}>
                <span>Measures it touches, with their latest move:</span>
                {touched(b).length ? touched(b).map((m) => (
                  <span key={m.code}><Chip href={`/centre/intent/map/${encodeURIComponent(m.code)}`}>{m.name}</Chip>{" "}
                    {m.latest_move ? `${num(m.latest_move.from)} to ${num(m.latest_move.to)} (${m.latest_move.period})${m.latest_move.change_pct === null ? "" : `, ${m.latest_move.change_pct > 0 ? "+" : ""}${m.latest_move.change_pct}%`}` : "Not available yet"}</span>
                )) : <span>none named</span>}
              </div>
              <div style={ROW}>
                <span>{b.moved_month ? `Your measures outside their range in ${monthName(b.moved_month)}:` : "Your measures that moved:"}</span>
                {b.moved?.length ? b.moved.map((m) => <Chip key={m.code} href={measurePage(m.code)}>{m.name}</Chip>) : <span>none outside their range that month</span>}
              </div>
              <Footnote>Source: {b.source}</Footnote>
            </SideCard>
          ))}
        </States>
      </Strip>
      <Footnote>Briefs are context from outside. Your own figures come only from your measures.</Footnote>
    </PageFrame>
  );
}
