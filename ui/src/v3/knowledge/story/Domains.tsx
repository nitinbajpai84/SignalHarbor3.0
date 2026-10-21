import { Failed, useRead } from "../../board/common";
import { getDomain, getUseCases, type Domain, type DomainItem, type RowKey } from "./api";
import { Dot } from "./Chip";

const ROWS: [RowKey, string, string][] = [["decisions", "Decisions", ""], ["kpis", "KPIs", ""], ["gold", "Gold tables", "gold"], ["silver", "Silver tables", "silver"], ["bronze", "Bronze sources", "bronze"]];
const WITH_SUB = new Set(["gold", "silver", "bronze"]);

export interface Cell { item: DomainItem; start: number; span: number; shared: boolean }

/** The contiguous runs of a list of columns: [0,1,3] is [0..1] and [3..3]. */
const runs = (cols: number[]): [number, number][] => cols.reduce<[number, number][]>((out, c) => {
  const last = out[out.length - 1];
  if (last && last[0] + last[1] === c) last[1] += 1; else out.push([c, 1]);
  return out;
}, []);

/** An item in every column of two or more is one banner; every other item spans the columns it is adjacent in, and is placed on the first free line. */
export function pack(items: DomainItem[], n: number): { banner: DomainItem[]; lines: Cell[][] } {
  const banner = n > 1 ? items.filter((i) => i.cols.length === n) : [];
  const lines: Cell[][] = [];
  for (const item of items.filter((i) => !banner.includes(i))) {
    for (const [start, span] of runs(item.cols)) {
      const cell = { item, start, span, shared: item.cols.length > 1 || item.shared_outside };
      const line = lines.find((l) => l.every((c) => c.start + c.span <= start || start + span <= c.start));
      if (line) line.push(cell); else lines.push([cell]);
    }
  }
  return { banner, lines };
}

/** One domain: its use cases as columns; Decisions, KPIs, Gold, Silver and Bronze as rows. A gold edge is shared. */
export default function Domains({ id, onDomain, onOpen }: { id: string | null; onDomain: (id: string) => void; onOpen: (ucId: string) => void }) {
  const [lists, again] = useRead(getUseCases);
  if (lists.state === "loading") return <p className="v3-mute" role="status">Reading the domains</p>;
  if (lists.state === "error") return <Failed message={lists.message} again={again} />;
  const top = [...lists.data.domains].sort((a, b) => b.count - a.count)[0];
  const pick = id && lists.data.domains.some((d) => d.id === id) ? id : top?.id;
  if (!pick) return <div className="v3-card"><p>No domains yet.</p></div>;
  return <DomainView key={pick} id={pick} onDomain={onDomain} onOpen={onOpen} />;
}

function DomainView({ id, onDomain, onOpen }: { id: string; onDomain: (id: string) => void; onOpen: (ucId: string) => void }) {
  const [got, again] = useRead(() => getDomain(id));
  if (got.state === "loading") return <p className="v3-mute" role="status">Reading the domain</p>;
  if (got.state === "error") return <Failed message={got.message} again={again} />;
  return <Grid d={got.data} onDomain={onDomain} onOpen={onOpen} />;
}

function Grid({ d, onDomain, onOpen }: { d: Domain; onDomain: (id: string) => void; onOpen: (ucId: string) => void }) {
  const n = d.usecases.length;
  const cols = { gridTemplateColumns: `150px repeat(${Math.max(n, 1)}, minmax(0, 1fr))` };
  return (
    <section className="kd" aria-label={`Domain ${d.name}`}>
      <div className="kd-head">
        <h2>{d.name}</h2>
        <span className="v3-mute">{n} use case{n === 1 ? "" : "s"} {"·"} {d.people} {d.people === 1 ? "person" : "people"}</span>
      </div>
      <p className="kd-intro">One column per use case. The rows show what each one needs; a gold-edged box is shared, built once and reused. Click a use case to open its full story.</p>
      {n === 0 ? <div className="v3-card"><p>No use case is in this domain yet. When a brief is signed whose figures come from {d.name.toLowerCase()} recipes, it appears here.</p></div> : (
        <>
          <div className="kd-grid" style={cols}>
            <span />
            {d.usecases.map((u) => <button key={u.id} type="button" className="kd-head-uc" onClick={() => onOpen(u.id)}><b>{u.title}</b><br />{u.who}{u.role ? ` · ${u.role}` : ""}</button>)}
          </div>
          {ROWS.map(([key, label, cls]) => {
            const { banner, lines } = pack(d.rows[key].items, n);
            const first = (extra: number) => (extra === 0 ? <span className={`kd-label ${cls}`}>{label}</span> : <span />);
            let k = 0;
            return (
              <div key={key} className="kd-block" role="group" aria-label={label}>
                {banner.length > 0 && (
                  <div className="kd-grid" style={cols}>{first(k++)}<span className={`kd-cell ${cls || "plain"} wide`}><b>Shared by all {n}:</b> {banner.map((b) => b.label).join(" · ")}</span></div>
                )}
                {lines.map((line, i) => (
                  <div className="kd-grid" style={cols} key={i}>
                    {first(k++)}
                    {line.map((c) => (
                      <span key={`${c.item.id}-${c.start}`} className={`kd-cell ${cls || "plain"}${c.shared ? " shared" : ""}`} style={{ gridColumn: `${c.start + 2} / span ${c.span}` }}>
                        <b>{c.item.label}</b>{WITH_SUB.has(key) && c.item.sub ? ` · ${c.item.sub}` : ""}{c.item.cols.length > 1 ? ` · shared by ${c.item.cols.length}` : c.item.shared_outside ? " · shared" : ""}
                        {c.shared && <Dot n={1} />}
                      </span>
                    ))}
                  </div>
                ))}
                {d.rows[key].hidden > 0 && <div className="kd-grid" style={cols}><span /><span className="v3-mute" style={{ gridColumn: "2 / -1" }}>+{d.rows[key].hidden} more</span></div>}
                {banner.length === 0 && lines.length === 0 && <div className="kd-grid" style={cols}>{first(0)}<span className="v3-mute" style={{ gridColumn: "2 / -1" }}>None recorded.</span></div>}
              </div>
            );
          })}
        </>
      )}
      <div className="kd-cards">
        <div className="ks-card">
          <p className="ks-kicker">Other domains</p>
          <p className="kd-others">{d.others.map((o, i) => <span key={o.id}>{i ? "  ·  " : ""}<button type="button" className="ks-link" onClick={() => onDomain(o.id)}>{o.name} {"·"} {o.count}</button></span>)}</p>
        </div>
        <div className="ks-card">
          <p className="ks-kicker">Why this view</p>
          <p className="kd-others">Everyone who works in {d.name.toLowerCase()} sees the whole process on one screen, and what a change would touch.</p>
        </div>
      </div>
    </section>
  );
}
