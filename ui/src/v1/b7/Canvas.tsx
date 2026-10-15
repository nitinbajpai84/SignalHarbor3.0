import { useRef, useState } from "react";

import { Button } from "../../design";
import type { Layout, LayoutItem, Size, Tile, TileData } from "../cxui/api";
import TileCard from "../cxui/TileCard";
import "./studio.css";

// DS1: the 12-column grid. The same component draws the studio canvas (editable) and the published dashboard in Consume (read-only).
// Drag a widget to move it; drag its corner to make it wider or taller (the chart fills the box). Keys and the More buttons do the same without a
// mouse: Alt+arrow moves the focused widget, + and - change its width.
export const WIDTH: Record<Size, number> = { small: 3, medium: 6, wide: 9, full: 12 };
export const SIZES: Size[] = ["small", "medium", "wide", "full"];
export const SIZE_WORDS: Record<Size, string> = { small: "Small", medium: "Medium", wide: "Wide", full: "Full" };
export const H_MAX = 4;
const tall = (i: LayoutItem) => i.h ?? 1;
const nearestSize = (cols: number): Size => SIZES.reduce((a, b) => (Math.abs(WIDTH[b] - cols) < Math.abs(WIDTH[a] - cols) ? b : a));

/** Can `id` sit at (row, col) with this size without leaving the grid or touching another widget? */
export function fits(items: LayoutItem[], id: string, row: number, col: number, size: Size, rows: number, h = 1): boolean {
  if (row < 0 || row + h > rows || col < 0 || col + WIDTH[size] > 12) return false;
  return !items.some((o) => o.id !== id && o.row < row + h && row < o.row + tall(o) && o.col < col + WIDTH[size] && col < o.col + WIDTH[o.size]);
}

/** The empty stretches of one row: [{col, width}]. */
export function freeRuns(items: LayoutItem[], row: number): { col: number; width: number }[] {
  const used = new Set<number>();
  for (const i of items) if (i.row <= row && row < i.row + tall(i)) for (let c = i.col; c < i.col + WIDTH[i.size]; c++) used.add(c);
  const runs: { col: number; width: number }[] = [];
  for (let c = 0; c < 12; c++) {
    if (used.has(c)) continue;
    const last = runs[runs.length - 1];
    if (last && last.col + last.width === c) last.width += 1; else runs.push({ col: c, width: 1 });
  }
  return runs;
}

export interface Slot { row: number; col: number }
const KEY_MOVE: Record<string, [number, number]> = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };

