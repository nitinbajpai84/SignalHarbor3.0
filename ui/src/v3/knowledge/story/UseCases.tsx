import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Failed, useRead } from "../../board/common";
import Chip from "./Chip";
import { KIND_NAME, day, getStory, getUseCases, pathOf, type Item, type Story as StoryData, type UseCases as Lists } from "./api";

const CAP = { silver: 5, assumption: 4 };

/** Left: live and in-progress use cases by domain. Main: the story of the chosen one, with a detail panel on the right. */
export default function UseCases({ find, ucId, onPick }: { find: string; ucId: string | null; onPick: (id: string) => void }) {
  const [got, again] = useRead(getUseCases);
  const q = find.trim().toLowerCase();
  if (got.state === "loading") return <p className="v3-mute" role="status">Reading the use cases</p>;
  if (got.state === "error") return <Failed message={got.message} again={again} />;
  const all = got.data.groups.flatMap((g) => g.items);
  if (!all.length) return <div className="v3-card"><p>No use cases yet. Once one is started, its story appears here, from the person who asked down to the files.</p></div>;
  const current = all.find((i) => i.id === ucId) ?? all[0];
  if (!current) return null;
  return (
    <div className="ks-body">
      <Side lists={got.data} q={q} current={current.id} onPick={onPick} />
      <Story key={current.id} id={current.id} />
    </div>
  );
}

function Side({ lists, q, current, onPick }: { lists: Lists; q: string; current: string; onPick: (id: string) => void }) {
  const groups = lists.groups.map((g) => ({ ...g, items: g.items.filter((i) => !q || i.find.includes(q)) })).filter((g) => g.items.length);
  return (
    <nav className="ks-side" aria-label="Use cases by domain">
      <p className="ks-kicker">By domain</p>
      {!groups.length && <p className="v3-mute">Nothing matches that.</p>}
      {groups.map((g) => (
        <div key={g.domain} className="ks-group">
          <p className="ks-gname">{g.name} {"·"} {g.items.length}</p>
          {g.items.map((i) => <button key={i.id} type="button" className={i.id === current ? "ks-uc on" : "ks-uc"} aria-current={i.id === current ? "true" : undefined} onClick={() => onPick(i.id)}>{i.title}</button>)}
        </div>
      ))}
    </nav>
  );
}

