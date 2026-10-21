import { Link } from "react-router-dom";

import { getBoards, studioPath } from "../api";
import V3Frame from "../Frame";
import { Failed, Page, Waiting, useRead } from "../board/common";

const day = (at: string | null) => (at ? new Date(at.length <= 10 ? `${at}T12:00:00` : at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "Not yet");

/** /v3/consume/boards: every board with its use case, owner, last refresh and whether a change is waiting in the studio. */
export default function BoardsPage() {
  const [got, again] = useRead(getBoards);
  return (
    <V3Frame back={<Link to="/v3/consume" className="b3-back">&larr; Consume</Link>}>
      <Page>
        <section className="v3b-head" aria-labelledby="h-boards">
          <h1 id="h-boards">Boards</h1>
          <span className="v3-mute">One for each live use case. Changes are drafted, approved by someone else, then published.</span>
        </section>
        {got.state === "loading" ? <Waiting what="Opening the boards…" />
          : got.state === "error" ? <Failed message={got.message} again={again} />
          : got.data.boards.length === 0 ? <div className="v3-card"><p>No board is published yet. One appears when a use case goes live.</p><div className="v3-row"><Link to="/v3/build">Go to Build</Link></div></div>
          : (
            <table aria-label="Boards">
              <thead><tr><th>Board</th><th>Use case</th><th>Owner</th><th>Last refresh</th><th>Change waiting</th><th /></tr></thead>
              <tbody>{got.data.boards.map((b) => (
                <tr key={`${b.pid}/${b.dashboard_id}`}>
                  <td><Link to={`/v3/board?pid=${encodeURIComponent(b.pid)}`}>{b.title}</Link></td>
                  <td>{b.use_case}</td>
                  <td>{b.owner ?? "Not named"}</td>
                  <td>{day(b.refreshed)}</td>
                  <td>{b.draft ? <span className="v3-pill needs">{b.status === "submitted" ? "Waiting for approval" : "Draft"}</span> : "None"}</td>
                  <td>{got.data.can_edit ? <Link to={studioPath(b.pid, b.dashboard_id)}>Edit</Link> : null}</td>
                </tr>))}
              </tbody>
            </table>
          )}
        <p className="v3-mute"><Link to="/v3/trust/model">See the data model</Link></p>
      </Page>
    </V3Frame>
  );
}
