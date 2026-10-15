import { useEffect, useRef, useState } from "react";

import Panel from "../../../components/Panel";
import Sticky from "../../../components/Sticky";
import { PRIORITIES, type Library, type LibraryProblem, type Priority } from "./roomApi";
import { m1PrivateRoom as room } from "../copy";

interface Props {
  library: Library;
  open: boolean;
  busy: boolean;
  onAdd: (problem: LibraryProblem, text: string, priority: Priority | null) => void;
}

/** M1-13: common problems from the company's pack, as copper stickies (the earlier prototype's colour for a suggestion).
 * Always shown: with no library the panel says so. Nothing is added until the person adds it. */
export default function LibraryPanel({ library, open, busy, onAdd }: Props) {
  const [picked, setPicked] = useState<LibraryProblem | null>(null);
  const [text, setText] = useState("");
  const [priority, setPriority] = useState<Priority | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (picked) box.current?.focus(); // the form opens beside its item: focus goes with it
  }, [picked]);

  const cancel = () => setPicked(null);
  return (
    <Panel title={room.libraryHeading} eyebrow={library.label || undefined} className="m1-library">
      {library.problems.length === 0 ? (
        <p className="n-empty ebody">{library.message ?? room.libraryEmpty}</p>
      ) : (
        <>
          <span className="n-illus">{room.illustrative}</span>
          <p className="n-muted">{room.libraryIntro}</p>
          <ul className="m1-note-list">
            {library.problems.map((p) => (
              <li key={p.id}>
                <Sticky tone="copper" className="m1-note-sticky" question={p.text}>
                  {open ? (
                    <button
                      type="button"
                      className="n-btn"
                      disabled={busy}
                      aria-label={`${room.libraryUse}: ${p.text}`}
                      onClick={() => {
                        setPicked(p);
                        setText(p.text);
                        setPriority(null);
                      }}
                    >
                      {room.libraryUse}
                    </button>
                  ) : null}
                  {picked?.id === p.id ? (
                    <form
                      className="m1-lib-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        onAdd(picked, text, priority);
                        cancel();
                      }}
                    >
                      <label>
                        {room.libraryReword}
                        <textarea ref={box} value={text} onChange={(e) => setText(e.target.value)} />
                      </label>
                      <label>
                        {room.priority}
                        <select
                          value={priority ?? ""}
                          onChange={(e) => setPriority(e.target.value === "" ? null : (e.target.value as Priority))}
                        >
                          <option value="">{room.priorityNone}</option>
                          {PRIORITIES.map((q) => (
                            <option key={q} value={q}>
                              {room.priorityNames[q]}
                            </option>
                          ))}
                        </select>
                      </label>
                      <div className="m1-actions">
                        <button type="submit" className="n-btn primary" disabled={busy || text.trim() === ""}>
                          {room.libraryAdd}
                        </button>
                        <button type="button" className="n-btn" onClick={cancel}>
                          {room.libraryCancel}
                        </button>
                      </div>
                    </form>
                  ) : null}
                </Sticky>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}