function Story({ id }: { id: string }) {
  const [got, again] = useRead(() => getStory(id));
  const [sel, setSel] = useState<string | null>(null);
  const [path, setPath] = useState<string | null>(null);
  const [more, setMore] = useState<Record<string, boolean>>({});
  const s = got.state === "ready" ? got.data : null;
  const lit = useMemo(() => (s && path ? pathOf(s.edges, path) : null), [s, path]);
  if (got.state === "loading") return <section className="ks-main"><p className="v3-mute" role="status">Reading the story</p></section>;
  if (got.state === "error" || !s) return <section className="ks-main"><Failed message={got.state === "error" ? got.message : "Nothing here."} again={again} /></section>;
  const all = [...s.decisions, ...s.kpis, ...s.gold, ...s.silver, ...s.bronze, ...s.used_by];
  const item = all.find((i) => i.id === sel) ?? s.kpis[0] ?? all[0] ?? null;
  const chip = (i: Item) => <Chip key={i.id} item={i} on={item?.id === i.id} dim={!!lit && !lit.has(i.id)} onPick={setSel} />;
  const row = (key: string, label: string, cls: string, items: Item[], cap = 0) => {
    const shown = cap && !more[key] ? items.slice(0, cap) : items;
    return (
      <div className="ks-row" key={key}>
        <h3 className={`ks-label ${cls}`}>{label}</h3>
        <div className="ks-chips">
          {items.length === 0 && <span className="v3-mute">{key === "kpis" ? "No figures yet." : "None recorded."}</span>}
          {shown.map(chip)}
          {cap > 0 && items.length > cap && <button type="button" className="ks-more" onClick={() => setMore({ ...more, [key]: !more[key] })}>{more[key] ? "Show fewer" : `+${items.length - cap} more`}</button>}
        </div>
      </div>
    );
  };
  const dec = s.decisions.filter((i) => i.kind !== "assumption");
  const asm = s.decisions.filter((i) => i.kind === "assumption");
  return (
    <>
      <section className="ks-main" aria-label={`Story of ${s.title}`}>
        <div className="ks-title">
          <h2>{s.title}</h2>
          <span className={s.live ? "v3-pill done" : "v3-pill act"}>{s.stage_label}</span>
        </div>
        <p className="ks-intro">From the person who asked, down to the files. Click any box to see its detail; a gold dot means it is shared with other use cases.</p>
        {path && lit && <p className="ks-pathbar" role="status">Showing only the path of {all.find((i) => i.id === path)?.label}. <button type="button" className="ks-link" onClick={() => setPath(null)}>Show everything</button></p>}
        <div className="ks-row"><h3 className="ks-label">Who asked</h3><div className="ks-chips"><span className="ks-who"><b>{s.who.name || "Someone in the office"}</b>{s.who.role ? ` · ${s.who.role}` : ""} {"·"} {day(s.who.at)}</span></div></div>
        <div className="ks-row"><h3 className="ks-label">What they asked</h3><blockquote className="ks-asked">{"“"}{s.asked || "No words were kept for this one."}{"”"}</blockquote></div>
        <div className="ks-row">
          <h3 className="ks-label">Decisions and rules</h3>
          <div className="ks-chips">
            {dec.length + asm.length === 0 && <span className="v3-mute">None signed yet.</span>}
            {dec.map(chip)}
            {(more.decisions ? asm : asm.slice(0, CAP.assumption)).map(chip)}
            {asm.length > CAP.assumption && <button type="button" className="ks-more" onClick={() => setMore({ ...more, decisions: !more.decisions })}>{more.decisions ? "Show fewer" : `+${asm.length - CAP.assumption} more assumptions`}</button>}
          </div>
        </div>
        {row("kpis", "KPIs", "", s.kpis)}
        {row("gold", "Gold tables", "gold", s.gold)}
        {row("silver", "Silver tables", "silver", s.silver, CAP.silver)}
        {row("bronze", "Bronze sources", "bronze", s.bronze)}
        {row("used_by", "Used by", "", s.used_by)}
      </section>
      <Detail item={item} story={s} path={path} setPath={setPath} />
    </>
  );
}

function Detail({ item, story, path, setPath }: { item: Item | null; story: StoryData; path: string | null; setPath: (id: string | null) => void }) {
  if (!item) return <aside className="ks-detail" aria-label="Detail"><p className="v3-mute">Pick a box to see what it is.</p></aside>;
  const on = path === item.id;
  return (
    <aside className="ks-detail" aria-label="Detail">
      <p className="ks-kicker">Selected {"·"} {KIND_NAME[item.kind]}</p>
      <h2>{item.label}</h2>
      {item.detail.map((d) => <p key={d.k} className="ks-line"><b>{d.k}:</b> {d.v}</p>)}
      {item.shared.length > 0 && (
        <p className="ks-line"><b>Shared with:</b> {item.shared.map((u, n) => <span key={u.id}>{n ? ", " : ""}<Link to={`/v3/knowledge?tab=usecases&uc=${encodeURIComponent(u.id)}`}>{u.title}</Link></span>)}</p>
      )}
      <div className="ks-links">
        {item.links?.map((l) => <Link key={l.to} to={l.to}>{l.label}</Link>)}
        <button type="button" className="ks-link" onClick={() => setPath(on ? null : item.id)}>{on ? "Show everything" : "Show only its path"}</button>
        <Link to={story.conversation}>Open the use case conversation</Link>
      </div>
    </aside>
  );
}
