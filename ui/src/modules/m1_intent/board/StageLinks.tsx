import { Link } from "react-router-dom";

import Panel from "../../../components/Panel";
import { getSession } from "../api";
import { m1Board as t } from "../copy";
import { useLoad } from "../useLoad";

const LATER = ["private_rooms", "board", "together", "paused", "signing"];

/** The organiser's way on from the session page to the board and the room (the stages after the private rooms). */
export default function StageLinks({ sessionId }: { sessionId: string }) {
  const { data } = useLoad(() => getSession(sessionId), `stage-links-${sessionId}`);
  if (!data || !LATER.includes(data.state)) return null;
  const label = data.state === "private_rooms" ? t.links.rooms : data.state === "board" ? t.links.board : t.links.together;
  return (
    <Panel title={t.links.title} className="m1-room">
      <Link className="n-btn primary" to={`/modules/m1_intent/sessions/${encodeURIComponent(sessionId)}/board`}>
        {label}
      </Link>
    </Panel>
  );
}
