import { Link } from "react-router-dom";

import { listFigures, type FigureRow, type FigureStatus } from "../api";
import V3Frame from "../Frame";
import { Failed, Waiting, useRead } from "../board/common";
import { usePhone } from "./k/usePhone";
import "./figures.css";

const TONE: Record<FigureStatus, string> = { verified: "done", held: "problem", draft: "needs" };
const STATUS_WORD: Record<FigureStatus, string> = { verified: "Verified", held: "Held", draft: "Draft" };
export const day = (at?: string | null) => {
  if (!at) return "Not yet";
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? at : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
};
export const Pill = ({ s }: { s: FigureStatus }) => <span className={`v3-pill ${TONE[s]}`}>{STATUS_WORD[s]}</span>;
const built = (f: FigureRow) => `${f.built_from.kind} ${f.built_from.id}`;

/** /v3/knowledge/figures: every figure the office has defined. */
export default function FiguresPage() {
  const [got, again] = useRead(listFigures);
  const phone = usePhone();
  const rows = got.state === "ready" ? got.data : null;
  return (
    <V3Frame>
      <main className="fg-page">
        <div>
          <span className="v3-mute">Knowledge · Figures</span>
          <h1>Figures this office uses</h1>
          <p className="v3-mute">Each figure is built from named files and checked before it is used. Open one to see where it comes from and what I assumed.</p>
        </div>
        {got.state === "loading" && <Waiting what="Reading the figures" />}
        {got.state === "error" && <Failed message={got.message} again={again} />}
        {rows && !rows.length && <p className="v3-mute">No figures yet. They appear when you confirm a brief.</p>}
        {rows && rows.length > 0 && (phone ? (
          <ul className="fg-cards">{rows.map((f) => (
            <li key={f.id}>
              <b><Link to={`/v3/knowledge/figures/${encodeURIComponent(f.id)}`}>{f.name}</Link></b>
              <span><Pill s={f.status} /></span>
              <span className="v3-mute">Built from {built(f)} · used by {f.used_by_count} · last run {day(f.last_run_at)}</span>
            </li>))}
          </ul>
        ) : (
          <section className="fg-wide">
            <table>
              <thead><tr><th>Figure</th><th>Status</th><th>Built from</th><th>Used by</th><th>Last run</th></tr></thead>
              <tbody>{rows.map((f) => (
                <tr key={f.id}>
                  <td><Link to={`/v3/knowledge/figures/${encodeURIComponent(f.id)}`}>{f.name}</Link></td>
                  <td><Pill s={f.status} /></td><td>{built(f)}</td><td>{f.used_by_count}</td><td>{day(f.last_run_at)}</td>
                </tr>))}
              </tbody>
            </table>
          </section>
        ))}
      </main>
    </V3Frame>
  );
}
