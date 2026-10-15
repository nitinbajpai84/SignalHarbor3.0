import { Link } from "react-router-dom";

import ScreenState from "../../components/ScreenState";
import { useLoad } from "../../components/useLoad";
import { PageFrame } from "../../design";
import AccessCard from "./AccessCard";
import { getAccess } from "./api";

// K1: requests to use library files. Pulse's card opens here; the same AccessCard can be shown inside Pulse.
const day = (iso: string) => new Date(iso).toLocaleDateString("en-GB", { dateStyle: "medium" });

export default function AccessPage() {
  const { state, data, message, retry } = useLoad(getAccess, "k1-access");
  return (
    <PageFrame title="Requests to use files">
      <ScreenState state={state} message={message} onRetry={retry}>
        {data ? (
          <>
            <h2 style={{ fontSize: 16 }}>Waiting for you</h2>
            {data.incoming.length ? data.incoming.map((r) => <AccessCard key={r.id} req={r} onDone={retry} />) : <p className="ds-muted">Nobody is waiting for you.</p>}
            <h2 style={{ fontSize: 16 }}>Your requests</h2>
            {data.mine.length ? (
              <ul>{data.mine.map((r) => (
                <li key={r.id}>{r.item_name}: {r.state === "requested" ? `waiting for ${r.to}` : r.state === "granted"
                  ? `approved by ${r.decided_by}${r.expires ? ` until ${day(r.expires)}` : ""}` : r.state === "denied" ? `${r.decided_by} could not share it just now` : "access taken back"}</li>
              ))}</ul>
            ) : <p className="ds-muted">You have not asked for any file.</p>}
            <p><Link className="ds-link" to="/centre/action">Back to Action</Link></p>
          </>
        ) : null}
      </ScreenState>
    </PageFrame>
  );
}
