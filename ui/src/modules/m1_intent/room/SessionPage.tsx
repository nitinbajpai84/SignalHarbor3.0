import { useState } from "react";
import { useParams } from "react-router-dom";

import { getSession } from "../api";
import PrepareScreen from "../PrepareScreen";
import { useLoad } from "../useLoad";
import OrganiserRoom from "./OrganiserRoom";
import StartRoom from "./StartRoom";

/**
 * The organiser's page for one session. A draft: the Prepare wizard, then "Start the room". A started session: the
 * room (link, seats, arrivals) above its read-only preparation. Loading, not found and errors stay PrepareScreen's:
 * this page adds the room only once the session is known. A saved draft is the starting point; "Save your draft
 * first" shows only while the wizard holds changes that are not saved yet.
 */
export default function SessionPage() {
  const { sessionId = "" } = useParams();
  const { data, retry } = useLoad(() => getSession(sessionId), `room-${sessionId}`);
  const [unsaved, setUnsaved] = useState(false);
  return (
    <>
      <PrepareScreen
        version={data?.state ?? "loading"}
        onUnsaved={setUnsaved}
        above={data && data.state !== "draft" ? <OrganiserRoom sessionId={sessionId} title={data.preparation.purpose} onChanged={retry} /> : null}
      />
      {data?.state === "draft" ? <StartRoom sessionId={sessionId} saved={!unsaved} onStarted={retry} /> : null}
    </>
  );
}
