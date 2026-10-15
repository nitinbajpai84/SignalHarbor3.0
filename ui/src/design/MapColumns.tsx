import { useCallback, useLayoutEffect, useRef, useState, type CSSProperties } from "react";

// The five-column map from the Graph artboard. Nodes are laid out by CSS grid; the SVG lines are drawn between the
// measured centres of the node shapes, re-measured by a ResizeObserver so the lines follow the columns at any width.

export interface MapNode { id: string; label: string; kind: string; restricted?: boolean }
export interface MapColumn { title: string; nodes: MapNode[] }
export interface MapEdge { from: string; to: string }

interface Point { x: number; y: number }

export function MapColumns({ columns, edges, onSelect, selectedId, holeIds = [] }: {
  columns: MapColumn[]; edges: MapEdge[]; onSelect?: (id: string) => void; selectedId?: string; holeIds?: string[];
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const shapes = useRef(new Map<string, HTMLElement>());
  const [pos, setPos] = useState<Record<string, Point>>({});
  const [hover, setHover] = useState<string | null>(null);

  const measure = useCallback(() => {
    const box = wrap.current?.getBoundingClientRect();
    if (!box) return;
    const next: Record<string, Point> = {};
    shapes.current.forEach((el, id) => {
      const r = el.getBoundingClientRect();
      next[id] = { x: r.left - box.left + r.width / 2, y: r.top - box.top + r.height / 2 };
    });
    setPos(next);
  }, []);

  useLayoutEffect(() => {
    measure();
    const el = wrap.current;
    if (!el || typeof ResizeObserver === "undefined") return; // jsdom and very old browsers: lines stay at the first measure
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [columns, measure]);

  const ids = new Set(columns.flatMap((c) => c.nodes.map((n) => n.id)));
  const holes = new Set(holeIds);
  const active = hover ?? selectedId ?? null;
  const drawn = edges.filter((e) => ids.has(e.from) && ids.has(e.to));
  const at = (id: string): Point => pos[id] ?? { x: 0, y: 0 };

  return (
    <div className={`ds-map${active ? " ds-map--hover" : ""}`} style={{ "--ds-cols": columns.length } as CSSProperties}>
      <div className="ds-map__heads">{columns.map((c) => <span key={c.title}>{c.title}</span>)}</div>
      <div className="ds-map__cols" ref={wrap}>
        <svg className="ds-map__lines" aria-hidden="true">
          {drawn.map((e) => {
            const a = at(e.from), b = at(e.to);
            const on = active !== null && (e.from === active || e.to === active);
            return <line key={`${e.from}>${e.to}`} data-from={e.from} data-to={e.to} className={on ? "ds-edge--on" : undefined} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />;
          })}
        </svg>
        {columns.map((c) => (
          <div key={c.title} className="ds-map__col">
            {c.nodes.map((n) => {
              const shapeRef = (el: HTMLElement | null) => { if (el) shapes.current.set(n.id, el); else shapes.current.delete(n.id); };
              if (n.restricted) {
                return (
                  <span key={n.id} className="ds-node ds-node--silhouette" role="img" aria-label="Restricted">
                    <span className="ds-node__shape" ref={shapeRef} />
                  </span>
                );
              }
              const cls = ["ds-node", `ds-node--${n.kind.toLowerCase()}`, holes.has(n.id) && "ds-node--hole", hover === n.id && "ds-node--hover", selectedId === n.id && "ds-node--selected"]
                .filter(Boolean).join(" ");
              return (
                <button key={n.id} type="button" className={cls} data-id={n.id} aria-pressed={selectedId === n.id}
                  aria-label={holes.has(n.id) ? `${n.label}, no source yet` : n.label}
                  onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)}
                  onFocus={() => setHover(n.id)} onBlur={() => setHover(null)}
                  onClick={() => onSelect?.(n.id)}>
                  <span className="ds-node__shape" ref={shapeRef} />
                  <span className="ds-node__label">{n.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
