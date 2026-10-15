import { useState } from "react";

import Panel from "../../../components/Panel";
import StatusPill from "../../../components/StatusPill";
import { ApiError } from "../../../api/client";
import { settleConflict, type Conflict } from "../api";
import { m2Cat as t } from "../copy";

interface Props {
  baselineId: string;
  conflicts: Conflict[];
  /** What to call the row a conflict is about (its source name), found by the screen. */
  rowName: (c: Conflict) => string;
  onChanged: () => void;
}

/** M2-24: two owners answered differently. Both versions and who said each; a named person settles it, Lens never does. */
export default function ConflictPanel({ baselineId, conflicts, rowName, onChanged }: Props) {
  const [typed, setTyped] = useState<Record<string, string>>({});
  const [note, setNote] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const settle = async (id: string, value: string) => {
    if (!value.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await settleConflict(baselineId, id, value.trim(), note[id] ?? "");
      onChanged();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "That could not be saved. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const shown = conflicts.filter((c) => c.state !== "closed");
  if (shown.length === 0) return null;
  return (
    <Panel title={t.conflicts.heading} eyebrow={t.conflicts.sub} className="m2-conflicts">
      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      <ul className="m1-list">
        {shown.map((c) =>
          c._hidden ? (
            <li key={c.id} className="n-muted">
              {t.conflicts.restricted}
            </li>
          ) : (
            <li key={c.id}>
              <strong>{t.conflicts.for(rowName(c), c.column ?? "")}</strong>{" "}
              {c.state === "settled" ? <StatusPill tone="success">{t.conflicts.settled(c.settled_by ?? "")}</StatusPill> : <StatusPill tone="warning">{t.marks.unknown}</StatusPill>}
              <ul>
                {(c.versions ?? []).map((v, i) => (
                  <li key={i} className="m1-row">
                    <span>
                      “{v.value}” <span className="n-muted">{t.said(v.by, v.at ?? "", "")}</span>
                    </span>
                    {c.state === "open" ? (
                      <button type="button" className="n-btn sm" disabled={busy} onClick={() => void settle(c.id, v.value)}>
                        {t.conflicts.use}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
              {c.state === "settled" ? (
                <p className="n-muted">
                  “{c.settled_value}” {c.note ? `· ${c.note}` : ""}
                </p>
              ) : (
                <div className="m1-row">
                  <label>
                    {t.conflicts.other}
                    <input value={typed[c.id] ?? ""} onChange={(e) => setTyped({ ...typed, [c.id]: e.target.value })} />
                  </label>
                  <label>
                    {t.conflicts.note}
                    <input value={note[c.id] ?? ""} onChange={(e) => setNote({ ...note, [c.id]: e.target.value })} />
                  </label>
                  <button type="button" className="n-btn" disabled={busy || !(typed[c.id] ?? "").trim()} onClick={() => void settle(c.id, typed[c.id] ?? "")}>
                    {t.conflicts.settle}
                  </button>
                </div>
              )}
            </li>
          ),
        )}
      </ul>
    </Panel>
  );
}
