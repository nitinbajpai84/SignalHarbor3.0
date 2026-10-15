import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useSession } from "../../useSession";
import { MicButton } from "../../v1/voice";
import V3Frame from "../Frame";
import { useRead } from "../board/common";
import { askConsume, getConsume, type ConsumeAnswer, type ConsumeData, type Reading } from "./consumeApi";
import "./consume.css";

type Turn = { q: string; a: ConsumeAnswer | null; error?: string };

const day = (at?: string | null) => (at ? new Date(at.length <= 10 ? `${at}T12:00:00` : at).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "");
const today = () => new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" });
const initials = (n?: string | null) => (n ?? "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "ME";
const tone = (change: string) => (/^[-−]/.test(change) ? "v3c-down" : change ? "v3c-up" : "");
const num = (v: string) => (/^-?[\d,]+(\.\d+)?$/.test(v) ? Number(v.replace(/,/g, "")) : null);
/** Chart colours carry meaning: the asked-about series is Harbor's answer (brass), the rest navy then slate. */
const COLOURS = ["var(--harbor)", "var(--act)", "var(--info)"];

const Check = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12" /></svg>;

/** Gold area chart from a daily series, else per-entity bars from the rows. Plain inline SVG; nothing is drawn when there is nothing to draw. */
function Chart({ series, rows }: { series?: number[]; rows: { label: string; value: string }[] }) {
  if (series && series.length > 1) {
    const lo = Math.min(...series), hi = Math.max(...series), span = hi - lo || 1;
    const pts = series.map((v, i) => `${10 + (i / (series.length - 1)) * 800},${115 - ((v - lo) / span) * 90}`);
    return (
      <svg className="v3c-chart" viewBox="0 0 820 140" role="img" aria-label="Trend">
        <defs><linearGradient id="v3c-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style={{ stopColor: "var(--harbor)", stopOpacity: 0.28 }} /><stop offset="1" style={{ stopColor: "var(--harbor)", stopOpacity: 0 }} /></linearGradient></defs>
        <polygon points={`10,120 ${pts.join(" ")} 810,120`} fill="url(#v3c-area)" />
        <polyline points={pts.join(" ")} fill="none" style={{ stroke: "var(--harbor)" }} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    );
  }
  const vals = rows.map((r) => num(r.value));
  if (rows.length < 2 || vals.some((v) => v === null)) return null;
  const hi = Math.max(...(vals as number[]), 1);
  return (
    <svg className="v3c-chart" viewBox="0 0 820 140" role="img" aria-label="Cash by entity">
      <g style={{ stroke: "var(--line)" }} strokeDasharray="3 5"><line x1="0" y1="20" x2="820" y2="20" /><line x1="0" y1="70" x2="820" y2="70" /><line x1="0" y1="120" x2="820" y2="120" /></g>
      {rows.map((r, i) => {
        const w = 820 / rows.length, h = Math.max(4, ((vals[i] as number) / hi) * 100);
        return <rect key={r.label} x={i * w + w * 0.2} y={120 - h} width={w * 0.6} height={h} rx="6" style={{ fill: COLOURS[i % 3] }} fillOpacity={i === 0 ? 0.95 : 0.8}><title>{`${r.label} ${r.value}`}</title></rect>;
      })}
    </svg>
  );
}

function csv(turn: Turn) {
  const a = turn.a!;
  const cell = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const lines = [["Question", turn.q], ...(a.figure ? [[a.figure.label, a.figure.value]] : []), ...(a.rows ?? []).map((r) => [r.label, r.value]), ["Source", a.source ?? ""]];
  const url = URL.createObjectURL(new Blob([`﻿${lines.map((l) => l.map(cell).join(",")).join("\r\n")}\r\n`], { type: "text/csv;charset=utf-8" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: "consume-answer.csv" });
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function Answer({ turn, golden, ask }: { turn: Turn; golden: string[]; ask: (q: string) => void }) {
  const a = turn.a;
  if (turn.error) return <div className="v3c-card" role="alert"><p className="err">{turn.error}</p><button type="button" className="again" onClick={() => ask(turn.q)}>Try again</button></div>;
  if (!a) return <div className="v3c-card"><div className="v3c-q">{turn.q}</div><p className="v3c-wait" role="status">Working it out…</p></div>;
  const guard = a.trace.find((s) => s.kind === "guard")?.label;
  const source = a.source ?? [a.used[0] ?? guard ?? "Worked out from the signed numbers", a.as_of ? `as of ${day(a.as_of)}` : ""].filter(Boolean).join(" · ");
  const rows = a.rows ?? [];
  const nums = rows.map((r) => num(r.value));
  const sum = nums.every((n) => n !== null) ? (nums as number[]).reduce((x, y) => x + y, 0) : 0;
  return (
    <section className="v3c-card v3c-print" aria-labelledby="v3c-ans">
      <div className="v3c-q">{turn.q}</div>
      <h2 id="v3c-ans">{a.figure?.label ?? "Answer"}</h2>
      {a.figure ? <div className="v3c-figrow"><span className="v3c-big">{a.figure.value}</span>{a.figure.change ? <span className={`v3c-chg ${tone(a.figure.change)}`}>{a.figure.change}</span> : null}</div> : null}
      <p className="v3c-sentence">{a.answer}</p>
      <Chart series={a.series} rows={rows} />
      {rows.length ? (
        <div className="v3c-rows">
          {rows.map((r, i) => {
            const n = nums[i];
            return (
              <div key={r.label} className="v3c-rowi" style={{ borderTopColor: COLOURS[i % 3] }}>
                <span>{r.label}{n != null && sum > 0 ? ` · ${((n / sum) * 100).toFixed(1)}%` : ""}</span>
                <span className="mono">{r.value}</span>
              </div>
            );
          })}
        </div>
      ) : null}
      <div className="v3c-chips noprint" role="group" aria-label="Follow-up questions">{golden.filter((q) => q !== turn.q).slice(0, 4).map((q) => <button key={q} type="button" onClick={() => ask(q)}>{q}</button>)}</div>
      <div className="v3c-acts noprint">
        <button type="button" className="go" onClick={() => window.print()}>Download PDF</button>
        <button type="button" onClick={() => csv(turn)}>Excel</button>
      </div>
      <p className="v3c-src"><Check /><span>Source: {source}</span></p>
      {a.ms !== undefined ? <small className="noprint">Answered in {a.ms} ms{a.cached ? " (from memory)" : ""}</small> : null}
    </section>
  );
}

function Card({ id, title, aside, children }: { id: string; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="v3c-card" id={id} aria-labelledby={`${id}-h`}>
      <div className="v3c-cardhead"><h2 id={`${id}-h`}>{title}</h2>{aside}</div>
      {children}
    </section>
  );
}

function Watch({ r }: { r: Reading }) {
  return (
    <article className={`v3c-tile${r.stale ? " stale" : ""}`} aria-label={r.label}>
      <div className="v3c-tilehead"><span className="mono">{r.code ?? ""}</span>{r.stale ? <span className="pill">Stale{r.dated ? ` · ${day(r.dated)}` : ""}</span> : <span>Cash</span>}</div>
      <span className="v3c-tname">{r.label}</span>
      <span className="v3c-tval">{r.value}</span>
      {r.stale ? <span className="v3c-tchg amber">{r.dated ? `Cash dated ${day(r.dated)}, not yet updated` : "Not yet updated"}</span> : r.change ? <span className={`v3c-tchg ${tone(r.change)}`}>{r.change}</span> : null}
    </article>
  );
}

const H = { fill: "var(--harbor)" }, HS = { stroke: "var(--harbor)" }, T = { fill: "var(--info-soft)" }, A = { fill: "var(--act)" }, I = { fill: "var(--info)" };
const THUMBS = [
  <><rect x="12" y="12" width="60" height="6" rx="3" style={H} /><rect x="12" y="28" width="126" height="20" rx="4" style={T} /><polyline points="16,44 34,40 52,42 70,36 88,34 106,30 124,26 134,24" fill="none" style={HS} strokeWidth="2" /><rect x="12" y="58" width="36" height="22" rx="4" style={T} /><rect x="54" y="58" width="36" height="22" rx="4" style={T} /><rect x="96" y="58" width="42" height="22" rx="4" style={T} /></>,
  <><rect x="12" y="12" width="48" height="6" rx="3" style={H} /><rect x="12" y="28" width="58" height="52" rx="4" style={T} /><rect x="78" y="28" width="60" height="24" rx="4" style={T} /><rect x="78" y="56" width="60" height="24" rx="4" style={T} /><rect x="20" y="40" width="42" height="5" rx="2" style={A} /><rect x="20" y="52" width="34" height="5" rx="2" style={A} /></>,
  <><rect x="12" y="12" width="54" height="6" rx="3" style={H} /><rect x="12" y="28" width="126" height="12" rx="4" style={T} /><rect x="12" y="46" width="126" height="12" rx="4" style={T} /><rect x="12" y="64" width="126" height="16" rx="4" style={T} /><rect x="16" y="31" width="70" height="6" rx="3" style={I} /><rect x="16" y="49" width="48" height="6" rx="3" style={I} /></>,
];

const isEmpty = (d: ConsumeData) => !d.figures.length && !d.watchlist.length && !d.boards.length && !d.note && !d.reports.length && !d.answer;

const TABS: [string, string, ReactNode][] = [
  ["ask", "Ask", <path key="a" d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />],
  ["boards", "Boards", <g key="b"><rect x="3" y="3" width="8" height="5" rx="2" /><rect x="13" y="3" width="8" height="8" rx="2" /><rect x="13" y="13" width="8" height="8" rx="2" /><rect x="3" y="10" width="8" height="11" rx="2" /></g>],
  ["note", "Note", <g key="n"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /><path d="M8 13h8" /><path d="M8 17h5" /></g>],
  ["reports", "Reports", <g key="r"><path d="M4 20V10" /><path d="M10 20V4" /><path d="M16 20v-7" /><path d="M22 20H2" /></g>],
];

export default function ConsumePage() {
  const [got, again] = useRead(getConsume);
  const { user } = useSession();
  const [q, setQ] = useState("");
  const [turn, setTurn] = useState<Turn | null>(null);
  const [tab, setTab] = useState("ask");
  const run = (text: string) => {
    setQ("");
    setTurn({ q: text, a: null });
    askConsume(text).then((a) => setTurn({ q: text, a }), (e: unknown) => setTurn({ q: text, a: null, error: e instanceof Error && e.message ? e.message : "I could not answer that just now. Please try again." }));
  };
  const busy = !!turn && !turn.a && !turn.error;
  const d = got.state === "ready" ? got.data : null;
  const golden = d ? d.golden.map((g) => g.q) : [];
  const shown: Turn | null = turn ?? (d?.answer ? { q: d.answer.q, a: d.answer } : null);
  return (
    <V3Frame>
      <div className="v3c">
        <main className="v3c-main">
          <div className="v3c-head">
            <div><p className="v3c-date">{today()}</p><h1>{d?.office || "Your office"}</h1></div>
            <div className="v3c-who"><span className="v3c-synth">Synthetic data</span><span className="v3c-av" role="img" aria-label={user?.display_name ?? "You"}>{initials(user?.display_name)}</span></div>
          </div>
          <nav className="v3c-tabs" aria-label="Consume tabs">
            {TABS.map(([id, label, icon]) => (
              <a key={id} href={`#${id}`} aria-current={tab === id ? "page" : undefined} onClick={() => setTab(id)}>
                <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{icon}</svg>
                <span>{label}</span>
              </a>
            ))}
          </nav>
          <form className="v3c-ask" id="ask" role="search" onSubmit={(e) => { e.preventDefault(); if (q.trim() && !busy) run(q.trim()); }}>
            <label className="v3b-sr" htmlFor="v3c-q">Ask anything about the numbers</label>
            <input id="v3c-q" type="text" value={q} placeholder="Ask anything about the portfolio" autoComplete="off" onChange={(e) => setQ(e.target.value)} />
            {q.trim() ? <button type="submit" className="send" disabled={busy}>Ask</button> : null}
            <MicButton onText={(t) => setQ((x) => (x ? `${x} ${t}` : t))} disabled={busy} agent="Lumen" />
          </form>
          {got.state === "loading" ? <p className="v3c-wait" role="status">Opening Consume…</p>
            : got.state === "error" ? <div className="v3c-card" role="alert"><p className="err">{got.message}</p><button type="button" className="again" onClick={again}>Try again</button></div>
            : d && isEmpty(d) && !turn ? <div className="v3c-card"><p>Nothing to read yet; a use case goes live in Build.</p><Link to="/v3/build">Go to Build</Link></div>
            : d ? (
              <>
                <div className="v3c-split">
                  {shown ? <Answer turn={shown} golden={golden} ask={run} />
                    : <section className="v3c-card"><h2>Ask anything</h2>
                      <div className="v3c-chips" role="group" aria-label="Questions people here ask often">{golden.slice(0, 4).map((g) => <button key={g} type="button" onClick={() => run(g)}>{g}</button>)}</div></section>}
                  <aside className="v3c-side" aria-labelledby="c-watch">
                    <h2 id="c-watch">Watchlist</h2>
                    {d.watchlist.length ? <div className="v3c-tiles">{d.watchlist.map((w) => <Watch key={w.label} r={w} />)}</div> : <p className="v3c-empty">Nothing to watch yet.</p>}
                  </aside>
                </div>
                <div className="v3c-lower">
                  <Card id="exposure" title="Total family exposure">
                    <span className="v3c-na">Not available yet</span>
                    <div className="v3c-bar" role="img" aria-label="Exposure split, not available yet"><span /><span /><span /></div>
                    <p className="v3c-empty">Public, private equity and hedge show here once net worth is reliable.</p>
                  </Card>
                  <Card id="boards" title="Your boards" aside={d.boards.length ? <small>{d.boards.length} board{d.boards.length === 1 ? "" : "s"}</small> : null}>
                    {d.boards.length ? (
                      <div className="v3c-boards">{d.boards.map((b, i) => (
                        <Link key={b.id} to="/v3/board" className="v3c-board">
                          <svg viewBox="0 0 150 92" width="100%" height="92" role="img" aria-label={`Board thumbnail, ${b.title}`}><rect width="150" height="92" rx="10" style={{ fill: "var(--paper)", stroke: "var(--line)" }} />{THUMBS[i % 3]}</svg>
                          <span>{b.title}</span>
                        </Link>))}
                      </div>
                    ) : <p className="v3c-empty">No board is published yet.</p>}
                  </Card>
                  <div className="v3c-stack">
                    <Card id="note" title="This morning's note">
                      {d.note ? <><p className="v3c-note">{d.note.headline}</p><Link to="/v3/note">Read the note →</Link></> : <p className="v3c-empty">There is no note yet.</p>}
                    </Card>
                    <Card id="reports" title="Reports">
                      {d.reports.length ? <ul className="v3c-list">{d.reports.map((r) => <li key={r.href}><span className="v3c-doc" aria-hidden="true">DOC</span><a href={r.href}>{r.name}</a></li>)}</ul> : <p className="v3c-empty">No report is ready yet.</p>}
                    </Card>
                  </div>
                </div>
              </>
            ) : null}
        </main>
      </div>
    </V3Frame>
  );
}
