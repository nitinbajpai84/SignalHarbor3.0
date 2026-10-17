import { useEffect, useState } from "react";

import { getFigure, type FigureRecord, type FigureVersion, type ThreadFigure } from "../api";
import "./trust.css";

const PILL = { verified: "done", held: "problem", draft: "needs" } as const;
const LABEL = { verified: "Verified", held: "Held", draft: "Draft" } as const;

function Row({ f }: { f: ThreadFigure }) {
  const [rec, setRec] = useState<FigureRecord | null | undefined>(undefined);
  useEffect(() => { let on = true; getFigure(f.figure_id).then((r) => on && setRec(r)).catch(() => on && setRec(null)); return () => { on = false; }; }, [f.figure_id]);
  const ver: FigureVersion | undefined = rec?.versions.find((v) => v.v === (f.hold?.v ?? f.v)) ?? rec?.versions.at(-1);
  const rows = ver?.runs.at(-1)?.rows;
  const t = ver?.tie_out;
  const why = f.hold?.reason ?? ver?.reason ?? (t && !t.ok ? t.rule : "");
  return (
    <li>
      <div className="t3-head"><b>{f.name}</b><span className={`v3-pill ${PILL[f.status]}`}>{LABEL[f.status]}</span></div>
      {rec === undefined ? <small className="v3-mute" role="status">Checking...</small> : (
        <>
          <span>{rows ? `${rows} row${rows === 1 ? "" : "s"}` : <>Not available yet{why && <small className="v3-mute">: {why}</small>}</>}</span>
          {t ? (
            <span className="t3-tie">
              <span className={`t3-mark ${t.ok ? "ok" : "bad"}`} aria-label={t.ok ? "Tie-out done" : "Tie-out problem"}>{t.ok ? "✓" : "✗"}</span>
              <span>{t.ok ? t.rule : why || t.rule}</span>
            </span>
          ) : <small className="v3-mute">Not tied out yet</small>}
        </>
      )}
      {f.status === "held" && (
        <p className="t3-held" role="note">{f.name} is held{f.hold?.reason ? `: ${f.hold.reason}` : ""}. The rest can still go live. {f.name} is not shown on the dashboard until it ties out.</p>
      )}
    </li>
  );
}

/** Decision 3: one row per figure the thread uses: rows, tie-out in words, and Verified / Held / Draft. */
export default function FigureChecks({ figures }: { figures?: ThreadFigure[] }) {
  if (!figures?.length) return null;
  return (
    <div className="t3-figs" aria-label="Figure checks">
      <ul>{figures.map((f) => <Row key={f.figure_id} f={f} />)}</ul>
    </div>
  );
}
