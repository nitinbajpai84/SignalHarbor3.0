import { Link } from "react-router-dom";

import { getRuns, type Run } from "../api";
import { TrustPage, useLoad } from "./b/Shell";

const HEADS = ["Run ID", "Thread", "Kind", "Started", "Files in", "Checks passed", "Result", "Signed by"];

export default function ProofPage() {
  const s = useLoad(getRuns, "runs");
  const runs: Run[] = s.data?.runs ?? [];
  return (
    <TrustPage kicker="Trust › Runs and proof · for the auditor" title="Every run, and the checks it passed" sub="Each row is one piece of work Harbor did." state={s}
      empty={s.data && !runs.length ? "No runs yet. The first run appears once a thread has worked on a copy." : false}>
      <section className="v3-card"><h2>Every run</h2>
        <div className="tr-scroll">
          <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
            <thead><tr>{HEADS.map((h) => <th key={h} style={{ textAlign: "left", padding: "0 10px 10px 0", fontSize: 12, color: "var(--mute)", fontWeight: 500 }}>{h}</th>)}</tr></thead>
            <tbody>{runs.map((r) => (
              <tr key={r.run_id} style={{ borderTop: "1px solid var(--line)" }}>
                <td className="num" style={{ padding: "10px 10px 10px 0" }}>{r.run_id}</td>
                <td><Link to={`/v3/thread/${encodeURIComponent(r.thread)}`}>{r.thread}</Link></td>
                <td>{r.kind === "live" ? "Live" : "Copy"}</td>
                <td>{r.started}</td>
                <td className="num">{r.files}</td>
                <td className="num"><span className={`v3-pill ${r.checks_passed < r.checks_total ? "problem" : "done"}`}>{r.checks_passed}/{r.checks_total}</span></td>
                <td>{r.result}</td>
                <td>{r.signed_by}</td>
              </tr>))}</tbody>
          </table>
        </div>
      </section>
      <section className="v3-card"><h2>Linked to the board</h2>
        <p className="v3-mute">Open any figure on the board and it shows the run behind it, the files it came from and the checks it passed.</p>
      </section>
    </TrustPage>
  );
}
