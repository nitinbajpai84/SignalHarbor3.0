import { useState } from "react";
import { Link } from "react-router-dom";

import { useSession } from "../../useSession";
import { addToBoard, getBoards, studioPath, type BoardAdded, type BoardRow } from "../api";

/** Same people the studio lets build: its MAKERS (company admin, analyst). The server checks again. */
const MAKERS = ["company_admin", "analyst"];

/** "Add to board" on a figure or an answer: a draft tile on the chosen board, approved by someone else in the studio before it is published. */
export default function AddToBoard({ figureId, label, value, text }: { figureId?: string; label: string; value?: string; text?: string }) {
  const { user } = useSession();
  const [boards, setBoards] = useState<BoardRow[] | null>(null);
  const [pick, setPick] = useState("");
  const [done, setDone] = useState<BoardAdded | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  if (!(user?.roles ?? []).some((r) => MAKERS.includes(r))) return null;
  const open = () => {
    setErr("");
    getBoards().then((r) => { setBoards(r.boards); setPick(r.boards[0]?.pid ?? ""); }, (e: unknown) => setErr(e instanceof Error && e.message ? e.message : "I could not list the boards."));
  };
  const add = () => {
    const b = boards?.find((x) => x.pid === pick);
    if (!b) return;
    setBusy(true); setErr("");
    addToBoard({ pid: b.pid, dashboard_id: b.dashboard_id, figure_id: figureId, label, value, text }).then(setDone, (e: unknown) => setErr(e instanceof Error && e.message ? e.message : "I could not add it.")).finally(() => setBusy(false));
  };
  const b = boards?.find((x) => x.pid === pick);
  return (
    <div className="v3b-add noprint">
      {done && b ? (
        <p role="status">Added to a draft of {b.title}. Someone else has to approve it before it shows on the board. <Link to={studioPath(b.pid, b.dashboard_id)}>Open it in the studio</Link></p>
      ) : boards === null ? (
        <button type="button" onClick={open}>Add to board</button>
      ) : boards.length === 0 ? (
        <p className="v3-mute">No board is published yet, so there is nowhere to add it.</p>
      ) : (
        <div className="v3-row">
          <label>Board <select value={pick} onChange={(e) => setPick(e.target.value)}>{boards.map((x) => <option key={x.pid} value={x.pid}>{x.title} ({x.use_case})</option>)}</select></label>
          <button type="button" className="go" disabled={busy} onClick={add}>Add to this board</button>
        </div>
      )}
      {err ? <p className="v3-err" role="alert">{err}</p> : null}
    </div>
  );
}