export default function Canvas({ pid, did, layout, editable = false, load, slot, onSlot, selected, onSelect, onChange, onRemove, onProblem }: {
  pid: string; did: string; layout: Layout; editable?: boolean; load?: (tileId: string) => Promise<TileData>;
  slot?: Slot | null; onSlot?: (s: Slot) => void; selected?: string | null; onSelect?: (id: string | null) => void;
  onChange?: (items: LayoutItem[]) => void; onRemove?: (id: string) => void; onProblem?: (words: string) => void;
}) {
  const [drag, setDrag] = useState<string | null>(null);
  const [ghost, setGhost] = useState<{ row: number; col: number; size: Size; h: number } | null>(null);
  const [more, setMore] = useState<string | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const { items, rows } = layout;
  const put = (it: LayoutItem, row: number, col: number, size: Size, h = tall(it)) => {
    if (!fits(items, it.id, row, col, size, rows, h)) { onProblem?.("That place is taken or off the grid. Choose an empty slot or make the widget smaller."); return; }
    onProblem?.("");
    onChange?.(items.map((o) => (o.id === it.id ? { ...o, row, col, size, h: h > 1 ? h : undefined } : o)));
  };
  /** The grid cell under the pointer: 12 columns, equal rows. */
  const cellAt = (x: number, y: number) => {
    const g = gridRef.current?.getBoundingClientRect();
    if (!g || !g.width) return null;
    const rowH = (g.height + 8) / Math.max(rows, 1);
    return { row: Math.max(0, Math.min(rows - 1, Math.floor((y - g.top) / rowH))), col: Math.max(0, Math.min(11, Math.floor(((x - g.left) / g.width) * 12))) };
  };
  const dropAt = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    const it = items.find((o) => o.id === drag); const at = cellAt(e.clientX, e.clientY);
    setDrag(null);
    if (it && at) put(it, at.row, Math.min(at.col, 12 - WIDTH[it.size]), it.size);
  };
  /** Drag the corner: the width snaps to a quarter of the grid, the height to whole rows (1 to 4). */
  const startResize = (it: LayoutItem) => (e: React.PointerEvent) => {
    e.preventDefault(); e.stopPropagation();
    const g = gridRef.current?.getBoundingClientRect(); if (!g) return;
    const colW = g.width / 12, rowH = (g.height + 8) / Math.max(rows, 1), x0 = e.clientX, y0 = e.clientY;
    const w0 = WIDTH[it.size], h0 = tall(it);
    let cur = { size: it.size, h: h0 };
    const onMove = (m: PointerEvent) => {
      const size = nearestSize(Math.max(3, Math.min(12 - it.col, w0 + Math.round((m.clientX - x0) / colW))));
      const h = Math.max(1, Math.min(H_MAX, rows - it.row, h0 + Math.round((m.clientY - y0) / rowH)));
      cur = { size: WIDTH[size] + it.col > 12 ? it.size : size, h };
      setGhost({ row: it.row, col: it.col, ...cur });
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove); window.removeEventListener("pointerup", onUp); setGhost(null);
      if (cur.size !== it.size || cur.h !== h0) put(it, it.row, it.col, cur.size, cur.h);
    };
    window.addEventListener("pointermove", onMove); window.addEventListener("pointerup", onUp);
  };
  const move = (it: LayoutItem, dr: number, dc: number) => put(it, it.row + dr, it.col + dc, it.size);
  const resize = (it: LayoutItem, size: Size) => put(it, it.row, it.col, size);
  const step = (it: LayoutItem, by: number) => { const n = SIZES[SIZES.indexOf(it.size) + by]; if (n) resize(it, n); };
  const keys = (it: LayoutItem) => (e: React.KeyboardEvent) => {
    if (!editable || e.target !== e.currentTarget) return;
    const m = KEY_MOVE[e.key];
    if (m && e.altKey) { e.preventDefault(); move(it, m[0], m[1]); } else if (e.key === "+" || e.key === "=") { e.preventDefault(); step(it, 1); } else if (e.key === "-") { e.preventDefault(); step(it, -1); }
  };
  const body = (it: LayoutItem) => {
    if (it.kind === "note" || !it.tile) return <article className="ds-card" aria-label={it.title} style={{ padding: 12, height: "100%" }}><p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{it.text}</p></article>;
    const tile: Tile = { id: it.tile, title: it.title, kpi: "", sql: "", spec: {}, note: "", state: "accepted" };
    const tid = it.tile;
    return <TileCard pid={pid} did={did} tile={tile} inGrid load={load ? () => load(tid) : undefined} />;
  };
  const grid: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    for (const run of freeRuns(items, r)) {
      if (!editable) continue;
      const on = slot?.row === r && slot.col === run.col;
      grid.push(run.width < WIDTH.small ? null : (
        <button key={`s-${r}-${run.col}`} type="button" className="b7-slot" aria-pressed={on} aria-label={`Add a widget here, row ${r + 1}, column ${run.col + 1}`}
          style={{ gridRow: r + 1, gridColumn: `${run.col + 1} / span ${run.width}` }} onClick={() => onSlot?.({ row: r, col: run.col })}
          onDragOver={(e) => { if (drag) e.preventDefault(); }} onDrop={dropAt}>
          Add a widget here
        </button>));
    }
  }
  for (const it of items) {
    grid.push(
      <div key={it.id} className="b7-item" data-selected={selected === it.id} data-dragging={drag === it.id} onClick={() => { if (editable && selected !== it.id) onSelect?.(it.id); }}
        style={{ gridRow: `${it.row + 1} / span ${tall(it)}`, gridColumn: `${it.col + 1} / span ${WIDTH[it.size]}` }}
        tabIndex={editable ? 0 : undefined} aria-label={editable ? `${it.title}. Drag to move, drag the corner to resize; Alt and an arrow key moves it; plus and minus change its width.` : undefined}
        draggable={editable} onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; setDrag(it.id); }} onDragEnd={() => setDrag(null)} onKeyDown={keys(it)}
        onDragOver={(e) => { if (drag && drag !== it.id) e.preventDefault(); }} onDrop={dropAt}>
        {body(it)}
        {it.reads?.length ? <p className="ds-muted" style={{ margin: "2px 0", fontSize: 12 }}>Reads: {it.reads.join(", ")}</p> : null}
        {editable ? <>
          <div className="b7-item-bar">
            <button type="button" className="b7-mini" aria-expanded={more === it.id} onClick={(e) => { e.stopPropagation(); setMore(more === it.id ? null : it.id); }}>More</button>
            <button type="button" className="b7-mini" aria-label={`Remove ${it.title}`} onClick={(e) => { e.stopPropagation(); onRemove?.(it.id); }}>Remove</button>
          </div>
          {more === it.id ? (
            <div role="group" aria-label={`Position and size of ${it.title}`} style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 4 }}>
              <Button aria-pressed={selected === it.id} onClick={() => onSelect?.(selected === it.id ? null : it.id)}>{selected === it.id ? "Selected" : "Select"}</Button>
              <Button onClick={() => move(it, -1, 0)}>Move up</Button><Button onClick={() => move(it, 1, 0)}>Move down</Button>
              <Button onClick={() => move(it, 0, -1)}>Move left</Button><Button onClick={() => move(it, 0, 1)}>Move right</Button>
              {SIZES.map((s) => <Button key={s} aria-pressed={it.size === s} onClick={() => resize(it, s)}>{SIZE_WORDS[s]}</Button>)}
              <Button onClick={() => put(it, it.row, it.col, it.size, Math.min(H_MAX, tall(it) + 1))}>Taller</Button>
              <Button onClick={() => put(it, it.row, it.col, it.size, Math.max(1, tall(it) - 1))}>Shorter</Button>
            </div>) : null}
          <span className="b7-resize" title="Drag to resize" onPointerDown={startResize(it)} />
        </> : null}
      </div>,
    );
  }
  if (ghost) grid.push(<div key="ghost" className="b7-ghost" aria-hidden="true" style={{ gridRow: `${ghost.row + 1} / span ${ghost.h}`, gridColumn: `${ghost.col + 1} / span ${WIDTH[ghost.size]}` }} />);
  return <div ref={gridRef} className="b7-grid" data-editable={editable} aria-label="Dashboard grid" onDragOver={(e) => { if (drag) e.preventDefault(); }} onDrop={dropAt}>{grid}</div>;
}
