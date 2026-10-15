import { useState, type ReactNode } from "react";

import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import Sticky from "../../../components/Sticky";
import * as L from "./layout";
import type { BoardCluster, BoardNote } from "../api";
import { m1Board as t } from "../copy";

/** One note as a yellow sticky, with who wrote it only where it was posted by name. An anonymous note says so and nothing more. */
export function NoteSticky({ note, children }: { note: BoardNote; children?: ReactNode }) {
  return (
    <Sticky tone="yellow" question={note.text} >
      <div className="n-muted" style={L.smallLine}>
        {note.anonymous ? t.anonymous : note.author_name ? t.by(note.author_name) : null}
        {note.mine ? ` · ${t.yours}` : ""}
      </div>
      {children}
    </Sticky>
  );
}

export function NoteList({ notes }: { notes: BoardNote[] }) {
  return (
    <ul style={L.noteList}>
      {notes.map((n) => (
        <li key={n.id}>
          <NoteSticky note={n} />
        </li>
      ))}
    </ul>
  );
}

interface Props {
  cluster: BoardCluster;
  clusters: BoardCluster[];
  editable: boolean;
  busy: boolean;
  /** The "On its own" panel: no rename, no split, and it is the place a note goes to leave a group. */
  own?: boolean;
  /** The list this group belongs to (its kind of note), shown while every kind is on screen. */
  kindName?: string;
  onMove: (noteId: string, to: string | null) => void;
  onRename?: (name: string) => Promise<void>;
  onSplit?: (noteIds: string[]) => Promise<void>;
}

/** A named group (or "On its own") with its notes. For the organiser: drag a note in, or choose Move; rename; split. */
export default function ClusterPanel({ cluster, clusters, editable, busy, own = false, kindName, onMove, onRename, onSplit }: Props) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(cluster.name);
  const [splitting, setSplitting] = useState(false);
  const [chosen, setChosen] = useState<string[]>([]);
  const target = own ? null : cluster.id;

  const toggle = (id: string) => setChosen((c) => (c.includes(id) ? c.filter((x) => x !== id) : [...c, id]));
  const actions = (
    <>
      {kindName ? <StatusPill tone="muted">{kindName}</StatusPill> : null}
      <StatusPill tone={own ? "muted" : "info"}>{t.noteCount(cluster.notes.length)}</StatusPill>
      {editable && !own ? (
        <>
          <button type="button" className="n-btn" aria-label={t.renameLabel(cluster.name)} disabled={busy} onClick={() => { setName(cluster.name); setRenaming(true); }}>
            {t.rename}
          </button>
          {cluster.notes.length > 1 ? (
            <button type="button" className="n-btn" aria-label={t.splitLabel(cluster.name)} disabled={busy} onClick={() => { setChosen([]); setSplitting(!splitting); }}>
              {t.split}
            </button>
          ) : null}
        </>
      ) : null}
    </>
  );
  const clusterStyle = cluster.colour !== undefined && cluster.colour !== null ? {
    borderLeft: `4px solid var(--cluster-${cluster.colour}, var(--line))`,
  } : {};

  return (
    <div
      style={clusterStyle}
      onDragOver={(e) => editable && e.preventDefault()}
      onDrop={(e) => {
        const id = e.dataTransfer.getData("text/plain");
        if (editable && id) {
          e.preventDefault();
          onMove(id, target);
        }
      }}
    >
      <Panel title={renaming ? undefined : cluster.name} label={renaming ? cluster.name : undefined} eyebrow={own ? t.onItsOwnHelp : undefined} actions={actions}>
        {renaming && onRename ? (
          <form
            className="m1-actions"
            onSubmit={(e) => {
              e.preventDefault();
              void onRename(name).then(() => setRenaming(false));
            }}
          >
            <label>
              {t.renameField}
              <input type="text" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
            </label>
            <button type="submit" className="n-btn primary" disabled={busy || name.trim() === ""}>
              {t.save}
            </button>
            <button type="button" className="n-btn" onClick={() => setRenaming(false)}>
              {t.cancel}
            </button>
          </form>
        ) : null}
        {cluster.reasoning && !own ? (
          <details style={{ marginBottom: 10, fontSize: 13 }}>
            <summary>{t.whyNorth}</summary>
            <p>{cluster.reasoning}</p>
          </details>
        ) : null}
        {splitting && onSplit ? <p className="n-muted">{t.splitHelp}</p> : null}
        {own && cluster.notes.length === 0 ? <p className="n-muted">{t.nothingAlone}</p> : null}
        <ul style={L.noteList}>
          {cluster.notes.map((n) => (
            <li key={n.id} draggable={editable} onDragStart={(e) => e.dataTransfer.setData("text/plain", n.id)}>
              <NoteSticky note={n}>
                {splitting ? (
                  <label style={{ display: "block", marginTop: 6, marginBottom: 0 }}>
                    <input type="checkbox" aria-label={t.splitPick(n.text)} checked={chosen.includes(n.id)} onChange={() => toggle(n.id)} />
                  </label>
                ) : null}
                {editable ? (
                  <label style={{ ...L.moveField, marginBottom: 0 }}>
                    <span className="n-muted">{t.moveTo}</span>
                    <select aria-label={t.moveLabel(n.text)} value="" disabled={busy} onChange={(e) => e.target.value !== "" && onMove(n.id, e.target.value === "own" ? null : e.target.value)}>
                      <option value="">{t.chooseGroup}</option>
                      {clusters.filter((c) => c.id !== cluster.id).map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                      {own ? null : <option value="own">{t.onItsOwn}</option>}
                    </select>
                  </label>
                ) : null}
              </NoteSticky>
            </li>
          ))}
        </ul>
        {splitting && onSplit ? (
          <button
            type="button"
            className="n-btn primary"
            disabled={busy || chosen.length === 0 || chosen.length >= cluster.notes.length}
            onClick={() => void onSplit(chosen).then(() => setSplitting(false))}
          >
            {t.splitDo}
          </button>
        ) : null}
      </Panel>
    </div>
  );
}
